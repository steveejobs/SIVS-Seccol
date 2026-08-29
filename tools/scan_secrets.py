#!/usr/bin/env python3
"""Bloqueia segredos comuns em arquivos rastreados, sem imprimir seu conteúdo."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PATTERNS = {
    "chave OpenRouter/OpenAI": re.compile(r"\bsk-(?:or-v1-)?[A-Za-z0-9_-]{20,}\b"),
    "chave AWS": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "token GitHub": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "chave privada": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True,
    )
    return [Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings = []
    for path in tracked_files():
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path}:{line_number} ({label})")
    if findings:
        print("Possíveis segredos encontrados:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("Nenhum padrão de segredo encontrado em arquivos rastreados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
