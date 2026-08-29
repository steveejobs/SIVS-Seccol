#!/usr/bin/env python3
"""Localiza linguagem técnica exposta na interface sem alterar arquivos.

Uso:
    python tools/audit_plain_language.py
    python tools/audit_plain_language.py --strict

O modo padrão é somente diagnóstico e sempre é seguro: não inicia o servidor,
não acessa a rede e não grava no repositório. ``--strict`` retorna código 1
quando encontrar termos que precisam de revisão humana, útil para CI futura.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "sivs_2_2" / "static"
TERMS = {
    "ledger": "histórico de movimentações/financeiro",
    "guardrail": "limites autorizados",
    "payload": "dados enviados",
    "idempot": "repetição segura",
    "shadow": "simulação sem ação externa",
    "webhook": "aviso automático recebido do serviço",
    "hash": "identificação de integridade do arquivo",
    "imutável": "histórico preservado, que não pode ser alterado",
    "AFD": "arquivo fiscal do relógio",
    "REP": "registro eletrônico de ponto",
    "AEJ": "arquivo de jornada",
    "NCM": "classificação fiscal da mercadoria",
    "CFOP": "código da operação fiscal",
    "CST": "código de situação tributária",
    "CSOSN": "código tributário do Simples Nacional",
    "OCR": "leitura de páginas escaneadas",
}
QUOTED_TEXT = re.compile(r"['\"`]([^'\"`]{3,})['\"`]")
HTML_TAG = re.compile(r"<[^>]*>")
INTERPOLATION = re.compile(r"\$\{[^}]*\}")


def findings() -> list[tuple[Path, int, str, str]]:
    """Return UI literals containing terms that require a human clarity check."""
    found: list[tuple[Path, int, str, str]] = []
    for path in sorted(UI_ROOT.rglob("*")):
        if path.suffix not in {".js", ".html"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for literal in QUOTED_TEXT.findall(line):
                # Remove código de templates HTML. Assim ``payload``, chaves de
                # API e atributos não são confundidos com texto que uma pessoa lê.
                visible = INTERPOLATION.sub(" ", HTML_TAG.sub(" ", literal))
                if not re.search(r"\s", visible):
                    continue
                for term, preferred in TERMS.items():
                    if re.search(rf"\b{re.escape(term)}\b", visible, re.IGNORECASE):
                        found.append((path.relative_to(ROOT), number, term, preferred))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita termos técnicos em textos da interface.")
    parser.add_argument("--strict", action="store_true", help="retorna erro se houver itens para revisão")
    args = parser.parse_args()
    items = findings()
    if not items:
        print("Linguagem clara: nenhum termo técnico isolado encontrado.")
        return 0
    print(f"{len(items)} termo(s) para revisão humana:")
    for path, line, term, preferred in items:
        print(f"- {path}:{line}: '{term}' -> prefira '{preferred}' ou explique-o no próprio contexto")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
