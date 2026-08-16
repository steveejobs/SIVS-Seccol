import http.client
import contextlib
import io
import json
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
from email.message import Message
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import (
    Database,
    DEFAULT_TENDER_KEYWORDS,
    MODULES,
    NORMATIVE_REQUIRED_MODULES,
    NORM_CATALOG,
    ROLE_MODULES,
    SECCOL_CONTEXT_TERMS,
    SECCOL_INSTRUMENT_CATALOG,
    SECCOL_PRODUCT_CATALOG,
    SECCOL_SERVICE_CATALOG,
    SOURCE_CATALOG,
    SIVSHandler,
    SIVSServer,
    VERSION,
    mountinfo_has_path,
    password_hash,
    password_verify,
    require_persistent_database,
    utc_now,
)


@contextlib.contextmanager
def temporary_database(filename):
    with tempfile.TemporaryDirectory() as directory:
        database = Database(Path(directory) / filename)
        try:
            yield database
        finally:
            database.close_thread_connection()


class DatabaseTests(unittest.TestCase):
    def test_production_requires_database_directory_to_be_a_mount(self):
        database_path = Path("/data/sivs.db")
        with patch.dict("os.environ", {"SIVS_REQUIRE_PERSISTENT_DB": "1"}):
            with patch.object(Path, "exists", return_value=True), patch(
                "server.database_directory_is_mount", return_value=False
            ):
                with self.assertRaisesRegex(RuntimeError, "monte um volume"):
                    require_persistent_database(database_path)
            with patch.object(Path, "exists", return_value=True), patch(
                "server.database_directory_is_mount", return_value=True
            ):
                self.assertTrue(require_persistent_database(database_path))

    def test_linux_mountinfo_recognizes_bind_mount(self):
        mountinfo = "36 25 0:32 / /data rw,relatime - ext4 /dev/root rw\n"
        self.assertTrue(mountinfo_has_path(mountinfo, "/data"))

    def test_password_round_trip(self):
        encoded = password_hash("Senha-Forte-123")
        self.assertTrue(password_verify("Senha-Forte-123", encoded))
        self.assertFalse(password_verify("senha-errada", encoded))

    def test_database_schema_catalogs_and_persistence(self):
        with temporary_database("test.db") as db:
            company_id = db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
            now = utc_now()
            user = db.execute(
                "INSERT INTO users(name,email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                ("Admin", "admin@example.com", password_hash("Senha-Forte-123"), "admin", now, now),
            ).lastrowid
            db.execute(
                """INSERT INTO records
                   (module,title,status,payload,created_by,created_at,updated_at,company_id)
                   VALUES(?,?,?,?,?,?,?,?)""",
                ("clientes", "Cliente teste", "Ativo", "{}", user, now, now, company_id),
            )
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM records WHERE company_id=? AND module='clientes'", (company_id,)), 1)
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM records WHERE company_id=? AND module='fontes'", (company_id,)),
                len(SOURCE_CATALOG))
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM records WHERE company_id=? AND module='normas_tecnicas'", (company_id,)),
                len(NORM_CATALOG))
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM attachments WHERE company_id=? AND category='Ficha de referência normativa'",
                (company_id,)), len(NORM_CATALOG))
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM records WHERE company_id=? AND module='produtos'",
                (company_id,)), len(SECCOL_PRODUCT_CATALOG))
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM records WHERE company_id=? AND module='instrumentos_seccol'",
                (company_id,)), len(SECCOL_INSTRUMENT_CATALOG))
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM records WHERE company_id=? AND module='catalogo_servicos'",
                (company_id,)), len(SECCOL_SERVICE_CATALOG))
            columns = {row["name"] for row in db.connection().execute("PRAGMA table_info(records)")}
            self.assertTrue({"deleted_at", "company_id", "subject_id"}.issubset(columns))
            self.assertEqual(db.scalar("SELECT COUNT(*) FROM record_versions"), 0)

    def test_database_rejects_cross_company_relationships_and_subjects(self):
        with temporary_database("integrity.db") as db:
            now = utc_now()
            first_company = db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
            second_company = db.execute(
                "INSERT INTO companies(name,created_at,updated_at) VALUES(?,?,?)",
                ("Outra empresa", now, now),
            ).lastrowid
            user_id = db.execute(
                "INSERT INTO users(name,email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                ("Admin", "integrity@example.com", password_hash("Senha-Forte-123"), "admin", now, now),
            ).lastrowid
            first_record = db.execute(
                """INSERT INTO records(module,title,status,payload,created_by,created_at,updated_at,company_id)
                   VALUES('clientes','Cliente A','Ativo','{}',?,?,?,?)""",
                (user_id, now, now, first_company),
            ).lastrowid
            second_record = db.execute(
                """INSERT INTO records(module,title,status,payload,created_by,created_at,updated_at,company_id)
                   VALUES('clientes','Cliente B','Ativo','{}',?,?,?,?)""",
                (user_id, now, now, second_company),
            ).lastrowid
            second_subject = db.execute(
                """INSERT INTO subjects(name,normalized_name,status,created_by,created_at,updated_at,company_id)
                   VALUES(?,?,?,?,?,?,?)""",
                ("Assunto B", f"{second_company}:assunto b", "Ativo", user_id, now, now, second_company),
            ).lastrowid
            with self.assertRaisesRegex(sqlite3.IntegrityError, "mesma empresa"):
                db.execute(
                    "INSERT INTO record_relationships(from_record_id,to_record_id,relationship_type,created_by,created_at) VALUES(?,?,?,?,?)",
                    (first_record, second_record, "Relacionado a", user_id, now),
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "mesma empresa"):
                db.execute(
                    "INSERT INTO record_subjects(record_id,subject_id,relationship_type,is_primary,created_by,created_at) VALUES(?,?,?,?,?,?)",
                    (first_record, second_subject, "Relacionado a", 1, user_id, now),
                )

    def test_user_and_password_survive_database_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "restart.db"
            first = Database(path)
            now = utc_now()
            first.execute(
                "INSERT INTO users(name,email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                ("Admin", "restart@example.com", password_hash("Senha-Forte-123"), "admin", now, now),
            )
            first.close_thread_connection()

            reopened = Database(path)
            try:
                row = reopened.connection().execute(
                    "SELECT email,password_hash FROM users WHERE email=?", ("restart@example.com",)
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertTrue(password_verify("Senha-Forte-123", row["password_hash"]))
            finally:
                reopened.close_thread_connection()

    def test_expected_modules_and_roles_exist(self):
        required = {
            "clientes", "licitacoes", "editais", "servicos", "calibracoes", "certificados",
            "normas_tecnicas", "laudos_tecnicos", "estudos_tecnicos", "financeiro", "frota",
            "catalogo_servicos", "instrumentos_seccol",
        }
        self.assertTrue(required.issubset(MODULES))
        self.assertEqual(NORMATIVE_REQUIRED_MODULES, {"certificados", "laudos_tecnicos", "estudos_tecnicos"})
        self.assertTrue(required.issubset(ROLE_MODULES["admin"]))
        self.assertTrue({"normas_tecnicas", "laudos_tecnicos"}.issubset(ROLE_MODULES["quality"]))
        self.assertEqual(VERSION, "2.2.0")

    def test_seccol_portfolio_is_classified_linked_and_idempotent(self):
        with temporary_database("portfolio.db") as db:
            company_id = db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
            total = len(SECCOL_PRODUCT_CATALOG) + len(SECCOL_INSTRUMENT_CATALOG) + len(SECCOL_SERVICE_CATALOG)
            self.assertEqual(db.scalar(
                """SELECT COUNT(*) FROM records WHERE company_id=?
                   AND json_extract(payload,'$.catalogo_seccol')=1""", (company_id,)), total)
            self.assertEqual(db.scalar(
                """SELECT COUNT(*) FROM attachments WHERE company_id=?
                   AND category='Ficha de portfólio SECCOL'""", (company_id,)), total)
            counter_id = db.scalar(
                """SELECT id FROM records WHERE company_id=? AND module='instrumentos_seccol'
                   AND json_extract(payload,'$.catalog_key')='instrumento-contador-particulas'""",
                (company_id,))
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM record_relationships WHERE from_record_id=? AND relationship_type='Fundamentado em'",
                (counter_id,)), 3)
            db.seed_seccol_portfolio(company_id)
            self.assertEqual(db.scalar(
                """SELECT COUNT(*) FROM records WHERE company_id=?
                   AND json_extract(payload,'$.catalogo_seccol')=1""", (company_id,)), total)

    def test_tender_vocabulary_is_specific_to_seccol(self):
        for term in (
            "controle de contaminação ambiental", "cabine de segurança biológica", "filtro HEPA",
            "qualificação ISO 5", "ISO 14644", "ensaio de inflow", "estanqueidade de filtro HEPA",
        ):
            self.assertIn(term, DEFAULT_TENDER_KEYWORDS)
        self.assertNotIn("equipamento hospitalar", DEFAULT_TENDER_KEYWORDS)
        self.assertIn("indústria farmacêutica", SECCOL_CONTEXT_TERMS)
        self.assertIn("ISO 21501-4", SECCOL_CONTEXT_TERMS)

    def test_relationships_are_company_isolated_and_idempotent(self):
        with temporary_database("relations.db") as db:
            now = utc_now()
            company_one = db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
            company_two = db.execute(
                "INSERT INTO companies(name,created_at,updated_at) VALUES(?,?,?)",
                ("Empresa B", now, now),
            ).lastrowid
            first = db.execute(
                """INSERT INTO records(module,title,status,payload,created_at,updated_at,company_id)
                   VALUES(?,?,?,?,?,?,?)""",
                ("clientes", "Hospital Central", "Ativo", "{}", now, now, company_one),
            ).lastrowid
            second = db.execute(
                """INSERT INTO records(module,title,status,payload,created_at,updated_at,company_id)
                   VALUES(?,?,?,?,?,?,?)""",
                ("frota", "Veículo técnico", "Ativo", "{}", now, now, company_one),
            ).lastrowid
            other_company = db.execute(
                """INSERT INTO records(module,title,status,payload,created_at,updated_at,company_id)
                   VALUES(?,?,?,?,?,?,?)""",
                ("clientes", "Hospital Central", "Ativo", "{}", now, now, company_two),
            ).lastrowid
            payload = {
                "assunto": "Certificação Hospital Central 2026",
                "relacionamentos": [{"record": f"clientes:{first}", "type": "Relacionado a"}],
            }
            db.sync_relationships(second, payload, company_id=company_one)
            db.sync_relationships(second, payload, company_id=company_one)
            db.connection().commit()
            self.assertIsNotNone(db.scalar("SELECT subject_id FROM records WHERE id=?", (second,)))
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM subjects WHERE normalized_name=?",
                (f"{company_one}:certificacao hospital central 2026",)), 1)
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM record_relationships WHERE from_record_id=?", (second,)), 1)
            with self.assertRaises(ValueError):
                db.sync_relationships(second, {
                    "assunto": "Certificação Hospital Central 2026",
                    "relacionamentos": [{"record": f"clientes:{other_company}", "type": "Relacionado a"}],
                }, company_id=company_one)
            db.connection().rollback()

    def test_subject_migration_is_idempotent(self):
        with temporary_database("migration.db") as db:
            company_id = db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
            now = utc_now()
            db.execute(
                """INSERT INTO records(module,title,status,payload,created_at,updated_at,company_id)
                   VALUES(?,?,?,?,?,?,?)""",
                ("servicos", "Qualificação", "Ativo", '{"assunto":"Sala Limpa A"}', now, now, company_id),
            )
            db.migrate_subjects()
            db.migrate_subjects()
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM subjects WHERE normalized_name=?", (f"{company_id}:sala limpa a",)), 1)

    def test_normative_base_rejects_missing_or_obsolete_reference(self):
        with temporary_database("norms.db") as db:
            company_id = db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
            norm_id = db.scalar(
                "SELECT id FROM records WHERE company_id=? AND module='normas_tecnicas' ORDER BY id LIMIT 1",
                (company_id,),
            )
            with self.assertRaisesRegex(ValueError, "Base normativa obrigatória"):
                db.validate_normative_base("certificados", {}, company_id)
            payload = {"relacionamentos": [{"record": f"normas_tecnicas:{norm_id}", "type": "Fundamentado em"}]}
            db.validate_normative_base("certificados", payload, company_id)
            db.execute("UPDATE records SET status='Obsoleta' WHERE id=?", (norm_id,))
            with self.assertRaisesRegex(ValueError, "Base normativa obrigatória"):
                db.validate_normative_base("laudos_tecnicos", payload, company_id)

    def test_catalogs_seed_independently_for_each_company(self):
        with temporary_database("companies.db") as db:
            now = utc_now()
            company_two = db.execute(
                "INSERT INTO companies(name,created_at,updated_at) VALUES(?,?,?)",
                ("Empresa B", now, now),
            ).lastrowid
            db.seed_sources(company_two)
            db.seed_norms(company_two)
            db.seed_seccol_portfolio(company_two)
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM records WHERE company_id=? AND module='fontes'", (company_two,)),
                len(SOURCE_CATALOG))
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM records WHERE company_id=? AND module='normas_tecnicas'", (company_two,)),
                len(NORM_CATALOG))
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM attachments WHERE company_id=? AND category='Ficha de referência normativa'",
                (company_two,)), len(NORM_CATALOG))
            self.assertEqual(db.scalar(
                """SELECT COUNT(*) FROM records WHERE company_id=?
                   AND json_extract(payload,'$.catalogo_seccol')=1""", (company_two,)),
                len(SECCOL_PRODUCT_CATALOG) + len(SECCOL_INSTRUMENT_CATALOG) + len(SECCOL_SERVICE_CATALOG))


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "api.db")
        self.server = SIVSServer(("127.0.0.1", 0), SIVSHandler, self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.cookie = None
        self.csrf = None

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, method, path, body=None, authenticated=True):
        headers = {}
        raw = None
        if body is not None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated and self.cookie:
            headers["Cookie"] = self.cookie
        if authenticated and self.csrf and method != "GET":
            headers["X-CSRF-Token"] = self.csrf
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path, body=raw, headers=headers)
        response = connection.getresponse()
        content = response.read()
        set_cookie = response.getheader("Set-Cookie")
        if set_cookie:
            self.cookie = set_cookie.split(";", 1)[0]
        status = response.status
        connection.close()
        data = json.loads(content.decode("utf-8")) if content else None
        return status, data

    def raw_request(self, method, path, raw=None, authenticated=True, content_type="application/json"):
        headers = {}
        if raw is not None:
            headers["Content-Type"] = content_type
        if authenticated and self.cookie:
            headers["Cookie"] = self.cookie
        if authenticated and self.csrf and method != "GET":
            headers["X-CSRF-Token"] = self.csrf
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        connection.request(method, path, body=raw, headers=headers)
        response = connection.getresponse()
        content = response.read()
        result_headers = {key.lower(): value for key, value in response.getheaders()}
        status = response.status
        connection.close()
        return status, content, result_headers

    def setup_admin(self):
        status, data = self.request("POST", "/api/setup", {
            "company": "SECCOL", "name": "Administrador", "email": "admin@seccol.test",
            "password": "Senha-Segura-123",
        }, authenticated=False)
        self.assertEqual(status, 200, data)
        self.csrf = data["csrfToken"]
        return data

    def test_user_creation_login_and_admin_password_reset(self):
        self.setup_admin()
        admin_cookie, admin_csrf = self.cookie, self.csrf
        status, created = self.request("POST", "/api/users", {
            "name": "Novo Usuário", "email": "novo.usuario@example.test",
            "password": "Senha-Inicial-123", "role": "operator",
        })
        self.assertEqual(status, 201, created)
        self.assertFalse(created["existingAccount"])

        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "novo.usuario@example.test", "password": "Senha-Inicial-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.assertEqual(login["user"]["email"], "novo.usuario@example.test")

        self.cookie, self.csrf = admin_cookie, admin_csrf
        user_id = created["id"]
        status, reset = self.request("POST", f"/api/users/{user_id}/password", {
            "password": "Senha-Redefinida-456",
        })
        self.assertEqual(status, 200, reset)
        self.cookie = None
        self.csrf = None
        status, old_login = self.request("POST", "/api/login", {
            "email": "novo.usuario@example.test", "password": "Senha-Inicial-123",
        }, authenticated=False)
        self.assertEqual(status, 401, old_login)
        status, new_login = self.request("POST", "/api/login", {
            "email": "novo.usuario@example.test", "password": "Senha-Redefinida-456",
        }, authenticated=False)
        self.assertEqual(status, 200, new_login)

    def test_end_to_end_multi_company_norms_and_xml_security(self):
        status, public_status = self.request("GET", "/api/status", authenticated=False)
        self.assertEqual(status, 200)
        self.assertEqual(public_status["version"], "2.2.0")
        self.setup_admin()

        status, modules = self.request("GET", "/api/modules")
        self.assertEqual(status, 200)
        self.assertIn("normas_tecnicas", modules["modules"])
        self.assertIn("instrumentos_seccol", modules["modules"])
        status, dashboard = self.request("GET", "/api/dashboard")
        self.assertEqual(status, 200)
        self.assertEqual(dashboard["operationalTotal"], 0)
        status, product_catalog = self.request("GET", "/api/records?module=produtos")
        self.assertEqual(status, 200)
        self.assertEqual(len(product_catalog["items"]), len(SECCOL_PRODUCT_CATALOG))

        base_record = {
            "module": "clientes", "title": "Hospital API", "status": "Ativo", "amount": None,
            "due_date": None, "payload": {
                "assunto": "Hospital API", "relacionamentos": [],
                "tipo_pessoa": "Pessoa jurídica", "documento": "04.252.011/0001-10",
                "razao_social": "Hospital API Ltda.",
            },
        }
        status, created = self.request("POST", "/api/records", base_record)
        self.assertEqual(status, 201, created)

        status, search = self.request("GET", "/api/search?q=Hospital%20API")
        self.assertEqual(status, 200, search)
        self.assertTrue(any(item["id"] == created["item"]["id"] for item in search["items"]))
        self.assertTrue(all(set(item) == {"id", "module", "title", "status", "dueDate", "updatedAt"}
                            for item in search["items"]))
        status, technical_search = self.request("GET", "/api/search?q=Contador")
        self.assertEqual(status, 200, technical_search)
        self.assertTrue(any(item["module"] == "instrumentos_seccol"
                            for item in technical_search["items"]))
        self.assertNotIn("fontes", {item["module"] for item in technical_search["items"]})
        status, dashboard = self.request("GET", "/api/dashboard")
        self.assertEqual(status, 200, dashboard)
        self.assertTrue(any(item["recordId"] == created["item"]["id"] for item in dashboard["workItems"]))

        certificate = {
            "module": "certificados", "title": "Certificado sem base", "status": "Rascunho",
            "amount": None, "due_date": None,
            "payload": {
                "assunto": "Certificação API", "relacionamentos": [], "numero": "CERT-001",
                "os": "OS-001", "equipamento": "CSB-001", "data_emissao": "2026-08-15",
                "revisao": "00", "aprovador": "Responsável técnico",
            },
        }
        status, rejected = self.request("POST", "/api/records", certificate)
        self.assertEqual(status, 400, rejected)
        self.assertIn("Base normativa obrigatória", rejected["message"])

        status, relations = self.request("GET", "/api/relations/options")
        self.assertEqual(status, 200)
        norm = next(item for item in relations["items"] if item["module"] == "normas_tecnicas")
        certificate["title"] = "Certificado com base"
        certificate["payload"]["relacionamentos"] = [
            {"record": f"normas_tecnicas:{norm['id']}", "type": "Fundamentado em"},
        ]
        status, accepted = self.request("POST", "/api/records", certificate)
        self.assertEqual(status, 201, accepted)
        self.assertEqual(accepted["item"]["payload"]["relacionamentos"][0]["type"], "Fundamentado em")
        status, norm_in_use = self.request("DELETE", f"/api/records/{norm['id']}")
        self.assertEqual(status, 409, norm_in_use)
        self.assertEqual(norm_in_use["error"], "norm_in_use")

        status, approver = self.request("POST", "/api/users", {
            "name": "Aprovadora", "email": "aprovadora@seccol.test",
            "password": "Senha-Aprovadora-123", "role": "approver",
        })
        self.assertEqual(status, 201, approver)
        status, approval = self.request(
            "POST", f"/api/records/{created['item']['id']}/approval",
            {"approval_type": "Aprovação de teste"},
        )
        self.assertEqual(status, 201, approval)
        status, operator = self.request("POST", "/api/users", {
            "name": "Operador", "email": "operador@seccol.test",
            "password": "Senha-Operador-123", "role": "operator",
        })
        self.assertEqual(status, 201, operator)
        status, operator_login = self.request("POST", "/api/login", {
            "email": "operador@seccol.test", "password": "Senha-Operador-123",
        }, authenticated=False)
        self.assertEqual(status, 200, operator_login)
        self.csrf = operator_login["csrfToken"]
        status, forbidden_decision = self.request(
            "POST", f"/api/approvals/{approval['id']}", {"status": "Aprovado"},
        )
        self.assertEqual(status, 403, forbidden_decision)
        status, admin_login = self.request("POST", "/api/login", {
            "email": "admin@seccol.test", "password": "Senha-Segura-123",
        }, authenticated=False)
        self.assertEqual(status, 200, admin_login)
        self.csrf = admin_login["csrfToken"]

        status, unsafe_xml = self.request("POST", "/api/xml/import", {
            "filename": "unsafe.xml", "xml": '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><NFe>&xxe;</NFe>',
        })
        self.assertEqual(status, 400, unsafe_xml)
        self.assertIn("DTD", unsafe_xml["message"])

        status, company = self.request("POST", "/api/companies", {"name": "SECCOL Filial"})
        self.assertEqual(status, 201, company)
        status, switched = self.request("POST", "/api/company/switch", {"company_id": company["id"]})
        self.assertEqual(status, 200, switched)
        status, empty_clients = self.request("GET", "/api/records?module=clientes")
        self.assertEqual(status, 200)
        self.assertEqual(empty_clients["items"], [])
        status, filial_norms = self.request("GET", "/api/records?module=normas_tecnicas")
        self.assertEqual(status, 200)
        self.assertEqual(len(filial_norms["items"]), len(NORM_CATALOG))
        admin_id = self.db.scalar("SELECT id FROM users WHERE email='admin@seccol.test'")
        self.db.execute(
            "UPDATE company_memberships SET active=0 WHERE company_id=? AND user_id=?",
            (company["id"], admin_id),
        )
        status, expired_membership = self.request("GET", "/api/me")
        self.assertEqual(status, 401, expired_membership)

    def test_setup_is_atomic_under_concurrency(self):
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def configure(index):
            body = json.dumps({
                "company": f"Empresa {index}", "name": f"Admin {index}",
                "email": f"admin{index}@example.test", "password": "Senha-Segura-123",
            }).encode("utf-8")
            barrier.wait()
            connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            connection.request("POST", "/api/setup", body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            response.read()
            with lock:
                results.append(response.status)
            connection.close()

        threads = [threading.Thread(target=configure, args=(index,)) for index in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM users"), 1)
        self.assertEqual(self.db.scalar("SELECT configured FROM setup_state WHERE id=1"), 1)

    def test_read_authorization_validation_and_connection_survival(self):
        self.setup_admin()
        status, user = self.request("POST", "/api/users", {
            "name": "Operador", "email": "operador@example.test",
            "password": "Senha-Operador-123", "role": "operator",
        })
        self.assertEqual(status, 201, user)
        status, login = self.request("POST", "/api/login", {
            "email": "operador@example.test", "password": "Senha-Operador-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, forbidden = self.request("GET", "/api/records?module=normas_tecnicas")
        self.assertEqual(status, 403, forbidden)
        self.assertEqual(forbidden["error"], "forbidden")
        status, search = self.request("GET", "/api/search?q=ISO")
        self.assertEqual(status, 200, search)
        self.assertNotIn("normas_tecnicas", {item["module"] for item in search["items"]})

        status, content, _headers = self.raw_request(
            "POST", "/api/records",
            b'{"module":"clientes","title":"X","amount":Infinity,"payload":{}}',
        )
        self.assertEqual(status, 400, content)
        self.assertIn(b"JSON inv", content)
        status, alive = self.request("GET", "/api/status", authenticated=False)
        self.assertEqual(status, 200, alive)

    def test_optimistic_lock_and_transactional_import(self):
        self.setup_admin()
        record = {
            "module": "clientes", "title": "Hospital Concorrente", "status": "Ativo",
            "amount": None, "due_date": None,
            "payload": {"assunto": "Hospital Concorrente", "relacionamentos": [],
                        "tipo_pessoa": "Pessoa jurídica", "documento": "04.252.011/0001-10",
                        "razao_social": "Hospital Concorrente Ltda."},
        }
        status, created = self.request("POST", "/api/records", record)
        self.assertEqual(status, 201, created)
        record_id = created["item"]["id"]
        record["revision"] = 1
        record["title"] = "Hospital — edição A"
        status, updated = self.request("PUT", f"/api/records/{record_id}", record)
        self.assertEqual(status, 200, updated)
        self.assertEqual(updated["item"]["revision"], 2)
        record["title"] = "Hospital — edição perdida"
        status, conflict = self.request("PUT", f"/api/records/{record_id}", record)
        self.assertEqual(status, 409, conflict)
        self.assertEqual(conflict["error"], "write_conflict")
        self.assertEqual(self.db.scalar("SELECT title FROM records WHERE id=?", (record_id,)),
                         "Hospital — edição A")

        before = self.db.scalar("SELECT COUNT(*) FROM records WHERE company_id=1 AND module='clientes'")
        status, malformed = self.request("POST", "/api/import", {"records": [42]})
        self.assertEqual(status, 400, malformed)
        after = self.db.scalar("SELECT COUNT(*) FROM records WHERE company_id=1 AND module='clientes'")
        self.assertEqual(before, after)
        status, alive = self.request("GET", "/api/me")
        self.assertEqual(status, 200, alive)

    def test_approval_segregation_duplicate_and_revision_expiry(self):
        self.setup_admin()
        status, approver = self.request("POST", "/api/users", {
            "name": "Aprovadora", "email": "approver@example.test",
            "password": "Senha-Aprovadora-123", "role": "approver",
        })
        self.assertEqual(status, 201, approver)
        record = {
            "module": "clientes", "title": "Cliente para aprovação", "status": "Ativo",
            "amount": None, "due_date": None,
            "payload": {"assunto": "Cliente para aprovação", "relacionamentos": [],
                        "tipo_pessoa": "Pessoa jurídica", "documento": "04.252.011/0001-10",
                        "razao_social": "Cliente Aprovação Ltda."},
        }
        status, created = self.request("POST", "/api/records", record)
        self.assertEqual(status, 201, created)
        record_id = created["item"]["id"]
        status, approval = self.request(
            "POST", f"/api/records/{record_id}/approval",
            {"approval_type": "Aprovação cadastral"},
        )
        self.assertEqual(status, 201, approval)
        status, duplicate = self.request(
            "POST", f"/api/records/{record_id}/approval",
            {"approval_type": "Aprovação cadastral"},
        )
        self.assertEqual(status, 409, duplicate)
        self.assertEqual(duplicate["error"], "approval_already_pending")
        status, own_decision = self.request(
            "POST", f"/api/approvals/{approval['id']}", {"status": "Aprovado"},
        )
        self.assertEqual(status, 409, own_decision)
        self.assertEqual(own_decision["error"], "segregation_required")
        record["revision"] = 1
        record["title"] = "Cliente alterado após solicitação"
        status, _updated = self.request("PUT", f"/api/records/{record_id}", record)
        self.assertEqual(status, 200)
        self.assertEqual(self.db.scalar("SELECT status FROM approvals WHERE id=?", (approval["id"],)),
                         "Expirada")

    def test_encrypted_database_backup_is_complete_and_valid(self):
        self.setup_admin()
        passphrase = "Senha-Backup-Muito-Forte-123"
        status, encrypted, headers = self.raw_request(
            "POST", "/api/backup", json.dumps({"passphrase": passphrase}).encode("utf-8")
        )
        self.assertEqual(status, 200, encrypted[:100])
        self.assertEqual(headers.get("x-sivs-format"), "SIVS-BACKUP-2")
        self.assertTrue(encrypted.startswith(b"SIVSBKP2"))
        self.assertEqual(headers.get("x-content-sha256"), __import__("hashlib").sha256(encrypted).hexdigest())

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        iterations = int.from_bytes(encrypted[8:12], "big")
        salt, nonce = encrypted[12:28], encrypted[28:40]
        header = encrypted[:40]
        key = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations
        ).derive(passphrase.encode("utf-8"))
        plaintext = AESGCM(key).decrypt(nonce, encrypted[40:], header)
        backup_path = Path(self.temp.name) / "restored-check.sqlite3"
        backup_path.write_bytes(plaintext)
        restored = sqlite3.connect(backup_path)
        try:
            self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(restored.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertGreater(restored.execute("SELECT COUNT(*) FROM attachments").fetchone()[0], 0)
            self.assertGreater(restored.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0], 0)
        finally:
            restored.close()

    def test_tender_job_reports_real_persisted_progress(self):
        self.setup_admin()
        original = SIVSHandler.execute_tender_search

        def fake_search(handler, session, data, progress=None):
            progress = progress or (lambda *_args: None)
            progress(35, "Fonte de teste consultada")
            time.sleep(0.05)
            progress(90, "Resultados de teste consolidados")
            return {"ok": True, "found": 2, "new": 1, "errors": [],
                    "pagesChecked": 1, "pagesPlanned": 1,
                    "sourceStatus": {"pncp": "concluído", "comprasgov": "não acionado"},
                    "message": "Pesquisa de teste concluída."}

        SIVSHandler.execute_tender_search = fake_search
        try:
            status, queued = self.request("POST", "/api/tenders/search", {
                "keywords": ["filtro HEPA"], "days": 7,
            })
            self.assertEqual(status, 202, queued)
            for _attempt in range(40):
                status, job = self.request("GET", f"/api/tenders/jobs/{queued['jobId']}")
                self.assertEqual(status, 200, job)
                if job["job"]["status"] == "completed":
                    break
                time.sleep(0.025)
            self.assertEqual(job["job"]["status"], "completed")
            self.assertEqual(job["job"]["progress"], 100)
            self.assertEqual(job["job"]["result"]["new"], 1)
        finally:
            SIVSHandler.execute_tender_search = original

    def test_tender_source_catalog_follows_tender_read_permission(self):
        self.setup_admin()
        self.db.execute(
            "UPDATE company_memberships SET permissions=? WHERE company_id=1 AND user_id=1",
            (json.dumps({"deny_read": ["fontes"]}),),
        )
        status, blocked = self.request("GET", "/api/records?module=fontes")
        self.assertEqual(status, 403, blocked)
        status, catalog = self.request("GET", "/api/tenders/sources")
        self.assertEqual(status, 200, catalog)
        self.assertGreater(len(catalog["items"]), 0)

    def test_tender_text_search_finds_official_result_outside_chronological_pages(self):
        self.setup_admin()
        requested_urls = []

        def fake_fetch(url, timeout=14, attempts=4):
            requested_urls.append(url)
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("q", [""])[0]
            if "cabine de segurança biológica" not in query:
                return {"items": [], "total": 0}
            return {"items": [{
                "numero_controle_pncp": "15126437000305-1-003219/2026",
                "description": "Serviços especializados de certificação de cabine de segurança biológica",
                "orgao_nome": "Órgão de teste",
                "uf": "PA",
                "municipio_nome": "Belém",
                "modalidade_licitacao_nome": "Pregão eletrônico",
                "data_publicacao_pncp": utc_now(),
                "data_fim_vigencia": "2026-08-30T18:00:00",
                "item_url": "/compras/15126437000305/2026/3219",
                "cancelado": False,
            }], "total": 1}

        runner = object.__new__(SIVSHandler)
        runner.server = self.server
        with patch.object(SIVSHandler, "fetch_tender_json", side_effect=fake_fetch):
            with patch("server.time.sleep"):
                result = runner.execute_tender_search(
                    {"id": 1, "company_id": 1},
                    {"keywords": ["cabine de segurança biológica", "filtro HEPA"], "days": 7},
                )

        self.assertEqual(result["found"], 1)
        self.assertEqual(result["new"], 1)
        self.assertEqual(len(requested_urls), 2)
        self.assertTrue(all("/api/search/" in url for url in requested_urls))
        stored = self.db.connection().execute(
            "SELECT * FROM tender_results WHERE external_id=?",
            ("15126437000305-1-003219/2026",),
        ).fetchone()
        self.assertIsNotNone(stored)
        self.assertEqual(stored["company_id"], 1)
        self.assertIn("cabine de segurança biológica", json.loads(stored["matched_terms"]))
        self.assertEqual(stored["source_url"], "https://pncp.gov.br/app/compras/15126437000305/2026/3219")

    def test_tender_search_rejects_generic_result_without_portfolio_evidence(self):
        self.setup_admin()

        def fake_fetch(url, timeout=14, attempts=4):
            return {"items": [{
                "numero_controle_pncp": "00000000000000-1-000001/2026",
                "description": "Manutenção predial, pintura e conservação de calçadas",
                "orgao_nome": "Órgão sem aderência técnica",
                "uf": "PA", "municipio_nome": "Belém",
                "modalidade_licitacao_nome": "Pregão eletrônico",
                "data_publicacao_pncp": utc_now(), "data_fim_vigencia": "2026-08-30T18:00:00",
                "item_url": "/compras/00000000000000/2026/1", "cancelado": False,
            }], "total": 1}

        runner = object.__new__(SIVSHandler)
        runner.server = self.server
        with patch.object(SIVSHandler, "fetch_tender_json", side_effect=fake_fetch):
            with patch("server.time.sleep"):
                result = runner.execute_tender_search(
                    {"id": 1, "company_id": 1},
                    {"keywords": ["manutenção de equipamentos"], "days": 7},
                )

        self.assertEqual(result["found"], 0)
        self.assertEqual(result["new"], 0)
        stored = self.db.connection().execute(
            "SELECT id FROM tender_results WHERE external_id='00000000000000-1-000001/2026'"
        ).fetchone()
        self.assertIsNone(stored)

    def test_tender_official_request_retries_rate_limit(self):
        headers = Message()
        headers["Retry-After"] = "0"
        limited = urllib.error.HTTPError(
            "https://pncp.example/api", 429, "Too Many Requests", headers, None
        )

        class Response(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        response = Response(b'{"data": [{"numeroControlePNCP": "teste"}]}')
        with patch("server.urllib.request.urlopen", side_effect=[limited, response]) as urlopen:
            with patch("server.time.sleep") as sleep:
                payload = SIVSHandler.fetch_tender_json("https://pncp.example/api")
        self.assertEqual(payload["data"][0]["numeroControlePNCP"], "teste")
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(0.5)

    def test_internal_assistant_filters_context_and_audits_query(self):
        self.setup_admin()
        now = utc_now()
        self.db.execute(
            """INSERT INTO records
               (module,title,status,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES(?,?,?,?,?,?,?,?,?,1)""",
            ("propostas", "Proposta Hospital Seguro", "Enviada", "2026-08-20",
             json.dumps({"cliente": "Hospital Seguro", "validade": "2026-08-20", "etapa": "Enviada"}),
             1, now, now, 1),
        )
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            status, result = self.request("POST", "/api/assistant/query", {
                "question": "Quais propostas vencem nesta semana?"
            })
        self.assertEqual(status, 200, result)
        self.assertEqual(result["intent"], "proposal_deadline")
        self.assertFalse(result["aiEnabled"])
        self.assertEqual(len(result["sources"]), 1)
        audit = self.db.connection().execute(
            "SELECT action,entity_type,detail FROM audit_log WHERE action='assistant_query' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(audit)
        self.assertEqual(audit["entity_type"], "assistant")

    def test_unified_customer_supplier_registration_requires_role_code(self):
        self.setup_admin()
        status, missing = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Parceiro sem classificação",
            "status": "Ativo", "payload": {"tipo_pessoa": "Pessoa jurídica"},
        })
        self.assertEqual(status, 400)
        self.assertIn("Cliente, Fornecedor ou Cliente e fornecedor", missing["message"])
        status, created = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Fornecedor unificado",
            "status": "Ativo", "payload": {"assunto": "Fornecedor parceiro", "tipo_cadastro": "F", "tipo_pessoa": "Pessoa jurídica", "documento": "12345678000195", "razao_social": "Fornecedor Parceiro", "avaliacao": "Pendente"},
        })
        self.assertEqual(status, 201, created)
        self.assertEqual(created["item"]["module"], "fornecedores")
        self.assertEqual(created["item"]["payload"]["codigo_cadastro"], "F-0001")
        status, unified = self.request("GET", "/api/records?module=clientes_fornecedores")
        self.assertEqual(status, 200)
        self.assertTrue(any(item["id"] == created["item"]["id"] for item in unified["items"]))

    def test_unified_supplier_registration_defaults_pending_evaluation(self):
        self.setup_admin()
        status, created = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Fornecedor sem avaliação inicial",
            "status": "Ativo", "payload": {
                "assunto": "Fornecedor parceiro", "tipo_cadastro": "F",
                "tipo_pessoa": "Pessoa jurídica", "documento": "12345678000195",
                "razao_social": "Fornecedor Parceiro",
            },
        })
        self.assertEqual(status, 201, created)
        self.assertEqual(created["item"]["module"], "fornecedores")
        self.assertEqual(created["item"]["payload"]["avaliacao"], "Pendente")

    def test_unified_both_legacy_short_role_is_accepted(self):
        self.setup_admin()
        status, created = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Parceiro ambos",
            "status": "Ativo", "payload": {
                "assunto": "Cliente e fornecedor", "tipo_cadastro": "C e F",
                "tipo_pessoa": "Pessoa jurídica", "documento": "12345678000195",
                "razao_social": "Parceiro Ambos",
            },
        })
        self.assertEqual(status, 201, created)
        self.assertEqual(created["item"]["module"], "clientes")
        self.assertEqual(created["item"]["payload"]["tipo_cadastro"], "A")

    def test_technical_report_preview_and_controlled_issue(self):
        self.setup_admin()
        admin_cookie, admin_csrf = self.cookie, self.csrf
        status, approver = self.request("POST", "/api/users", {
            "name": "Responsável aprovador", "email": "rt@example.test",
            "password": "Senha-Responsavel-123", "role": "approver",
        })
        self.assertEqual(status, 201, approver)
        public_norm = self.db.connection().execute(
            """SELECT id FROM records WHERE company_id=1 AND module='normas_tecnicas'
               AND json_extract(payload,'$.licenciamento') NOT LIKE 'Comercial%' ORDER BY id LIMIT 1"""
        ).fetchone()
        self.assertIsNotNone(public_norm)
        report = {
            "module": "laudos_tecnicos", "title": "Laudo de sala limpa", "status": "Rascunho",
            "amount": None, "due_date": "2026-08-31",
            "payload": {
                "assunto": "Certificação sala limpa", "numero": "LT-2026-001", "os": "OS-001",
                "cliente": "Hospital Teste", "local_avaliado": "Sala ISO 7",
                "responsavel_tecnico": "Eng. Responsável", "data_emissao": "2026-08-15",
                "metodo": "Método controlado conforme procedimento vigente",
                "regra_decisao": "Conforme quando todos os limites aplicáveis forem atendidos",
                "conclusao": "Os resultados registrados atendem aos critérios informados.",
                "relacionamentos": [{"record": f"normas_tecnicas:{public_norm['id']}",
                                      "type": "Fundamentado em"}],
            },
        }
        status, created = self.request("POST", "/api/records", report)
        self.assertEqual(status, 201, created)
        report_id = created["item"]["id"]
        status, preview, headers = self.raw_request("GET", f"/api/reports/{report_id}/preview")
        self.assertEqual(status, 200, preview[:100])
        self.assertTrue(preview.startswith(b"%PDF-"))
        self.assertEqual(headers.get("content-type"), "application/pdf")

        status, approval = self.request(
            "POST", f"/api/records/{report_id}/approval", {"approval_type": "Emissão técnica"}
        )
        self.assertEqual(status, 201, approval)
        status, login = self.request("POST", "/api/login", {
            "email": "rt@example.test", "password": "Senha-Responsavel-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, decided = self.request(
            "POST", f"/api/approvals/{approval['id']}", {"status": "Aprovado"}
        )
        self.assertEqual(status, 200, decided)
        self.cookie, self.csrf = admin_cookie, admin_csrf
        status, issued = self.request("POST", f"/api/reports/{report_id}/issue", {})
        self.assertEqual(status, 201, issued)
        self.assertEqual(len(issued["sha256"]), 64)
        self.assertEqual(self.db.scalar("SELECT status FROM records WHERE id=?", (report_id,)), "Emitido")
        status, final_pdf, _headers = self.raw_request(
            "GET", f"/api/attachments/{issued['attachmentId']}"
        )
        self.assertEqual(status, 200)
        self.assertTrue(final_pdf.startswith(b"%PDF-"))

    def test_missing_static_asset_returns_404(self):
        status, content, _headers = self.raw_request(
            "GET", "/arquivo-que-nao-existe.js", authenticated=False
        )
        self.assertEqual(status, 404, content)

    def test_frontend_assets_are_never_served_with_stale_cache(self):
        for path in ("/app.js", "/theme/components.css", "/service-worker.js"):
            status, content, headers = self.raw_request("GET", path, authenticated=False)
            self.assertEqual(status, 200, content[:100])
            self.assertIn("no-store", headers.get("cache-control", ""))
            self.assertEqual(headers.get("pragma"), "no-cache")


if __name__ == "__main__":
    unittest.main()
