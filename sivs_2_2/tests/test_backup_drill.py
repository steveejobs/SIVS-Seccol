import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


ROOT = Path(__file__).resolve().parents[2]
DRILL = ROOT / "tools" / "verify_backup_drill.py"
PASSWORD_ENV = "SIVS_TEST_BACKUP_PASSWORD"


class BackupDrillTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        database = self.directory / "source.sqlite3"
        connection = sqlite3.connect(database)
        try:
            for table in (
                "users", "sessions", "companies", "company_memberships", "records",
                "attachments", "approvals", "audit_log", "system_events",
                "schema_migrations", "setup_state",
            ):
                connection.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY)')
            connection.execute("INSERT INTO companies DEFAULT VALUES")
            connection.execute("INSERT INTO users DEFAULT VALUES")
            connection.commit()
        finally:
            connection.close()

        password = "senha-de-teste-nao-produtiva"
        plaintext = database.read_bytes()
        iterations = 100_000
        salt = os.urandom(16)
        nonce = os.urandom(12)
        header = b"SIVSBKP2" + iterations.to_bytes(4, "big") + salt + nonce
        key = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations,
        ).derive(password.encode("utf-8"))
        self.backup = self.directory / "external.sivsbackup"
        self.backup.write_bytes(header + AESGCM(key).encrypt(nonce, plaintext, header))
        self.environment = os.environ.copy()
        self.environment[PASSWORD_ENV] = password

    def tearDown(self):
        self.temporary.cleanup()

    def run_drill(self, environment=None):
        return subprocess.run(
            [
                sys.executable,
                str(DRILL),
                str(self.backup),
                "--passphrase-env",
                PASSWORD_ENV,
            ],
            cwd=ROOT,
            env=environment or self.environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def test_external_backup_is_verified_without_touching_production(self):
        result = self.run_drill()

        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence["format"], "SIVS-BACKUP-2")
        self.assertEqual(evidence["integrityCheck"], "ok")
        self.assertEqual(evidence["foreignKeyViolations"], 0)
        self.assertFalse(evidence["productionDatabaseTouched"])
        self.assertEqual(evidence["counts"]["companies"], 1)
        self.assertNotIn(self.environment[PASSWORD_ENV], result.stdout + result.stderr)

    def test_wrong_password_fails_closed(self):
        environment = self.environment.copy()
        environment[PASSWORD_ENV] = "incorreta"
        result = self.run_drill(environment)

        self.assertEqual(result.returncode, 1)
        self.assertIn("reprovado", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
