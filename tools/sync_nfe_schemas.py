#!/usr/bin/env python3
"""Baixa e confere o pacote oficial de schemas NF-e 010e_v1.02.

O padrão apenas descreve a operação. Use --apply para instalar os cinco XSDs
no diretório versionado da aplicação. Nenhum arquivo fora desse destino é tocado.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import sys
import urllib.request
import http.cookiejar
import zipfile
from pathlib import Path, PurePosixPath


SOURCE = "https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=akib2DRpJN4="
EXPECTED_SHA256 = "D44AE5AA6A0D1CABF6235D2D2D47B75BE5DD87BC6B90A7EC3DCEC99C3D41BDA1"
PREFIX = PurePosixPath("PL_010e_v1.02/NFe")
FILES = {
    "DFeTiposBasicos_v1.00.xsd",
    "leiauteNFe_v4.00.xsd",
    "nfe_v4.00.xsd",
    "tiposBasico_v4.00.xsd",
    "xmldsig-core-schema_v1.01.xsd",
}
ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "sivs_2_2" / "fiscal" / "schemas" / "nfe" / "010e_v1.02"


def download() -> bytes:
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "SIVS-SECCOL-schema-sync/1.0"})
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    with opener.open(request, timeout=30) as response:
        body = response.read(2 * 1024 * 1024 + 1)
    if len(body) > 2 * 1024 * 1024:
        raise RuntimeError("Pacote oficial excedeu o limite de 2 MB")
    digest = hashlib.sha256(body).hexdigest().upper()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"SHA-256 inesperado: {digest}")
    return body


def install(body: bytes) -> None:
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        entries = {}
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if info.is_dir() or path.parent != PREFIX or path.name not in FILES:
                continue
            if info.file_size > 2 * 1024 * 1024:
                raise RuntimeError(f"XSD excede o limite: {path.name}")
            entries[path.name] = archive.read(info)
    if set(entries) != FILES:
        raise RuntimeError(f"Pacote incompleto: faltam {sorted(FILES - set(entries))}")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    resolved = DESTINATION.resolve()
    for name, content in entries.items():
        target = (DESTINATION / name).resolve()
        if target.parent != resolved:
            raise RuntimeError("Destino de schema inválido")
        target.write_bytes(content)
    file_hashes = "".join(
        f"SHA-256 {name}: {hashlib.sha256(entries[name]).hexdigest().upper()}\n"
        for name in sorted(entries)
    )
    (DESTINATION / "SOURCE.txt").write_text(
        f"Fonte oficial: {SOURCE}\nPacote: 010e_v1.02\nSHA-256 do ZIP: {EXPECTED_SHA256}\n{file_hashes}",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="instala os schemas após validar o pacote")
    args = parser.parse_args()
    print(f"Fonte: {SOURCE}")
    print(f"Destino: {DESTINATION}")
    print(f"SHA-256 esperado: {EXPECTED_SHA256}")
    if not args.apply:
        print("Simulação: nenhum arquivo alterado. Use --apply para instalar.")
        return 0
    body = download()
    install(body)
    print(f"Instalados {len(FILES)} schemas oficiais em {DESTINATION}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1)
