import sys
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fiscal_nfe import (
    NFeError, authorization_envelope, build_identity, build_unsigned_nfe,
    deterministic_numeric_code, modulo11_check_digit, parse_authorization_response,
    processed_nfe, receipt_query, sign_nfe, validate_schema, verify_schema_bundle,
    verify_signature,
)


class FiscalNFeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SECCOL HOMOLOGACAO")])
        now = datetime.now(timezone.utc)
        cls.certificate = (
            x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(cls.key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=30))
            .sign(cls.key, hashes.SHA256())
        )
        cls.schema = ROOT / "fiscal" / "schemas" / "nfe" / "010e_v1.02" / "nfe_v4.00.xsd"

    def sample_xml(self, tax_overrides=None):
        issued_at = datetime(2026, 8, 27, 15, 30, tzinfo=timezone(timedelta(hours=-3)))
        identity = build_identity(
            state_code="52", issued_at=issued_at, cnpj="12345678000195", model="55",
            series=1, number=1, emission_type=1, numeric_code=deterministic_numeric_code(1, 1, 1),
        )
        issuer = {
            "cnpj": "12345678000195", "legal_name": "SECCOL HOMOLOGACAO LTDA",
            "trade_name": "SECCOL", "state_registration": "123456789", "crt": "3",
            "street": "Rua de Homologacao", "number": "100", "district": "Centro",
            "municipality_code": "5208707", "municipality": "Goiania", "uf": "GO",
            "postal_code": "74000000", "phone": "6233330000",
        }
        recipient = {
            "cnpj": "11222333000181", "name": "CLIENTE TESTE LTDA", "ie_indicator": "9",
            "street": "Rua Cliente", "number": "200", "district": "Centro",
            "municipality_code": "5208707", "municipality": "Goiania", "uf": "GO",
            "postal_code": "74000001", "email": "fiscal@example.test",
        }
        operation = {
            "state_code": "52", "nature": "VENDA DE MERCADORIA", "series": 1, "number": 1,
            "environment": 2, "direction": 1, "destination": 1, "finality": 1,
            "final_consumer": 1, "presence": 1, "payment_method": "90", "payment_cents": 0,
        }
        item = {
            "code": "P-001", "description": "PRODUTO PARA HOMOLOGACAO", "ncm": "90318099",
            "cfop": "5102", "origin": "0", "unit": "UN", "quantity_micros": 1_000_000,
            "unit_value_micros": 10000 * 10000, "total_cents": 10000, "base_cents": 10000,
            "taxes": [
                {"taxCode": "ICMS", "cst": "00", "rateBps": 1800, "taxableBaseCents": 10000, "amountCents": 1800},
                {"taxCode": "PIS", "cst": "01", "rateBps": 165, "taxableBaseCents": 10000, "amountCents": 165},
                {"taxCode": "COFINS", "cst": "01", "rateBps": 760, "taxableBaseCents": 10000, "amountCents": 760},
            ],
        }
        for tax in item["taxes"]:
            tax.update((tax_overrides or {}).get(tax["taxCode"], {}))
        return identity, build_unsigned_nfe(identity=identity, issued_at=issued_at, issuer=issuer,
                                             recipient=recipient, operation=operation, items=[item])

    def test_access_key_check_digit_and_deterministic_code(self):
        identity, _ = self.sample_xml()
        self.assertEqual(len(identity.access_key), 44)
        self.assertEqual(identity.access_key[-1], modulo11_check_digit(identity.access_key[:-1]))
        self.assertEqual(deterministic_numeric_code(9, 2, 4), deterministic_numeric_code(9, 2, 4))

    def test_signed_xml_verifies_and_matches_official_schema(self):
        identity, unsigned = self.sample_xml()
        signed = sign_nfe(unsigned, self.key, self.certificate)
        verify_signature(signed)
        validate_schema(signed, self.schema)
        envelope = authorization_envelope(signed, 1)
        self.assertIn(identity.access_key.encode(), envelope)
        self.assertNotIn(b"PRIVATE KEY", signed)

    def test_tampering_breaks_the_signature(self):
        _, unsigned = self.sample_xml()
        signed = sign_nfe(unsigned, self.key, self.certificate)
        with self.assertRaisesRegex(NFeError, "Digest"):
            verify_signature(signed.replace(b"100.00", b"101.00", 1))

    def test_authorization_response_is_parsed_without_trusting_text(self):
        response = b'''<?xml version="1.0"?><retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><tpAmb>2</tpAmb><cStat>104</cStat><xMotivo>Lote processado</xMotivo><protNFe><infProt><tpAmb>2</tpAmb><verAplic>GO</verAplic><chNFe>52123456789012345678901234567890123456789012</chNFe><dhRecbto>2026-08-27T15:31:00-03:00</dhRecbto><nProt>152600000000001</nProt><digVal>AA==</digVal><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe></retEnviNFe>'''
        result = parse_authorization_response(response)
        self.assertTrue(result["authorized"])
        self.assertEqual(result["protocol"], "152600000000001")

    def test_authorized_protocol_builds_processed_xml_and_danfe(self):
        from server import SIVSHandler

        identity, unsigned = self.sample_xml()
        signed = sign_nfe(unsigned, self.key, self.certificate)
        response = f'''<?xml version="1.0"?><retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><tpAmb>2</tpAmb><cStat>104</cStat><xMotivo>Lote processado</xMotivo><protNFe versao="4.00"><infProt><tpAmb>2</tpAmb><verAplic>GO</verAplic><chNFe>{identity.access_key}</chNFe><dhRecbto>2026-08-27T15:31:00-03:00</dhRecbto><nProt>152600000000001</nProt><digVal>AA==</digVal><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe></retEnviNFe>'''.encode()
        processed = processed_nfe(signed, response)
        self.assertIn(b"nfeProc", processed)
        self.assertIn(identity.access_key.encode(), processed)
        pdf = SIVSHandler.build_danfe_pdf(processed)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 2000)

    def test_protocol_for_another_key_is_rejected(self):
        _, unsigned = self.sample_xml()
        signed = sign_nfe(unsigned, self.key, self.certificate)
        response = b'''<retEnviNFe xmlns="http://www.portalfiscal.inf.br/nfe"><protNFe><infProt><chNFe>52123456789012345678901234567890123456789012</chNFe><nProt>1</nProt><cStat>100</cStat><xMotivo>Autorizado</xMotivo></infProt></protNFe></retEnviNFe>'''
        with self.assertRaisesRegex(NFeError, "n.o corresponde"):
            processed_nfe(signed, response)

    def test_receipt_query_is_strict_and_namespaced(self):
        query = receipt_query("123456789012345", environment=2)
        self.assertIn(b"consReciNFe", query)
        self.assertIn(b"<nRec>123456789012345</nRec>", query)
        with self.assertRaisesRegex(NFeError, "15 d.gitos"):
            receipt_query("123")

    def test_schema_bundle_integrity_is_pinned(self):
        verify_schema_bundle(self.schema.parent)
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "schemas"
            shutil.copytree(self.schema.parent, copied)
            target = copied / "nfe_v4.00.xsd"
            target.write_bytes(target.read_bytes() + b"\n")
            with self.assertRaisesRegex(NFeError, "Integridade"):
                verify_schema_bundle(copied)

    def test_reduced_icms_and_other_pis_cofins_groups_match_schema(self):
        _, unsigned = self.sample_xml({
            "ICMS": {"cst": "20", "baseReductionBps": 1000, "taxableBaseCents": 9000, "amountCents": 1620},
            "PIS": {"cst": "49"}, "COFINS": {"cst": "49"},
        })
        signed = sign_nfe(unsigned, self.key, self.certificate)
        validate_schema(signed, self.schema)


if __name__ == "__main__":
    unittest.main()
