#!/usr/bin/env python3
"""Ensaia restauracao de backup externo sem tocar no banco de producao.

Por padrao apenas le, decifra em diretorio temporario, executa verificacoes de
integridade e imprime uma evidencia JSON. A senha vem de prompt ou de uma
variavel indicada explicitamente; nunca e aceita como argumento de linha de
comando nem incluida no relatorio.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "sivs_2_2"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from restore_backup import decrypt_backup, verify_database


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica uma copia SIVS-BACKUP-2 externa em restauracao temporaria",
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument(
        "--passphrase-env",
        help="nome da variavel de ambiente que contem a senha (o valor nunca e exibido)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="grava a evidencia JSON neste arquivo; sem esta opcao nada e alterado",
    )
    args = parser.parse_args()
    source = args.backup.expanduser().resolve()
    if not source.is_file():
        parser.error("o backup externo nao existe")
    passphrase = (
        os.environ.get(args.passphrase_env, "")
        if args.passphrase_env
        else getpass.getpass("Senha do backup: ")
    )
    if not passphrase:
        parser.error("a senha do backup nao foi informada")

    try:
        encrypted_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="sivs-restore-drill-") as directory:
            restored = Path(directory) / "restored.sqlite3"
            restored.write_bytes(decrypt_backup(source, passphrase))
            summary = verify_database(restored)
            connection = sqlite3.connect(restored)
            try:
                foreign_key_errors = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
            finally:
                connection.close()
            if quick_check != "ok" or foreign_key_errors:
                raise ValueError("o banco restaurado falhou na verificacao referencial")
        evidence = {
            "format": "SIVS-BACKUP-2",
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
            "backupFile": source.name,
            "encryptedSha256": encrypted_hash,
            "integrityCheck": "ok",
            "foreignKeyViolations": 0,
            "counts": summary,
            "productionDatabaseTouched": False,
        }
        rendered = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            report = args.report.expanduser().resolve()
            if report == Path(report.anchor):
                parser.error("o relatorio nao pode ser gravado na raiz do sistema")
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"Ensaio de restauracao reprovado: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
