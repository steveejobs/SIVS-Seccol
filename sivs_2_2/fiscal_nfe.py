"""Núcleo determinístico de NF-e 4.00.

Este módulo não escolhe regras fiscais. Ele recebe uma fotografia já aprovada pelo
motor tributário, monta o XML oficial, assina com o A1 e valida contra o XSD
versionado. Transporte e persistência continuam sob responsabilidade do servidor.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from lxml import etree


NFE_NS = "http://www.portalfiscal.inf.br/nfe"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
NSMAP = {None: NFE_NS}
SCHEMA_VERSION = "010e_v1.02"
SCHEMA_SHA256 = "D44AE5AA6A0D1CABF6235D2D2D47B75BE5DD87BC6B90A7EC3DCEC99C3D41BDA1"
SCHEMA_FILE_SHA256 = {
    "DFeTiposBasicos_v1.00.xsd": "7FE1DBD89A1DD80826C5134C2406B7EB5DF4FA7A9177C5AA6E72319CABA7C6D2",
    "leiauteNFe_v4.00.xsd": "598C71780CBC6B54F170464BD6D5538C2D01A99D987A1666B662D4E166B84BF7",
    "nfe_v4.00.xsd": "ADCE3646C13CEB54922EC3142FC1DC45BD4FB839AC35AD583E86C733C07D27DF",
    "tiposBasico_v4.00.xsd": "772619C85723E598840667CA66E7298A250442DF47EEB94B397D2A333CE62047",
    "xmldsig-core-schema_v1.01.xsd": "F56744A5F51C03F027DE13F39F869307091781A9EF1D91B1EBE14719CE28E1AC",
}


class NFeError(ValueError):
    """Erro seguro de preparação, assinatura ou validação da NF-e."""


@dataclass(frozen=True)
class NFeIdentity:
    access_key: str
    numeric_code: str
    check_digit: str


def digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def money(cents: int) -> str:
    return f"{Decimal(int(cents)) / Decimal(100):.2f}"


def quantity(micros: int) -> str:
    value = Decimal(int(micros)) / Decimal(1_000_000)
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def rate(basis_points: int) -> str:
    return f"{Decimal(int(basis_points)) / Decimal(100):.2f}"


def modulo11_check_digit(base43: str) -> str:
    if not re.fullmatch(r"\d{43}", base43):
        raise NFeError("Base da chave da NF-e deve possuir 43 dígitos")
    weight, total = 2, 0
    for character in reversed(base43):
        total += int(character) * weight
        weight = 2 if weight == 9 else weight + 1
    remainder = total % 11
    return str(0 if remainder in (0, 1) else 11 - remainder)


def build_identity(*, state_code: str, issued_at: datetime, cnpj: str, model: str,
                   series: int, number: int, emission_type: int, numeric_code: str) -> NFeIdentity:
    cnpj_digits = digits(cnpj)
    numeric = digits(numeric_code).zfill(8)
    if not re.fullmatch(r"\d{2}", state_code) or len(cnpj_digits) != 14:
        raise NFeError("UF ou CNPJ inválido para compor a chave da NF-e")
    if model != "55" or not 1 <= series <= 999 or not 1 <= number <= 999_999_999:
        raise NFeError("Modelo, série ou número da NF-e inválido")
    if not re.fullmatch(r"\d{8}", numeric) or not 1 <= emission_type <= 9:
        raise NFeError("Código numérico ou tipo de emissão inválido")
    base = (f"{state_code}{issued_at:%y%m}{cnpj_digits}{model}{series:03d}"
            f"{number:09d}{emission_type}{numeric}")
    check = modulo11_check_digit(base)
    return NFeIdentity(base + check, numeric, check)


def deterministic_numeric_code(document_id: int, revision: int, company_id: int) -> str:
    material = f"SIVS-NFE|{company_id}|{document_id}|{revision}".encode("ascii")
    return f"{int.from_bytes(hashlib.sha256(material).digest()[:4], 'big') % 100_000_000:08d}"


def _element(parent, name: str, value=None):
    node = etree.SubElement(parent, f"{{{NFE_NS}}}{name}")
    if value is not None:
        node.text = str(value)
    return node


def _required_text(data: dict, key: str, label: str, maximum: int) -> str:
    value = " ".join(str(data.get(key) or "").split())
    if not value or len(value) > maximum:
        raise NFeError(f"{label} é obrigatório e deve possuir até {maximum} caracteres")
    return value


def _address(parent, tag: str, data: dict, *, recipient=False):
    address = _element(parent, tag)
    _element(address, "xLgr", _required_text(data, "street", "Logradouro", 60))
    _element(address, "nro", _required_text(data, "number", "Número", 60))
    complement = " ".join(str(data.get("complement") or "").split())
    if complement:
        _element(address, "xCpl", complement[:60])
    _element(address, "xBairro", _required_text(data, "district", "Bairro", 60))
    municipality_code = digits(data.get("municipality_code"))
    if not re.fullmatch(r"\d{7}", municipality_code):
        raise NFeError("Código IBGE do município deve possuir 7 dígitos")
    _element(address, "cMun", municipality_code)
    _element(address, "xMun", _required_text(data, "municipality", "Município", 60))
    uf = str(data.get("uf") or "").upper()
    if not re.fullmatch(r"[A-Z]{2}", uf):
        raise NFeError("UF do endereço é inválida")
    _element(address, "UF", uf)
    postal = digits(data.get("postal_code"))
    if postal:
        if len(postal) != 8:
            raise NFeError("CEP deve possuir 8 dígitos")
        _element(address, "CEP", postal)
    _element(address, "cPais", "1058")
    _element(address, "xPais", "BRASIL")
    phone = digits(data.get("phone"))
    if phone:
        _element(address, "fone", phone[:14])
    return address


def _tax_by_code(item: dict) -> dict:
    result = {}
    for tax in item.get("taxes") or []:
        code = str(tax.get("taxCode") or "").upper()
        if code in result:
            raise NFeError(f"Item possui mais de um resultado de {code}")
        result[code] = tax
    return result


def _legacy_taxes(imposto, item: dict, base_cents: int) -> dict:
    taxes = _tax_by_code(item)
    totals = {"icms_base": 0, "icms": 0, "ipi": 0, "pis": 0, "cofins": 0}
    origin = str(item.get("origin") or "0")
    icms = taxes.get("ICMS")
    if not icms:
        raise NFeError("ICMS é obrigatório na fotografia fiscal do item")
    group = _element(imposto, "ICMS")
    cst, csosn = str(icms.get("cst") or ""), str(icms.get("csosn") or "")
    if csosn:
        if csosn not in {"102", "103", "300", "400"}:
            raise NFeError(f"CSOSN {csosn} ainda não possui gerador XML homologado")
        node = _element(group, f"ICMSSN{csosn}")
        _element(node, "orig", origin)
        _element(node, "CSOSN", csosn)
    elif cst == "00":
        node = _element(group, "ICMS00")
        _element(node, "orig", origin); _element(node, "CST", cst); _element(node, "modBC", "3")
        _element(node, "vBC", money(icms["taxableBaseCents"])); _element(node, "pICMS", rate(icms["rateBps"]))
        _element(node, "vICMS", money(icms["amountCents"])); totals["icms_base"] = int(icms["taxableBaseCents"]); totals["icms"] = int(icms["amountCents"])
    elif cst == "20":
        node = _element(group, "ICMS20")
        _element(node, "orig", origin); _element(node, "CST", cst); _element(node, "modBC", "3")
        _element(node, "pRedBC", rate(icms["baseReductionBps"])); _element(node, "vBC", money(icms["taxableBaseCents"]))
        _element(node, "pICMS", rate(icms["rateBps"])); _element(node, "vICMS", money(icms["amountCents"]))
        totals["icms_base"] = int(icms["taxableBaseCents"]); totals["icms"] = int(icms["amountCents"])
    elif cst in {"40", "41", "50"}:
        node = _element(group, "ICMS40")
        _element(node, "orig", origin); _element(node, "CST", cst)
    else:
        raise NFeError(f"CST ICMS {cst or 'ausente'} ainda não possui gerador XML homologado")

    ipi = taxes.get("IPI")
    if ipi:
        group = _element(imposto, "IPI"); _element(group, "cEnq", "999")
        cst = str(ipi.get("cst") or "")
        if cst in {"50", "99"}:
            node = _element(group, "IPITrib"); _element(node, "CST", cst)
            _element(node, "vBC", money(ipi["taxableBaseCents"])); _element(node, "pIPI", rate(ipi["rateBps"]))
            _element(node, "vIPI", money(ipi["amountCents"])); totals["ipi"] = int(ipi["amountCents"])
        elif cst in {"01", "02", "03", "04", "05", "51", "52", "53", "54", "55"}:
            node = _element(group, "IPINT"); _element(node, "CST", cst)
        else:
            raise NFeError(f"CST IPI {cst or 'ausente'} ainda não possui gerador XML homologado")

    for code, tag, total_key in (("PIS", "PIS", "pis"), ("COFINS", "COFINS", "cofins")):
        tax = taxes.get(code)
        if not tax:
            raise NFeError(f"{code} é obrigatório na fotografia fiscal do item")
        group = _element(imposto, tag); cst = str(tax.get("cst") or "")
        if cst in {"01", "02"}:
            node = _element(group, f"{tag}Aliq"); _element(node, "CST", cst)
            _element(node, "vBC", money(tax["taxableBaseCents"])); _element(node, f"p{tag}", rate(tax["rateBps"]))
            _element(node, f"v{tag}", money(tax["amountCents"])); totals[total_key] = int(tax["amountCents"])
        elif cst in {"04", "05", "06", "07", "08", "09"}:
            node = _element(group, f"{tag}NT"); _element(node, "CST", cst)
        elif cst in {"49", "50", "51", "52", "53", "54", "55", "56", "60", "61", "62", "63", "64", "65", "66", "67", "70", "71", "72", "73", "74", "75", "98", "99"}:
            node = _element(group, f"{tag}Outr"); _element(node, "CST", cst)
            _element(node, "vBC", money(tax["taxableBaseCents"])); _element(node, f"p{tag}", rate(tax["rateBps"]))
            _element(node, f"v{tag}", money(tax["amountCents"])); totals[total_key] = int(tax["amountCents"])
        else:
            raise NFeError(f"CST {code} {cst or 'ausente'} ainda não possui gerador XML homologado")
    return totals


def build_unsigned_nfe(*, identity: NFeIdentity, issued_at: datetime, issuer: dict,
                       recipient: dict, operation: dict, items: list[dict]) -> bytes:
    if not items or len(items) > 990:
        raise NFeError("A NF-e deve possuir de 1 a 990 itens")
    nfe = etree.Element(f"{{{NFE_NS}}}NFe", nsmap=NSMAP)
    inf = _element(nfe, "infNFe"); inf.set("Id", f"NFe{identity.access_key}"); inf.set("versao", "4.00")
    ide = _element(inf, "ide")
    _element(ide, "cUF", operation["state_code"]); _element(ide, "cNF", identity.numeric_code)
    _element(ide, "natOp", _required_text(operation, "nature", "Natureza da operação", 60))
    _element(ide, "mod", "55"); _element(ide, "serie", int(operation["series"])); _element(ide, "nNF", int(operation["number"]))
    _element(ide, "dhEmi", issued_at.isoformat(timespec="seconds")); _element(ide, "tpNF", str(operation.get("direction", "1")))
    _element(ide, "idDest", str(operation.get("destination", "1"))); _element(ide, "cMunFG", digits(issuer["municipality_code"]))
    if operation.get("municipality_fg_ibs"):
        _element(ide, "cMunFGIBS", digits(operation["municipality_fg_ibs"]))
    _element(ide, "tpImp", "1"); _element(ide, "tpEmis", str(operation.get("emission_type", 1)))
    _element(ide, "cDV", identity.check_digit); _element(ide, "tpAmb", str(operation.get("environment", 2)))
    _element(ide, "finNFe", str(operation.get("finality", 1))); _element(ide, "indFinal", str(operation.get("final_consumer", 1)))
    _element(ide, "indPres", str(operation.get("presence", 1))); _element(ide, "procEmi", "0")
    _element(ide, "verProc", str(operation.get("app_version", "SIVS-2.2"))[:20])

    emit = _element(inf, "emit"); _element(emit, "CNPJ", digits(issuer["cnpj"]))
    _element(emit, "xNome", _required_text(issuer, "legal_name", "Razão social do emitente", 60))
    if issuer.get("trade_name"): _element(emit, "xFant", str(issuer["trade_name"])[:60])
    _address(emit, "enderEmit", issuer)
    _element(emit, "IE", digits(issuer["state_registration"])); _element(emit, "CRT", str(issuer["crt"]))

    dest = _element(inf, "dest"); document = digits(recipient.get("cnpj") or recipient.get("cpf"))
    _element(dest, "CNPJ" if len(document) == 14 else "CPF", document)
    name = _required_text(recipient, "name", "Nome do destinatário", 60)
    _element(dest, "xNome", "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL" if int(operation.get("environment", 2)) == 2 else name)
    _address(dest, "enderDest", recipient, recipient=True)
    ie_indicator = str(recipient.get("ie_indicator") or "")
    if ie_indicator not in {"1", "2", "9"}:
        raise NFeError("Indicador de inscrição estadual do destinatário é inválido")
    recipient_ie = digits(recipient.get("state_registration"))
    if ie_indicator == "1" and not recipient_ie:
        raise NFeError("Inscrição estadual é obrigatória para destinatário contribuinte")
    _element(dest, "indIEDest", ie_indicator)
    if ie_indicator == "1": _element(dest, "IE", recipient_ie)
    if recipient.get("email"): _element(dest, "email", str(recipient["email"])[:60])

    totals = {"products": 0, "discount": 0, "freight": 0, "insurance": 0, "other": 0,
              "icms_base": 0, "icms": 0, "ipi": 0, "pis": 0, "cofins": 0}
    for line, item in enumerate(items, 1):
        det = _element(inf, "det"); det.set("nItem", str(line)); prod = _element(det, "prod")
        _element(prod, "cProd", _required_text(item, "code", f"Código do item {line}", 60))
        _element(prod, "cEAN", str(item.get("ean") or "SEM GTIN")); _element(prod, "xProd", _required_text(item, "description", f"Descrição do item {line}", 120))
        _element(prod, "NCM", digits(item["ncm"]));
        if item.get("cest"): _element(prod, "CEST", digits(item["cest"]))
        _element(prod, "CFOP", digits(item["cfop"])); unit = str(item.get("unit") or "UN")[:6]
        _element(prod, "uCom", unit); _element(prod, "qCom", quantity(item["quantity_micros"])); _element(prod, "vUnCom", money(int(item["unit_value_micros"]) // 10000))
        _element(prod, "vProd", money(item["total_cents"])); _element(prod, "cEANTrib", str(item.get("ean_tax") or item.get("ean") or "SEM GTIN"))
        _element(prod, "uTrib", unit); _element(prod, "qTrib", quantity(item["quantity_micros"])); _element(prod, "vUnTrib", money(int(item["unit_value_micros"]) // 10000))
        _element(prod, "indTot", "1")
        imposto = _element(det, "imposto"); legacy = _legacy_taxes(imposto, item, item["base_cents"])
        for key, value in legacy.items(): totals[key] += value
        totals["products"] += int(item["total_cents"])

    total = _element(inf, "total"); icms_tot = _element(total, "ICMSTot")
    for tag, value in (("vBC", totals["icms_base"]), ("vICMS", totals["icms"]), ("vICMSDeson", 0),
                       ("vFCPUFDest", 0), ("vICMSUFDest", 0), ("vICMSUFRemet", 0), ("vFCP", 0),
                       ("vBCST", 0), ("vST", 0), ("vFCPST", 0), ("vFCPSTRet", 0),
                       ("vProd", totals["products"]), ("vFrete", 0), ("vSeg", 0), ("vDesc", 0),
                       ("vII", 0), ("vIPI", totals["ipi"]), ("vIPIDevol", 0), ("vPIS", totals["pis"]),
                       ("vCOFINS", totals["cofins"]), ("vOutro", 0), ("vNF", totals["products"] + totals["ipi"])):
        _element(icms_tot, tag, money(value))
    transp = _element(inf, "transp"); _element(transp, "modFrete", str(operation.get("freight_mode", 9)))
    pag = _element(inf, "pag"); det_pag = _element(pag, "detPag")
    _element(det_pag, "tPag", str(operation.get("payment_method", "90"))); _element(det_pag, "vPag", money(operation.get("payment_cents", 0)))
    additional = str(operation.get("additional_information") or "").strip()
    if additional:
        inf_adic = _element(inf, "infAdic"); _element(inf_adic, "infCpl", additional[:5000])
    return etree.tostring(nfe, encoding="UTF-8", xml_declaration=True, pretty_print=False)


def sign_nfe(xml_content: bytes, private_key, certificate) -> bytes:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)
    root = etree.fromstring(xml_content, parser)
    inf = root.find(f"{{{NFE_NS}}}infNFe")
    if inf is None or not re.fullmatch(r"NFe\d{44}", inf.get("Id") or ""):
        raise NFeError("XML sem identificador válido da NF-e")
    canonical_inf = etree.tostring(inf, method="c14n", exclusive=False, with_comments=False)
    digest = base64.b64encode(hashlib.sha1(canonical_inf).digest()).decode("ascii")
    signature = etree.Element(f"{{{DS_NS}}}Signature", nsmap={None: DS_NS})
    signed_info = etree.SubElement(signature, f"{{{DS_NS}}}SignedInfo")
    etree.SubElement(signed_info, f"{{{DS_NS}}}CanonicalizationMethod", Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    etree.SubElement(signed_info, f"{{{DS_NS}}}SignatureMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1")
    reference = etree.SubElement(signed_info, f"{{{DS_NS}}}Reference", URI=f"#{inf.get('Id')}")
    transforms = etree.SubElement(reference, f"{{{DS_NS}}}Transforms")
    etree.SubElement(transforms, f"{{{DS_NS}}}Transform", Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature")
    etree.SubElement(transforms, f"{{{DS_NS}}}Transform", Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    etree.SubElement(reference, f"{{{DS_NS}}}DigestMethod", Algorithm="http://www.w3.org/2000/09/xmldsig#sha1")
    etree.SubElement(reference, f"{{{DS_NS}}}DigestValue").text = digest
    canonical_info = etree.tostring(signed_info, method="c14n", exclusive=False, with_comments=False)
    signed = private_key.sign(canonical_info, padding.PKCS1v15(), hashes.SHA1())
    etree.SubElement(signature, f"{{{DS_NS}}}SignatureValue").text = base64.b64encode(signed).decode("ascii")
    key_info = etree.SubElement(signature, f"{{{DS_NS}}}KeyInfo")
    x509_data = etree.SubElement(key_info, f"{{{DS_NS}}}X509Data")
    der = certificate.public_bytes(serialization.Encoding.DER)
    etree.SubElement(x509_data, f"{{{DS_NS}}}X509Certificate").text = base64.b64encode(der).decode("ascii")
    root.append(signature)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=False)


def verify_signature(xml_content: bytes) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)
    root = etree.fromstring(xml_content, parser); signature = root.find(f"{{{DS_NS}}}Signature")
    inf = root.find(f"{{{NFE_NS}}}infNFe")
    if signature is None or inf is None:
        raise NFeError("Assinatura XML ausente")
    signed_info = signature.find(f"{{{DS_NS}}}SignedInfo")
    digest_value = signature.findtext(f".//{{{DS_NS}}}DigestValue")
    expected = base64.b64encode(hashlib.sha1(etree.tostring(inf, method="c14n")).digest()).decode("ascii")
    if digest_value != expected:
        raise NFeError("Digest da NF-e não confere")
    certificate = x509.load_der_x509_certificate(base64.b64decode(signature.findtext(f".//{{{DS_NS}}}X509Certificate")))
    try:
        certificate.public_key().verify(base64.b64decode(signature.findtext(f"{{{DS_NS}}}SignatureValue")),
                                        etree.tostring(signed_info, method="c14n"), padding.PKCS1v15(), hashes.SHA1())
    except Exception as exc:
        raise NFeError("Assinatura digital da NF-e é inválida") from exc


def verify_schema_bundle(schema_directory: Path) -> None:
    for filename, expected in SCHEMA_FILE_SHA256.items():
        candidate = Path(schema_directory) / filename
        if not candidate.is_file() or hashlib.sha256(candidate.read_bytes()).hexdigest().upper() != expected:
            raise NFeError(f"Integridade do pacote XSD oficial não confere: {filename}")


def validate_schema(xml_content: bytes, schema_path: Path) -> None:
    if not schema_path.is_file():
        raise NFeError(f"Schema oficial não instalado: {schema_path.name}")
    verify_schema_bundle(schema_path.parent)
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        schema = etree.XMLSchema(etree.parse(str(schema_path), parser))
        document = etree.fromstring(xml_content, parser)
        schema.assertValid(document)
    except (etree.XMLSchemaError, etree.DocumentInvalid, etree.XMLSyntaxError) as exc:
        detail = str(exc.error_log.last_error or exc)[:500] if hasattr(exc, "error_log") else str(exc)[:500]
        raise NFeError(f"XML rejeitado pelo schema NF-e {SCHEMA_VERSION}: {detail}") from None


def authorization_envelope(signed_nfe: bytes, batch_id: int, *, synchronous=True) -> bytes:
    if not 1 <= int(batch_id) <= 999_999_999_999_999:
        raise NFeError("Identificador do lote de NF-e inválido")
    root = etree.Element(f"{{{NFE_NS}}}enviNFe", nsmap=NSMAP, versao="4.00")
    _element(root, "idLote", int(batch_id)); _element(root, "indSinc", "1" if synchronous else "0")
    root.append(etree.fromstring(signed_nfe, etree.XMLParser(resolve_entities=False, no_network=True)))
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=False)


def receipt_query(receipt: str, *, environment=2) -> bytes:
    receipt_number = digits(receipt)
    if not re.fullmatch(r"\d{15}", receipt_number):
        raise NFeError("Recibo de autorização da NF-e deve possuir 15 dígitos")
    if int(environment) not in {1, 2}:
        raise NFeError("Ambiente da consulta de recibo é inválido")
    root = etree.Element(f"{{{NFE_NS}}}consReciNFe", nsmap=NSMAP, versao="4.00")
    _element(root, "tpAmb", int(environment)); _element(root, "nRec", receipt_number)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=False)


def parse_authorization_response(xml_content: bytes) -> dict:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        root = etree.fromstring(xml_content, parser)
    except etree.XMLSyntaxError as exc:
        raise NFeError("Resposta de autorização da SEFAZ não é XML válido") from exc
    text = lambda name: root.findtext(f".//{{{NFE_NS}}}{name}")
    protocol_node = root.find(f".//{{{NFE_NS}}}infProt")
    protocol_text = (lambda name: protocol_node.findtext(f"{{{NFE_NS}}}{name}")) if protocol_node is not None else text
    status = protocol_text("cStat")
    if not status or not status.isdigit():
        raise NFeError("Resposta da SEFAZ sem código de status")
    protocol = protocol_text("nProt")
    return {"statusCode": status, "reason": protocol_text("xMotivo") or "Resposta sem motivo",
            "batchStatusCode": text("cStat"), "receipt": text("nRec"),
            "protocol": protocol, "accessKey": protocol_text("chNFe"),
            "authorized": status in {"100", "150"} and bool(protocol), "rawSha256": hashlib.sha256(xml_content).hexdigest()}


def processed_nfe(signed_nfe: bytes, authorization_response: bytes) -> bytes:
    """Monta o nfeProc somente depois de conferir protocolo, chave e assinatura."""
    verify_signature(signed_nfe)
    response = parse_authorization_response(authorization_response)
    if not response["authorized"]:
        raise NFeError("Somente NF-e autorizada pode gerar o XML processado")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_blank_text=True)
    nfe = etree.fromstring(signed_nfe, parser)
    inf = nfe.find(f"{{{NFE_NS}}}infNFe")
    access_key = (inf.get("Id") or "")[3:] if inf is not None else ""
    response_root = etree.fromstring(authorization_response, parser)
    protocol = response_root.find(f".//{{{NFE_NS}}}protNFe")
    if protocol is None or access_key != response["accessKey"]:
        raise NFeError("Protocolo de autorização não corresponde à chave da NF-e")
    root = etree.Element(f"{{{NFE_NS}}}nfeProc", nsmap=NSMAP, versao="4.00")
    root.append(nfe)
    root.append(protocol)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=False)
