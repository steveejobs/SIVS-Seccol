#!/usr/bin/env python3
"""Redefinição emergencial de senha do SIVS, segura e em modo simulação por padrão."""

from __future__ import annotations

import argparse
import base64
import hashlib
import secrets
import sqlite3
import string
from datetime import datetime, timezone
from pathlib import Path


PBKDF2_ITERATIONS = 310_000


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, PBKDF2_ITERATIONS
    )
    return (
        f"pbkdf2_sha256${PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode()}$"
        f"{base64.b64encode(digest).decode()}"
    )


def temporary_password(length=20):
    alphabet = string.ascii_letters + string.digits + "-_.!"
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(char.islower() for char in value)
                and any(char.isupper() for char in value)
                and any(char.isdigit() for char in value)):
            return value


def snapshot_database(connection, database_path):
    backup_dir = database_path.parent / "admin-backups"
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"sivs-before-password-reset-{stamp}.sqlite3"
    destination = sqlite3.connect(target)
    try:
        connection.backup(destination)
        if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("A cópia de segurança não passou no quick_check")
    finally:
        destination.close()
    target.chmod(0o600)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="E-mail exato da conta do SIVS")
    parser.add_argument("--database", default="/data/sivs.db", type=Path)
    parser.add_argument(
        "--apply", action="store_true",
        help="Confirma a alteração; sem esta opção o comando apenas simula.",
    )
    args = parser.parse_args()
    email = args.email.strip().lower()
    if not args.database.is_file():
        raise SystemExit(f"Banco não encontrado: {args.database}")

    database = sqlite3.connect(args.database)
    database.row_factory = sqlite3.Row
    try:
        user = database.execute(
            "SELECT id,email,active FROM users WHERE email=? COLLATE NOCASE", (email,)
        ).fetchone()
        if not user:
            raise SystemExit("Usuário não encontrado; nenhuma alteração foi feita.")
        print(f"Conta localizada: {user['email']} (ativa={bool(user['active'])})")
        if not args.apply:
            print("SIMULAÇÃO: use --apply para gerar e gravar uma senha provisória.")
            return

        backup = snapshot_database(database, args.database)
        password = temporary_password()
        database.execute("BEGIN IMMEDIATE")
        database.execute(
            "UPDATE users SET password_hash=?,active=1,updated_at=? WHERE id=?",
            (password_hash(password), utc_now(), user["id"]),
        )
        database.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
        database.execute(
            """INSERT INTO audit_log
               (user_id,action,entity_type,entity_id,detail,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                user["id"], "emergency_password_reset", "user", str(user["id"]),
                '{"source":"offline_admin_tool"}', utc_now(),
            ),
        )
        database.commit()
        print(f"Backup verificado: {backup}")
        print(f"Senha provisória: {password}")
        print("As sessões anteriores foram encerradas. Troque a senha após entrar.")
    except Exception:
        if database.in_transaction:
            database.rollback()
        raise
    finally:
        database.close()


if __name__ == "__main__":
    main()
