#!/usr/bin/env python3
"""Verifica ou restaura um backup criptografado SIVS-BACKUP-2 com segurança."""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path


MAGIC = b"SIVSBKP2"
REQUIRED_TABLES = {
    "users", "sessions", "companies", "company_memberships", "records",
    "attachments", "approvals", "audit_log", "schema_migrations", "setup_state",
}


def decrypt_backup(source: Path, passphrase: str) -> bytes:
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as exc:
        raise RuntimeError("Instale a dependência: pip install cryptography") from exc
    encrypted = source.read_bytes()
    if len(encrypted) < 57 or not encrypted.startswith(MAGIC):
        raise ValueError("O arquivo não possui o formato SIVS-BACKUP-2")
    iterations = int.from_bytes(encrypted[8:12], "big")
    if not 100_000 <= iterations <= 5_000_000:
        raise ValueError("Parâmetro criptográfico inválido")
    salt, nonce, header = encrypted[12:28], encrypted[28:40], encrypted[:40]
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations,
    ).derive(passphrase.encode("utf-8"))
    try:
        return AESGCM(key).decrypt(nonce, encrypted[40:], header)
    except Exception as exc:
        raise ValueError("Senha incorreta ou backup corrompido") from exc


def verify_database(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"Falha de integridade SQLite: {integrity}")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise ValueError("Backup incompleto; tabelas ausentes: " + ", ".join(missing))
        return {
            "companies": connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
            "users": connection.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "records": connection.execute("SELECT COUNT(*) FROM records").fetchone()[0],
            "attachments": connection.execute("SELECT COUNT(*) FROM attachments").fetchone()[0],
            "audit_events": connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica ou restaura um backup integral criptografado do SIVS 2.2"
    )
    parser.add_argument("backup", type=Path, help="arquivo .sivsbackup")
    parser.add_argument("--database", type=Path, default=Path("data/sivs.db"),
                        help="banco de destino (padrão: data/sivs.db)")
    parser.add_argument("--verify-only", action="store_true",
                        help="decifra e verifica sem substituir o banco")
    parser.add_argument("--force", action="store_true",
                        help="confirma a substituição do banco de destino")
    args = parser.parse_args()
    backup = args.backup.expanduser().resolve()
    target = args.database.expanduser().resolve()
    if not backup.is_file():
        parser.error("o arquivo de backup não existe")
    if target == Path(target.anchor):
        parser.error("o destino não pode ser a raiz do sistema")
    if not args.verify_only and not args.force:
        parser.error("use --force para confirmar a restauração")
    passphrase = getpass.getpass("Senha do backup: ")
    if not passphrase:
        parser.error("a senha não pode ficar vazia")

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="sivs-restore-", suffix=".sqlite3", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(decrypt_backup(backup, passphrase))
        os.chmod(temporary, 0o600)
        summary = verify_database(temporary)
        print("Backup íntegro:", ", ".join(f"{key}={value}" for key, value in summary.items()))
        if args.verify_only:
            return 0
        safety_copy = None
        if target.exists():
            safety_copy = target.with_name(
                f"{target.name}.before-restore-{datetime.now():%Y%m%d-%H%M%S}"
            )
            shutil.copy2(target, safety_copy)
            os.chmod(safety_copy, 0o600)
        os.replace(temporary, target)
        os.chmod(target, 0o600)
        print(f"Banco restaurado em: {target}")
        if safety_copy:
            print(f"Cópia de segurança anterior: {safety_copy}")
        return 0
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"Restauração cancelada: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
