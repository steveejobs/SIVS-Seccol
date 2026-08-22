import http.client
import base64
import contextlib
import hashlib
import hmac
import io
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import zipfile
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import (
    Database,
    DEFAULT_OPENROUTER_TENDER_MODEL,
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
    create_prestart_database_backup,
    mountinfo_has_path,
    password_hash,
    password_verify,
    require_persistent_database,
    validate_persistent_database_state,
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
    def test_docker_runtime_keeps_secrets_out_of_build_and_drops_privileges(self):
        root = Path(__file__).resolve().parents[2]
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        entrypoint = (root / "docker-entrypoint.sh").read_text(encoding="utf-8")
        self.assertNotIn("OPENROUTER_API_KEY", dockerfile)
        self.assertIn('ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]', dockerfile)
        self.assertIn("apt-get install --no-install-recommends -y gosu", dockerfile)
        self.assertIn("chown -R sivs:sivs /data", entrypoint)
        self.assertIn('exec gosu sivs "$@"', entrypoint)

    def test_tender_ai_uses_cost_conscious_default_model(self):
        self.assertEqual(DEFAULT_OPENROUTER_TENDER_MODEL, "openai/gpt-5-mini")

    def test_tender_ai_quality_gate_rejects_missing_citations(self):
        analysis = {
            "resumo": "Resumo", "recomendacao": "Revisar", "minuta_esclarecimento": "",
            "minuta_impugnacao": "", "prazos": [], "habilitacao": [],
            "requisitos_tecnicos": [], "obrigacoes_contratadas": [], "criterios_julgamento": [],
            "riscos_pendencias": [], "citacoes": [],
            "participacao": {"situacao": "nao_verificada", "itens": [], "justificativa": "Sem dados"},
        }
        self.assertEqual(SIVSHandler.tender_analysis_quality_errors(analysis), [])
        self.assertIn(
            "nenhuma citação verificável",
            SIVSHandler.tender_analysis_quality_errors(analysis, require_citation=True),
        )

    def test_tender_ai_falls_back_when_compact_model_output_is_incomplete(self):
        incomplete = {
            "resumo": "Resumo", "recomendacao": "Revisar", "minuta_esclarecimento": "",
            "minuta_impugnacao": "", "prazos": [], "habilitacao": [],
            "requisitos_tecnicos": [], "obrigacoes_contratadas": [], "criterios_julgamento": [],
            "riscos_pendencias": [], "citacoes": [],
            "participacao": {"situacao": "nao_verificada", "itens": [], "justificativa": "Sem dados"},
        }
        complete = dict(incomplete, citacoes=[{
            "documento": "edital.pdf", "pagina": 1, "achado": "Entrega em 30 dias",
        }])
        responses = [
            io.StringIO(json.dumps({"model": "openai/gpt-5-mini", "choices": [{
                "message": {"content": json.dumps(incomplete)}
            }]})),
            io.StringIO(json.dumps({"model": "openai/gpt-5.4-mini", "choices": [{
                "message": {"content": json.dumps(complete)}
            }]})),
        ]
        handler = SIVSHandler.__new__(SIVSHandler)
        environment = {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_TENDER_MODEL": "openai/gpt-5-mini",
            "OPENROUTER_TENDER_FALLBACK_MODEL": "openai/gpt-5.4-mini",
        }
        with patch.dict(os.environ, environment, clear=False), patch(
            "server.urllib.request.urlopen", side_effect=responses,
        ) as urlopen:
            analysis, model = handler.openrouter_tender_analysis(
                {"title": "Edital"}, [{"document": "edital.pdf", "page": 1, "text": "Entrega em 30 dias"}],
            )
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(model, "openai/gpt-5.4-mini")
        self.assertEqual(analysis["citacoes"][0]["pagina"], 1)

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

    def test_production_refuses_missing_or_unconfigured_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sivs.db"
            with patch.dict("os.environ", {}, clear=False):
                os.environ.pop("SIVS_ALLOW_EMPTY_DB_INITIALIZATION", None)
                with self.assertRaisesRegex(RuntimeError, "ausente ou vazio"):
                    validate_persistent_database_state(path)
                database = Database(path)
                database.close_thread_connection()
                with self.assertRaisesRegex(RuntimeError, "sem configuracao administrativa"):
                    validate_persistent_database_state(path)

    def test_empty_database_bootstrap_requires_explicit_temporary_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sivs.db"
            with patch.dict(
                "os.environ", {"SIVS_ALLOW_EMPTY_DB_INITIALIZATION": "1"}
            ):
                state = validate_persistent_database_state(path)
            self.assertTrue(state["bootstrap"])
            self.assertEqual(state["users"], 0)

    def test_configured_database_gets_integral_prestart_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sivs.db"
            database = Database(path)
            now = utc_now()
            database.execute(
                "INSERT INTO users(name,email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                ("Admin", "guard@example.com", password_hash("Senha-Forte-123"), "admin", now, now),
            )
            database.execute(
                "UPDATE setup_state SET configured=1,configured_at=? WHERE id=1", (now,)
            )
            database.close_thread_connection()

            state = validate_persistent_database_state(path)
            snapshot = create_prestart_database_backup(path, retention=2)

            self.assertFalse(state["bootstrap"])
            self.assertEqual(state["users"], 1)
            self.assertTrue(snapshot.exists())
            copy = sqlite3.connect(snapshot)
            try:
                self.assertEqual(copy.execute("PRAGMA quick_check").fetchone()[0], "ok")
                self.assertEqual(copy.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            finally:
                copy.close()

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

    def test_tender_keywords_are_deduplicated_and_spreadsheet_headers_are_detected(self):
        self.assertEqual(
            SIVSHandler.normalize_tender_keywords("Filtro HEPA, filtro hepa; ISO 14644\nPAO"),
            ["Filtro HEPA", "ISO 14644", "PAO"],
        )
        csv_content = (
            "categoria;palavra_chave;ativa\n"
            "Filtros;filtro HEPA;sim\n"
            "Filtros;FILTRO hepa;sim\n"
            "Áreas;qualificação de sala limpa;não\n"
            "Ensaios;teste PAO;sim\n"
        ).encode("utf-8")
        parsed = SIVSHandler.tender_spreadsheet_keywords("termos.csv", csv_content)
        self.assertEqual(parsed["keywords"], ["filtro HEPA", "teste PAO"])
        self.assertEqual(parsed["duplicates"], 1)
        self.assertEqual(parsed["ignored"], 1)
        self.assertTrue(parsed["headerDetected"])
        self.assertEqual(parsed["entries"][0]["category"], "Filtros")

    def test_tender_xlsx_import_reads_active_keyword_column(self):
        requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")
        self.assertRegex(requirements, r"(?m)^defusedxml>=0\.7,<1$")
        from openpyxl import Workbook
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Vocabulário"
        sheet.append(["Palavra-chave", "Categoria", "Ativa"])
        sheet.append(["cabine de segurança biológica", "Cabines", "sim"])
        sheet.append(["manutenção predial", "Genérico", "não"])
        stream = io.BytesIO()
        workbook.save(stream)
        parsed = SIVSHandler.tender_spreadsheet_keywords("vocabulário.xlsx", stream.getvalue())
        self.assertEqual(parsed["sheet"], "Vocabulário")
        self.assertEqual(parsed["keywords"], ["cabine de segurança biológica"])

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

    def test_erp_hierarchy_inventory_and_fiscal_schema_are_migrated_idempotently(self):
        with temporary_database("erp-foundation.db") as db:
            company_id = db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
            branch = db.connection().execute(
                "SELECT * FROM branches WHERE company_id=? AND is_headquarters=1", (company_id,)
            ).fetchone()
            warehouse = db.connection().execute(
                "SELECT * FROM warehouses WHERE company_id=?", (company_id,)
            ).fetchone()
            self.assertIsNotNone(db.scalar("SELECT holding_id FROM companies WHERE id=?", (company_id,)))
            self.assertIsNotNone(branch)
            self.assertEqual(warehouse["branch_id"], branch["id"])
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=223"),
                "erp-multicompany-inventory-fiscal-foundation",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=224"),
                "commercial-service-purchase-document-items",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=225"),
                "tender-keywords-and-quality-feedback",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=226"),
                "functional-access-costed-inventory-controllership",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=227"),
                "sefaz-readiness-a1-vault-accounting-export",
            )
            balance_columns = {
                row["name"] for row in db.connection().execute(
                    "PRAGMA table_info(inventory_balances)"
                )
            }
            movement_columns = {
                row["name"] for row in db.connection().execute(
                    "PRAGMA table_info(inventory_movements)"
                )
            }
            self.assertIn("inventory_value_cents", balance_columns)
            self.assertTrue({
                "unit_cost_cents", "value_delta_cents", "balance_value_cents",
            }.issubset(movement_columns))
            for table in (
                "inventory_balances", "inventory_movements", "inventory_reservations",
                "fiscal_schema_versions", "fiscal_operations", "tax_profiles", "tax_rules",
                "company_fiscal_profiles", "product_fiscal_profiles", "fiscal_documents",
                "fiscal_document_items", "fiscal_certificates", "xml_documents",
                "document_items", "sefaz_configurations", "accounting_exports",
            ):
                self.assertEqual(db.scalar(f"SELECT COUNT(*) FROM {table}"), 0)
            db.ensure_company_structure(company_id, "SECCOL")
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM branches WHERE company_id=?", (company_id,)
            ), 1)
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM warehouses WHERE company_id=?", (company_id,)
            ), 1)

    def test_sefaz_status_transport_uses_official_nfe_400_contract(self):
        captured = {}
        response_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
          <soap:Body><nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4">
            <retConsStatServ xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
              <tpAmb>2</tpAmb><verAplic>GO_NFE_4.00</verAplic><cStat>107</cStat>
              <xMotivo>Servico em Operacao</xMotivo><cUF>52</cUF>
              <dhRecbto>2026-08-18T12:00:00-03:00</dhRecbto><tMed>1</tMed>
            </retConsStatServ>
          </nfeResultMsg></soap:Body>
        </soap:Envelope>"""

        class Response:
            status = 200
            def read(self, _limit):
                return response_xml

        class Connection:
            def __init__(self, host, port, context, timeout):
                captured.update(host=host, port=port, context=context, timeout=timeout)
            def request(self, method, path, body, headers):
                captured.update(method=method, path=path, body=body, headers=headers)
            def getresponse(self):
                return Response()
            def close(self):
                captured["closed"] = True

        with patch("server.http.client.HTTPSConnection", Connection):
            result = SIVSHandler.sefaz_status_transport(
                "https://homolog.sefaz.go.gov.br/nfe/services/NFeStatusServico4",
                object(), "52", "HOMOLOGATION",
            )
        self.assertEqual(result["cStat"], "107")
        self.assertEqual(result["xMotivo"], "Servico em Operacao")
        self.assertEqual(captured["host"], "homolog.sefaz.go.gov.br")
        self.assertEqual(captured["method"], "POST")
        self.assertIn(b'consStatServ', captured["body"])
        self.assertIn(b'<ns2:tpAmb>2</ns2:tpAmb>', captured["body"])
        self.assertIn(b'<ns2:cUF>52</ns2:cUF>', captured["body"])
        self.assertIn("application/soap+xml", captured["headers"]["Content-Type"])
        self.assertTrue(captured["closed"])


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

    def raw_request(self, method, path, raw=None, authenticated=True, content_type="application/json", extra_headers=None):
        headers = {}
        if raw is not None:
            headers["Content-Type"] = content_type
        headers.update(extra_headers or {})
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

    def test_signed_website_lead_enters_crm_once_and_notifies_the_company(self):
        self.setup_admin()
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        secret = "website-leads-test-secret-with-more-than-32-characters"
        event = {
            "version": "1.0",
            "event": "lead.created",
            "id": "3f1dc3a1-0ea8-4c7f-9870-8cc420160730",
            "occurredAt": "2026-08-21T15:30:00.000Z",
            "source": {
                "page": "https://seccol.com.br/contato",
                "referrer": "https://www.google.com/",
                "utm": {"source": "google", "campaign": "areas-limpas"},
            },
            "lead": {
                "name": "Maria Souza",
                "company": "Hospital Exemplo",
                "phone": "+55 62 99999-0000",
                "email": "maria@hospital.example",
                "location": "Goiânia, GO",
                "need": "Certificação de área limpa",
                "details": "Precisamos avaliar uma área limpa antes da próxima inspeção.",
                "consent": True,
            },
        }
        raw = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = "sha256=" + hmac.new(
            secret.encode("utf-8"), timestamp.encode("ascii") + b"." + raw,
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "X-Seccol-Timestamp": timestamp,
            "X-Seccol-Signature": signature,
        }
        environment = {
            "SIVS_WEBSITE_LEADS_SECRET": secret,
            "SIVS_WEBSITE_LEADS_COMPANY_ID": str(company_id),
        }
        with patch.dict(os.environ, environment, clear=False):
            status, content, _headers = self.raw_request(
                "POST", "/api/integrations/website/leads", raw,
                authenticated=False, extra_headers=headers,
            )
            created = json.loads(content.decode("utf-8"))
            self.assertEqual(status, 201, created)
            self.assertEqual(created["protocol"], "SITE-3F1DC3A10E")
            self.assertFalse(created["duplicate"])

            status, content, _headers = self.raw_request(
                "POST", "/api/integrations/website/leads", raw,
                authenticated=False, extra_headers=headers,
            )
            duplicate = json.loads(content.decode("utf-8"))
            self.assertEqual(status, 200, duplicate)
            self.assertTrue(duplicate["duplicate"])

            tampered = raw.replace(b"Hospital Exemplo", b"Hospital Alterado")
            status, content, _headers = self.raw_request(
                "POST", "/api/integrations/website/leads", tampered,
                authenticated=False, extra_headers=headers,
            )
            rejected = json.loads(content.decode("utf-8"))
            self.assertEqual(status, 401, rejected)
            self.assertEqual(rejected["error"], "invalid_signature")

        rows = self.db.connection().execute(
            "SELECT * FROM records WHERE company_id=? AND module='crm'", (company_id,)
        ).fetchall()
        self.assertEqual(len(rows), 1)
        lead = json.loads(rows[0]["payload"])
        self.assertEqual(rows[0]["status"], "Novo lead")
        self.assertEqual(lead["origem"], "Site institucional")
        self.assertEqual(lead["telefone"], "+55 62 99999-0000")
        self.assertEqual(lead["email"], "maria@hospital.example")
        self.assertEqual(lead["localizacao"], "Goiânia, GO")
        self.assertEqual(
            self.db.scalar("SELECT COUNT(*) FROM website_lead_receipts WHERE company_id=?", (company_id,)),
            1,
        )
        self.assertEqual(
            self.db.scalar("SELECT COUNT(*) FROM notifications WHERE company_id=? AND record_id=?", (company_id, rows[0]["id"])),
            1,
        )
        self.db.execute("DELETE FROM records WHERE id=?", (rows[0]["id"],))
        self.assertIsNone(self.db.scalar(
            "SELECT record_id FROM website_lead_receipts WHERE company_id=?", (company_id,)
        ))
        with patch.dict(os.environ, environment, clear=False):
            status, content, _headers = self.raw_request(
                "POST", "/api/integrations/website/leads", raw,
                authenticated=False, extra_headers=headers,
            )
        deleted_duplicate = json.loads(content.decode("utf-8"))
        self.assertEqual(status, 200, deleted_duplicate)
        self.assertTrue(deleted_duplicate["duplicate"])
        self.assertIsNone(deleted_duplicate["leadId"])

    def test_control_center_tracks_sessions_changes_errors_and_remote_termination(self):
        self.setup_admin()
        admin_cookie, admin_csrf = self.cookie, self.csrf
        status, created = self.request("POST", "/api/users", {
            "name": "Operador monitorado", "email": "monitorado@seccol.test",
            "password": "Senha-Monitorada-123", "role": "operator",
        })
        self.assertEqual(status, 201, created)

        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "monitorado@seccol.test", "password": "Senha-Monitorada-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        operator_cookie, operator_csrf = self.cookie, login["csrfToken"]
        self.csrf = operator_csrf
        status, reported = self.request("POST", "/api/telemetry/client-error", {
            "message": "Falha visual controlada", "source": "/app.js",
            "line": 42, "column": 7, "stack": "Error: teste", "page": "/?screen=dashboard",
        })
        self.assertEqual(status, 202, reported)

        self.cookie, self.csrf = admin_cookie, admin_csrf
        status, center = self.request("GET", "/api/control-center")
        self.assertEqual(status, 200, center)
        self.assertEqual(center["summary"]["activeUsers"], 2)
        self.assertGreaterEqual(center["summary"]["activeSessions"], 2)
        self.assertTrue(center["health"]["schedulerRunning"])
        self.assertGreater(center["requests"]["sinceStart"], 0)
        self.assertTrue(any(item["action"] == "create" for item in center["changes"]))
        error = next(item for item in center["events"] if item["message"] == "Falha visual controlada")
        monitored = next(item for item in center["sessions"] if item["email"] == "monitorado@seccol.test")
        self.assertNotIn("token_hash", monitored)
        self.assertFalse(monitored["current"])

        status, ended = self.request("DELETE", f"/api/control-center/sessions/{monitored['id']}", {})
        self.assertEqual(status, 200, ended)
        status, resolved = self.request(
            "POST", f"/api/control-center/events/{error['id']}/resolve", {},
        )
        self.assertEqual(status, 200, resolved)
        self.assertEqual(
            self.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action='terminate'"), 1,
        )
        self.assertIsNotNone(self.db.scalar(
            "SELECT resolved_at FROM system_events WHERE id=?", (error["id"],),
        ))

        self.cookie, self.csrf = operator_cookie, operator_csrf
        status, rejected = self.request("GET", "/api/me")
        self.assertEqual(status, 401, rejected)

        self.cookie, self.csrf = admin_cookie, admin_csrf
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        admin_id = self.db.scalar("SELECT id FROM users WHERE email='admin@seccol.test'")
        self.db.execute(
            "UPDATE company_memberships SET role='manager' WHERE company_id=? AND user_id=?",
            (company_id, admin_id),
        )
        status, forbidden = self.request("GET", "/api/control-center")
        self.assertEqual(status, 403, forbidden)

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

    def test_self_service_password_recovery_is_generic_one_time_and_revokes_sessions(self):
        self.setup_admin()
        captured = []

        def capture_mail(recipient, name, token):
            captured.append((recipient, name, token))

        with patch("server.send_password_reset_email", side_effect=capture_mail):
            status, requested = self.request(
                "POST", "/api/password/forgot",
                {"email": "admin@seccol.test"}, authenticated=False,
            )
            self.assertEqual(status, 202, requested)
            deadline = time.time() + 2
            while not captured and time.time() < deadline:
                time.sleep(0.01)

        self.assertEqual(captured[0][0], "admin@seccol.test")
        token = captured[0][2]
        self.cookie = None
        self.csrf = None
        status, reset = self.request(
            "POST", "/api/password/reset",
            {"token": token, "password": "Nova-Senha-Segura-456"},
            authenticated=False,
        )
        self.assertEqual(status, 200, reset)

        status, reused = self.request(
            "POST", "/api/password/reset",
            {"token": token, "password": "Outra-Senha-Segura-789"},
            authenticated=False,
        )
        self.assertEqual(status, 400, reused)
        self.assertEqual(reused["error"], "invalid_token")
        status, old_login = self.request(
            "POST", "/api/login",
            {"email": "admin@seccol.test", "password": "Senha-Segura-123"},
            authenticated=False,
        )
        self.assertEqual(status, 401, old_login)
        status, new_login = self.request(
            "POST", "/api/login",
            {"email": "admin@seccol.test", "password": "Nova-Senha-Segura-456"},
            authenticated=False,
        )
        self.assertEqual(status, 200, new_login)

        status, unknown = self.request(
            "POST", "/api/password/forgot",
            {"email": "nao-existe@seccol.test"}, authenticated=False,
        )
        self.assertEqual(status, 202, unknown)
        self.assertEqual(unknown["message"], requested["message"])

    def test_admin_can_define_effective_company_permissions_and_capabilities(self):
        self.setup_admin()
        admin_cookie, admin_csrf = self.cookie, self.csrf
        status, created = self.request("POST", "/api/users", {
            "name": "Operador restrito", "email": "restrito@seccol.test",
            "password": "Senha-Restrita-123", "role": "operator",
        })
        self.assertEqual(status, 201, created)
        user_id = created["id"]

        status, users = self.request("GET", "/api/users")
        self.assertEqual(status, 200, users)
        operator = next(item for item in users["items"] if item["id"] == user_id)
        self.assertIsInstance(operator["permissions"], dict)
        self.assertEqual(
            set(operator["effective_permissions"]), {"read", "write", "export"},
        )
        self.assertEqual(
            set(operator["effective_capabilities"]), {"audit", "trash", "approvals"},
        )

        status, updated = self.request("PUT", f"/api/users/{user_id}", {
            "role": "operator", "active": True,
            "effectivePermissions": {
                "read": ["estoque"], "write": ["estoque"], "export": ["estoque"],
            },
            "effectiveCapabilities": {
                "audit": True, "trash": False, "approvals": False,
            },
        })
        self.assertEqual(status, 200, updated)

        status, invalid = self.request("PUT", f"/api/users/{user_id}", {
            "role": "operator", "active": True,
            "effectivePermissions": {
                "read": ["estoque"], "write": ["estoque"], "export": [],
            },
            "effectiveCapabilities": {"settings": True},
        })
        self.assertEqual(status, 400, invalid)

        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "restrito@seccol.test", "password": "Senha-Restrita-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, inventory = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, inventory)
        status, forbidden = self.request("GET", "/api/records?module=crm")
        self.assertEqual(status, 403, forbidden)
        status, audit = self.request("GET", "/api/audit")
        self.assertEqual(status, 200, audit)
        status, trash = self.request("GET", "/api/trash")
        self.assertEqual(status, 403, trash)

        self.cookie, self.csrf = admin_cookie, admin_csrf
        status, users = self.request("GET", "/api/users")
        self.assertEqual(status, 200, users)
        operator = next(item for item in users["items"] if item["id"] == user_id)
        self.assertEqual(operator["effective_permissions"]["read"], ["estoque"])
        self.assertEqual(operator["effective_permissions"]["write"], ["estoque"])
        self.assertEqual(operator["effective_permissions"]["export"], ["estoque"])
        self.assertEqual(operator["effective_capabilities"], {
            "audit": True, "trash": False, "approvals": False,
        })

    def test_trash_permanent_deletion_is_confirmed_audited_and_company_scoped(self):
        self.setup_admin()

        def create_client(title, document):
            status, result = self.request("POST", "/api/records", {
                "module": "clientes", "title": title, "status": "Ativo",
                "amount": None, "due_date": None,
                "payload": {
                    "assunto": title, "relacionamentos": [],
                    "tipo_pessoa": "Pessoa jurídica", "tipo_cadastro": "Fornecedor (F)",
                    "documento": document, "razao_social": title,
                },
            })
            self.assertEqual(status, 201, result)
            return result["item"]["id"]

        protected_id = create_client("Fornecedor ainda utilizado", "11.222.333/0001-81")
        source_id = create_client("Cadastro ativo dependente", "45.723.174/0001-10")
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        user_id = self.db.scalar("SELECT id FROM users WHERE email='admin@seccol.test'")
        self.db.execute(
            """INSERT INTO record_relationships
               (from_record_id,to_record_id,relationship_type,created_by,created_at)
               VALUES(?,?,?,?,?)""",
            (source_id, protected_id, "Relacionado a", user_id, utc_now()),
        )
        status, deleted = self.request("DELETE", f"/api/records/{protected_id}")
        self.assertEqual(status, 200, deleted)
        status, blocked = self.request(
            "DELETE", f"/api/trash/{protected_id}", {"confirmation": "EXCLUIR"},
        )
        self.assertEqual(status, 409, blocked)
        self.assertEqual(blocked["error"], "record_referenced")
        self.assertIsNotNone(self.db.scalar("SELECT id FROM records WHERE id=?", (protected_id,)))

        disposable_id = create_client("Fornecedor descartável", "04.252.011/0001-10")
        status, deleted = self.request("DELETE", f"/api/records/{disposable_id}")
        self.assertEqual(status, 200, deleted)
        status, rejected = self.request(
            "DELETE", f"/api/trash/{disposable_id}", {"confirmation": "apagar"},
        )
        self.assertEqual(status, 400, rejected)
        self.assertIsNotNone(self.db.scalar("SELECT id FROM records WHERE id=?", (disposable_id,)))
        status, purged = self.request(
            "DELETE", f"/api/trash/{disposable_id}", {"confirmation": "EXCLUIR"},
        )
        self.assertEqual(status, 200, purged)
        self.assertEqual(purged["purged"], 1)
        self.assertIsNone(self.db.scalar("SELECT id FROM records WHERE id=?", (disposable_id,)))
        self.assertEqual(
            self.db.scalar("SELECT COUNT(*) FROM record_versions WHERE record_id=?", (disposable_id,)), 0,
        )

        bulk_id = create_client("Fornecedor para esvaziar", "04.252.011/0001-10")
        status, deleted = self.request("DELETE", f"/api/records/{bulk_id}")
        self.assertEqual(status, 200, deleted)

        other_company = self.db.execute(
            "INSERT INTO companies(name,created_at,updated_at) VALUES(?,?,?)",
            ("Empresa isolada", utc_now(), utc_now()),
        ).lastrowid
        isolated_id = self.db.execute(
            """INSERT INTO records
               (module,title,status,payload,created_by,created_at,updated_at,deleted_at,company_id)
               VALUES('clientes','Excluído de outra empresa','Ativo','{}',?,?,?,?,?)""",
            (user_id, utc_now(), utc_now(), utc_now(), other_company),
        ).lastrowid

        status, result = self.request("DELETE", "/api/trash", {"confirmation": "ESVAZIAR"})
        self.assertEqual(status, 200, result)
        self.assertEqual(result["purged"], 1)
        self.assertEqual(result["blocked"], 1)
        self.assertIsNone(self.db.scalar("SELECT id FROM records WHERE id=?", (bulk_id,)))
        self.assertEqual(
            self.db.scalar("SELECT COUNT(*) FROM record_versions WHERE record_id=?", (bulk_id,)), 0,
        )
        self.assertIsNotNone(self.db.scalar("SELECT id FROM records WHERE id=?", (protected_id,)))
        self.assertIsNotNone(self.db.scalar("SELECT id FROM records WHERE id=?", (isolated_id,)))
        self.assertEqual(
            self.db.scalar(
                "SELECT COUNT(*) FROM audit_log WHERE company_id=? AND action='purge' AND entity_type='trash'",
                (company_id,),
            ),
            2,
        )
        self.assertEqual(self.db.connection().execute("PRAGMA foreign_key_check").fetchall(), [])

        self.db.execute(
            "UPDATE company_memberships SET role='manager' WHERE company_id=? AND user_id=?",
            (company_id, user_id),
        )
        status, forbidden = self.request("DELETE", "/api/trash", {"confirmation": "ESVAZIAR"})
        self.assertEqual(status, 403, forbidden)

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
        status, visible_approvals = self.request("GET", "/api/approvals?status=Pendente")
        self.assertEqual(status, 200, visible_approvals)
        own_item = next(item for item in visible_approvals["items"] if item["id"] == approval["id"])
        self.assertFalse(own_item["can_decide"])
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

    def test_specialized_records_default_to_their_real_initial_status(self):
        self.setup_admin()
        crm = {
            "module": "crm", "title": "Lead sem status explícito",
            "payload": {
                "assunto": "Prospecção", "etapa": "Novo lead", "origem": "Indicação",
                "proximo_passo": "Contato inicial", "probabilidade": "10",
                "relacionamentos": [],
            },
        }
        status, created = self.request("POST", "/api/records", crm)
        self.assertEqual(status, 201, created)
        self.assertEqual(created["item"]["status"], "Novo lead")

        crm["title"] = "Lead com status incompatível"
        crm["status"] = "Ativo"
        status, rejected = self.request("POST", "/api/records", crm)
        self.assertEqual(status, 400, rejected)
        self.assertEqual(rejected["error"], "bad_request")

    def test_record_lists_hydrate_resources_with_bounded_queries(self):
        self.setup_admin()
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        user_id = self.db.scalar("SELECT id FROM users ORDER BY id LIMIT 1")
        now = "2026-08-17T12:00:00+00:00"
        with self.db.transaction(immediate=True):
            for index in range(40):
                self.db.execute(
                    """INSERT INTO records
                       (module,title,status,payload,created_by,created_at,updated_at,company_id)
                       VALUES('crm',?,'Novo lead',?,?,?,?,?)""",
                    (f"Lead lote {index}", json.dumps({"assunto": f"Lead lote {index}"}),
                     user_id, now, now, company_id),
                )
        rows = self.db.connection().execute(
            "SELECT * FROM records WHERE company_id=? AND module='crm' ORDER BY id",
            (company_id,),
        ).fetchall()
        handler = object.__new__(SIVSHandler)
        handler.server = type("SerializerServer", (), {"db": self.db})()
        statements = []
        self.db.connection().set_trace_callback(statements.append)
        try:
            items = handler.records_json(rows)
        finally:
            self.db.connection().set_trace_callback(None)
        selects = [statement for statement in statements
                   if statement.lstrip().upper().startswith("SELECT")]
        self.assertEqual(len(items), 40)
        self.assertLessEqual(len(selects), 4, selects)
        self.assertTrue(all(item["attachments"] == [] for item in items))
        self.assertTrue(all(item["payload"]["relacionamentos"] == [] for item in items))

    def test_xml_import_requires_the_active_company_as_recipient(self):
        self.setup_admin()
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
          <NFe><infNFe Id="NFe11111111111111111111111111111111111111111111">
            <ide><natOp>Compra</natOp><nNF>123</nNF><dhEmi>2026-08-17T10:00:00-03:00</dhEmi></ide>
            <emit><CNPJ>04252011000110</CNPJ><xNome>Fornecedor XML</xNome></emit>
            <dest><CNPJ>11222333000181</CNPJ><xNome>Empresa destinatária</xNome></dest>
            <det nItem="1"><prod><cProd>P-XML-1</cProd><xProd>Produto XML</xProd>
              <NCM>00000000</NCM><CFOP>1102</CFOP><uCom>UN</uCom><qCom>2.0000</qCom>
              <vUnCom>10.00</vUnCom><vProd>20.00</vProd></prod></det>
            <total><ICMSTot><vNF>20.00</vNF></ICMSTot></total>
          </infNFe></NFe>
        </nfeProc>"""
        body = {"filename": "nfe-123.xml", "xml": xml}

        status, missing = self.request("POST", "/api/xml/import", body)
        self.assertEqual(status, 409, missing)
        self.assertEqual(missing["error"], "company_document_required")

        status, _settings = self.request("PUT", "/api/settings", {
            "company": {"name": "SECCOL", "cnpj": "12345678000195"},
        })
        self.assertEqual(status, 200)
        status, mismatch = self.request("POST", "/api/xml/import", body)
        self.assertEqual(status, 409, mismatch)
        self.assertEqual(mismatch["error"], "invoice_recipient_mismatch")

        status, _settings = self.request("PUT", "/api/settings", {
            "company": {"name": "SECCOL", "cnpj": "11222333000181"},
        })
        self.assertEqual(status, 200)
        status, imported = self.request("POST", "/api/xml/import", body)
        self.assertEqual(status, 201, imported)
        self.assertEqual(imported["items"], 1)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM records WHERE module='importacoes_xml'"
        ), 1)

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

    def test_tender_keyword_import_and_measured_precision(self):
        self.setup_admin()
        content = "palavra_chave;categoria;ativa\nfiltro HEPA;Filtros;sim\nteste PAO;Ensaios;sim\n".encode("utf-8")
        status, imported = self.request("POST", "/api/tenders/keywords/import", {
            "filename": "palavras.csv", "content": base64.b64encode(content).decode("ascii"),
        })
        self.assertEqual(status, 200, imported)
        self.assertEqual(imported["keywords"], ["filtro HEPA", "teste PAO"])

        now = utc_now()
        result_ids = []
        for index in range(2):
            result_ids.append(self.db.execute(
                """INSERT INTO tender_results
                   (source_key,external_id,title,object_text,matched_terms,relevance_score,status,
                    raw_json,created_at,updated_at,company_id)
                   VALUES(?,?,?,?,?,80,'Novo','{}',?,?,1)""",
                (f"quality-{index}", f"quality-{index}", "Pregão — teste",
                 "Certificação de cabine com filtro HEPA", '["filtro HEPA"]', now, now),
            ).lastrowid)
        for result_id, feedback in zip(result_ids, ("relevant", "irrelevant")):
            status, response = self.request("PUT", f"/api/tenders/results/{result_id}", {
                "relevanceFeedback": feedback,
            })
            self.assertEqual(status, 200, response)
        status, results = self.request("GET", "/api/tenders/results")
        self.assertEqual(status, 200, results)
        self.assertEqual(results["quality"]["evaluated"], 2)
        self.assertEqual(results["quality"]["precisionPercent"], 50.0)
        self.assertFalse(results["quality"]["minimumSampleReached"])

    def test_tender_pdf_preview_corrects_generic_pncp_mime_type(self):
        self.setup_admin()
        now = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,matched_terms,relevance_score,status,
                raw_json,created_at,updated_at,company_id)
               VALUES('preview','preview-1','Edital','Objeto','[]',80,'Novo','{}',?,?,1)""",
            (now, now),
        ).lastrowid
        self.db.execute(
            """INSERT INTO tender_details
               (tender_result_id,company_id,official_data,items_json,documents_json,
                value_source,analysis_json,refreshed_at)
               VALUES(?,1,'{}','[]',?,'unavailable','{}',?)""",
            (result_id, json.dumps([{"titulo": "edital-sem-extensao"}]), now),
        )
        with patch.object(
            SIVSHandler, "tender_document_bytes",
            return_value=(b"%PDF-1.7\nconteudo", "application/octet-stream"),
        ):
            status, content, headers = self.raw_request(
                "GET", f"/api/tenders/results/{result_id}/documentos/0"
            )
        self.assertEqual(status, 200)
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertEqual(headers["content-type"], "application/pdf")
        self.assertEqual(headers["x-sivs-previewable"], "1")
        self.assertTrue(headers["content-disposition"].startswith("inline;"))

    def test_tender_ai_failure_is_persisted_for_visible_report_state(self):
        self.setup_admin()
        now = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,agency,matched_terms,relevance_score,status,
                raw_json,created_at,updated_at,company_id)
               VALUES('analysis','analysis-1','Edital','Objeto','Órgão','[]',80,'Novo','{}',?,?,1)""",
            (now, now),
        ).lastrowid
        self.db.execute(
            """INSERT INTO tender_details
               (tender_result_id,company_id,official_data,items_json,documents_json,
                value_source,analysis_json,refreshed_at)
               VALUES(?,1,'{}','[]',?,'unavailable','{}',?)""",
            (result_id, json.dumps([{"titulo": "edital.pdf"}]), now),
        )
        page = {"document": "edital.pdf", "page": 1, "text": "Prazo de entrega", "hasImages": False}
        with patch.object(
            SIVSHandler, "tender_document_bytes",
            return_value=(b"%PDF-1.7", "application/pdf"),
        ), patch.object(SIVSHandler, "tender_pdf_text", return_value=[page]), patch.dict(
            os.environ, {"OPENROUTER_API_KEY": ""}, clear=False,
        ):
            status, failed = self.request(
                "POST", f"/api/tenders/results/{result_id}/analyze", {}
            )
        self.assertEqual(status, 502, failed)
        self.assertEqual(failed["error"], "ai_not_configured")
        stored = json.loads(self.db.scalar(
            "SELECT analysis_json FROM tender_details WHERE tender_result_id=?", (result_id,)
        ))
        self.assertEqual(stored["status"], "failed")
        self.assertEqual(stored["pagesRead"], 1)
        self.assertNotIn("OPENROUTER_API_KEY", stored["message"])

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

    def test_tender_pages_markdown_flags_images_instead_of_dropping_them(self):
        pages = [
            {"document": "Edital.pdf", "page": 1, "text": "Objeto: certificacao de cabines.", "hasImages": False},
            {"document": "Edital.pdf", "page": 2, "text": "", "hasImages": True},
            {"document": "Anexo.pdf", "page": 1, "text": "Planilha de precos anexa.", "hasImages": True},
        ]
        markdown = SIVSHandler.tender_pages_markdown(pages)

        self.assertIn("# Edital.pdf", markdown)
        self.assertIn("## Página 1", markdown)
        self.assertIn("Objeto: certificacao de cabines.", markdown)
        self.assertIn("# Anexo.pdf", markdown)
        self.assertIn("Planilha de precos anexa.", markdown)
        image_notes = markdown.count("não convertida para texto")
        self.assertEqual(image_notes, 2)
        self.assertNotIn("[Página sem texto extraível.]", markdown)

    def test_tender_pages_markdown_truncates_at_block_boundary(self):
        pages = [
            {"document": "Edital.pdf", "page": number, "text": "x" * 40, "hasImages": False}
            for number in range(1, 6)
        ]
        markdown = SIVSHandler.tender_pages_markdown(pages, max_chars=120)

        self.assertLessEqual(len(markdown), 120)
        self.assertNotIn("Página 5", markdown)
        # cada página incluída deve ter seu texto completo — nenhuma foi cortada no meio.
        self.assertEqual(markdown.count("## Página"), markdown.count("x" * 40))

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
        deadline = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        self.db.execute(
            """INSERT INTO records
               (module,title,status,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES(?,?,?,?,?,?,?,?,?,1)""",
            ("propostas", "Proposta Hospital Seguro", "Enviada", deadline,
             json.dumps({"cliente": "Hospital Seguro", "validade": deadline, "etapa": "Enviada"}),
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

    def test_partner_lookup_uses_configured_cnpj_and_viacep_with_cache(self):
        self.setup_admin()

        class Response(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        cnpj_response = Response(json.dumps({
            "company": {"name": "Fornecedor Teste Ltda."}, "alias": "Fornecedor Teste",
            "phones": [{"area": "11", "number": "33334444"}], "emails": [{"address": "contato@example.test"}],
            "address": {"zip": "01001-000", "street": "Praça da Sé", "district": "Sé", "city": "São Paulo", "state": "SP"},
        }).encode())
        cep_response = Response(json.dumps({
            "cep": "01001000", "logradouro": "Praça da Sé", "bairro": "Sé", "localidade": "São Paulo", "uf": "SP",
        }).encode())
        with patch.dict("os.environ", {"CNPJA_API_KEY": "test-key"}):
            with patch("server.urllib.request.urlopen", side_effect=[cnpj_response, cep_response]) as urlopen:
                status, cnpj = self.request("GET", "/api/partner-lookup?cnpj=12345678000195")
                self.assertEqual(status, 200, cnpj)
                self.assertEqual(cnpj["source"], "CNPJá Comercial")
                self.assertEqual(cnpj["fields"]["razao_social"], "Fornecedor Teste Ltda.")
                self.assertEqual(cnpj["fields"]["cep"], "01001000")
                status, cep = self.request("GET", "/api/partner-lookup?cep=01001000")
                self.assertEqual(status, 200, cep)
                self.assertEqual(cep["source"], "ViaCEP")
                self.assertEqual(cep["fields"]["logradouro"], "Praça da Sé")
                status, cached = self.request("GET", "/api/partner-lookup?cep=01001000")
                self.assertEqual(status, 200, cached)
                self.assertTrue(cached["cached"])
                self.assertEqual(urlopen.call_count, 2)

    def test_partner_lookup_uses_viacep_for_cep(self):
        self.setup_admin()

        class Response(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        response = Response(b'{"logradouro":"Rua Teste","bairro":"Centro","localidade":"Recife","uf":"PE"}')
        with patch("server.urllib.request.urlopen", return_value=response) as urlopen:
            status, result = self.request("GET", "/api/partner-lookup?cep=50000000")
        self.assertEqual(status, 200, result)
        self.assertTrue(result["configured"])
        self.assertEqual(result["source"], "ViaCEP")
        self.assertIn("viacep.com.br", urlopen.call_args.args[0].full_url)

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

    def test_unified_registration_defaults_role_from_document_kind(self):
        self.setup_admin()
        cases = [
            ("Pessoa física padrão", "52998224725", "Pessoa física", "C", "clientes"),
            ("Pessoa jurídica padrão", "12345678000195", "Pessoa jurídica", "F", "fornecedores"),
        ]
        for title, document, person_type, role, stored_module in cases:
            status, created = self.request("POST", "/api/records", {
                "module": "clientes_fornecedores", "title": title, "status": "Ativo",
                "payload": {
                    "assunto": title, "documento": document,
                    "tipo_pessoa": person_type, "razao_social": title,
                },
            })
            self.assertEqual(status, 201, created)
            self.assertEqual(created["item"]["module"], stored_module)
            self.assertEqual(created["item"]["payload"]["tipo_cadastro"], role)

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

    def test_party_document_is_a_normalized_unique_company_key(self):
        self.setup_admin()
        first_client = None
        cases = [
            ("Cliente CPF único", "52998224725", "C", "529.982.247-25", "CPF"),
            ("Fornecedor CNPJ único", "12345678000195", "F", "12.345.678/0001-95", "CNPJ"),
        ]
        for title, document, role, repeated_document, label in cases:
            payload = {
                "assunto": title, "tipo_cadastro": role, "documento": document,
                "tipo_pessoa": "Pessoa física" if role == "C" else "Pessoa jurídica",
                "razao_social": title,
            }
            status, created = self.request("POST", "/api/records", {
                "module": "clientes_fornecedores", "title": title,
                "status": "Ativo", "payload": payload,
            })
            self.assertEqual(status, 201, created)
            self.assertEqual(created["item"]["payload"]["documento"], document)
            if role == "C":
                first_client = created["item"]
            payload["documento"] = repeated_document
            status, duplicate = self.request("POST", "/api/records", {
                "module": "clientes_fornecedores", "title": title + " duplicado",
                "status": "Ativo", "payload": payload,
            })
            self.assertEqual(status, 409, duplicate)
            self.assertEqual(duplicate["error"], "duplicate_party_document")
            self.assertIn(label, duplicate["message"])

        status, another = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Outro cliente",
            "status": "Ativo", "payload": {
                "assunto": "Outro cliente", "tipo_cadastro": "C",
                "documento": "11144477735", "tipo_pessoa": "Pessoa física",
                "razao_social": "Outro cliente",
            },
        })
        self.assertEqual(status, 201, another)
        update_payload = dict(another["item"]["payload"])
        update_payload["documento"] = first_client["payload"]["documento"]
        status, duplicate_update = self.request("PUT", f"/api/records/{another['item']['id']}", {
            "module": "clientes_fornecedores", "title": another["item"]["title"],
            "status": another["item"]["status"], "payload": update_payload,
            "revision": another["item"]["revision"],
        })
        self.assertEqual(status, 409, duplicate_update)
        self.assertEqual(duplicate_update["error"], "duplicate_party_document")

        indexes = {
            row["name"] for row in self.db.connection().execute("PRAGMA index_list(records)")
        }
        self.assertIn("idx_records_company_party_document_active", indexes)

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

        original_builder = SIVSHandler.build_technical_report_pdf

        def change_context_during_render(*args, **kwargs):
            body = original_builder(*args, **kwargs)
            self.db.execute(
                "UPDATE records SET revision=revision+1,updated_at=? WHERE id=?",
                (utc_now(), report_id),
            )
            return body

        with patch.object(
            SIVSHandler, "build_technical_report_pdf", side_effect=change_context_during_render,
        ):
            status, blocked_issue = self.request("POST", f"/api/reports/{report_id}/issue", {})
        self.assertEqual(status, 409, blocked_issue)
        self.assertEqual(blocked_issue["error"], "issuance_context_changed")
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM attachments WHERE record_id=? AND category='Documento técnico emitido'",
            (report_id,),
        ), 0)

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

    def test_registered_partners_are_shared_by_validated_relational_id(self):
        self.setup_admin()
        status, client = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Hospital Relacional",
            "status": "Ativo", "payload": {
                "assunto": "Hospital Relacional", "tipo_cadastro": "C",
                "documento": "52998224725", "tipo_pessoa": "Pessoa física",
                "razao_social": "Hospital Relacional",
            },
        })
        self.assertEqual(status, 201, client)
        status, supplier = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Fornecedor Relacional",
            "status": "Ativo", "payload": {
                "assunto": "Fornecedor Relacional", "tipo_cadastro": "F",
                "documento": "04252011000110", "tipo_pessoa": "Pessoa jurídica",
                "razao_social": "Fornecedor Relacional", "avaliacao": "Pendente",
            },
        })
        self.assertEqual(status, 201, supplier)

        status, options = self.request("GET", "/api/relations/options")
        self.assertEqual(status, 200, options)
        option = next(item for item in options["items"] if item["id"] == client["item"]["id"])
        self.assertEqual(option["party_type"], "C")
        self.assertEqual(option["document"], "52998224725")
        status, partner_options = self.request("GET", "/api/partners/options")
        self.assertEqual(status, 200, partner_options)
        self.assertEqual(partner_options["counts"], {"C": 1, "F": 1, "A": 0})
        self.assertEqual(
            {item["title"] for item in partner_options["items"]},
            {"Hospital Relacional", "Fornecedor Relacional"},
        )

        proposal = {
            "module": "propostas", "title": "Proposta vinculada", "status": "Rascunho",
            "payload": {
                "assunto": "Proposta vinculada", "numero": "PROP-REL-001",
                "cliente": "Nome adulterado", "cliente_id": client["item"]["id"],
                "validade": "2026-09-30", "etapa": "Rascunho",
                "local_execucao": "Unidade principal", "relacionamentos": [],
            },
        }
        status, created = self.request("POST", "/api/records", proposal)
        self.assertEqual(status, 201, created)
        self.assertEqual(created["item"]["payload"]["cliente"], "Hospital Relacional")
        self.assertEqual(created["item"]["payload"]["cliente_id"], client["item"]["id"])
        self.assertTrue(any(
            relation["record"] == f"clientes:{client['item']['id']}" and relation["type"] == "Cliente"
            for relation in created["item"]["payload"]["relacionamentos"]
        ))

        proposal["payload"]["cliente_id"] = supplier["item"]["id"]
        status, rejected = self.request("POST", "/api/records", proposal)
        self.assertEqual(status, 400, rejected)
        self.assertIn("cliente compatível", rejected["message"])

        self.db.execute(
            "UPDATE records SET title='Hospital Atualizado' WHERE id=?",
            (client["item"]["id"],),
        )
        status, refreshed = self.request("GET", f"/api/records/{created['item']['id']}")
        self.assertEqual(status, 200, refreshed)
        self.assertEqual(refreshed["item"]["payload"]["cliente"], "Hospital Atualizado")

    @staticmethod
    def fiscal_test_pfx(password):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.x509.oid import NameOID

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SECCOL TESTE"),
            x509.NameAttribute(NameOID.COMMON_NAME, "A1 HOMOLOGACAO 11105408000144"),
        ])
        now = datetime.now(timezone.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject).issuer_name(issuer).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=365))
            .sign(key, hashes.SHA256())
        )
        return pkcs12.serialize_key_and_certificates(
            b"sivs-test", key, certificate, None,
            serialization.BestAvailableEncryption(password.encode("utf-8")),
        )

    def test_fiscal_readiness_encrypts_a1_and_checks_sefaz_homologation(self):
        self.setup_admin()
        status, branches = self.request("GET", "/api/branches")
        self.assertEqual(status, 200, branches)
        branch_id = branches["items"][0]["id"]
        configuration = {
            "branchId": branch_id,
            "legalName": "F.F. CONTROLE E CERTIFICACAO LTDA",
            "cnpj": "11.105.408/0001-44",
            "stateRegistration": "123456789",
            "municipalRegistration": "987654",
            "uf": "GO",
            "municipalityCode": "5208707",
            "taxRegime": "REGIME_NORMAL",
            "environment": "HOMOLOGATION",
            "enabled": True,
            "useOfficialPreset": True,
        }
        status, configured = self.request("PUT", "/api/fiscal/configuration", configuration)
        self.assertEqual(status, 200, configured)
        self.assertEqual(configured["company"]["uf"], "GO")
        self.assertTrue(any(item["environment"] == "HOMOLOGATION"
                            for item in configured["configurations"]))
        endpoint = self.db.scalar(
            "SELECT status_service_url FROM sefaz_configurations WHERE company_id=1"
        )
        self.assertEqual(
            endpoint,
            "https://homolog.sefaz.go.gov.br/nfe/services/NFeStatusServico4",
        )
        configuration["environment"] = "PRODUCTION"
        status, locked = self.request("PUT", "/api/fiscal/configuration", configuration)
        self.assertEqual(status, 409, locked)
        self.assertEqual(locked["error"], "sefaz_production_locked")

        password = "Senha-A1-Temporaria"
        pfx = self.fiscal_test_pfx(password)
        master_key = base64.b64encode(b"fiscal-test-key-32-bytes-long!!!"[:32]).decode("ascii")
        with patch.dict(os.environ, {"SIVS_FISCAL_MASTER_KEY": master_key}):
            status, imported = self.request("POST", "/api/fiscal/certificate", {
                "branchId": branch_id,
                "password": password,
                "contentBase64": base64.b64encode(pfx).decode("ascii"),
            })
            self.assertEqual(status, 201, imported)
            certificate_id = imported["certificate"]["id"]
            encrypted = bytes(self.db.connection().execute(
                "SELECT encrypted_content FROM fiscal_certificates WHERE id=?",
                (certificate_id,),
            ).fetchone()[0])
            self.assertTrue(encrypted.startswith(b"SIVSA11"))
            self.assertNotIn(password.encode("utf-8"), encrypted)
            self.assertNotIn(pfx[:64], encrypted)

            response = {
                "tpAmb": "2", "verAplic": "GO_NFE_4.00", "cStat": "107",
                "xMotivo": "Servico em Operacao", "cUF": "52",
                "dhRecbto": "2026-08-18T12:00:00-03:00", "tMed": "1",
            }
            with patch.object(SIVSHandler, "sefaz_status_transport", return_value=response):
                status, checked = self.request("POST", "/api/fiscal/sefaz/status", {
                    "branchId": branch_id, "environment": "HOMOLOGATION",
                })
            self.assertEqual(status, 200, checked)
            self.assertTrue(checked["operational"])
            self.assertEqual(checked["statusCode"], "107")
            status, readiness = self.request("GET", "/api/fiscal/readiness")
            self.assertEqual(status, 200, readiness)
            self.assertTrue(readiness["canCheckStatus"])
            self.assertFalse(readiness["canIssue"])
            self.assertNotIn("encrypted_content", readiness["certificate"])
            self.db.execute(
                "UPDATE fiscal_certificates SET valid_to=? WHERE id=?",
                ("2020-01-01T00:00:00+00:00", certificate_id),
            )
            with patch.object(SIVSHandler, "sefaz_status_transport") as transport:
                status, expired = self.request("POST", "/api/fiscal/sefaz/status", {
                    "branchId": branch_id, "environment": "HOMOLOGATION",
                })
            self.assertEqual(status, 409, expired)
            self.assertEqual(expired["error"], "fiscal_certificate_expired")
            transport.assert_not_called()
        self.assertEqual(
            self.db.scalar("SELECT COUNT(*) FROM audit_log WHERE entity_type='sefaz'"), 2,
        )

    def test_accounting_export_is_audited_exact_and_company_scoped(self):
        self.setup_admin()
        status, created = self.request("POST", "/api/records", {
            "module": "financeiro", "title": "Título contábil agosto",
            "status": "Ativo", "amount": 1234.56,
            "due_date": "2026-08-30",
            "payload": {"assunto": "Competência agosto", "tipo_lancamento": "Receita",
                        "categoria": "Serviços", "documento": "FIN-2026-08-01",
                        "conta": "Conta corrente", "centro_custo": "Operação"},
        })
        self.assertEqual(status, 201, created)
        status, content, headers = self.raw_request(
            "GET", "/api/accounting/export?period=2026-08",
        )
        self.assertEqual(status, 200, content[:300])
        self.assertEqual(headers["x-sivs-format"], "SIVS-ACCOUNTING-1")
        self.assertEqual(headers["x-content-sha256"], __import__("hashlib").sha256(content).hexdigest())
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            self.assertIn("manifest.json", archive.namelist())
            self.assertIn("lancamentos/registros.csv", archive.namelist())
            self.assertIn("lancamentos/itens_documentos.csv", archive.namelist())
            self.assertIn("financeiro/lancamentos.csv", archive.namelist())
            self.assertIn("fiscal/documentos.csv", archive.namelist())
            self.assertIn("estoque/movimentos.csv", archive.namelist())
            self.assertIn("LEIA-ME.txt", archive.namelist())
            manifest = json.loads(archive.read("manifest.json"))
            records_csv = archive.read("lancamentos/registros.csv").decode("utf-8-sig")
            financial_csv = archive.read("financeiro/lancamentos.csv").decode("utf-8-sig")
        self.assertEqual(manifest["format"], "SIVS-ACCOUNTING-1")
        self.assertEqual(manifest["period"], "2026-08")
        self.assertEqual(manifest["company"]["id"], 1)
        self.assertIn("Título contábil agosto", records_csv)
        self.assertIn("123456", records_csv)
        self.assertIn("Título contábil agosto", financial_csv)
        self.assertTrue(all(item["sha256"] for item in manifest["files"]))
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM accounting_exports"), 1)
        self.assertEqual(
            self.db.scalar("SELECT COUNT(*) FROM audit_log WHERE entity_type='accounting'"), 1,
        )

    def test_fiscal_domain_records_locally_without_simulating_sefaz(self):
        self.setup_admin()
        status, created = self.request("POST", "/api/records", {
            "module": "fiscal", "title": "Documento fiscal local", "status": "Rascunho",
            "payload": {"assunto": "Preparação fiscal", "tipo_nota": "NF-e",
                        "numero": "1", "serie": "1", "chave": "0" * 44,
                        "destinatario": "Cliente local", "cfop": "Não parametrizado",
                        "finalidade": "Registro local"},
        })
        self.assertEqual(status, 201, created)
        status, registered = self.request(
            "POST", f"/api/fiscal/{created['item']['id']}/registrar",
            {"detail": "Registro sem transmissão"},
        )
        self.assertEqual(status, 201, registered)
        self.assertEqual(registered["status"], "Registrado localmente")
        status, refused = self.request(
            "POST", f"/api/fiscal/{created['item']['id']}/cancelar", {},
        )
        self.assertEqual(status, 501, refused)
        self.assertEqual(refused["error"], "fiscal_engine_not_implemented")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM fiscal_documents"), 0)

    def test_inventory_ledger_reservations_transfer_audit_and_company_isolation(self):
        self.setup_admin()
        status, snapshot = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, snapshot)
        self.assertEqual(len(snapshot["warehouses"]), 1)
        self.assertEqual(len(snapshot["branches"]), 1)
        product_id = snapshot["products"][0]["id"]
        warehouse_id = snapshot["warehouses"][0]["id"]

        status, movement = self.request("POST", "/api/inventory/movements", {
            "movementType": "ADJUSTMENT_IN", "warehouseId": warehouse_id,
            "productId": product_id, "quantity": "10.500000", "lot": "LOTE-A",
            "unitCost": "12.50",
            "originType": "INITIAL_BALANCE", "originId": "INV-001",
            "reason": "Inventário inicial conferido",
        })
        self.assertEqual(status, 201, movement)
        status, reservation = self.request("POST", "/api/inventory/reservations", {
            "warehouseId": warehouse_id, "productId": product_id,
            "quantity": "4", "lot": "LOTE-A", "originType": "SALES_ORDER",
            "originId": "PV-001", "reference": "Cliente teste",
        })
        self.assertEqual(status, 201, reservation)
        status, snapshot = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, snapshot)
        balance = next(item for item in snapshot["balances"] if item["lot"] == "LOTE-A")
        self.assertEqual(balance["physicalQuantity"], 10.5)
        self.assertEqual(balance["reservedQuantity"], 4)
        self.assertEqual(balance["availableQuantity"], 6.5)
        self.assertEqual(snapshot["movements"][0]["movement_type"], "RESERVE")

        status, rejected = self.request("POST", "/api/inventory/movements", {
            "movementType": "SALE_OUT", "warehouseId": warehouse_id,
            "productId": product_id, "quantity": "7", "lot": "LOTE-A",
            "originType": "SALES_ORDER", "originId": "PV-002",
        })
        self.assertEqual(status, 409, rejected)
        self.assertEqual(rejected["error"], "inventory_conflict")

        status, released = self.request(
            "POST", f"/api/inventory/reservations/{reservation['id']}/release", {},
        )
        self.assertEqual(status, 200, released)
        status, expired_reservation = self.request("POST", "/api/inventory/reservations", {
            "warehouseId": warehouse_id, "productId": product_id,
            "quantity": "1", "lot": "LOTE-A", "originType": "SALES_ORDER",
            "originId": "PV-EXPIRADA", "reference": "Reserva vencida",
            "expiresAt": "2020-01-01",
        })
        self.assertEqual(status, 201, expired_reservation)
        self.assertEqual(self.server._release_expired_inventory_reservations(), 1)
        expired_row = self.db.connection().execute(
            "SELECT status,released_by FROM inventory_reservations WHERE id=?",
            (expired_reservation["id"],),
        ).fetchone()
        self.assertEqual(expired_row["status"], "RELEASED")
        self.assertIsNone(expired_row["released_by"])
        expiration_movement = self.db.connection().execute(
            """SELECT movement_type,reserved_delta_micros,reason
               FROM inventory_movements WHERE reservation_id=? ORDER BY id DESC LIMIT 1""",
            (expired_reservation["id"],),
        ).fetchone()
        self.assertEqual(expiration_movement["movement_type"], "RELEASE_RESERVATION")
        self.assertEqual(expiration_movement["reserved_delta_micros"], -1_000_000)
        self.assertEqual(expiration_movement["reason"], "Expiração automática da reserva")
        branch_id = snapshot["branches"][0]["id"]
        status, warehouse = self.request("POST", "/api/inventory/warehouses", {
            "branchId": branch_id, "code": "CAMPO", "name": "Depósito de campo",
            "location": "Veículo técnico",
        })
        self.assertEqual(status, 201, warehouse)
        status, transfer = self.request("POST", "/api/inventory/movements", {
            "movementType": "TRANSFER_OUT", "warehouseId": warehouse_id,
            "counterpartWarehouseId": warehouse["id"], "productId": product_id,
            "quantity": "3", "lot": "LOTE-A", "originType": "TRANSFER",
            "originId": "TR-001", "reference": "Reposição de campo",
        })
        self.assertEqual(status, 201, transfer)
        self.assertIsNotNone(transfer["pairedMovementId"])
        status, snapshot = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, snapshot)
        balances = {item["warehouse_id"]: item for item in snapshot["balances"]
                    if item["product_record_id"] == product_id and item["lot"] == "LOTE-A"}
        self.assertEqual(balances[warehouse_id]["physicalQuantity"], 7.5)
        self.assertEqual(balances[warehouse["id"]]["physicalQuantity"], 3)
        self.assertEqual(balances[warehouse_id]["reservedQuantity"], 0)
        self.assertEqual(
            {snapshot["movements"][0]["movement_type"], snapshot["movements"][1]["movement_type"]},
            {"TRANSFER_IN", "TRANSFER_OUT"},
        )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "imutável"):
            self.db.execute(
                "UPDATE inventory_movements SET reason='alterado' WHERE id=?",
                (movement["movementId"],),
            )
        self.db.connection().rollback()
        self.assertGreaterEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE entity_type='inventory'"
        ), 4)

        status, legacy = self.request("POST", "/api/records", {
            "module": "estoque", "title": "Saldo editável indevido", "status": "Ativo",
            "payload": {"assunto": "Estoque antigo", "produto": "Produto",
                        "lote": "X", "quantidade": 1, "localizacao": "Matriz",
                        "movimento": "Entrada"},
        })
        self.assertEqual(status, 409, legacy)
        self.assertEqual(legacy["error"], "inventory_ledger_required")

        barrier = threading.Barrier(3)
        concurrent_results = []

        def concurrent_output(sequence):
            body = json.dumps({
                "movementType": "SALE_OUT", "warehouseId": warehouse_id,
                "productId": product_id, "quantity": "5", "lot": "LOTE-A",
                "originType": "SALES_ORDER", "originId": f"PV-CONC-{sequence}",
            }).encode("utf-8")
            connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            barrier.wait()
            connection.request("POST", "/api/inventory/movements", body=body, headers={
                "Content-Type": "application/json", "Cookie": self.cookie,
                "X-CSRF-Token": self.csrf,
            })
            response = connection.getresponse()
            response.read()
            concurrent_results.append(response.status)
            connection.close()

        workers = [threading.Thread(target=concurrent_output, args=(index,)) for index in (1, 2)]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join(timeout=12)
        self.assertEqual(sorted(concurrent_results), [201, 409])
        status, after_concurrency = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, after_concurrency)
        source_balance = next(item for item in after_concurrency["balances"]
                              if item["warehouse_id"] == warehouse_id
                              and item["product_record_id"] == product_id
                              and item["lot"] == "LOTE-A")
        self.assertEqual(source_balance["physicalQuantity"], 2.5)

        status, company = self.request("POST", "/api/companies", {"name": "Empresa B"})
        self.assertEqual(status, 201, company)
        status, switched = self.request(
            "POST", "/api/company/switch", {"company_id": company["id"]},
        )
        self.assertEqual(status, 200, switched)
        status, isolated = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, isolated)
        self.assertEqual(isolated["balances"], [])
        status, cross_company = self.request("POST", "/api/inventory/movements", {
            "movementType": "ADJUSTMENT_IN", "warehouseId": warehouse_id,
            "productId": product_id, "quantity": "1", "unitCost": "12.50",
            "originType": "INITIAL_BALANCE",
            "originId": "INV-B", "reason": "Tentativa cruzada",
        })
        self.assertEqual(status, 409, cross_company)

    def test_document_items_calculate_totals_and_reserve_stock_atomically(self):
        self.setup_admin()
        status, inventory = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, inventory)
        product_id = inventory["products"][0]["id"]
        warehouse_id = inventory["warehouses"][0]["id"]
        status, _movement = self.request("POST", "/api/inventory/movements", {
            "movementType": "ADJUSTMENT_IN", "warehouseId": warehouse_id,
            "productId": product_id, "quantity": "10", "lot": "LOTE-WF",
            "unitCost": "15.00",
            "originType": "INITIAL_BALANCE", "originId": "WF-INITIAL",
            "reason": "Saldo para teste do workflow",
        })
        self.assertEqual(status, 201, _movement)
        status, customer = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Hospital faturável", "status": "Ativo",
            "payload": {
                "assunto": "Cliente da venda", "tipo_cadastro": "C",
                "tipo_pessoa": "Pessoa jurídica", "documento": "12345678000195",
                "razao_social": "Hospital faturável", "aprovado_faturamento": True,
                "bloqueado": False, "relacionamentos": [],
            },
        })
        self.assertEqual(status, 201, customer)
        status, unapproved_customer = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Cliente não aprovado", "status": "Ativo",
            "payload": {
                "assunto": "Cliente pendente", "tipo_cadastro": "C",
                "tipo_pessoa": "Pessoa jurídica", "documento": "11222333000181",
                "razao_social": "Cliente não aprovado", "aprovado_faturamento": False,
                "bloqueado": False, "relacionamentos": [],
            },
        })
        self.assertEqual(status, 201, unapproved_customer)
        sale_payload = {
            "assunto": "Venda integrada", "cliente": "Hospital faturável",
            "cliente_id": customer["item"]["id"],
            "documento": "PV-001", "vendedor": "Equipe comercial",
            "forma_pagamento": "Transferência", "condicao_pagamento": "30 dias",
            "relacionamentos": [],
        }
        unapproved_payload = {**sale_payload, "cliente": "Cliente não aprovado",
                              "cliente_id": unapproved_customer["item"]["id"]}
        status, unapproved_sale = self.request("POST", "/api/records", {
            "module": "vendas", "title": "Venda bloqueada por cadastro", "status": "Rascunho",
            "payload": unapproved_payload,
        })
        self.assertEqual(status, 400, unapproved_sale)
        self.assertIn("não aprovado para faturamento", unapproved_sale["message"])
        status, invalid_start = self.request("POST", "/api/records", {
            "module": "vendas", "title": "Venda fora do fluxo", "status": "Confirmado",
            "payload": sale_payload,
        })
        self.assertEqual(status, 400, invalid_start)
        status, sale = self.request("POST", "/api/records", {
            "module": "vendas", "title": "Pedido de venda PV-001", "status": "Rascunho",
            "payload": sale_payload,
        })
        self.assertEqual(status, 201, sale)
        sale_id = sale["item"]["id"]
        status, invalid_jump = self.request("PUT", f"/api/records/{sale_id}", {
            "module": "vendas", "title": "Pedido de venda PV-001", "status": "Faturado",
            "payload": sale_payload, "revision": sale["item"]["revision"],
        })
        self.assertEqual(status, 400, invalid_jump)
        status, sale = self.request("PUT", f"/api/records/{sale_id}", {
            "module": "vendas", "title": "Pedido de venda PV-001", "status": "Confirmado",
            "payload": sale_payload, "revision": sale["item"]["revision"],
        })
        self.assertEqual(status, 200, sale)
        status, duplicate_number = self.request("POST", "/api/records", {
            "module": "vendas", "title": "Outra venda PV-001", "status": "Rascunho",
            "payload": sale_payload,
        })
        self.assertEqual(status, 409, duplicate_number)
        self.assertEqual(duplicate_number["error"], "duplicate_business_key")

        status, composition = self.request("GET", f"/api/records/{sale_id}/items")
        self.assertEqual(status, 200, composition)
        service_id = next(item["id"] for item in composition["catalog"]
                          if item["module"] == "catalogo_servicos")
        status, product_line = self.request("POST", f"/api/records/{sale_id}/items", {
            "recordRevision": composition["recordRevision"], "itemKind": "PRODUCT",
            "catalogRecordId": product_id, "description": "Produto controlado",
            "quantity": "2", "unitPrice": "100.10", "discount": "0.20",
            "warehouseId": warehouse_id, "lot": "LOTE-WF",
        })
        self.assertEqual(status, 201, product_line)
        self.assertEqual(product_line["totals"]["totalCents"], 20000)

        status, service_line = self.request("POST", f"/api/records/{sale_id}/items", {
            "recordRevision": product_line["recordRevision"], "itemKind": "SERVICE",
            "catalogRecordId": service_id, "description": "Serviço técnico",
            "quantity": "1.5", "unitPrice": "50.00", "discount": "0",
        })
        self.assertEqual(status, 201, service_line)
        self.assertEqual(service_line["totals"], {
            "subtotalCents": 27520, "discountCents": 20,
            "totalCents": 27500, "itemCount": 2,
        })
        self.assertEqual(self.db.scalar("SELECT amount FROM records WHERE id=?", (sale_id,)), 275)

        status, stale = self.request("POST", f"/api/records/{sale_id}/items", {
            "recordRevision": product_line["recordRevision"], "itemKind": "SERVICE",
            "catalogRecordId": service_id, "quantity": "1", "unitPrice": "1",
        })
        self.assertEqual(status, 409, stale)
        self.assertEqual(stale["error"], "write_conflict")

        status, reserved = self.request(
            "POST", f"/api/records/{sale_id}/reserve-items", {},
        )
        self.assertEqual(status, 200, reserved)
        self.assertEqual(reserved["items"], 1)
        status, composition = self.request("GET", f"/api/records/{sale_id}/items")
        self.assertEqual(status, 200, composition)
        product_item = next(item for item in composition["items"]
                            if item["itemKind"] == "PRODUCT")
        self.assertEqual(product_item["reservationStatus"], "ACTIVE")
        status, inventory = self.request("GET", "/api/inventory")
        balance = next(item for item in inventory["balances"] if item["lot"] == "LOTE-WF")
        self.assertEqual(balance["reservedQuantity"], 2)
        self.assertEqual(balance["availableQuantity"], 8)

        status, protected_sale = self.request("DELETE", f"/api/records/{sale_id}")
        self.assertEqual(status, 409, protected_sale)
        self.assertEqual(protected_sale["error"], "active_inventory_reservations")

        status, locked = self.request(
            "DELETE", f"/api/records/{sale_id}/items/{product_item['id']}", {
                "recordRevision": composition["recordRevision"],
                "itemRevision": product_item["revision"],
            },
        )
        self.assertEqual(status, 409, locked)
        self.assertIn("Libere a reserva", locked["message"])

        status, released = self.request(
            "POST", f"/api/records/{sale_id}/release-items", {},
        )
        self.assertEqual(status, 200, released)
        status, inventory = self.request("GET", "/api/inventory")
        balance = next(item for item in inventory["balances"] if item["lot"] == "LOTE-WF")
        self.assertEqual(balance["reservedQuantity"], 0)
        status, protected_product = self.request("DELETE", f"/api/records/{product_id}")
        self.assertEqual(status, 409, protected_product)
        self.assertEqual(protected_product["error"], "catalog_item_in_use")
        movement_types = [item["movement_type"] for item in inventory["movements"][:2]]
        self.assertEqual(movement_types, ["RELEASE_RESERVATION", "RESERVE"])

        status, current_sale = self.request("GET", f"/api/records/{sale_id}")
        self.assertEqual(status, 200, current_sale)
        status, sale = self.request("PUT", f"/api/records/{sale_id}", {
            "module": "vendas", "title": "Pedido de venda PV-001", "status": "Separação",
            "payload": sale_payload, "revision": current_sale["item"]["revision"],
        })
        self.assertEqual(status, 200, sale)
        status, reserved = self.request(
            "POST", f"/api/records/{sale_id}/reserve-items", {},
        )
        self.assertEqual(status, 200, reserved)
        status, sale = self.request("PUT", f"/api/records/{sale_id}", {
            "module": "vendas", "title": "Pedido de venda PV-001", "status": "Faturado",
            "payload": sale_payload, "revision": sale["item"]["revision"],
        })
        self.assertEqual(status, 200, sale)
        status, blocked_completion = self.request("PUT", f"/api/records/{sale_id}", {
            "module": "vendas", "title": "Pedido de venda PV-001", "status": "Concluído",
            "payload": sale_payload, "revision": sale["item"]["revision"],
        })
        self.assertEqual(status, 409, blocked_completion)
        self.assertEqual(blocked_completion["error"], "active_inventory_reservations")

        status, fulfilled = self.request(
            "POST", f"/api/records/{sale_id}/fulfill-items", {},
        )
        self.assertEqual(status, 200, fulfilled)
        self.assertEqual(fulfilled["items"], 1)
        status, inventory = self.request("GET", "/api/inventory")
        balance = next(item for item in inventory["balances"] if item["lot"] == "LOTE-WF")
        self.assertEqual(balance["physicalQuantity"], 8)
        self.assertEqual(balance["reservedQuantity"], 0)
        self.assertEqual(balance["availableQuantity"], 8)
        self.assertEqual(inventory["movements"][0]["movement_type"], "SALE_OUT")
        status, composition = self.request("GET", f"/api/records/{sale_id}/items")
        product_item = next(item for item in composition["items"]
                            if item["itemKind"] == "PRODUCT")
        self.assertEqual(product_item["reservationStatus"], "FULFILLED")
        self.assertEqual(composition["fulfilledReservations"], 1)
        status, locked_fulfilled = self.request(
            "DELETE", f"/api/records/{sale_id}/items/{product_item['id']}", {
                "recordRevision": composition["recordRevision"],
                "itemRevision": product_item["revision"],
            },
        )
        self.assertEqual(status, 409, locked_fulfilled)
        self.assertIn("já foi baixado", locked_fulfilled["message"])
        status, sale = self.request("PUT", f"/api/records/{sale_id}", {
            "module": "vendas", "title": "Pedido de venda PV-001", "status": "Concluído",
            "payload": sale_payload, "revision": sale["item"]["revision"],
        })
        self.assertEqual(status, 200, sale)
        self.assertGreaterEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE entity_type IN ('document_item','vendas')"
        ), 8)

    def test_missing_static_asset_returns_404(self):
        status, content, _headers = self.raw_request(
            "GET", "/arquivo-que-nao-existe.js", authenticated=False
        )
        self.assertEqual(status, 404, content)

    def test_service_order_parts_leave_stock_through_the_audited_ledger(self):
        self.setup_admin()
        status, inventory = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, inventory)
        product_id = inventory["products"][0]["id"]
        warehouse_id = inventory["warehouses"][0]["id"]
        status, _movement = self.request("POST", "/api/inventory/movements", {
            "movementType": "ADJUSTMENT_IN", "warehouseId": warehouse_id,
            "productId": product_id, "quantity": "3", "lot": "LOTE-OS",
            "unitCost": "20.00",
            "originType": "INITIAL_BALANCE", "originId": "OS-INITIAL",
            "reason": "Saldo para execução da O.S.",
        })
        self.assertEqual(status, 201, _movement)
        status, customer = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Cliente da O.S.", "status": "Ativo",
            "payload": {
                "assunto": "Cliente técnico", "tipo_cadastro": "C",
                "tipo_pessoa": "Pessoa jurídica", "documento": "04252011000110",
                "razao_social": "Cliente da O.S.", "bloqueado": False,
            },
        })
        self.assertEqual(status, 201, customer)
        service_order_payload = {
            "assunto": "Execução técnica", "numero": "OS-LEDGER-001",
            "cliente": "Cliente da O.S.", "cliente_id": customer["item"]["id"],
            "tecnico": "Técnico responsável", "tipo_os": "Manutenção",
            "local_execucao": "Instalação do cliente",
        }
        status, service_order = self.request("POST", "/api/records", {
            "module": "ordens_servico", "title": "O.S. com peça controlada",
            "status": "Aberta", "payload": service_order_payload,
        })
        self.assertEqual(status, 201, service_order)
        service_order_id = service_order["item"]["id"]
        status, service_order = self.request("PUT", f"/api/records/{service_order_id}", {
            "module": "ordens_servico", "title": "O.S. com peça controlada",
            "status": "Em execução", "payload": service_order_payload,
            "revision": service_order["item"]["revision"],
        })
        self.assertEqual(status, 200, service_order)
        status, composition = self.request("GET", f"/api/records/{service_order_id}/items")
        self.assertEqual(status, 200, composition)
        status, _item = self.request("POST", f"/api/records/{service_order_id}/items", {
            "recordRevision": composition["recordRevision"], "itemKind": "PRODUCT",
            "catalogRecordId": product_id, "description": "Peça aplicada na manutenção",
            "quantity": "1", "unitPrice": "10", "warehouseId": warehouse_id,
            "lot": "LOTE-OS",
        })
        self.assertEqual(status, 201, _item)
        status, reserved = self.request(
            "POST", f"/api/records/{service_order_id}/reserve-items", {},
        )
        self.assertEqual(status, 200, reserved)
        status, fulfilled = self.request(
            "POST", f"/api/records/{service_order_id}/fulfill-items", {},
        )
        self.assertEqual(status, 200, fulfilled)
        status, inventory = self.request("GET", "/api/inventory")
        balance = next(item for item in inventory["balances"] if item["lot"] == "LOTE-OS")
        self.assertEqual(balance["physicalQuantity"], 2)
        self.assertEqual(balance["reservedQuantity"], 0)
        movement = next(item for item in inventory["movements"]
                        if item["movement_type"] == "SERVICE_ORDER_OUT")
        self.assertEqual(movement["origin_type"], "SERVICE_ORDER")
        self.assertEqual(movement["reference"], "O.S. com peça controlada")
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE entity_type='ordens_servico' AND action='fulfill'",
        ), 1)

    def test_purchase_order_receiving_creates_one_audited_inventory_entry(self):
        self.setup_admin()
        status, inventory = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, inventory)
        product_id = inventory["products"][0]["id"]
        warehouse_id = inventory["warehouses"][0]["id"]
        status, supplier = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Fornecedor aprovado", "status": "Ativo",
            "payload": {
                "assunto": "Fornecedor operacional", "tipo_cadastro": "F",
                "tipo_pessoa": "Pessoa jurídica", "documento": "12345678000195",
                "razao_social": "Fornecedor aprovado", "avaliacao": "Aprovado",
                "aprovado_compras": True, "bloqueado": False,
            },
        })
        self.assertEqual(status, 201, supplier)
        purchase_payload = {
            "assunto": "Reposição de estoque", "numero": "PC-LEDGER-001",
            "fornecedor": "Fornecedor aprovado", "fornecedor_id": supplier["item"]["id"],
            "condicao_pagamento": "30 dias", "centro_custo": "Operação",
        }
        status, purchase = self.request("POST", "/api/records", {
            "module": "pedidos_compra", "title": "Pedido de reposição",
            "status": "Rascunho", "payload": purchase_payload,
        })
        self.assertEqual(status, 201, purchase)
        purchase_id = purchase["item"]["id"]
        status, composition = self.request("GET", f"/api/records/{purchase_id}/items")
        self.assertEqual(status, 200, composition)
        status, item_created = self.request("POST", f"/api/records/{purchase_id}/items", {
            "recordRevision": composition["recordRevision"], "itemKind": "PRODUCT",
            "catalogRecordId": product_id, "description": "Produto recebido",
            "quantity": "2", "unitPrice": "25", "warehouseId": warehouse_id,
            "lot": "LOTE-PC",
        })
        self.assertEqual(status, 201, item_created)
        status, purchase = self.request("PUT", f"/api/records/{purchase_id}", {
            "module": "pedidos_compra", "title": "Pedido de reposição",
            "status": "Emitido", "payload": purchase_payload,
            "revision": item_created["recordRevision"],
        })
        self.assertEqual(status, 200, purchase)
        status, premature = self.request("PUT", f"/api/records/{purchase_id}", {
            "module": "pedidos_compra", "title": "Pedido de reposição",
            "status": "Recebido", "payload": purchase_payload,
            "revision": purchase["item"]["revision"],
        })
        self.assertEqual(status, 409, premature)
        self.assertEqual(premature["error"], "active_inventory_reservations")

        status, received = self.request(
            "POST", f"/api/records/{purchase_id}/receive-items", {},
        )
        self.assertEqual(status, 200, received)
        self.assertEqual(received["items"], 1)
        status, duplicate_receive = self.request(
            "POST", f"/api/records/{purchase_id}/receive-items", {},
        )
        self.assertEqual(status, 409, duplicate_receive)
        status, composition = self.request("GET", f"/api/records/{purchase_id}/items")
        product_item = composition["items"][0]
        self.assertTrue(product_item["receiptMovementId"])
        self.assertEqual(composition["receivedItems"], 1)
        status, locked = self.request(
            "DELETE", f"/api/records/{purchase_id}/items/{product_item['id']}", {
                "recordRevision": composition["recordRevision"],
                "itemRevision": product_item["revision"],
            },
        )
        self.assertEqual(status, 409, locked)
        self.assertIn("já foi recebido", locked["message"])
        status, cancellation = self.request("PUT", f"/api/records/{purchase_id}", {
            "module": "pedidos_compra", "title": "Pedido de reposição",
            "status": "Cancelado", "payload": purchase_payload,
            "revision": purchase["item"]["revision"],
        })
        self.assertEqual(status, 409, cancellation)
        status, purchase = self.request("PUT", f"/api/records/{purchase_id}", {
            "module": "pedidos_compra", "title": "Pedido de reposição",
            "status": "Recebido", "payload": purchase_payload,
            "revision": purchase["item"]["revision"],
        })
        self.assertEqual(status, 200, purchase)
        status, inventory = self.request("GET", "/api/inventory")
        balance = next(item for item in inventory["balances"] if item["lot"] == "LOTE-PC")
        self.assertEqual(balance["physicalQuantity"], 2)
        movement = next(item for item in inventory["movements"]
                        if item["movement_type"] == "PURCHASE_IN")
        self.assertEqual(movement["origin_type"], "PURCHASE_ORDER")
        self.assertEqual(movement["reference"], "Pedido de reposição")
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE entity_type='pedidos_compra' AND action='receive'",
        ), 1)

    def test_function_permissions_separate_stock_values_movements_and_attachments(self):
        self.setup_admin()
        admin_cookie, admin_csrf = self.cookie, self.csrf
        status, inventory = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, inventory)
        product_id = inventory["products"][0]["id"]
        warehouse_id = inventory["warehouses"][0]["id"]
        status, movement = self.request("POST", "/api/inventory/movements", {
            "movementType": "ADJUSTMENT_IN", "warehouseId": warehouse_id,
            "productId": product_id, "quantity": "5", "lot": "LOTE-RBAC",
            "unitCost": "18.40", "originType": "INITIAL_BALANCE",
            "originId": "RBAC-001", "reason": "Saldo controlado",
        })
        self.assertEqual(status, 201, movement)
        status, customer = self.request("POST", "/api/records", {
            "module": "clientes", "title": "Cliente com evidência", "status": "Ativo",
            "payload": {
                "assunto": "Cliente com evidência", "tipo_pessoa": "Pessoa jurídica",
                "documento": "12345678000195", "razao_social": "Cliente com evidência",
                "relacionamentos": [],
            },
        })
        self.assertEqual(status, 201, customer)
        record_id = customer["item"]["id"]

        status, created = self.request("POST", "/api/users", {
            "name": "Estoquista restrito", "email": "estoque.rbac@seccol.test",
            "password": "Senha-Estoque-123", "role": "operator",
            "effectivePermissions": {
                "read": ["estoque", "clientes"],
                "write": ["estoque", "clientes"], "export": [],
            },
            "effectiveActions": {
                "estoque": ["reserve_stock", "release_stock"],
                "clientes": ["manage_attachments"],
            },
            "effectiveCapabilities": {
                "audit": False, "trash": False, "approvals": False,
            },
        })
        self.assertEqual(status, 201, created)
        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "estoque.rbac@seccol.test", "password": "Senha-Estoque-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]

        status, modules = self.request("GET", "/api/modules")
        self.assertEqual(status, 200, modules)
        self.assertEqual(
            set(modules["actionPermissions"]["estoque"]),
            {"reserve_stock", "release_stock"},
        )
        self.assertIn("clientes_fornecedores", modules["readableModules"])
        self.assertEqual(
            set(modules["actionPermissions"]["clientes_fornecedores"]),
            {"manage_attachments"},
        )
        status, restricted_inventory = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, restricted_inventory)
        self.assertFalse(restricted_inventory["valueVisible"])
        self.assertIsNone(restricted_inventory["valuation"]["inventoryValueCents"])
        balance = next(item for item in restricted_inventory["balances"]
                       if item["lot"] == "LOTE-RBAC")
        self.assertIsNone(balance["inventoryValueCents"])
        status, forbidden_movement = self.request("POST", "/api/inventory/movements", {
            "movementType": "SALE_OUT", "warehouseId": warehouse_id,
            "productId": product_id, "quantity": "1", "lot": "LOTE-RBAC",
            "originType": "SALES_ORDER", "originId": "RBAC-SALE",
        })
        self.assertEqual(status, 403, forbidden_movement)
        self.assertEqual(forbidden_movement["error"], "operation_forbidden")
        status, reservation = self.request("POST", "/api/inventory/reservations", {
            "warehouseId": warehouse_id, "productId": product_id,
            "quantity": "1", "lot": "LOTE-RBAC", "originType": "SALES_ORDER",
            "originId": "RBAC-RESERVE", "reference": "Reserva autorizada",
        })
        self.assertEqual(status, 201, reservation)
        pdf = base64.b64encode(b"%PDF-1.4\n%%EOF").decode("ascii")
        status, attached = self.request(
            "POST", f"/api/records/{record_id}/attachments", {
                "filename": "evidencia.pdf", "mime_type": "application/pdf",
                "content": pdf, "category": "Evidência",
            },
        )
        self.assertEqual(status, 201, attached)
        status, forbidden_approval = self.request(
            "POST", f"/api/records/{record_id}/approval", {
                "approval_type": "Aprovação cadastral",
            },
        )
        self.assertEqual(status, 403, forbidden_approval)
        self.assertEqual(forbidden_approval["error"], "operation_forbidden")
        status, forbidden_crm = self.request("GET", "/api/records?module=crm")
        self.assertEqual(status, 403, forbidden_crm)

        self.cookie, self.csrf = admin_cookie, admin_csrf
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE action='upload' AND entity_type='attachment'",
        ), 1)

    def test_individual_approval_function_can_be_granted_without_broad_editor_role(self):
        self.setup_admin()
        status, customer = self.request("POST", "/api/records", {
            "module": "clientes", "title": "Cadastro para decisão", "status": "Ativo",
            "payload": {
                "assunto": "Cadastro para decisão", "tipo_pessoa": "Pessoa jurídica",
                "documento": "12345678000195", "razao_social": "Cadastro para decisão",
                "relacionamentos": [],
            },
        })
        self.assertEqual(status, 201, customer)
        status, user = self.request("POST", "/api/users", {
            "name": "Aprovador funcional", "email": "aprovador.funcional@seccol.test",
            "password": "Senha-Aprovacao-123", "role": "operator",
            "effectivePermissions": {
                "read": ["clientes"], "write": [], "export": [],
            },
            "effectiveActions": {"clientes": ["decide_approval"]},
            "effectiveCapabilities": {
                "audit": False, "trash": False, "approvals": True,
            },
        })
        self.assertEqual(status, 201, user)
        status, approval = self.request(
            "POST", f"/api/records/{customer['item']['id']}/approval", {
                "approval_type": "Aprovação individual",
            },
        )
        self.assertEqual(status, 201, approval)
        self.assertEqual(approval["requestedTo"], user["id"])

        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "aprovador.funcional@seccol.test", "password": "Senha-Aprovacao-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, pending = self.request("GET", "/api/approvals?status=Pendente")
        self.assertEqual(status, 200, pending)
        item = next(entry for entry in pending["items"] if entry["id"] == approval["id"])
        self.assertTrue(item["can_decide"])
        status, decided = self.request(
            "POST", f"/api/approvals/{approval['id']}", {
                "status": "Aprovado", "comment": "Cadastro conferido",
            },
        )
        self.assertEqual(status, 200, decided)
        self.assertEqual(decided["status"], "Aprovado")
        status, forbidden_update = self.request(
            "PUT", f"/api/records/{customer['item']['id']}", {
                "module": "clientes", "title": "Tentativa de edição", "status": "Ativo",
                "payload": customer["item"]["payload"],
                "revision": customer["item"]["revision"],
            },
        )
        self.assertEqual(status, 403, forbidden_update)

    def test_inventory_costing_preserves_exact_value_through_reservation_transfer_and_issue(self):
        self.setup_admin()
        status, inventory = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, inventory)
        product_id = inventory["products"][0]["id"]
        source_id = inventory["warehouses"][0]["id"]
        branch_id = inventory["branches"][0]["id"]
        status, missing_cost = self.request("POST", "/api/inventory/movements", {
            "movementType": "ADJUSTMENT_IN", "warehouseId": source_id,
            "productId": product_id, "quantity": "10", "lot": "LOTE-CUSTO",
            "originType": "INITIAL_BALANCE", "originId": "CUSTO-SEM-VALOR",
            "reason": "Não deve entrar sem custo",
        })
        self.assertEqual(status, 400, missing_cost)
        status, entry = self.request("POST", "/api/inventory/movements", {
            "movementType": "ADJUSTMENT_IN", "warehouseId": source_id,
            "productId": product_id, "quantity": "10", "lot": "LOTE-CUSTO",
            "unitCost": "12.50", "originType": "INITIAL_BALANCE",
            "originId": "CUSTO-001", "reason": "Custo inicial conferido",
        })
        self.assertEqual(status, 201, entry)
        status, reservation = self.request("POST", "/api/inventory/reservations", {
            "warehouseId": source_id, "productId": product_id,
            "quantity": "4", "lot": "LOTE-CUSTO", "originType": "SALES_ORDER",
            "originId": "CUSTO-RESERVA", "reference": "Venda reservada",
        })
        self.assertEqual(status, 201, reservation)
        status, valued = self.request("GET", "/api/inventory")
        self.assertEqual(valued["valuation"]["inventoryValueCents"], 12500)
        self.assertEqual(valued["valuation"]["reservedValueCents"], 5000)
        status, destination = self.request("POST", "/api/inventory/warehouses", {
            "branchId": branch_id, "code": "CUSTO", "name": "Depósito de custo",
            "location": "Unidade de testes",
        })
        self.assertEqual(status, 201, destination)
        status, transfer = self.request("POST", "/api/inventory/movements", {
            "movementType": "TRANSFER_OUT", "warehouseId": source_id,
            "counterpartWarehouseId": destination["id"], "productId": product_id,
            "quantity": "3", "lot": "LOTE-CUSTO", "originType": "TRANSFER",
            "originId": "CUSTO-TR-001", "reference": "Transferência valorada",
        })
        self.assertEqual(status, 201, transfer)
        status, issued = self.request("POST", "/api/inventory/movements", {
            "movementType": "SALE_OUT", "warehouseId": destination["id"],
            "productId": product_id, "quantity": "2", "lot": "LOTE-CUSTO",
            "originType": "SALES_ORDER", "originId": "CUSTO-VENDA-001",
        })
        self.assertEqual(status, 201, issued)
        status, snapshot = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, snapshot)
        self.assertEqual(snapshot["valuation"]["inventoryValueCents"], 10000)
        balances = {item["warehouse_id"]: item for item in snapshot["balances"]
                    if item["lot"] == "LOTE-CUSTO"}
        self.assertEqual(balances[source_id]["inventoryValueCents"], 8750)
        self.assertEqual(balances[destination["id"]]["inventoryValueCents"], 1250)
        self.assertEqual(balances[source_id]["averageUnitCostCents"], 1250)
        sale = next(item for item in snapshot["movements"]
                    if item["origin_id"] == "CUSTO-VENDA-001")
        self.assertEqual(sale["unitCostCents"], 1250)
        self.assertEqual(sale["valueDeltaCents"], -2500)
        transfer_movements = [item for item in snapshot["movements"]
                              if item["origin_id"] == "CUSTO-TR-001"]
        self.assertEqual(sum(item["valueDeltaCents"] for item in transfer_movements), 0)

    def test_controllership_consolidates_exact_values_privacy_and_company_isolation(self):
        self.setup_admin()
        admin_cookie, admin_csrf = self.cookie, self.csrf
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        user_id = self.db.scalar("SELECT id FROM users WHERE email='admin@seccol.test'")
        now = utc_now()
        due = "2020-01-01"

        def insert_record(module, title, status, amount, payload=None, due_date=None):
            self.db.execute(
                """INSERT INTO records
                   (module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (module, title, status, amount, due_date,
                 json.dumps(payload or {}, ensure_ascii=False), user_id, now, now, company_id),
            )

        insert_record("vendas", "Venda faturada", "Faturado", 100.10)
        insert_record("vendas", "Pedido confirmado", "Confirmado", 50.00)
        insert_record("caixa", "Recebimento", "Ativo", 80.10, {"tipo_movimento": "Entrada"})
        insert_record("caixa", "Pagamento", "Ativo", 20.00, {"tipo_movimento": "Saída"})
        insert_record("contas_receber", "Recebível vencido", "Em aberto", 30.00,
                      due_date=due)
        insert_record("contas_pagar", "Pagável vencido", "Vencido", 10.00,
                      due_date=due)
        status, inventory = self.request("GET", "/api/inventory")
        product_id = inventory["products"][0]["id"]
        warehouse_id = inventory["warehouses"][0]["id"]
        status, entry = self.request("POST", "/api/inventory/movements", {
            "movementType": "ADJUSTMENT_IN", "warehouseId": warehouse_id,
            "productId": product_id, "quantity": "2", "lot": "LOTE-CONTROLE",
            "unitCost": "10.00", "originType": "INITIAL_BALANCE",
            "originId": "CTRL-001", "reason": "Valor para controladoria",
        })
        self.assertEqual(status, 201, entry)
        status, overview = self.request("GET", "/api/management/overview")
        self.assertEqual(status, 200, overview)
        self.assertEqual(overview["billing"]["totalCents"], 10010)
        self.assertEqual(overview["billing"]["openOrdersCents"], 5000)
        self.assertEqual(overview["cashflow"]["cashInCents"], 8010)
        self.assertEqual(overview["cashflow"]["cashOutCents"], 2000)
        self.assertEqual(overview["cashflow"]["balanceCents"], 6010)
        self.assertEqual(overview["overdue"]["receivableCents"], 3000)
        self.assertEqual(overview["overdue"]["payableCents"], 1000)
        self.assertEqual(overview["inventory"]["totalValueCents"], 2000)
        self.assertEqual(overview["billing"]["costOfSalesCents"], 0)
        self.assertEqual(overview["billing"]["grossContributionCents"], 10010)

        status, restricted = self.request("POST", "/api/users", {
            "name": "Analista de faturamento", "email": "faturamento@seccol.test",
            "password": "Senha-Faturamento-123", "role": "viewer",
            "effectivePermissions": {
                "read": ["controladoria", "vendas"], "write": [], "export": [],
            },
            "effectiveActions": {
                "controladoria": ["view_billing"], "vendas": ["view_values"],
            },
        })
        self.assertEqual(status, 201, restricted)
        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "faturamento@seccol.test", "password": "Senha-Faturamento-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, limited = self.request("GET", "/api/management/overview")
        self.assertEqual(status, 200, limited)
        self.assertEqual(limited["visibility"], {
            "billing": True, "cashflow": False,
            "inventoryValue": False, "overdue": False,
        })
        self.assertEqual(limited["billing"]["totalCents"], 10010)
        self.assertIsNone(limited["billing"]["costOfSalesCents"])
        self.assertIsNone(limited["cashflow"]["balanceCents"])
        self.assertIsNone(limited["inventory"]["totalValueCents"])
        self.assertIsNone(limited["overdue"]["receivableCents"])

        self.cookie, self.csrf = admin_cookie, admin_csrf
        status, company = self.request("POST", "/api/companies", {"name": "Empresa isolada"})
        self.assertEqual(status, 201, company)
        status, switched = self.request(
            "POST", "/api/company/switch", {"company_id": company["id"]},
        )
        self.assertEqual(status, 200, switched)
        status, isolated = self.request("GET", "/api/management/overview")
        self.assertEqual(status, 200, isolated)
        self.assertEqual(isolated["billing"]["totalCents"], 0)
        self.assertEqual(isolated["cashflow"]["balanceCents"], 0)
        self.assertEqual(isolated["inventory"]["totalValueCents"], 0)
        self.assertEqual(isolated["overdue"]["receivableCents"], 0)

    def test_frontend_assets_are_never_served_with_stale_cache(self):
        for path in (
            "/app.js", "/theme/components.css", "/theme/control-center.css",
            "/js/modules/control-center.js", "/manifest.json", "/service-worker.js",
        ):
            status, content, headers = self.raw_request("GET", path, authenticated=False)
            self.assertEqual(status, 200, content[:100])
            self.assertIn("no-store", headers.get("cache-control", ""))
            self.assertEqual(headers.get("pragma"), "no-cache")


if __name__ == "__main__":
    unittest.main()
