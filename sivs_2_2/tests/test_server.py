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
    TENDER_COMPANY_DOCUMENT_CATALOG,
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
    def test_legacy_integral_settlement_migrates_to_multi_event_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy-ledger.db"
            database = Database(path)
            company_id = database.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
            now = utc_now()
            financial_id = database.execute(
                """INSERT INTO records
                   (module,title,status,amount,due_date,payload,created_at,updated_at,company_id,revision)
                   VALUES('contas_receber','Título legado','Recebido',75,'2026-08-20',?, ?,?,?,1)""",
                (json.dumps({"assunto": "Título legado"}), now, now, company_id),
            ).lastrowid
            cash_id = database.execute(
                """INSERT INTO records
                   (module,title,status,amount,due_date,payload,created_at,updated_at,company_id,revision)
                   VALUES('caixa','Caixa legado','Ativo',75,'2026-08-20',?, ?,?,?,1)""",
                (json.dumps({"assunto": "Caixa legado", "conta": "Banco legado",
                             "forma_pagamento": "TED", "tipo_movimento": "Entrada"}),
                 now, now, company_id),
            ).lastrowid
            connection = database.connection()
            connection.executescript(
                """DROP TRIGGER trg_financial_settlement_scope_insert;
                   DROP TRIGGER trg_financial_settlement_immutable_update;
                   DROP TRIGGER trg_financial_settlement_immutable_delete;
                   DROP INDEX idx_financial_settlements_company;
                   DROP INDEX idx_financial_settlements_title;
                   DROP INDEX idx_financial_settlement_one_reversal;
                   DROP TABLE financial_settlements;
                   CREATE TABLE financial_settlements (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                     financial_record_id INTEGER NOT NULL UNIQUE REFERENCES records(id),
                     cash_record_id INTEGER NOT NULL UNIQUE REFERENCES records(id),
                     direction TEXT NOT NULL,amount_cents INTEGER NOT NULL,
                     settled_at TEXT NOT NULL,created_by INTEGER,created_at TEXT NOT NULL
                   );
                   CREATE INDEX idx_financial_settlements_company
                     ON financial_settlements(company_id,settled_at);
                   DELETE FROM schema_migrations WHERE version=238;"""
            )
            connection.execute(
                """INSERT INTO financial_settlements
                   (company_id,financial_record_id,cash_record_id,direction,amount_cents,
                    settled_at,created_at) VALUES(?,?,?,?,?,?,?)""",
                (company_id, financial_id, cash_id, "IN", 7500, "2026-08-20", now),
            )
            connection.commit()
            database.close_thread_connection()

            migrated = Database(path)
            try:
                row = migrated.connection().execute(
                    "SELECT * FROM financial_settlements WHERE financial_record_id=?",
                    (financial_id,),
                ).fetchone()
                self.assertEqual(row["entry_type"], "SETTLEMENT")
                self.assertEqual(row["principal_cents"], 7500)
                self.assertEqual(row["cash_amount_cents"], 7500)
                self.assertEqual(row["account"], "Banco legado")
                self.assertEqual(row["payment_method"], "TED")
                self.assertTrue(migrated.scalar(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
                    "AND name='idx_financial_settlements_company'"
                ))
                self.assertEqual(
                    migrated.scalar("SELECT name FROM schema_migrations WHERE version=238"),
                    "partial-settlements-reversals-bank-reconciliation",
                )
            finally:
                migrated.close_thread_connection()

    def test_docker_runtime_keeps_secrets_out_of_build_and_drops_privileges(self):
        root = Path(__file__).resolve().parents[2]
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        entrypoint = (root / "docker-entrypoint.sh").read_text(encoding="utf-8")
        self.assertNotIn("OPENROUTER_API_KEY", dockerfile)
        self.assertIn('ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]', dockerfile)
        self.assertIn("apt-get install --no-install-recommends -y gosu", dockerfile)
        self.assertIn("chown -R sivs:sivs /data", entrypoint)
        self.assertIn('exec gosu sivs "$@"', entrypoint)

    def test_tender_ai_uses_balanced_default_model(self):
        self.assertEqual(DEFAULT_OPENROUTER_TENDER_MODEL, "openai/gpt-5.4-mini")

    def test_tender_deterministic_extraction_finds_deadlines_and_catalog_requirements(self):
        pages = [{
            "document": "Edital 42.pdf", "page": 17, "hasImages": False,
            "text": (
                "O prazo para entrega da proposta termina em 30/08/2026 às 14:30. "
                "Para habilitação serão exigidos atestado de capacidade técnica, "
                "certificado de regularidade do FGTS e balanço patrimonial."
            ),
        }]
        deadlines, requirements = SIVSHandler.tender_deterministic_findings(pages)
        self.assertEqual(deadlines[0]["value"], "30/08/2026 às 14:30")
        self.assertEqual(deadlines[0]["reference"], "Edital 42.pdf, pág. 17")
        found = {item["documentType"] for item in requirements}
        self.assertEqual(found, {
            "technical_capacity_certificate", "fgts_certificate", "financial_statements",
        })
        self.assertTrue(all(item["reference"] == "Edital 42.pdf, pág. 17"
                            for item in requirements))

    def test_tender_ocr_uses_bounded_tesseract_process(self):
        completed = type("OCRResult", (), {
            "returncode": 0, "stdout": "Texto reconhecido".encode(), "stderr": b"",
        })()
        with patch.object(SIVSHandler, "tender_ocr_executable", return_value="tesseract"), \
                patch("server.subprocess.run", return_value=completed) as run:
            text = SIVSHandler.tender_ocr_image(b"imagem")
        self.assertEqual(text, "Texto reconhecido")
        self.assertEqual(run.call_args.kwargs["timeout"], 45)
        self.assertEqual(run.call_args.args[0][:3], ["tesseract", "stdin", "stdout"])

    def test_tender_ai_quality_gate_rejects_missing_citations(self):
        analysis = {
            "resumo": "Resumo", "recomendacao": "Revisar", "minuta_esclarecimento": "",
            "minuta_impugnacao": "", "prazos": [], "habilitacao": [],
            "requisitos_tecnicos": [], "obrigacoes_contratadas": [], "criterios_julgamento": [],
            "riscos_pendencias": [], "citacoes": [], "itens_comerciais": [],
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
            "riscos_pendencias": [], "citacoes": [], "itens_comerciais": [],
            "participacao": {"situacao": "nao_verificada", "itens": [], "justificativa": "Sem dados"},
        }
        complete = dict(incomplete, citacoes=[{
            "documento": "edital.pdf", "pagina": 1, "achado": "Entrega em 30 dias",
        }])
        responses = [
            io.StringIO(json.dumps({"model": "openai/gpt-5.4-mini", "choices": [{
                "message": {"content": json.dumps(incomplete)}
            }]})),
            io.StringIO(json.dumps({"model": "openai/gpt-5.4", "choices": [{
                "message": {"content": json.dumps(complete)}
            }]})),
        ]
        handler = SIVSHandler.__new__(SIVSHandler)
        environment = {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_TENDER_MODEL": "openai/gpt-5.4-mini",
            "OPENROUTER_TENDER_FALLBACK_MODEL": "openai/gpt-5.4",
        }
        with patch.dict(os.environ, environment, clear=False), patch(
            "server.urllib.request.urlopen", side_effect=responses,
        ) as urlopen:
            analysis, model = handler.openrouter_tender_analysis(
                {"title": "Edital"}, [{"document": "edital.pdf", "page": 1, "text": "Entrega em 30 dias"}],
            )
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(model, "openai/gpt-5.4")
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
            db.connection().rollback()
            tender_id = db.execute(
                """INSERT INTO tender_results
                   (source_key,external_id,title,object_text,matched_terms,relevance_score,status,raw_json,
                    created_at,updated_at,company_id)
                   VALUES('integrity','integrity-1','Edital A','Objeto A','[]',80,'Novo','{}',?,?,?)""",
                (now, now, first_company),
            ).lastrowid
            with self.assertRaisesRegex(
                sqlite3.IntegrityError, "cross-company tender analysis exception",
            ):
                db.execute(
                    """INSERT INTO tender_analysis_exceptions
                       (company_id,tender_result_id,exception_key,category,severity,status,
                        message,created_at,updated_at)
                       VALUES(?,?,'foreign-exception','OCR','CRITICAL','OPEN','Falha',?,?)""",
                    (second_company, tender_id, now, now),
                )
            db.connection().rollback()
            with self.assertRaisesRegex(sqlite3.IntegrityError, "cross-company tender proposal"):
                db.execute(
                    """INSERT INTO tender_proposals
                       (company_id,tender_result_id,status,current_version,created_at,updated_at)
                       VALUES(?,?,'DRAFT',0,?,?)""",
                    (second_company, tender_id, now, now),
                )
            db.connection().rollback()
            proposal_id = db.execute(
                """INSERT INTO tender_proposals
                   (company_id,tender_result_id,status,current_version,created_by,created_at,updated_at)
                   VALUES(?,?,'DRAFT',1,?,?,?)""",
                (first_company, tender_id, user_id, now, now),
            ).lastrowid
            version_id = db.execute(
                """INSERT INTO tender_proposal_versions
                   (proposal_id,company_id,version,commercial_json,created_by,created_at)
                   VALUES(?,?,1,'{}',?,?)""",
                (proposal_id, first_company, user_id, now),
            ).lastrowid
            foreign_product = db.execute(
                """INSERT INTO records
                   (module,title,status,payload,created_by,created_at,updated_at,company_id)
                   VALUES('produtos','Produto externo','Ativo','{}',?,?,?,?)""",
                (user_id, now, now, second_company),
            ).lastrowid
            with self.assertRaisesRegex(sqlite3.IntegrityError, "cross-company tender proposal item"):
                db.execute(
                    """INSERT INTO tender_proposal_version_items
                       (version_id,company_id,sort_order,source_kind,source_reference,
                        catalog_record_id,description,unit,quantity_micros,unit_cost_cents,
                        minimum_unit_price_cents,unit_price_cents,line_cost_cents,line_total_cents)
                       VALUES(?, ?,0,'MANUAL','item 1',?,'Produto','UN',1000000,100,100,120,100,120)""",
                    (version_id, first_company, foreign_product),
                )
            db.connection().rollback()

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
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=230"),
                "tender-company-documents-and-participation-packages",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=231"),
                "tender-multiple-documents-custom-requirements-alerts",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=232"),
                "tender-commercial-proposal-governance",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=233"),
                "tender-erp-feasibility-and-operational-sync",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=234"),
                "tender-operational-handoff-and-financial-origins",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=235"),
                "tender-coverage-monitor-and-persistent-retries",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=236"),
                "tender-deterministic-extraction-ocr-exceptions",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=237"),
                "financial-settlement-cash-ledger",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=238"),
                "partial-settlements-reversals-bank-reconciliation",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=239"),
                "tender-browser-agent-governance-and-bid-guard",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=245"),
                "notification-lifecycle-preferences-and-email-digests",
            )
            self.assertEqual(
                db.scalar("SELECT name FROM schema_migrations WHERE version=246"),
                "tender-control-decisions-risks-milestones-evidence",
            )
            self.assertEqual(db.scalar(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                "AND name IN ('tender_operational_handoffs','financial_document_origins',"
                "'tender_retry_queue','tender_analysis_exceptions','financial_settlements',"
                "'tender_agent_policies','tender_agent_runs','tender_agent_commands',"
                "'tender_agent_receipts')"
            ), 9)
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
            proposal_item_columns = {
                row["name"] for row in db.connection().execute(
                    "PRAGMA table_info(tender_proposal_version_items)"
                )
            }
            self.assertTrue({
                "catalog_module", "catalog_code", "catalog_cost_cents", "cost_source",
                "available_quantity_micros", "supply_mode", "supply_notes",
                "catalog_exception_reason",
            }.issubset(proposal_item_columns))
            for table in (
                "inventory_balances", "inventory_movements", "inventory_reservations",
                "fiscal_schema_versions", "fiscal_operations", "tax_profiles", "tax_rules",
                "company_fiscal_profiles", "product_fiscal_profiles", "fiscal_documents",
                "fiscal_document_items", "fiscal_certificates", "xml_documents",
                "document_items", "sefaz_configurations", "accounting_exports",
                "company_tender_documents", "tender_participation_profiles",
                "tender_document_requirements", "tender_requirement_documents",
                "notification_alerts", "tender_proposals", "tender_proposal_versions",
                "notification_preferences", "notification_email_deliveries",
                "notification_email_digests",
                "tender_control_profiles", "tender_control_versions",
                "tender_milestones", "tender_risks",
                "tender_protocol_evidence",
                "tender_proposal_version_items", "tender_proposal_decisions",
                "financial_settlements",
                "bank_statement_entries",
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
        # Operações que semeiam a estrutura completa de uma empresa podem exceder
        # cinco segundos em hosts Windows sob carga; mantenha o mesmo limite do helper bruto.
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
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

    def test_dashboard_explains_tender_stage_and_next_action(self):
        self.setup_admin()
        due_date = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        status, created = self.request("POST", "/api/records", {
            "module": "licitacoes", "title": "Pregão — município de teste",
            "status": "Captação", "amount": None, "due_date": due_date,
            "payload": {
                "assunto": "Pregão de teste", "relacionamentos": [],
                "orgao": "Município de teste", "edital": "001/2026",
                "portal": "https://pncp.gov.br", "modalidade": "Pregão",
                "data_abertura": due_date,
            },
        })
        self.assertEqual(status, 201, created)
        self.db.execute(
            "UPDATE records SET status='Documentação' WHERE id=?", (created["item"]["id"],)
        )
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        now = utc_now()
        tender_result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,agency,matched_terms,relevance_score,status,
                raw_json,converted_record_id,created_at,updated_at,company_id)
               VALUES(?,?,?,?,?,'[]',0,'Convertido',?,?,?, ?,?)""",
            ("pncp", "dashboard-test-001", "Pregão — município de teste", "Objeto de teste",
             "Município de teste", "{}", created["item"]["id"], now, now, company_id),
        ).lastrowid
        self.db.execute(
            """INSERT INTO tender_document_requirements
               (company_id,tender_result_id,document_type,title,stage,required,created_at,updated_at)
               VALUES(?,?,?,?,? ,1,?,?)""",
            (company_id, tender_result_id, "fiscal_clearance", "Regularidade fiscal",
             "QUALIFICATION", now, now),
        )
        self.db.execute(
            """INSERT INTO tender_milestones
               (company_id,tender_result_id,milestone_type,title,due_at,status,sort_order,created_at,updated_at)
               VALUES(?,?, 'PROPOSAL','Enviar proposta',?,'PENDING',0,?,?)""",
            (company_id, tender_result_id, f"{due_date}T12:00:00+00:00", now, now),
        )
        self.db.execute(
            """INSERT INTO tender_risks
               (company_id,tender_result_id,category,title,probability,impact,status,sort_order,created_at,updated_at)
               VALUES(?,?, 'DOCUMENTAL','Certidão pendente',5,5,'OPEN',0,?,?)""",
            (company_id, tender_result_id, now, now),
        )

        status, dashboard = self.request("GET", "/api/dashboard")
        self.assertEqual(status, 200, dashboard)
        item = next(item for item in dashboard["workItems"] if item["recordId"] == created["item"]["id"])
        self.assertEqual(item["status"], "Documentação")
        self.assertIn("Decisão GO/NO-GO", item["pendingReason"])
        self.assertIn("1 documento(s) obrigatório(s)", item["pendingReason"])
        self.assertIn("Marco pendente: Enviar proposta", item["pendingReason"])
        self.assertIn("1 risco(s) crítico(s)", item["pendingReason"])
        self.assertIn("checklist do edital", item["requiredAction"])
        self.assertEqual(item["actionLabel"], "Próxima ação")
        self.assertEqual(item["tenderResultId"], tender_result_id)

    def test_notification_lifecycle_preferences_and_individual_actions(self):
        self.setup_admin()
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        user_id = self.db.scalar("SELECT id FROM users WHERE email='admin@seccol.test'")
        now = utc_now()
        info_id = self.db.execute(
            """INSERT INTO notifications
               (company_id,user_id,title,message,module,target,level,category,created_at)
               VALUES(?,?,?,?,?,'crm','info','crm',?)""",
            (company_id, user_id, "Lead recebido", "Novo lead do site.", "crm", now),
        ).lastrowid
        critical_id = self.db.execute(
            """INSERT INTO notifications
               (company_id,user_id,title,message,module,target,level,category,created_at)
               VALUES(?,?,?,?,?,'editais','error','tenders',?)""",
            (company_id, user_id, "Documento vencido", "Regularize o documento.", "editais", now),
        ).lastrowid
        self.db.execute(
            """INSERT INTO notification_alerts
               (company_id,alert_key,notification_id,entity_type,entity_id,due_date,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (company_id, "test-critical", critical_id, "tender_result", 1, None, now),
        )

        status, current = self.request("GET", "/api/notifications")
        self.assertEqual(status, 200, current)
        self.assertEqual({item["id"] for item in current["items"]}, {info_id, critical_id})
        self.assertEqual(current["unreadCount"], 2)
        critical = next(item for item in current["items"] if item["id"] == critical_id)
        self.assertEqual(critical["alert_entity_type"], "tender_result")
        self.assertEqual(critical["alert_entity_id"], 1)
        # Uma versão antiga da PWA não pode bloquear a central por enviar o nome
        # antigo da aba, nem um valor corrompido pode alterar o escopo dos dados.
        status, legacy_view = self.request("GET", "/api/notifications?view=pending")
        self.assertEqual(status, 200, legacy_view)
        self.assertEqual(legacy_view["view"], "active")
        self.assertEqual({item["id"] for item in legacy_view["items"]}, {info_id, critical_id})
        status, fallback_view = self.request("GET", "/api/notifications?view=undefined")
        self.assertEqual(status, 200, fallback_view)
        self.assertEqual(fallback_view["view"], "active")
        self.assertEqual({item["id"] for item in fallback_view["items"]}, {info_id, critical_id})

        status, read = self.request("POST", f"/api/notifications/{info_id}/read", {})
        self.assertEqual(status, 200, read)
        status, current = self.request("GET", "/api/notifications?view=active")
        self.assertEqual(status, 200, current)
        self.assertEqual([item["id"] for item in current["items"]], [critical_id])
        status, history = self.request("GET", "/api/notifications?view=history")
        self.assertEqual(status, 200, history)
        self.assertIn(info_id, {item["id"] for item in history["items"]})

        status, dismissed = self.request("POST", f"/api/notifications/{info_id}/dismiss", {})
        self.assertEqual(status, 200, dismissed)
        status, blocked = self.request("POST", f"/api/notifications/{critical_id}/dismiss", {})
        self.assertEqual(status, 409, blocked)

        preferences = {
            "categories": {"approvals": True, "crm": False, "tenders": False,
                           "whatsapp": True, "system": True},
            "minimumLevel": "warning", "dailyEmail": True, "criticalEmail": True,
            "dailyDigestHour": 8,
            "quietHours": {"enabled": True, "start": "18:00", "end": "08:00"},
        }
        status, saved = self.request("PUT", "/api/notification-preferences", preferences)
        self.assertEqual(status, 200, saved)
        status, current = self.request("GET", "/api/notifications")
        self.assertEqual(status, 200, current)
        # Alertas críticos não podem ser ocultados pelas preferências pessoais.
        self.assertEqual([item["id"] for item in current["items"]], [critical_id])
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE entity_type='notification' AND entity_id=?",
            (info_id,),
        ), 2)

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

    def test_whatsapp_webhook_creates_a_crm_conversation_and_respects_seller_scope(self):
        self.setup_admin()
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        secret = "whatsapp-app-secret-with-at-least-32-characters"
        verify_token = "verify-whatsapp-seccol"
        environment = {
            "SIVS_WHATSAPP_COMPANY_ID": str(company_id),
            "SIVS_WHATSAPP_PHONE_NUMBER_ID": "106540352242922",
            "SIVS_WHATSAPP_DISPLAY_PHONE": "+55 62 3333-0000",
            "SIVS_WHATSAPP_APP_SECRET": secret,
            "SIVS_WHATSAPP_VERIFY_TOKEN": verify_token,
            "SIVS_WHATSAPP_ACCESS_TOKEN": "",
            "SIVS_WHATSAPP_GRAPH_VERSION": "v23.0",
        }
        event = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "waba-test", "changes": [{"field": "messages", "value": {
                "messaging_product": "whatsapp",
                "metadata": {"display_phone_number": "+55 62 3333-0000",
                             "phone_number_id": "106540352242922"},
                "contacts": [{"wa_id": "5562999990000", "profile": {"name": "Ana Cliente"}}],
                "messages": [{"from": "5562999990000", "id": "wamid.TESTE-001",
                              "timestamp": str(int(time.time())), "type": "text",
                              "text": {"body": "Olá, preciso de uma certificação."}}],
            }}]}],
        }
        raw = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, environment, clear=False):
            status, challenge, headers = self.raw_request(
                "GET", "/api/integrations/whatsapp/webhook?hub.mode=subscribe&"
                f"hub.verify_token={urllib.parse.quote(verify_token)}&hub.challenge=420024",
                authenticated=False,
            )
            self.assertEqual(status, 200)
            self.assertEqual(challenge, b"420024")
            self.assertIn("text/plain", headers["content-type"])
            status, content, _headers = self.raw_request(
                "POST", "/api/integrations/whatsapp/webhook", raw,
                authenticated=False, extra_headers={"X-Hub-Signature-256": signature},
            )
            received = json.loads(content.decode("utf-8"))
            self.assertEqual(status, 200, received)
            self.assertEqual(received["received"], 1)
            status, content, _headers = self.raw_request(
                "POST", "/api/integrations/whatsapp/webhook", raw,
                authenticated=False, extra_headers={"X-Hub-Signature-256": signature},
            )
            self.assertEqual(json.loads(content.decode("utf-8"))["received"], 0)

            status, workspace = self.request("GET", "/api/whatsapp/workspace")
            self.assertEqual(status, 200, workspace)
            self.assertFalse(workspace["integration"]["configured"])
            self.assertEqual(workspace["selected"]["contact_name"], "Ana Cliente")
            self.assertEqual(workspace["messages"][0]["body"], "Olá, preciso de uma certificação.")
            self.assertIn("view_all_whatsapp", workspace["operations"])
            self.assertEqual(workspace["policy"]["outsideWindow"], "MANUAL_COMPLIANCE_REQUIRED")

        crm = self.db.connection().execute(
            "SELECT * FROM records WHERE company_id=? AND module='crm'", (company_id,),
        ).fetchall()
        self.assertEqual(len(crm), 1)
        self.assertEqual(json.loads(crm[0]["payload"])["origem"], "WhatsApp")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM whatsapp_messages"), 1)
        self.assertGreaterEqual(self.db.scalar("SELECT COUNT(*) FROM whatsapp_quick_replies"), 3)

        status, seller = self.request("POST", "/api/users", {
            "name": "Vendedora WhatsApp", "email": "vendedora.whatsapp@seccol.test",
            "password": "Senha-Vendedora-123", "role": "seller",
        })
        self.assertEqual(status, 201, seller)
        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "vendedora.whatsapp@seccol.test", "password": "Senha-Vendedora-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, modules = self.request("GET", "/api/modules")
        self.assertEqual(status, 200, modules)
        self.assertEqual(set(modules["actionPermissions"]["whatsapp"]), {
            "claim_whatsapp", "reply_whatsapp",
        })
        status, seller_workspace = self.request("GET", "/api/whatsapp/workspace")
        self.assertEqual(status, 200, seller_workspace)
        self.assertEqual(len(seller_workspace["conversations"]), 1)
        conversation_id = seller_workspace["conversations"][0]["id"]
        status, claimed = self.request(
            "POST", f"/api/whatsapp/conversations/{conversation_id}/claim", {},
        )
        self.assertEqual(status, 200, claimed)
        self.assertEqual(self.db.scalar(
            "SELECT assigned_user_id FROM whatsapp_conversations WHERE id=?", (conversation_id,),
        ), seller["id"])

    def test_uazapi_instance_qr_webhook_and_send_are_multi_company_and_server_only(self):
        self.setup_admin()
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        environment = {
            "SIVS_UAZAPI_API_TOKEN": "rotated-test-token-never-used-in-production",
            "SIVS_UAZAPI_CREATE_URL": (
                "https://grlwciflaotripbumhve.supabase.co/functions/v1/create-instance-url"
            ),
            "SIVS_UAZAPI_CREATE_HOSTS": "grlwciflaotripbumhve.supabase.co",
            "SIVS_UAZAPI_DEVICE_NAME": "SIVS Teste",
            "SIVS_WHATSAPP_MASTER_KEY": base64.b64encode(bytes(range(32))).decode("ascii"),
            "SIVS_PUBLIC_URL": "https://sivs.example.test",
        }
        calls = []

        def provider_response(request, timeout=0):
            calls.append(request)
            url = request.full_url
            if url.endswith("/create-instance-url"):
                headers = {key.lower(): value for key, value in request.header_items()}
                self.assertNotIn("authorization", headers)
                self.assertNotIn("apikey", headers)
                self.assertNotIn("token", headers)
                create_body = json.loads(request.data.decode("utf-8"))
                self.assertEqual(create_body["token"], environment["SIVS_UAZAPI_API_TOKEN"])
                return io.BytesIO(json.dumps({
                    "server_url": "https://tenant-test.uazapi.com",
                    "Instance Token": "instance-token-with-more-than-20-characters",
                    "instance": {"name": "instance-test"},
                }).encode())
            if url.endswith("/webhook"):
                body = json.loads(request.data.decode("utf-8"))
                self.assertRegex(body["url"], r"^https://sivs\.example\.test/api/integrations/whatsapp/uazapi/")
                self.assertEqual(body["events"], ["connection", "messages", "messages_update"])
                return io.BytesIO(b'{"ok":true}')
            if url.endswith("/instance/connect"):
                return io.BytesIO(json.dumps({
                    "connected": False,
                    "instance": {"status": "connecting", "qrcode": "aGVsbG8="},
                }).encode())
            if url.endswith("/instance/status"):
                return io.BytesIO(json.dumps({
                    "status": {"connected": True},
                    "instance": {"status": "connected", "phone": "556233330000",
                                 "profileName": "SECCOL"},
                }).encode())
            if url.endswith("/send/text"):
                body = json.loads(request.data.decode("utf-8"))
                self.assertEqual(body["number"], "5562999990000")
                self.assertEqual(body["text"], "Olá, Ana!")
                self.assertEqual(body["track_source"], "sivs")
                return io.BytesIO(b'{"messageid":"uazapi-out-001"}')
            if url.endswith("/instance") and request.method == "DELETE":
                return io.BytesIO(b'{"deleted":true}')
            raise AssertionError(f"Chamada externa inesperada: {request.method} {url}")

        with patch.dict(os.environ, environment, clear=False), patch(
            "server.urllib.request.urlopen", side_effect=provider_response,
        ):
            status, created = self.request("POST", "/api/whatsapp/instance", {})
            self.assertEqual(status, 201, created)
            self.assertEqual(created["instance"]["provider"], "UAZAPI")
            stored = self.db.connection().execute(
                "SELECT * FROM whatsapp_instances WHERE company_id=?", (company_id,),
            ).fetchone()
            self.assertNotIn(b"instance-token", bytes(stored["instance_token_cipher"]))
            status, other_company = self.request(
                "POST", "/api/companies", {"name": "Empresa sem WhatsApp"},
            )
            self.assertEqual(status, 201, other_company)
            status, _switched = self.request(
                "POST", "/api/company/switch", {"company_id": other_company["id"]},
            )
            self.assertEqual(status, 200)
            status, isolated_workspace = self.request("GET", "/api/whatsapp/workspace")
            self.assertEqual(status, 200, isolated_workspace)
            self.assertFalse(isolated_workspace["integration"]["configured"])
            self.assertEqual(isolated_workspace["conversations"], [])
            status, _switched = self.request(
                "POST", "/api/company/switch", {"company_id": company_id},
            )
            self.assertEqual(status, 200)

            status, connecting = self.request("POST", "/api/whatsapp/instance/connect", {})
            self.assertEqual(status, 200, connecting)
            self.assertEqual(connecting["qrcode"], "aGVsbG8=")
            status, connected = self.request("GET", "/api/whatsapp/instance/status")
            self.assertEqual(status, 200, connected)
            self.assertTrue(connected["instance"]["isConnected"])

            webhook_event = {
                "event": "messages", "instance": stored["instance_name"],
                "data": {
                    "messageid": "uazapi-in-001", "sender": "5562999990000@s.whatsapp.net",
                    "fromMe": False, "messageType": "text",
                    "text": "Preciso de calibração.", "created": utc_now(),
                    "chat": {"phone": "5562999990000", "wa_contactName": "Ana Cliente"},
                },
            }
            raw = json.dumps(webhook_event, ensure_ascii=False).encode("utf-8")
            status, content, _headers = self.raw_request(
                "POST", f"/api/integrations/whatsapp/uazapi/{stored['webhook_public_id']}",
                raw, authenticated=False,
            )
            self.assertEqual(status, 200, content)
            self.assertEqual(json.loads(content)["received"], 1)
            status, workspace = self.request("GET", "/api/whatsapp/workspace")
            self.assertEqual(status, 200, workspace)
            self.assertTrue(workspace["integration"]["connected"])
            self.assertEqual(workspace["selected"]["contact_name"], "Ana Cliente")
            self.assertNotIn("instance_token", json.dumps(workspace))

            status, sent = self.request(
                "POST", f"/api/whatsapp/conversations/{workspace['selected']['id']}/messages",
                {"text": "Olá, Ana!", "clientRequestId": "request_uazapi_test_0001"},
            )
            self.assertEqual(status, 201, sent)
            self.assertEqual(self.db.scalar(
                "SELECT external_id FROM whatsapp_messages WHERE client_request_id=?",
                ("request_uazapi_test_0001",),
            ), "uazapi-out-001")

            status, deleted = self.request("DELETE", "/api/whatsapp/instance")
            self.assertEqual(status, 200, deleted)
            self.assertEqual(self.db.scalar(
                "SELECT COUNT(*) FROM whatsapp_instances WHERE company_id=?", (company_id,),
            ), 0)

    def test_control_center_tracks_sessions_changes_errors_and_remote_termination(self):
        self.setup_admin()
        admin_cookie, admin_csrf = self.cookie, self.csrf
        status, created = self.request("POST", "/api/users", {
            "name": "Operador monitorado", "email": "monitorado@seccol.test",
            "password": "Senha-Monitorada-123", "role": "operator",
        })
        self.assertEqual(status, 201, created)

        overdue_date = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        status, operational_record = self.request("POST", "/api/records", {
            "module": "arquivos", "title": "Procedimento aguardando revisão",
            "status": "Ativo", "due_date": overdue_date,
            "payload": {
                "assunto": "Revisão de procedimento", "responsavel": "Operador monitorado",
                "identificador": "POP-TESTE-001", "categoria": "Procedimento",
            },
        })
        self.assertEqual(status, 201, operational_record)
        company_id = self.db.scalar("SELECT id FROM companies ORDER BY id LIMIT 1")
        admin_id = self.db.scalar("SELECT id FROM users WHERE email='admin@seccol.test'")
        monitored_id = created["id"]
        self.db.execute(
            """INSERT INTO approvals
               (company_id,record_id,approval_type,status,requested_by,requested_to,requested_at)
               VALUES(?,?,?,'Pendente',?,?,?)""",
            (company_id, operational_record["item"]["id"], "Revisão administrativa",
             admin_id, monitored_id, utc_now()),
        )

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
        monitored_team_member = next(item for item in center["team"] if item["id"] == monitored_id)
        self.assertEqual(monitored_team_member["readableModules"], len(ROLE_MODULES["operator"]))
        self.assertTrue(any(item["recordId"] == operational_record["item"]["id"]
                            and item["overdue"] for item in center["operations"]["work"]))
        self.assertEqual(center["operations"]["summary"]["pendingApprovals"], 1)
        self.assertEqual(center["operations"]["pendingApprovals"][0]["requestedTo"], "Operador monitorado")
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
        dashboard_item = next(
            item for item in dashboard["workItems"] if item["recordId"] == created["item"]["id"]
        )
        self.assertTrue(dashboard_item["requiredAction"])
        self.assertEqual(dashboard_item["timingLabel"], "Revisar")

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
            <cobr><dup><nDup>001</nDup><dVenc>2026-09-10</dVenc><vDup>20.00</vDup></dup></cobr>
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
        self.assertEqual(imported["parcels"], 1)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM records WHERE module='importacoes_xml'"
        ), 1)
        payable = self.db.connection().execute(
            "SELECT * FROM records WHERE company_id=1 AND module='contas_pagar'"
        ).fetchone()
        self.assertEqual(payable["amount"], 20)
        payable_payload = json.loads(payable["payload"])
        self.assertTrue(payable_payload["fornecedor_id"])
        self.assertEqual(payable_payload["tipo_parte"], "Fornecedor (F)")
        self.assertEqual(payable_payload["origem_modulo"], "importacoes_xml")
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM financial_document_origins WHERE financial_record_id=?",
            (payable["id"],),
        ), 1)
        payable_payload.update({
            "conta": "Banco XML", "forma_pagamento": "Boleto",
            "data_pagamento": "2026-09-10",
        })
        status, settled = self.request("PUT", f"/api/records/{payable['id']}", {
            "module": "contas_pagar", "title": payable["title"], "status": "Pago",
            "amount": payable["amount"], "due_date": payable["due_date"],
            "payload": payable_payload, "revision": payable["revision"],
        })
        self.assertEqual(status, 200, settled)
        cash = self.db.connection().execute(
            "SELECT amount,payload FROM records WHERE id=? AND module='caixa'",
            (settled["cashRecordId"],),
        ).fetchone()
        self.assertEqual(cash["amount"], 20)
        self.assertEqual(json.loads(cash["payload"])["tipo_movimento"], "Saída")

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

    def test_tender_coverage_retries_exact_failed_queries_and_alerts_terminal_failure(self):
        self.server._stop_workers.set()
        self.server._scheduler.join(timeout=2)
        self.setup_admin()
        now = utc_now()
        origin_job = self.db.execute(
            """INSERT INTO tender_jobs
               (company_id,status,request_json,progress,stage,created_by,created_at,finished_at)
               VALUES(1,'completed',?,100,'Pesquisa parcial',1,?,?)""",
            (json.dumps({"keywords": ["filtro HEPA", "cabine de segurança biológica"],
                         "days": 7}), now, now),
        ).lastrowid
        runner = object.__new__(SIVSHandler)
        runner.server = self.server
        runner._sync_tender_retry(origin_job, 1, {
            "keywords": ["filtro HEPA", "cabine de segurança biológica"], "days": 7,
        }, result={
            "failedQueries": ["filtro HEPA"], "errors": ["PNCP: HTTP 429"],
            "pagesChecked": 1,
        })
        retry = self.db.connection().execute(
            "SELECT * FROM tender_retry_queue WHERE origin_job_id=?", (origin_job,),
        ).fetchone()
        self.assertEqual(retry["status"], "PENDING")
        self.assertEqual(json.loads(retry["failed_queries_json"]), ["filtro HEPA"])
        status, coverage = self.request("GET", "/api/tenders/coverage")
        self.assertEqual(status, 200, coverage)
        self.assertEqual(coverage["coverage"]["health"], "ATTENTION")
        self.assertEqual(coverage["coverage"]["pendingRetries"], 1)

        self.db.execute(
            "UPDATE tender_retry_queue SET next_attempt_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), retry["id"]),
        )
        with patch("server.threading.Thread.start"):
            self.assertEqual(self.server._enqueue_due_tender_retries(), 1)
        queued = self.db.connection().execute(
            "SELECT * FROM tender_retry_queue WHERE id=?", (retry["id"],),
        ).fetchone()
        self.assertEqual(queued["status"], "RUNNING")
        self.assertEqual(queued["attempt_count"], 1)
        request_data = json.loads(self.db.scalar(
            "SELECT request_json FROM tender_jobs WHERE id=?", (queued["retry_job_id"],),
        ))
        self.assertEqual(request_data["_retryQueries"], ["filtro HEPA"])
        self.assertEqual(request_data["_coverageRetryId"], retry["id"])

        self.db.execute(
            "UPDATE tender_retry_queue SET attempt_count=5 WHERE id=?", (retry["id"],),
        )
        runner._sync_tender_retry(
            queued["retry_job_id"], 1, request_data,
            result={"failedQueries": ["filtro HEPA"], "errors": ["HTTP 429"],
                    "pagesChecked": 0},
        )
        terminal = self.db.connection().execute(
            "SELECT status,next_attempt_at FROM tender_retry_queue WHERE id=?", (retry["id"],),
        ).fetchone()
        self.assertEqual(terminal["status"], "ABANDONED")
        self.assertIsNone(terminal["next_attempt_at"])
        self.assertEqual(self.server._refresh_tender_coverage_alerts(), 1)
        notification = self.db.connection().execute(
            """SELECT title,level,module,target FROM notifications
               WHERE company_id=1 AND module='editais' ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        self.assertEqual(notification["level"], "error")
        self.assertEqual(notification["target"], "editais")

    def test_tender_retry_revalidates_search_permission_before_enqueue(self):
        self.server._stop_workers.set()
        self.server._scheduler.join(timeout=2)
        self.setup_admin()
        now = utc_now()
        origin_job = self.db.execute(
            """INSERT INTO tender_jobs
               (company_id,status,request_json,progress,stage,created_by,created_at,finished_at)
               VALUES(1,'completed','{}',100,'Parcial',1,?,?)""",
            (now, now),
        ).lastrowid
        retry_id = self.db.execute(
            """INSERT INTO tender_retry_queue
               (company_id,origin_job_id,request_json,failed_queries_json,status,
                attempt_count,next_attempt_at,created_at,updated_at)
               VALUES(1,?,'{}','[\"filtro HEPA\"]','PENDING',0,?,?,?)""",
            (origin_job, now, now, now),
        ).lastrowid
        self.db.execute(
            "UPDATE company_memberships SET permissions=? WHERE company_id=1 AND user_id=1",
            (json.dumps({"actions": {"editais": []}}),),
        )
        self.assertEqual(self.server._enqueue_due_tender_retries(), 0)
        retry = self.db.connection().execute(
            "SELECT status,last_error FROM tender_retry_queue WHERE id=?", (retry_id,),
        ).fetchone()
        self.assertEqual(retry["status"], "ABANDONED")
        self.assertIn("permissão", retry["last_error"])
        self.server.db.close_thread_connection()

    def test_tender_autonomy_captures_without_value_and_converts_strict_match(self):
        self.setup_admin()
        status, saved = self.request("PUT", "/api/settings", {"tenderAutonomy": {
            "enabled": True, "captureRegardlessOfValue": True,
            "captureSingleCatalogItem": False,
            "autoConvertCompatible": True, "externalSubmission": True,
            "externalBidding": True,
        }})
        self.assertEqual(status, 200, saved)
        policy = json.loads(self.db.scalar(
            "SELECT value FROM company_settings WHERE company_id=1 AND key='tenderAutonomy'"
        ))
        self.assertFalse(policy["externalSubmission"])
        self.assertFalse(policy["externalBidding"])
        self.assertTrue(policy["captureSingleCatalogItem"])
        started = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,agency,modality,source_url,deadline,
                estimated_value,matched_terms,relevance_score,status,raw_json,created_at,
                updated_at,company_id)
               VALUES('pncp','12345678000195-1-42/2026','Pregão autônomo','Calibração e filtro HEPA',
                      'Órgão teste','Pregão eletrônico','https://pncp.gov.br/app/editais/teste',
                      '2026-09-15',NULL,'[]',95,'Novo',?,?,?,1)""",
            (json.dumps({"_strict_match": True}), started, started),
        ).lastrowid
        runner = object.__new__(SIVSHandler)
        runner.server = self.server
        def fake_official_fetch(url, **_kwargs):
            if url.endswith("/itens"):
                return [{"numeroItem": 1, "orcamentoSigiloso": True}]
            if url.endswith("/arquivos"):
                return [{"titulo": "Edital", "url": "https://pncp.gov.br/arquivo.pdf"}]
            return {"orcamentoSigilosoCodigo": 1, "objetoCompra": "Calibração"}
        runner.fetch_tender_json = fake_official_fetch
        outcome = runner.autonomous_tender_prepare(1, 1, started)
        self.assertEqual(outcome["capturedRegardlessOfValue"], 1)
        self.assertEqual(outcome["officialDetailsFetched"], 1)
        self.assertEqual(outcome["converted"], 1)
        converted = self.db.connection().execute(
            "SELECT converted_record_id,status FROM tender_results WHERE id=?", (result_id,),
        ).fetchone()
        self.assertEqual(converted["status"], "Convertido")
        record = self.db.connection().execute(
            "SELECT amount,payload FROM records WHERE id=?", (converted["converted_record_id"],),
        ).fetchone()
        self.assertIsNone(record["amount"])
        payload = json.loads(record["payload"])
        self.assertTrue(payload["automacao_valor_ignorado_na_captacao"])
        self.assertEqual(payload["automacao_portal_status"], "AGENTE_SHADOW_APOS_APROVACAO")
        self.assertFalse(payload["automacao_portal_efeito_externo"])
        detail = self.db.connection().execute(
            "SELECT documents_json,value_source FROM tender_details WHERE tender_result_id=?",
            (result_id,),
        ).fetchone()
        self.assertEqual(detail["value_source"], "sigiloso")
        self.assertEqual(len(json.loads(detail["documents_json"])), 1)

    def test_tender_autonomy_revalidates_actor_permissions_before_converting(self):
        self.setup_admin()
        started = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,agency,modality,source_url,deadline,
                estimated_value,matched_terms,relevance_score,status,raw_json,created_at,
                updated_at,company_id)
               VALUES('pncp','auto-denied','Pregão restrito','Calibração compatível',
                      'Órgão teste','Pregão eletrônico','https://pncp.gov.br/app/editais/teste',
                      '2026-09-15',1000,'[]',95,'Novo',?,?,?,1)""",
            (json.dumps({"_strict_match": True}), started, started),
        ).lastrowid
        self.db.execute(
            "UPDATE company_memberships SET permissions=? WHERE company_id=1 AND user_id=1",
            (json.dumps({"deny_write": ["licitacoes"]}),),
        )
        runner = object.__new__(SIVSHandler)
        runner.server = self.server
        outcome = runner.autonomous_tender_prepare(1, 1, started)
        self.assertEqual(outcome["converted"], 0)
        self.assertEqual(outcome["blocked"][0]["reason"], "AUTOMATION_ACTOR_PERMISSION_REQUIRED")
        self.assertIsNone(self.db.scalar(
            "SELECT converted_record_id FROM tender_results WHERE id=?", (result_id,),
        ))

    def test_tender_autonomy_enters_generic_notice_with_one_official_catalog_item(self):
        self.setup_admin()
        started = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,agency,modality,source_url,deadline,
                estimated_value,matched_terms,relevance_score,status,raw_json,created_at,
                updated_at,company_id)
               VALUES('pncp','12345678000195-1-43/2026','Pregão de equipamentos',
                      'Aquisição de equipamentos hospitalares','Órgão teste','Pregão eletrônico',
                      'https://pncp.gov.br/app/editais/teste','2026-09-15',5000,?,45,
                      'Analisar',?,?,?,1)""",
            (json.dumps(["Cabine de Segurança Biológica"]), json.dumps({
                "_strict_match": False,
                "_candidate_item_match": True,
                "_match_scope": "PENDING_OFFICIAL_ITEM",
            }), started, started),
        ).lastrowid
        runner = object.__new__(SIVSHandler)
        runner.server = self.server

        def fake_official_fetch(url, **_kwargs):
            if url.endswith("/itens"):
                return [{
                    "numeroItem": 7,
                    "descricao": "Cabine de Segurança Biológica classe II tipo A2",
                }, {
                    "numeroItem": 8,
                    "descricao": "Mesa administrativa em madeira",
                }]
            if url.endswith("/arquivos"):
                return [{"titulo": "Edital", "url": "https://pncp.gov.br/edital.pdf"}]
            return {"objetoCompra": "Aquisição de equipamentos hospitalares"}

        runner.fetch_tender_json = fake_official_fetch
        outcome = runner.autonomous_tender_prepare(1, 1, started)
        self.assertEqual(outcome["singleItemMatches"], 1)
        self.assertEqual(outcome["converted"], 1)
        converted = self.db.connection().execute(
            "SELECT converted_record_id,raw_json FROM tender_results WHERE id=?", (result_id,),
        ).fetchone()
        raw = json.loads(converted["raw_json"])
        self.assertEqual(raw["_match_scope"], "OFFICIAL_ITEM")
        self.assertEqual(raw["_catalog_priority"], "LOW")
        record = self.db.connection().execute(
            "SELECT payload FROM records WHERE id=?", (converted["converted_record_id"],),
        ).fetchone()
        payload = json.loads(record["payload"])
        self.assertEqual(payload["automacao_prioridade_catalogo"], "LOW")
        self.assertEqual(payload["automacao_itens_oficiais_compativeis"][0]["item"], 7)

    def test_tender_autonomy_creates_continuous_schedule_without_an_operator(self):
        self.server._stop_workers.set()
        self.server._scheduler.join(timeout=2)
        self.setup_admin()
        self.db.execute("DELETE FROM search_schedules WHERE company_id=1")
        status, custom = self.request("POST", "/api/tenders/schedules", {
            "name": "Plano comercial diário", "frequency": "daily",
            "keywords": ["filtro HEPA"], "days": 7,
        })
        self.assertEqual(status, 201, custom)
        self.assertEqual(self.server._ensure_autonomous_tender_schedules(), 1)
        self.assertEqual(self.server._ensure_autonomous_tender_schedules(), 0)
        schedule = self.db.connection().execute(
            """SELECT name,frequency,active,next_run_at,created_by FROM search_schedules
               WHERE company_id=1 AND name='Agente autônomo de licitações'"""
        ).fetchone()
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM search_schedules WHERE company_id=1"
        ), 2)
        self.assertEqual(schedule["name"], "Agente autônomo de licitações")
        self.assertEqual(schedule["frequency"], "every_2_hours")
        self.assertEqual(schedule["active"], 1)
        self.assertIsNotNone(schedule["next_run_at"])
        self.assertEqual(schedule["created_by"], 1)
        status, saved = self.request("PUT", "/api/settings", {
            "tenderAutonomy": {"enabled": False},
        })
        self.assertEqual(status, 200, saved)
        self.assertEqual(self.server._ensure_autonomous_tender_schedules(), 0)
        self.assertEqual(self.db.scalar(
            """SELECT active FROM search_schedules WHERE company_id=1
               AND name='Agente autônomo de licitações'"""
        ), 0)
        self.assertEqual(self.db.scalar(
            """SELECT active FROM search_schedules WHERE company_id=1
               AND name='Plano comercial diário'"""
        ), 1)
        self.server.db.close_thread_connection()

    def test_due_tender_schedule_waits_for_active_retry_without_skipping_rotation(self):
        self.server._stop_workers.set()
        self.server._scheduler.join(timeout=2)
        self.setup_admin()
        self.server._ensure_autonomous_tender_schedules()
        due_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(
            timespec="seconds"
        )
        schedule_id = self.db.scalar(
            """SELECT id FROM search_schedules WHERE company_id=1
               AND name='Agente autônomo de licitações'"""
        )
        self.db.execute(
            "UPDATE search_schedules SET next_run_at=? WHERE id=?", (due_at, schedule_id),
        )
        self.db.execute(
            """INSERT INTO tender_jobs
               (company_id,status,request_json,progress,stage,created_by,created_at)
               VALUES(1,'running','{}',40,'Retentativa em execução',1,?)""",
            (utc_now(),),
        )
        self.server._enqueue_due_tender_schedules()
        self.assertEqual(self.db.scalar(
            "SELECT next_run_at FROM search_schedules WHERE id=?", (schedule_id,),
        ), due_at)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM tender_jobs WHERE company_id=1"
        ), 1)
        self.server.db.close_thread_connection()

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

    def test_tender_document_vault_checklist_and_package_are_guarded(self):
        self.setup_admin()
        self.assertGreaterEqual(len(TENDER_COMPANY_DOCUMENT_CATALOG), 45)
        catalog_keys = {item["key"] for item in TENDER_COMPANY_DOCUMENT_CATALOG}
        self.assertTrue({
            "partner_registry_or_board_certificate", "financial_indices_calculation",
            "bid_guarantee", "technical_team_credentials", "sample_or_catalog",
            "independent_proposal_declaration", "price_proposal_signed",
            "contract_signature_documents",
        }.issubset(catalog_keys))
        pdf = b"%PDF-1.7\n% cofre documental de teste"
        status, missing_expiry = self.request("POST", "/api/tender-documents", {
            "documentType": "federal_tax_certificate",
            "filename": "certidao-sem-validade.pdf",
            "content": base64.b64encode(pdf).decode("ascii"),
        })
        self.assertEqual(status, 400, missing_expiry)
        self.assertIn("Informe a validade", missing_expiry["message"])
        status, uploaded = self.request("POST", "/api/tender-documents", {
            "documentType": "federal_tax_certificate",
            "title": "Certidão federal",
            "issuer": "Receita Federal",
            "issueDate": "2026-08-01",
            "expiresAt": "2026-12-31",
            "scope": "ALL",
            "filename": "certidao-federal.pdf",
            "content": base64.b64encode(pdf).decode("ascii"),
        })
        self.assertEqual(status, 201, uploaded)
        document_id = uploaded["id"]
        status, vault = self.request("GET", "/api/tender-documents")
        self.assertEqual(status, 200, vault)
        self.assertEqual(vault["items"][0]["validityStatus"], "VALID")
        self.assertNotIn("content", vault["items"][0])

        now = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,matched_terms,relevance_score,status,
                raw_json,created_at,updated_at,company_id)
               VALUES('documents','documents-1','Pregão documental','Objeto','[]',80,'Novo','{}',?,?,1)""",
            (now, now),
        ).lastrowid
        status, detail = self.request("GET", f"/api/tenders/results/{result_id}")
        self.assertEqual(status, 200, detail)
        participation = detail["item"]["participationDocuments"]
        federal = next(item for item in participation["requirements"]
                       if item["document_type"] == "federal_tax_certificate")
        self.assertEqual(federal["candidates"][0]["id"], document_id)

        checklist = {
            "confirmed": True,
            "qualificationWithInitialProposal": False,
            "notes": "Conferido no edital.",
            "requirements": [{
                "documentType": "federal_tax_certificate", "required": True,
                "stage": "QUALIFICATION", "selectedDocumentId": document_id,
                "sourceReference": "item 8.4, pág. 17",
            }, {
                "documentType": "pcd_quota_declaration", "required": True,
                "stage": "INITIAL_PROPOSAL", "selectedDocumentId": None,
                "sourceReference": "item 5.2 do edital",
            }],
        }
        missing_reference = json.loads(json.dumps(checklist))
        missing_reference["requirements"][0]["sourceReference"] = ""
        status, blocked = self.request(
            "PUT", f"/api/tenders/results/{result_id}/participation-documents",
            missing_reference,
        )
        self.assertEqual(status, 409, blocked)
        self.assertEqual(blocked["error"], "checklist_blocked")

        status, saved = self.request(
            "PUT", f"/api/tenders/results/{result_id}/participation-documents", checklist,
        )
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["participationDocuments"]["profile"]["checklistStatus"], "CONFIRMED")
        status, content, headers = self.raw_request(
            "GET", f"/api/tenders/results/{result_id}/participation-package?stage=QUALIFICATION",
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            self.assertIn("MANIFESTO.json", archive.namelist())
            manifest = json.loads(archive.read("MANIFESTO.json"))
            self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(pdf).hexdigest())
            self.assertTrue(any(name.endswith("certidao-federal.pdf") for name in archive.namelist()))

        status, _ = self.request(
            "PUT", f"/api/tender-documents/{document_id}", {"status": "ARCHIVED"},
        )
        self.assertEqual(status, 200)
        status, blocked_package = self.request(
            "GET", f"/api/tenders/results/{result_id}/participation-package?stage=QUALIFICATION",
        )
        self.assertEqual(status, 409, blocked_package)
        self.assertEqual(blocked_package["error"], "checklist_not_confirmed")
        self.assertEqual(self.db.scalar(
            "SELECT checklist_status FROM tender_participation_profiles WHERE tender_result_id=?",
            (result_id,),
        ), "DRAFT")

    def test_tender_multiple_custom_documents_and_alerts_are_idempotent(self):
        self.setup_admin()

        def upload(document_type, title, suffix, expires_at=None):
            content = f"%PDF-1.7\n{title}-{suffix}".encode("utf-8")
            status, response = self.request("POST", "/api/tender-documents", {
                "documentType": document_type, "title": title, "scope": "ALL",
                "expiresAt": expires_at, "filename": f"{suffix}.pdf",
                "content": base64.b64encode(content).decode("ascii"),
            })
            self.assertEqual(status, 201, response)
            return response["id"], content

        today = datetime.now(timezone.utc).date()
        technical_one, body_one = upload(
            "technical_capacity_certificate", "Atestado hospitalar", "atestado-hospital",
        )
        technical_two, body_two = upload(
            "technical_capacity_certificate", "Atestado farmacêutico", "atestado-farma",
        )
        custom_document, custom_body = upload(
            "other_edital_document", "Declaração do Anexo VII", "anexo-vii",
        )
        expiring_document, _ = upload(
            "federal_tax_certificate", "Certidão federal", "certidao-alerta",
            (today + timedelta(days=7)).isoformat(),
        )
        now = utc_now()
        deadline = (today + timedelta(days=3)).isoformat()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,agency,deadline,matched_terms,
                relevance_score,status,raw_json,created_at,updated_at,company_id)
               VALUES('multiple','multiple-1','Pregão com anexos','Serviço técnico','Órgão teste',?,
                      '[]',90,'Novo','{}',?,?,1)""",
            (deadline, now, now),
        ).lastrowid
        checklist = {
            "confirmed": True, "qualificationWithInitialProposal": False,
            "requirements": [{
                "documentType": "technical_capacity_certificate", "required": True,
                "stage": "QUALIFICATION",
                "selectedDocumentIds": [technical_one, technical_two],
                "sourceReference": "item 9.7 e subitens",
            }, {
                "documentType": "custom:anexo_vii_001", "title": "Declaração conforme Anexo VII",
                "custom": True, "portalDeclaration": False, "required": True,
                "stage": "INITIAL_PROPOSAL", "selectedDocumentIds": [custom_document],
                "sourceReference": "Anexo VII, pág. 42",
            }],
        }
        status, saved = self.request(
            "PUT", f"/api/tenders/results/{result_id}/participation-documents", checklist,
        )
        self.assertEqual(status, 200, saved)
        requirements = saved["participationDocuments"]["requirements"]
        technical = next(item for item in requirements
                         if item["document_type"] == "technical_capacity_certificate")
        custom = next(item for item in requirements if item["document_type"] == "custom:anexo_vii_001")
        self.assertEqual(technical["selected_document_ids"], [technical_one, technical_two])
        self.assertTrue(custom["is_custom"])
        self.assertEqual(custom["vault_document_type"], "other_edital_document")

        status, package, _ = self.raw_request(
            "GET", f"/api/tenders/results/{result_id}/participation-package?stage=QUALIFICATION",
        )
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            manifest = json.loads(archive.read("MANIFESTO.json"))
            self.assertEqual(len(manifest["files"]), 2)
            self.assertEqual(
                {entry["sha256"] for entry in manifest["files"]},
                {hashlib.sha256(body_one).hexdigest(), hashlib.sha256(body_two).hexdigest()},
            )
        status, custom_package, _ = self.raw_request(
            "GET", f"/api/tenders/results/{result_id}/participation-package?stage=INITIAL_PROPOSAL",
        )
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(custom_package)) as archive:
            manifest = json.loads(archive.read("MANIFESTO.json"))
            self.assertEqual(manifest["files"][0]["title"], "Declaração conforme Anexo VII")
            self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(custom_body).hexdigest())

        created = self.server._refresh_tender_alerts()
        alert_count = self.db.scalar("SELECT COUNT(*) FROM notification_alerts")
        self.assertGreaterEqual(created, 2)
        self.assertEqual(self.server._refresh_tender_alerts(), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM notification_alerts"), alert_count)
        status, notifications = self.request("GET", "/api/notifications")
        self.assertEqual(status, 200, notifications)
        titles = {item["title"] for item in notifications["items"]}
        self.assertIn("Documento de licitação próximo do vencimento", titles)
        self.assertIn("Prazo de proposta se aproxima", titles)
        self.assertTrue(all(item["module"] == "editais" for item in notifications["items"]))

        tender_alert = self.db.connection().execute(
            """SELECT id,notification_id FROM notification_alerts
               WHERE company_id=1 AND entity_type='tender_result' AND entity_id=?""",
            (result_id,),
        ).fetchone()
        self.assertIsNotNone(tender_alert)
        self.db.execute(
            "UPDATE tender_results SET deadline=? WHERE id=? AND company_id=1",
            ((today + timedelta(days=20)).isoformat(), result_id),
        )
        self.server._refresh_tender_alerts()
        self.assertEqual(self.db.scalar(
            """SELECT COUNT(*) FROM notification_alerts
               WHERE company_id=1 AND entity_type='tender_result' AND entity_id=?""",
            (result_id,),
        ), 0)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM notifications WHERE id=?", (tender_alert["notification_id"],),
        ), 1)
        resolved_alert = self.db.connection().execute(
            "SELECT resolved_at,resolution_note FROM notifications WHERE id=?",
            (tender_alert["notification_id"],),
        ).fetchone()
        self.assertIsNotNone(resolved_alert["resolved_at"])
        self.assertIn("prazo", resolved_alert["resolution_note"].lower())

        # Simula a virada do dia: documento antes valido passa a estar vencido.
        self.db.execute(
            "UPDATE company_tender_documents SET expires_at=? WHERE id=? AND company_id=1",
            ((today - timedelta(days=1)).isoformat(), technical_two),
        )
        self.assertGreaterEqual(self.server._refresh_tender_alerts(), 1)
        self.assertEqual(self.db.scalar(
            "SELECT checklist_status FROM tender_participation_profiles WHERE tender_result_id=?",
            (result_id,),
        ), "DRAFT")
        invalidation_audit = self.db.connection().execute(
            """SELECT company_id,detail FROM audit_log
               WHERE action='invalidate' AND entity_type='tender_document_checklist'
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        self.assertEqual(invalidation_audit["company_id"], 1)
        self.assertEqual(json.loads(invalidation_audit["detail"])["reason"],
                         "expired_company_document")

        second_company = self.db.execute(
            "INSERT INTO companies(name,created_at,updated_at) VALUES('Outra empresa',?,?)",
            (now, now),
        ).lastrowid
        foreign_document = self.db.execute(
            """INSERT INTO company_tender_documents
               (company_id,document_type,title,scope,status,filename,mime_type,content,size,
                sha256,created_at,updated_at)
               VALUES(?,'technical_capacity_certificate','Atestado externo','ALL','ACTIVE',
                      'externo.pdf','application/pdf',?,?,?, ?,?)""",
            (second_company, body_one, len(body_one), hashlib.sha256(body_one).hexdigest(), now, now),
        ).lastrowid
        foreign = json.loads(json.dumps(checklist))
        foreign["confirmed"] = False
        foreign["requirements"][0]["selectedDocumentIds"] = [foreign_document]
        status, rejected = self.request(
            "PUT", f"/api/tenders/results/{result_id}/participation-documents", foreign,
        )
        self.assertEqual(status, 400, rejected)
        self.assertIn("não pertence", rejected["message"])
        self.assertIsNotNone(expiring_document)

    def test_tender_commercial_proposal_is_versioned_segregated_and_packaged(self):
        self.setup_admin()
        admin_cookie, admin_csrf = self.cookie, self.csrf
        now = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,agency,modality,source_url,deadline,
                estimated_value,matched_terms,relevance_score,status,raw_json,created_at,
                updated_at,company_id)
               VALUES('proposal','proposal-1','Pregão comercial','Fornecimento de instrumentos',
                      'Órgão teste','Pregão eletrônico','https://pncp.gov.br/app/editais/teste',
                      '2026-09-15',1000,'[]',95,'Novo','{}',?,?,1)""",
            (now, now),
        ).lastrowid
        self.db.execute(
            """INSERT INTO tender_details
               (tender_result_id,company_id,official_data,items_json,documents_json,
                value_source,analysis_json,refreshed_at)
               VALUES(?,1,'{}',?,'[]','items','{}',?)""",
            (result_id, json.dumps([{
                "numeroItem": 7, "descricao": "Instrumento de medição calibrado",
                "quantidade": 2, "unidadeMedida": "UN",
                "valorUnitarioEstimado": 175.50,
            }]), now),
        )
        status, approver = self.request("POST", "/api/users", {
            "name": "Aprovadora de propostas",
            "email": "aprovadora.proposta@seccol.test",
            "password": "Senha-Proposta-123",
            "role": "operator",
            "effectivePermissions": {"read": ["editais"], "write": [], "export": []},
            "effectiveActions": {"editais": ["view_values", "decide_approval"]},
            "effectiveCapabilities": {"audit": False, "trash": False, "approvals": True},
        })
        self.assertEqual(status, 201, approver)
        status, inventory = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, inventory)
        product_id = inventory["products"][0]["id"]
        warehouse_id = inventory["warehouses"][0]["id"]
        status, movement = self.request("POST", "/api/inventory/movements", {
            "movementType": "ADJUSTMENT_IN", "warehouseId": warehouse_id,
            "productId": product_id, "quantity": "2", "lot": "PROPOSTA-TESTE",
            "unitCost": "100.00", "originType": "INITIAL_BALANCE",
            "originId": "PROPOSTA-001", "reason": "Custo conferido para proposta",
        })
        self.assertEqual(status, 201, movement)
        status, service = self.request("POST", "/api/records", {
            "module": "catalogo_servicos", "title": "Certificação de área limpa",
            "status": "Ativo", "amount": 500, "payload": {
                "codigo": "SERV-ACL", "categoria": "Certificação",
                "tipo_servico": "Área limpa", "descricao": "Certificação de área limpa",
                "custo_referencia": 300,
                "fonte_oficial": "https://seccol.com.br/servicos/area-limpa",
                "verificado_em": "2026-08-22", "assunto": "Certificação de área limpa",
                "relacionamentos": [],
            },
        })
        self.assertEqual(status, 201, service)
        service_id = service["item"]["id"]
        status, detail = self.request("GET", f"/api/tenders/results/{result_id}")
        self.assertEqual(status, 200, detail)
        suggestion = detail["item"]["commercialProposal"]["suggestedItems"][0]
        self.assertEqual(suggestion["sourceKind"], "PNCP")
        self.assertEqual(suggestion["sourceItemNumber"], "7")
        self.assertEqual(suggestion["referencePrice"], 175.5)
        proposal_catalog = detail["item"]["commercialProposal"]["catalog"]
        product_catalog = next(item for item in proposal_catalog if item["id"] == product_id)
        service_catalog = next(item for item in proposal_catalog if item["id"] == service_id)
        self.assertEqual(product_catalog["defaultCost"], 100)
        self.assertEqual(product_catalog["availableQuantity"], 2)
        self.assertEqual(product_catalog["costSource"], "INVENTORY_AVERAGE")
        self.assertEqual(service_catalog["defaultPrice"], 500)
        self.assertEqual(service_catalog["defaultCost"], 300)
        self.assertEqual(service_catalog["costSource"], "CATALOG_REFERENCE")
        proposal_body = {
            "expectedVersion": 0,
            "items": [{
                "sourceKind": "MANUAL", "sourceItemNumber": "1",
                "sourceReference": "item 4.1, página 12",
                "description": "Instrumento de medição calibrado", "unit": "UN",
                "quantity": "2", "unitCost": "100.00",
                "minimumUnitPrice": "120.00", "unitPrice": "150.00",
                "catalogRecordId": product_id, "supplyMode": "STOCK",
            }, {
                "sourceKind": "MANUAL", "sourceItemNumber": "2",
                "sourceReference": "item 4.2, página 13",
                "description": "Certificação de área limpa", "unit": "UN",
                "quantity": "1", "unitCost": "300.00",
                "minimumUnitPrice": "350.00", "unitPrice": "500.00",
                "catalogRecordId": service_id, "supplyMode": "SERVICE_CAPACITY",
            }],
            "commercial": {
                "validityDays": 60, "deliveryTerms": "Entrega em até 20 dias",
                "paymentTerms": "Pagamento em 30 dias", "warrantyTerms": "12 meses",
                "notes": "Valores conferidos pelo responsável comercial.",
            },
        }
        below_cost = json.loads(json.dumps(proposal_body))
        below_cost["items"][0]["unitCost"] = "90.00"
        status, blocked = self.request(
            "PUT", f"/api/tenders/results/{result_id}/commercial-proposal", below_cost,
        )
        self.assertEqual(status, 400, blocked)
        self.assertIn("custo interno vigente", blocked["message"])
        below_floor = json.loads(json.dumps(proposal_body))
        below_floor["items"][0]["unitPrice"] = "110.00"
        status, blocked = self.request(
            "PUT", f"/api/tenders/results/{result_id}/commercial-proposal", below_floor,
        )
        self.assertEqual(status, 400, blocked)
        self.assertIn("abaixo do piso", blocked["message"])

        status, saved = self.request(
            "PUT", f"/api/tenders/results/{result_id}/commercial-proposal", proposal_body,
        )
        self.assertEqual(status, 200, saved)
        proposal = saved["commercialProposal"]["proposal"]
        self.assertEqual(proposal["version"], 1)
        self.assertEqual(proposal["totals"]["cost"], 500.0)
        self.assertEqual(proposal["totals"]["price"], 800.0)

        status, conflict = self.request(
            "PUT", f"/api/tenders/results/{result_id}/commercial-proposal", proposal_body,
        )
        self.assertEqual(status, 409, conflict)
        self.assertEqual(conflict["error"], "proposal_conflict")
        status, checklist_blocked = self.request(
            "POST", f"/api/tenders/results/{result_id}/commercial-proposal/submit",
            {"expectedVersion": 1},
        )
        self.assertEqual(status, 409, checklist_blocked)
        self.assertEqual(checklist_blocked["error"], "proposal_blocked")

        status, checklist = self.request(
            "PUT", f"/api/tenders/results/{result_id}/participation-documents", {
                "confirmed": True, "qualificationWithInitialProposal": False,
                "notes": "Edital conferido sem exigências adicionais.", "requirements": [],
            },
        )
        self.assertEqual(status, 200, checklist)
        status, submitted = self.request(
            "POST", f"/api/tenders/results/{result_id}/commercial-proposal/submit",
            {"expectedVersion": 1},
        )
        self.assertEqual(status, 409, submitted)
        self.assertEqual(submitted["error"], "proposal_blocked")
        self.assertIn("Converta a oportunidade", submitted["message"])
        status, converted = self.request("POST", f"/api/tenders/convert/{result_id}", {})
        self.assertEqual(status, 200, converted)
        operational_record_id = converted["recordId"]
        status, submitted = self.request(
            "POST", f"/api/tenders/results/{result_id}/commercial-proposal/submit",
            {"expectedVersion": 1},
        )
        self.assertEqual(status, 200, submitted)
        self.assertEqual(submitted["commercialProposal"]["proposal"]["status"],
                         "PENDING_APPROVAL")
        status, own_decision = self.request(
            "POST", f"/api/tenders/results/{result_id}/commercial-proposal/decision", {
                "expectedVersion": 1, "decision": "APPROVED", "comment": "Aprovada.",
            },
        )
        self.assertEqual(status, 403, own_decision)
        self.assertEqual(own_decision["error"], "segregation_required")

        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "aprovadora.proposta@seccol.test", "password": "Senha-Proposta-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, approved = self.request(
            "POST", f"/api/tenders/results/{result_id}/commercial-proposal/decision", {
                "expectedVersion": 1, "decision": "APPROVED",
                "comment": "Custos, piso e condições comerciais conferidos.",
            },
        )
        self.assertEqual(status, 200, approved)
        self.assertEqual(approved["commercialProposal"]["proposal"]["status"], "APPROVED")
        operational = self.db.connection().execute(
            "SELECT * FROM records WHERE id=? AND company_id=1", (operational_record_id,),
        ).fetchone()
        operational_payload = json.loads(operational["payload"])
        self.assertEqual(operational["amount"], 800)
        self.assertEqual(operational["status"], "Captação")
        self.assertEqual(operational_payload["etapa"], "Captação")
        self.assertEqual(operational_payload["proposta_comercial_status"], "APROVADA_INTERNA")
        self.assertEqual(operational_payload["proposta_comercial_versao_aprovada"], 1)
        self.assertEqual(operational_payload["proposta_comercial_valor_centavos"], 80000)
        status, forbidden_package = self.request(
            "GET", f"/api/tenders/results/{result_id}/commercial-proposal-package",
        )
        self.assertEqual(status, 403, forbidden_package)

        self.cookie, self.csrf = admin_cookie, admin_csrf
        status, package, headers = self.raw_request(
            "GET", f"/api/tenders/results/{result_id}/commercial-proposal-package",
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"PROPOSTA-COMERCIAL.pdf", "ITENS.csv", "MANIFESTO.json"},
            )
            manifest = json.loads(archive.read("MANIFESTO.json"))
            self.assertEqual(manifest["version"], 1)
            self.assertEqual(manifest["status"], "APPROVED")
            self.assertEqual(manifest["totalPriceCents"], 80000)

        status, detail = self.request("GET", f"/api/tenders/results/{result_id}")
        self.assertEqual(status, 200, detail)
        agent = detail["item"]["portalAgent"]
        self.assertEqual(agent["policy"]["mode"], "SHADOW")
        self.assertEqual(agent["policy"]["status"], "ARMED")
        self.assertEqual(agent["policy"]["approved_total_cents"], 80000)
        self.assertEqual(agent["policy"]["floor_total_cents"], 59000)
        self.assertEqual(agent["runs"][0]["status"], "RUNNING")
        self.assertTrue(agent["receipts"])
        self.assertTrue(all(not receipt["external_effect"] for receipt in agent["receipts"]))
        self.assertFalse(agent["viewerAvailable"])
        status, viewer_missing = self.request(
            "POST", f"/api/tenders/results/{result_id}/portal-agent/viewer", {},
        )
        self.assertEqual(status, 409, viewer_missing)
        self.assertEqual(viewer_missing["error"], "viewer_not_configured")
        with patch("server.TENDER_AGENT_VIEWER_URL", "https://viewer.seccol.test/sessao"), patch(
            "server.TENDER_AGENT_VIEWER_SECRET", "viewer-test-secret-with-at-least-32-characters",
        ):
            status, viewer = self.request(
                "POST", f"/api/tenders/results/{result_id}/portal-agent/viewer", {},
            )
            self.assertEqual(status, 200, viewer)
            self.assertTrue(viewer["viewerUrl"].startswith("https://viewer.seccol.test/sessao?ticket=v1."))
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE action='open_viewer' AND company_id=1",
        ), 1)

        bid_event = {
            "phase": "DISPUTE_OPEN", "currentBest": "790.00",
            "suggestedBid": "789.00", "idempotencyKey": "portal-event-proposal-1",
        }
        status, evaluated = self.request(
            "POST", f"/api/tenders/results/{result_id}/portal-agent/evaluate", bid_event,
        )
        self.assertEqual(status, 200, evaluated)
        self.assertEqual(evaluated["authorizedValue"], 789.0)
        self.assertEqual(evaluated["executionState"], "COMPLETED")
        status, duplicate = self.request(
            "POST", f"/api/tenders/results/{result_id}/portal-agent/evaluate", bid_event,
        )
        self.assertEqual(status, 200, duplicate)
        self.assertTrue(duplicate["duplicate"])
        status, floor_blocked = self.request(
            "POST", f"/api/tenders/results/{result_id}/portal-agent/evaluate", {
                "phase": "DISPUTE_OPEN", "currentBest": "590.00",
                "suggestedBid": "580.00", "idempotencyKey": "portal-event-floor-1",
            },
        )
        self.assertEqual(status, 409, floor_blocked)
        self.assertEqual(floor_blocked["error"], "floor_reached")
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM tender_agent_commands WHERE action='PLACE_BID'",
        ), 1)
        policy_id = agent["policy"]["id"]
        run_id = agent["runs"][0]["id"]
        self.db.execute(
            """UPDATE tender_agent_policies SET mode='AUTONOMOUS',allow_live_bidding=1,
               written_authorization_reference='ATA-DIRETORIA-2026-08-23'
               WHERE id=? AND company_id=1""", (policy_id,),
        )
        sequence = self.db.scalar(
            "SELECT MAX(sequence)+1 FROM tender_agent_commands WHERE run_id=?", (run_id,),
        )
        queued_command = self.db.execute(
            """INSERT INTO tender_agent_commands
               (company_id,run_id,sequence,action,state,requested_value_cents,
                authorized_value_cents,payload_json,idempotency_key,created_at)
               VALUES(1,?,?,'PLACE_BID','QUEUED',78000,78000,?,'worker-live-bid-1',?)""",
            (run_id, sequence, json.dumps({"phase": "DISPUTE_OPEN"}), now),
        ).lastrowid
        worker_secret = "tender-agent-test-secret-with-at-least-32-characters"

        def signed_worker_request(path, payload):
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            timestamp = str(int(time.time()))
            signature = "sha256=" + hmac.new(
                worker_secret.encode(), timestamp.encode("ascii") + b"." + raw,
                hashlib.sha256,
            ).hexdigest()
            status_code, content, _headers = self.raw_request(
                "POST", path, raw, authenticated=False,
                extra_headers={"X-SIVS-Agent-Timestamp": timestamp,
                               "X-SIVS-Agent-Signature": signature},
            )
            return status_code, json.loads(content.decode("utf-8"))

        with patch.dict(os.environ, {
            "SIVS_TENDER_AGENT_SECRET": worker_secret,
            "SIVS_TENDER_AGENT_COMPANY_ID": "1",
        }, clear=False), patch("server.TENDER_AGENT_PRODUCTION_ENABLED", True):
            status, leased = signed_worker_request(
                "/api/integrations/tender-agent/lease",
                {"version": "1.0", "workerId": "worker-test-portal-01"},
            )
            self.assertEqual(status, 200, leased)
            self.assertEqual(leased["command"]["id"], queued_command)
            self.assertEqual(leased["command"]["authorizedValueCents"], 78000)
            self.assertEqual(self.db.scalar(
                "SELECT last_own_bid_cents FROM tender_agent_runs WHERE id=?", (run_id,),
            ), 78900)
            status, result = signed_worker_request(
                "/api/integrations/tender-agent/result", {
                    "version": "1.0", "workerId": "worker-test-portal-01",
                    "commandId": queued_command, "outcome": "COMPLETED",
                    "externalEffect": True, "portalProtocol": "PROTOCOLO-LANCE-001",
                    "evidenceSha256": "a" * 64,
                    "detail": {"message": "Lance confirmado pelo portal homologado."},
                },
            )
            self.assertEqual(status, 200, result)
            self.assertFalse(result["duplicate"])
            self.assertEqual(self.db.scalar(
                "SELECT last_own_bid_cents FROM tender_agent_runs WHERE id=?", (run_id,),
            ), 78000)
        worker_receipt = self.db.connection().execute(
            "SELECT * FROM tender_agent_receipts WHERE command_id=? ORDER BY id DESC LIMIT 1",
            (queued_command,),
        ).fetchone()
        self.assertEqual(worker_receipt["external_effect"], 1)
        self.assertEqual(worker_receipt["portal_protocol"], "PROTOCOLO-LANCE-001")
        second_company = self.db.execute(
            "INSERT INTO companies(name,created_at,updated_at) VALUES('Empresa isolada',?,?)",
            (now, now),
        ).lastrowid
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """INSERT INTO tender_agent_runs
                   (company_id,policy_id,status,adapter,created_at)
                   VALUES(?,?,'RUNNING','BROWSER_PROTOCOL',?)""",
                (second_company, agent["policy"]["id"], now),
            )
        self.db.connection().rollback()

        proposal_id = self.db.scalar(
            "SELECT id FROM tender_proposals WHERE tender_result_id=? AND company_id=1",
            (result_id,),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "UPDATE tender_proposal_versions SET total_price_cents=1 WHERE proposal_id=?",
                (proposal_id,),
            )
        self.db.connection().rollback()
        status, reopened = self.request(
            "POST", f"/api/tenders/results/{result_id}/commercial-proposal/reopen",
            {"expectedVersion": 1, "comment": "Nova rodada comercial"},
        )
        self.assertEqual(status, 200, reopened)
        self.assertEqual(self.db.scalar(
            "SELECT status FROM tender_agent_policies WHERE id=?", (policy_id,),
        ), "CLOSED")
        self.assertEqual(self.db.scalar(
            "SELECT status FROM tender_agent_runs WHERE id=?", (run_id,),
        ), "CANCELLED")
        reopened_payload = json.loads(self.db.connection().execute(
            "SELECT payload FROM records WHERE id=?", (operational_record_id,),
        ).fetchone()["payload"])
        self.assertEqual(reopened_payload["proposta_comercial_status"], "EM_REVISAO")
        self.assertEqual(reopened_payload["proposta_comercial_versao_aprovada"], 1)
        revised_body = json.loads(json.dumps(proposal_body))
        revised_body["expectedVersion"] = 1
        revised_body["items"][0]["unitPrice"] = "160.00"
        status, revised = self.request(
            "PUT", f"/api/tenders/results/{result_id}/commercial-proposal", revised_body,
        )
        self.assertEqual(status, 200, revised)
        self.assertEqual(revised["commercialProposal"]["proposal"]["version"], 2)
        revised_operational_payload = json.loads(self.db.connection().execute(
            "SELECT payload FROM records WHERE id=?", (operational_record_id,),
        ).fetchone()["payload"])
        self.assertEqual(revised_operational_payload["proposta_comercial_versao"], 2)
        self.assertEqual(revised_operational_payload["proposta_comercial_status"], "RASCUNHO")
        self.assertEqual(revised_operational_payload["proposta_comercial_versao_aprovada"], 1)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM tender_proposal_versions WHERE proposal_id=?", (proposal_id,),
        ), 2)
        self.assertEqual(self.db.scalar(
            """SELECT total_price_cents FROM tender_proposal_versions
               WHERE proposal_id=? AND version=1""", (proposal_id,),
        ), 80000)

        status, submitted_v2 = self.request(
            "POST", f"/api/tenders/results/{result_id}/commercial-proposal/submit",
            {"expectedVersion": 2},
        )
        self.assertEqual(status, 200, submitted_v2)
        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "aprovadora.proposta@seccol.test", "password": "Senha-Proposta-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, approved_v2 = self.request(
            "POST", f"/api/tenders/results/{result_id}/commercial-proposal/decision", {
                "expectedVersion": 2, "decision": "APPROVED",
                "comment": "Versão final conferida para execução.",
            },
        )
        self.assertEqual(status, 200, approved_v2)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM tender_agent_policies WHERE tender_result_id=?", (result_id,),
        ), 2)
        self.cookie, self.csrf = admin_cookie, admin_csrf

        status, customer = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Órgão público faturável",
            "status": "Ativo", "payload": {
                "assunto": "Órgão público", "tipo_cadastro": "C",
                "tipo_pessoa": "Pessoa jurídica", "documento": "04252011000110",
                "razao_social": "Órgão público faturável", "aprovado_faturamento": True,
                "bloqueado": False, "relacionamentos": [],
            },
        })
        self.assertEqual(status, 201, customer)
        for stage in ("Análise", "Documentação", "Proposta enviada", "Habilitação", "Homologada"):
            status, current = self.request("GET", f"/api/records/{operational_record_id}")
            self.assertEqual(status, 200, current)
            current_item = current["item"]
            current_payload = current_item["payload"]
            current_payload["etapa"] = stage
            status, transitioned = self.request("PUT", f"/api/records/{operational_record_id}", {
                "module": "licitacoes", "title": current_item["title"], "status": stage,
                "amount": current_item["amount"], "due_date": current_item["due_date"],
                "payload": current_payload, "revision": current_item["revision"],
            })
            self.assertEqual(status, 200, transitioned)

        status, handoff = self.request(
            "POST", f"/api/tenders/results/{result_id}/operational-handoff", {
                "customerRecordId": customer["item"]["id"],
                "instrumentNumber": "EMP-2026-001", "manager": "Gestora do contrato",
                "technicalOwner": "Responsável técnico SECCOL",
                "startDate": "2026-09-20", "endDate": "2027-09-19",
                "billingDueDate": "2026-10-30",
                "executionLocation": "Instalações do órgão contratante",
            },
        )
        self.assertEqual(status, 201, handoff)
        self.assertFalse(handoff["alreadyCreated"])
        handoff_data = handoff["handoff"]
        self.assertEqual(handoff_data["executionModule"], "ordens_servico")
        self.assertIsNone(handoff_data["purchaseRequestRecordId"])
        contract_id = handoff_data["contractRecordId"]
        execution_id = handoff_data["executionRecordId"]
        self.assertEqual(self.db.scalar(
            "SELECT amount FROM records WHERE id=? AND module='contratos'", (contract_id,),
        ), 820)
        execution_items = self.db.connection().execute(
            """SELECT item_kind,warehouse_id,lot_key,total_cents FROM document_items
               WHERE company_id=1 AND record_id=? ORDER BY sort_order""",
            (execution_id,),
        ).fetchall()
        self.assertEqual(len(execution_items), 2)
        self.assertEqual(execution_items[0]["item_kind"], "PRODUCT")
        self.assertEqual(execution_items[0]["warehouse_id"], warehouse_id)
        self.assertEqual(execution_items[0]["lot_key"], "PROPOSTA-TESTE")
        self.assertEqual(execution_items[1]["item_kind"], "SERVICE")
        status, repeated = self.request(
            "POST", f"/api/tenders/results/{result_id}/operational-handoff", {},
        )
        self.assertEqual(status, 200, repeated)
        self.assertTrue(repeated["alreadyCreated"])
        self.assertEqual(repeated["handoff"]["executionRecordId"], execution_id)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM tender_operational_handoffs WHERE tender_result_id=?",
            (result_id,),
        ), 1)
        status, protected_execution = self.request("DELETE", f"/api/records/{execution_id}")
        self.assertEqual(status, 409, protected_execution)
        self.assertEqual(protected_execution["error"], "tender_handoff_in_use")
        status, blocked_reopen = self.request(
            "POST", f"/api/tenders/results/{result_id}/commercial-proposal/reopen",
            {"expectedVersion": 2, "comment": "Tentativa posterior"},
        )
        self.assertEqual(status, 409, blocked_reopen)
        self.assertEqual(blocked_reopen["error"], "tender_handoff_exists")

        status, execution = self.request("GET", f"/api/records/{execution_id}")
        execution_payload = execution["item"]["payload"]
        status, execution = self.request("PUT", f"/api/records/{execution_id}", {
            "module": "ordens_servico", "title": execution["item"]["title"],
            "status": "Em execução", "amount": execution["item"]["amount"],
            "due_date": execution["item"]["due_date"], "payload": execution_payload,
            "revision": execution["item"]["revision"],
        })
        self.assertEqual(status, 200, execution)
        status, reserved = self.request("POST", f"/api/records/{execution_id}/reserve-items", {})
        self.assertEqual(status, 200, reserved)
        status, fulfilled = self.request("POST", f"/api/records/{execution_id}/fulfill-items", {})
        self.assertEqual(status, 200, fulfilled)
        status, execution = self.request("GET", f"/api/records/{execution_id}")
        status, concluded = self.request("PUT", f"/api/records/{execution_id}", {
            "module": "ordens_servico", "title": execution["item"]["title"],
            "status": "Concluída", "amount": execution["item"]["amount"],
            "due_date": execution["item"]["due_date"],
            "payload": execution["item"]["payload"],
            "revision": execution["item"]["revision"],
        })
        self.assertEqual(status, 200, concluded)
        self.assertEqual(concluded["financialModule"], "contas_receber")
        receivable_id = concluded["financialRecordId"]
        receivable = self.db.connection().execute(
            "SELECT * FROM records WHERE id=? AND company_id=1", (receivable_id,),
        ).fetchone()
        receivable_payload = json.loads(receivable["payload"])
        self.assertEqual(receivable["module"], "contas_receber")
        self.assertEqual(receivable["amount"], 820)
        self.assertEqual(receivable["due_date"], "2026-10-30")
        self.assertEqual(receivable_payload["cliente_id"], customer["item"]["id"])
        self.assertEqual(receivable_payload["origem_registro_id"], execution_id)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM financial_document_origins WHERE source_record_id=?",
            (execution_id,),
        ), 1)
        status, protected_receivable = self.request("DELETE", f"/api/records/{receivable_id}")
        self.assertEqual(status, 409, protected_receivable)
        self.assertEqual(protected_receivable["error"], "financial_origin_in_use")

    def test_complete_connected_business_journey_settles_cash_end_to_end(self):
        # Reutiliza o percurso mais longo já validado, mas mantém o mesmo servidor, sessão,
        # empresa e banco para continuar até a liquidação dos dois lados financeiros.
        self.test_tender_commercial_proposal_is_versioned_segregated_and_packaged()

        receivable_id = self.db.scalar(
            """SELECT o.financial_record_id FROM financial_document_origins o
               JOIN records source ON source.id=o.source_record_id
               WHERE o.company_id=1 AND o.financial_module='contas_receber'
                 AND source.module='ordens_servico'
               ORDER BY o.id DESC LIMIT 1"""
        )
        self.assertTrue(receivable_id)
        status, receivable = self.request("GET", f"/api/records/{receivable_id}")
        self.assertEqual(status, 200, receivable)
        receivable_payload = receivable["item"]["payload"]
        receivable_payload.update({
            "conta": "Banco operacional", "forma_pagamento": "Transferência",
            "data_recebimento": "2026-10-30",
        })
        status, partial = self.request(
            "POST", f"/api/financial/titles/{receivable_id}/settlements", {
                "revision": receivable["item"]["revision"], "principal": "300,00",
                "discount": "10,00", "interest": "5,00", "fee": "2,00",
                "date": "2026-10-30", "account": "Banco operacional",
                "paymentMethod": "Transferência", "note": "Primeiro recebimento parcial",
            },
        )
        self.assertEqual(status, 201, partial)
        self.assertEqual(partial["title"]["status"], "Parcial")
        self.assertEqual(partial["remainingCents"], 52000)
        self.assertEqual(partial["entries"][0]["cash_amount_cents"], 29300)
        status, settled_receivable = self.request(
            "POST", f"/api/financial/titles/{receivable_id}/settlements", {
                "revision": partial["title"]["revision"], "principal": "520,00",
                "date": "2026-10-30", "account": "Banco operacional",
                "paymentMethod": "Transferência", "note": "Liquidação do saldo",
            },
        )
        self.assertEqual(status, 201, settled_receivable)
        self.assertEqual(settled_receivable["title"]["status"], "Recebido")
        incoming_cash_id = settled_receivable["cashRecordId"]
        incoming = self.db.connection().execute(
            "SELECT module,status,amount,due_date,payload FROM records WHERE id=?",
            (incoming_cash_id,),
        ).fetchone()
        self.assertEqual((incoming["module"], incoming["status"], incoming["amount"]),
                         ("caixa", "Ativo", 520))
        self.assertEqual(json.loads(incoming["payload"])["tipo_movimento"], "Entrada")

        status, inventory = self.request("GET", "/api/inventory")
        self.assertEqual(status, 200, inventory)
        product_id = inventory["products"][0]["id"]
        warehouse_id = inventory["warehouses"][0]["id"]
        status, supplier = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Fornecedor jornada completa",
            "status": "Ativo", "payload": {
                "assunto": "Fornecedor da operação completa", "tipo_cadastro": "F",
                "tipo_pessoa": "Pessoa jurídica", "documento": "12345678000195",
                "razao_social": "Fornecedor jornada completa", "avaliacao": "Aprovado",
                "aprovado_compras": True, "bloqueado": False,
            },
        })
        self.assertEqual(status, 201, supplier)
        purchase_payload = {
            "assunto": "Reposição após execução do contrato", "numero": "PC-E2E-001",
            "fornecedor": supplier["item"]["title"],
            "fornecedor_id": supplier["item"]["id"], "condicao_pagamento": "À vista",
            "centro_custo": "Operações", "gerar_conta_pagar_ao_receber": True,
        }
        status, purchase = self.request("POST", "/api/records", {
            "module": "pedidos_compra", "title": "Reposição da jornada completa",
            "status": "Rascunho", "payload": purchase_payload,
        })
        self.assertEqual(status, 201, purchase)
        purchase_id = purchase["item"]["id"]
        status, composition = self.request("GET", f"/api/records/{purchase_id}/items")
        self.assertEqual(status, 200, composition)
        status, item = self.request("POST", f"/api/records/{purchase_id}/items", {
            "recordRevision": composition["recordRevision"], "itemKind": "PRODUCT",
            "catalogRecordId": product_id, "description": "Reposição de instrumento",
            "quantity": "2", "unitPrice": "25.00", "warehouseId": warehouse_id,
            "lot": "LOTE-E2E-COMPRA",
        })
        self.assertEqual(status, 201, item)
        status, purchase = self.request("PUT", f"/api/records/{purchase_id}", {
            "module": "pedidos_compra", "title": "Reposição da jornada completa",
            "status": "Emitido", "payload": purchase_payload,
            "revision": item["recordRevision"],
        })
        self.assertEqual(status, 200, purchase)
        status, received = self.request(
            "POST", f"/api/records/{purchase_id}/receive-items", {},
        )
        self.assertEqual(status, 200, received)
        self.assertEqual(received["status"], "Recebido")
        payable_id = received["financialRecordId"]
        self.assertTrue(payable_id)
        status, payable = self.request("GET", f"/api/records/{payable_id}")
        self.assertEqual(status, 200, payable)
        payable_payload = payable["item"]["payload"]
        payable_payload.update({
            "conta": "Banco operacional", "forma_pagamento": "PIX",
            "data_pagamento": "2026-10-30",
        })
        status, settled_payable = self.request("PUT", f"/api/records/{payable_id}", {
            "module": "contas_pagar", "title": payable["item"]["title"],
            "status": "Pago", "amount": payable["item"]["amount"],
            "due_date": payable["item"]["due_date"], "payload": payable_payload,
            "revision": payable["item"]["revision"],
        })
        self.assertEqual(status, 200, settled_payable)
        outgoing_cash_id = settled_payable["cashRecordId"]
        outgoing = self.db.connection().execute(
            "SELECT module,status,amount,payload FROM records WHERE id=?",
            (outgoing_cash_id,),
        ).fetchone()
        self.assertEqual((outgoing["module"], outgoing["status"], outgoing["amount"]),
                         ("caixa", "Ativo", 50))
        self.assertEqual(json.loads(outgoing["payload"])["tipo_movimento"], "Saída")

        status, control = self.request("GET", "/api/management/overview")
        self.assertEqual(status, 200, control)
        self.assertEqual(control["cashflow"]["cashInCents"], 81300)
        self.assertEqual(control["cashflow"]["cashOutCents"], 5000)
        self.assertEqual(control["cashflow"]["balanceCents"], 76300)
        self.assertEqual(control["cashflow"]["receivableOpenCents"], 0)
        self.assertEqual(control["cashflow"]["payableOpenCents"], 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM financial_settlements"), 3)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE action='settle'"
        ), 3)
        status, protected_cash = self.request("DELETE", f"/api/records/{incoming_cash_id}")
        self.assertEqual(status, 409, protected_cash)
        self.assertEqual(protected_cash["error"], "financial_settlement_locked")
        status, protected_title = self.request("DELETE", f"/api/records/{payable_id}")
        self.assertEqual(status, 409, protected_title)
        self.assertEqual(protected_title["error"], "financial_settlement_locked")

        status, readiness = self.request("GET", "/api/fiscal/readiness")
        self.assertEqual(status, 200, readiness)
        self.assertIsNone(readiness["certificate"])
        self.assertFalse(readiness["canCheckStatus"])
        self.assertFalse(readiness["canIssue"])

        status, second_company = self.request(
            "POST", "/api/companies", {"name": "Empresa isolada da jornada"},
        )
        self.assertEqual(status, 201, second_company)
        status, switched = self.request(
            "POST", "/api/company/switch", {"company_id": second_company["id"]},
        )
        self.assertEqual(status, 200, switched)
        status, hidden_cash = self.request("GET", f"/api/records/{incoming_cash_id}")
        self.assertEqual(status, 404, hidden_cash)
        status, isolated_control = self.request("GET", "/api/management/overview")
        self.assertEqual(status, 200, isolated_control)
        self.assertEqual(isolated_control["cashflow"]["cashInCents"], 0)
        self.assertEqual(isolated_control["cashflow"]["cashOutCents"], 0)

    def test_partial_settlement_reconciliation_and_reversal_are_connected_and_isolated(self):
        self.setup_admin()
        now = utc_now()
        title_id = self.db.execute(
            """INSERT INTO records
               (module,title,status,amount,due_date,payload,created_by,created_at,updated_at,
                company_id,revision)
               VALUES('contas_receber','Receber — TESTE-LEDGER','Em aberto',100,
                      '2026-12-20',?,1,?,?,1,1)""",
            (json.dumps({"assunto": "Teste do ledger", "cliente": "Cliente teste",
                         "categoria": "Serviços técnicos"}), now, now),
        ).lastrowid
        status, partial = self.request(
            "POST", f"/api/financial/titles/{title_id}/settlements", {
                "revision": 1, "principal": "40,00", "discount": "5,00",
                "interest": "2,00", "fee": "1,00", "date": "2026-11-10",
                "account": "Banco operacional", "paymentMethod": "PIX",
                "note": "Recebimento parcial do cliente",
            },
        )
        self.assertEqual(status, 201, partial)
        self.assertEqual(partial["remainingCents"], 6000)
        self.assertEqual(partial["settledCents"], 4000)
        self.assertEqual(partial["entries"][0]["cash_amount_cents"], 3600)
        self.assertEqual(partial["title"]["status"], "Parcial")
        cash_id = partial["cashRecordId"]
        settlement_id = partial["settlementId"]

        csv_content = (
            "id;data;tipo;valor;descricao\n"
            "BANK-0001;10/11/2026;credito;36,00;PIX cliente teste\n"
        )
        status, imported = self.request("POST", "/api/bank-reconciliation/import", {
            "filename": "extrato-novembro.csv", "content": csv_content,
        })
        self.assertEqual(status, 200, imported)
        self.assertEqual(imported["imported"], 1)
        status, duplicate = self.request("POST", "/api/bank-reconciliation/import", {
            "filename": "extrato-novembro.csv", "content": csv_content,
        })
        self.assertEqual((status, duplicate["duplicates"]), (200, 1))
        status, reconciliation = self.request("GET", "/api/bank-reconciliation")
        self.assertEqual(status, 200, reconciliation)
        statement = reconciliation["items"][0]
        self.assertEqual(statement["candidates"][0]["id"], cash_id)
        status, matched = self.request(
            "POST", f"/api/bank-reconciliation/{statement['id']}/match",
            {"cashRecordId": cash_id},
        )
        self.assertEqual(status, 200, matched)

        status, blocked = self.request(
            "POST", f"/api/financial/settlements/{settlement_id}/reverse", {
                "revision": partial["title"]["revision"], "date": "2026-11-11",
                "reason": "Baixa registrada na conta incorreta",
            },
        )
        self.assertEqual(status, 409, blocked)
        self.assertIn("conciliação", blocked["message"])
        status, unmatched = self.request(
            "POST", f"/api/bank-reconciliation/{statement['id']}/unmatch", {},
        )
        self.assertEqual(status, 200, unmatched)
        status, reversed_entry = self.request(
            "POST", f"/api/financial/settlements/{settlement_id}/reverse", {
                "revision": partial["title"]["revision"], "date": "2026-11-11",
                "reason": "Baixa registrada na conta incorreta",
            },
        )
        self.assertEqual(status, 201, reversed_entry)
        self.assertEqual(reversed_entry["remainingCents"], 10000)
        self.assertEqual(reversed_entry["settledCents"], 0)
        self.assertEqual(reversed_entry["title"]["status"], "Em aberto")
        reversal_cash = self.db.connection().execute(
            "SELECT amount,payload FROM records WHERE id=?", (reversed_entry["cashRecordId"],),
        ).fetchone()
        self.assertEqual(reversal_cash["amount"], 36)
        self.assertEqual(json.loads(reversal_cash["payload"])["tipo_movimento"], "Saída")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.connection().execute(
                "UPDATE financial_settlements SET note='alterado' WHERE id=?",
                (settlement_id,),
            )
        self.db.connection().rollback()

        status, company = self.request("POST", "/api/companies", {"name": "Empresa ledger isolada"})
        self.assertEqual(status, 201, company)
        status, _ = self.request("POST", "/api/company/switch", {"company_id": company["id"]})
        self.assertEqual(status, 200)
        status, hidden = self.request("GET", f"/api/financial/titles/{title_id}/settlements")
        self.assertEqual(status, 404, hidden)
        status, isolated = self.request("GET", "/api/bank-reconciliation")
        self.assertEqual(status, 200, isolated)
        self.assertEqual(isolated["items"], [])

    def test_financial_title_split_is_exact_audited_and_blocks_parent_settlement(self):
        self.setup_admin()
        now = utc_now()
        title_id = self.db.execute(
            """INSERT INTO records(module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('contas_pagar','Fornecedor - contrato','Em aberto',100,'2026-10-10',?,1,?,?,1,1)""",
            (json.dumps({"assunto": "Contrato", "fornecedor": "Fornecedor teste", "categoria": "ServiÃ§os"}), now, now),
        ).lastrowid
        status, invalid = self.request("POST", f"/api/financial/titles/{title_id}/installments", {
            "revision": 1, "installments": [{"dueDate": "2026-10-10", "amount": "40,00"}, {"dueDate": "2026-11-10", "amount": "50,00"}],
        })
        self.assertEqual(status, 409, invalid)
        status, split = self.request("POST", f"/api/financial/titles/{title_id}/installments", {
            "revision": 1, "installments": [{"dueDate": "2026-10-10", "amount": "40,00"}, {"dueDate": "2026-11-10", "amount": "60,00"}],
        })
        self.assertEqual(status, 201, split)
        self.assertEqual(len(split["installmentIds"]), 2)
        parent = self.db.connection().execute("SELECT status,revision FROM records WHERE id=?", (title_id,)).fetchone()
        self.assertEqual((parent["status"], parent["revision"]), ("Parcelado", 2))
        children = self.db.connection().execute("SELECT amount,due_date FROM records WHERE id IN (?,?) ORDER BY due_date", tuple(split["installmentIds"])).fetchall()
        self.assertEqual([(row["amount"], row["due_date"]) for row in children], [(40, "2026-10-10"), (60, "2026-11-10")])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM financial_title_split_items"), 2)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action='split' AND entity_id=?", (title_id,)), 1)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM notifications WHERE record_id=? AND module='contas_pagar'", (title_id,)), 1)
        status, blocked = self.request("POST", f"/api/financial/titles/{title_id}/settlements", {
            "revision": 2, "principal": "100,00", "discount": "0", "interest": "0", "fee": "0",
            "date": "2026-10-10", "account": "Banco operacional", "paymentMethod": "PIX", "note": "Tentativa",
        })
        self.assertEqual(status, 409, blocked)
        status, child = self.request("POST", f"/api/financial/titles/{split['installmentIds'][0]}/settlements", {
            "revision": 1, "principal": "40,00", "discount": "0", "interest": "0", "fee": "0",
            "date": "2026-10-10", "account": "Banco operacional", "paymentMethod": "PIX", "note": "Parcela paga",
        })
        self.assertEqual((status, child["title"]["status"]), (201, "Pago"))

    def test_tender_control_versions_decision_risks_deadlines_and_immutable_evidence(self):
        self.setup_admin()
        now = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,agency,modality,source_url,deadline,
                estimated_value,matched_terms,relevance_score,status,raw_json,created_at,
                updated_at,company_id)
               VALUES('control','control-1','Pregao controlado','Fornecimento de filtros HEPA',
                      'Orgao teste','Pregao eletronico','https://pncp.gov.br/app/editais/teste',
                      '2026-10-15T18:00:00-03:00',50000,'[]',95,'Analisar','{}',?,?,1)""",
            (now, now),
        ).lastrowid

        status, detail = self.request("GET", f"/api/tenders/results/{result_id}")
        self.assertEqual(status, 200, detail)
        initial = detail["item"]["control"]
        self.assertEqual(initial["profile"]["decision"], "PENDING")
        self.assertEqual(initial["profile"]["revision"], 0)
        self.assertEqual(initial["suggestedMilestones"][0]["type"], "PROPOSAL")

        payload = {
            "expectedRevision": 0,
            "decision": "GO",
            "decisionReason": "Objeto aderente ao catalogo e capacidade operacional confirmada.",
            "responsibleUserId": 1,
            "milestones": [{
                "type": "PROPOSAL", "title": "Protocolar proposta",
                "dueAt": "2026-10-15T18:00:00-03:00", "status": "PENDING",
                "responsibleUserId": 1, "sourceReference": "Edital, item 8",
                "notes": "Concluir uma hora antes do limite oficial.",
            }],
            "risks": [{
                "category": "PORTAL", "title": "Indisponibilidade do portal",
                "probability": 4, "impact": 5, "status": "OPEN",
                "ownerUserId": 1,
                "mitigation": "Antecipar protocolo e manter operador em contingencia.",
            }],
        }
        status, saved = self.request(
            "PUT", f"/api/tenders/results/{result_id}/control", payload,
        )
        self.assertEqual(status, 200, saved)
        control = saved["control"]
        self.assertEqual(control["profile"]["revision"], 1)
        self.assertEqual(control["profile"]["decision"], "GO")
        self.assertEqual(control["summary"]["criticalRisks"], 1)
        self.assertEqual(control["risks"][0]["score"], 20)
        self.assertEqual(control["milestones"][0]["status"], "PENDING")
        self.assertEqual(control["history"][0]["revision"], 1)
        snapshot = json.loads(self.db.scalar(
            "SELECT snapshot_json FROM tender_control_versions WHERE tender_result_id=?",
            (result_id,),
        ))
        self.assertEqual(snapshot["decision"], "GO")
        self.assertEqual(snapshot["risks"][0]["probability"], 4)

        status, conflict = self.request(
            "PUT", f"/api/tenders/results/{result_id}/control", payload,
        )
        self.assertEqual(status, 409, conflict)
        self.assertEqual(conflict["error"], "tender_control_conflict")

        pdf = b"%PDF-1.4\nprotocolo-sivs\n%%EOF"
        status, evidence = self.request(
            "POST", f"/api/tenders/results/{result_id}/control/evidence", {
                "eventType": "PROPOSAL", "portal": "Compras.gov.br",
                "protocol": "PROTOCOLO-2026-001",
                "occurredAt": "2026-10-15T16:30:00-03:00",
                "filename": "protocolo.pdf",
                "content": base64.b64encode(pdf).decode("ascii"),
                "notes": "Proposta recebida pelo portal.",
            },
        )
        self.assertEqual(status, 201, evidence)
        evidence_id = evidence["id"]
        status, content, headers = self.raw_request(
            "GET", f"/api/tenders/results/{result_id}/control/evidence/{evidence_id}/download",
        )
        self.assertEqual(status, 200)
        self.assertEqual(content, pdf)
        self.assertEqual(headers["content-type"], "application/pdf")
        self.assertEqual(headers["x-content-sha256"], hashlib.sha256(pdf).hexdigest())
        self.assertEqual(
            self.db.scalar(
                "SELECT COUNT(*) FROM audit_log WHERE entity_type='tender_protocol_evidence'"
            ), 2,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.connection().execute(
                "UPDATE tender_protocol_evidence SET notes='alterado' WHERE id=?",
                (evidence_id,),
            )
        self.db.connection().rollback()

        status, company = self.request(
            "POST", "/api/companies", {"name": "Empresa isolada para licitacao"},
        )
        self.assertEqual(status, 201, company)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.connection().execute(
                """INSERT INTO tender_risks
                   (company_id,tender_result_id,category,title,probability,impact,status,
                    sort_order,created_at,updated_at)
                   VALUES(?,?,'PORTAL','Risco cruzado',3,3,'OPEN',0,?,?)""",
                (company["id"], result_id, now, now),
            )
        self.db.connection().rollback()

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

    def test_tender_extraction_feeds_checklist_and_requires_audited_exception_resolution(self):
        self.setup_admin()
        now = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,agency,matched_terms,relevance_score,status,
                raw_json,created_at,updated_at,company_id)
               VALUES('extraction','extraction-1','Edital OCR','Certificação de cabine','Órgão',
                      '[]',90,'Novo','{}',?,?,1)""",
            (now, now),
        ).lastrowid
        self.db.execute(
            """INSERT INTO tender_details
               (tender_result_id,company_id,official_data,items_json,documents_json,
                value_source,analysis_json,extraction_json,refreshed_at)
               VALUES(?,1,'{}','[]',?,'unavailable','{}','{}',?)""",
            (result_id, json.dumps([{"titulo": "Edital principal.pdf"}]), now),
        )
        page = {
            "document": "Edital principal.pdf", "page": 9,
            "text": ("Entrega das propostas até 31/08/2026 às 09:00. "
                     "Apresentar atestado de capacidade técnica para habilitação."),
            "hasImages": True, "ocrStatus": "completed",
        }
        with patch.object(
            SIVSHandler, "tender_document_bytes",
            return_value=(b"%PDF-1.7", "application/pdf"),
        ), patch.object(SIVSHandler, "tender_pdf_pages_with_ocr", return_value=[page]), \
                patch.object(SIVSHandler, "tender_ocr_executable", return_value="tesseract"):
            status, extracted = self.request(
                "POST", f"/api/tenders/results/{result_id}/extract", {},
            )
        self.assertEqual(status, 200, extracted)
        extraction = extracted["extraction"]
        self.assertEqual(extraction["status"], "COMPLETED")
        self.assertEqual(extraction["ocrPages"][0]["page"], 9)
        self.assertEqual(extraction["deadlines"][0]["value"], "31/08/2026 às 09:00")
        self.assertEqual(
            extraction["suggestedRequirements"][0]["documentType"],
            "technical_capacity_certificate",
        )
        status, detail = self.request("GET", f"/api/tenders/results/{result_id}")
        self.assertEqual(status, 200, detail)
        suggested = next(
            item for item in detail["item"]["participationDocuments"]["requirements"]
            if item["document_type"] == "technical_capacity_certificate"
        )
        self.assertEqual(suggested["source_reference"], "Edital principal.pdf, pág. 9")
        self.assertIsNotNone(suggested["extraction_suggestion"])

        runner = object.__new__(SIVSHandler)
        runner.server = self.server
        runner.sync_tender_analysis_exceptions(result_id, 1, [{
            "category": "OCR", "severity": "CRITICAL", "document": "Anexo escaneado.pdf",
            "page": 3, "message": "Página sem texto OCR verificável.",
        }])
        self.assertTrue(runner.tender_analysis_blockers(result_id, 1))
        status, exception_center = self.request("GET", "/api/tenders/exceptions")
        self.assertEqual(status, 200, exception_center)
        self.assertEqual(len(exception_center["items"]), 1)
        self.assertEqual(exception_center["items"][0]["tender_result_id"], result_id)
        self.assertEqual(self.db.scalar(
            """SELECT COUNT(*) FROM notification_alerts
               WHERE company_id=1 AND entity_type='tender_analysis_exception'"""
        ), 1)
        status, blocked = self.request(
            "PUT", f"/api/tenders/results/{result_id}/participation-documents",
            {"confirmed": True, "requirements": []},
        )
        self.assertEqual(status, 409, blocked)
        self.assertEqual(blocked["error"], "document_extraction_blocked")
        exception_id = self.db.scalar(
            """SELECT id FROM tender_analysis_exceptions
               WHERE tender_result_id=? AND status='OPEN'""", (result_id,),
        )
        status, short = self.request(
            "POST", f"/api/tenders/results/{result_id}/exceptions/{exception_id}/resolve",
            {"note": "curta"},
        )
        self.assertEqual(status, 400, short)
        status, resolved = self.request(
            "POST", f"/api/tenders/results/{result_id}/exceptions/{exception_id}/resolve",
            {"note": "Documento conferido manualmente na página oficial do PNCP."},
        )
        self.assertEqual(status, 200, resolved)
        self.assertEqual(resolved["exceptions"][0]["status"], "RESOLVED")
        runner.sync_tender_analysis_exceptions(result_id, 1, [{
            "category": "OCR", "severity": "CRITICAL", "document": "Anexo escaneado.pdf",
            "page": 3, "message": "Página sem texto OCR verificável.",
        }])
        self.assertEqual(self.db.scalar(
            "SELECT status FROM tender_analysis_exceptions WHERE id=?", (exception_id,),
        ), "RESOLVED")
        self.assertEqual(runner.tender_analysis_blockers(result_id, 1), [])
        status, exception_center = self.request("GET", "/api/tenders/exceptions")
        self.assertEqual(status, 200, exception_center)
        self.assertEqual(exception_center["items"], [])
        self.assertEqual(self.db.scalar(
            """SELECT COUNT(*) FROM notification_alerts
               WHERE company_id=1 AND entity_type='tender_analysis_exception'"""
        ), 0)
        self.assertEqual(self.db.scalar(
            """SELECT COUNT(*) FROM audit_log WHERE company_id=1
               AND action='resolve' AND entity_type='tender_analysis_exception'"""
        ), 1)

    def test_tender_official_document_change_invalidates_previous_extraction_and_resolutions(self):
        self.setup_admin()
        now = utc_now()
        result_id = self.db.execute(
            """INSERT INTO tender_results
               (source_key,external_id,title,object_text,matched_terms,relevance_score,status,
                raw_json,created_at,updated_at,company_id)
               VALUES('pncp','12345678000195-1-77/2026','Edital alterado','Objeto','[]',
                      90,'Novo','{}',?,?,1)""",
            (now, now),
        ).lastrowid
        self.db.execute(
            """INSERT INTO tender_details
               (tender_result_id,company_id,official_data,items_json,documents_json,value_source,
                analysis_json,extraction_json,refreshed_at)
               VALUES(?,1,'{}','[]',?,'unavailable',?,?,?)""",
            (result_id, json.dumps([{"titulo": "Edital v1.pdf", "url": "https://pncp.gov.br/v1"}]),
             json.dumps({"status": "completed"}), json.dumps({"status": "COMPLETED"}), now),
        )
        runner = object.__new__(SIVSHandler)
        runner.server = self.server
        runner.sync_tender_analysis_exceptions(result_id, 1, [{
            "category": "OCR", "severity": "CRITICAL", "document": "Edital v1.pdf",
            "page": 2, "message": "Conferir imagem.",
        }])
        self.db.execute(
            """UPDATE tender_analysis_exceptions SET status='RESOLVED',
               resolution_note='Conferido',resolved_at=? WHERE tender_result_id=?""",
            (now, result_id),
        )

        def fake_fetch(url, **_kwargs):
            if url.endswith("/itens"):
                return []
            if url.endswith("/arquivos"):
                return [{"titulo": "Edital v2.pdf", "url": "https://pncp.gov.br/v2"}]
            return {"objetoCompra": "Objeto atualizado"}

        runner.fetch_tender_json = fake_fetch
        row = self.db.connection().execute(
            "SELECT * FROM tender_results WHERE id=?", (result_id,),
        ).fetchone()
        runner.refresh_tender_official_data(row, {"id": 1, "company_id": 1})
        detail = self.db.connection().execute(
            "SELECT extraction_json,analysis_json FROM tender_details WHERE tender_result_id=?",
            (result_id,),
        ).fetchone()
        self.assertEqual(json.loads(detail["extraction_json"]), {})
        self.assertEqual(json.loads(detail["analysis_json"]), {})
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM tender_analysis_exceptions WHERE tender_result_id=?",
            (result_id,),
        ), 0)
        audit = json.loads(self.db.scalar(
            """SELECT detail FROM audit_log WHERE entity_type='tender_result'
               AND entity_id=? AND action='refresh' ORDER BY id DESC LIMIT 1""",
            (str(result_id),),
        ))
        self.assertTrue(audit["document_analysis_invalidated"])

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
        # A busca completa o lote com termos do catálogo ativo para não depender
        # apenas das palavras informadas pelo operador.
        self.assertEqual(len(requested_urls), 8)
        self.assertTrue(all("/api/search/" in url for url in requested_urls))
        stored = self.db.connection().execute(
            "SELECT * FROM tender_results WHERE external_id=?",
            ("15126437000305-1-003219/2026",),
        ).fetchone()
        self.assertIsNotNone(stored)
        self.assertEqual(stored["company_id"], 1)
        self.assertIn("cabine de segurança biológica", json.loads(stored["matched_terms"]))
        self.assertEqual(stored["source_url"], "https://pncp.gov.br/app/compras/15126437000305/2026/3219")

    def test_tender_search_keeps_catalog_candidate_pending_without_official_evidence(self):
        self.setup_admin()
        status, saved = self.request("PUT", "/api/settings", {"tenderAutonomy": {
            "enabled": True,
            "captureSingleCatalogItem": False,
        }})
        self.assertEqual(status, 200, saved)

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

        self.assertEqual(result["found"], 1)
        self.assertEqual(result["new"], 1)
        stored = self.db.connection().execute(
            """SELECT id,status,raw_json FROM tender_results
               WHERE external_id='00000000000000-1-000001/2026'"""
        ).fetchone()
        self.assertIsNotNone(stored)
        self.assertEqual(stored["status"], "Analisar")
        raw = json.loads(stored["raw_json"])
        self.assertTrue(raw["_candidate_item_match"])
        self.assertFalse(raw["_strict_match"])
        self.assertEqual(raw["_match_scope"], "PENDING_OFFICIAL_ITEM")
        status, listed = self.request("GET", "/api/tenders/results")
        self.assertEqual(status, 200, listed)
        pending = next(item for item in listed["items"] if item["id"] == stored["id"])
        self.assertFalse(pending["strict_match"])
        self.assertEqual(pending["catalog_priority"], "NONE")

    def test_tender_search_keeps_generic_notice_as_official_item_candidate(self):
        self.setup_admin()

        def fake_fetch(url, timeout=14, attempts=4):
            return {"items": [{
                "numero_controle_pncp": "12345678000195-1-000099/2026",
                "description": "Aquisição de equipamentos para laboratório",
                "orgao_nome": "Órgão candidato", "uf": "PA", "municipio_nome": "Belém",
                "modalidade_licitacao_nome": "Pregão eletrônico",
                "data_publicacao_pncp": utc_now(), "data_fim_vigencia": "2026-08-30T18:00:00",
                "item_url": "/compras/12345678000195/2026/99", "cancelado": False,
            }], "total": 1}

        runner = object.__new__(SIVSHandler)
        runner.server = self.server
        with patch.object(SIVSHandler, "fetch_tender_json", side_effect=fake_fetch):
            with patch("server.time.sleep"):
                result = runner.execute_tender_search(
                    {"id": 1, "company_id": 1},
                    {"keywords": ["Cabine de Segurança Biológica"], "days": 7},
                )

        self.assertEqual(result["found"], 1)
        stored = self.db.connection().execute(
            "SELECT status,raw_json FROM tender_results WHERE external_id=?",
            ("12345678000195-1-000099/2026",),
        ).fetchone()
        self.assertEqual(stored["status"], "Analisar")
        raw = json.loads(stored["raw_json"])
        self.assertTrue(raw["_candidate_item_match"])
        self.assertFalse(raw["_strict_match"])
        self.assertEqual(raw["_match_scope"], "PENDING_OFFICIAL_ITEM")

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

    def test_internal_assistant_searches_focuses_and_falls_back_from_invalid_ai(self):
        self.setup_admin()
        now = utc_now()
        cursor = self.db.execute(
            """INSERT INTO records
               (module,title,status,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('clientes','Hospital Contextual','Ativo',?,?,?,?,1,1)""",
            (json.dumps({"razao_social": "Hospital Contextual"}), 1, now, now),
        )
        focused_id = cursor.lastrowid
        self.db.execute(
            """INSERT INTO records
               (module,title,status,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('clientes','Empresa sem relação','Ativo',?,?,?,?,1,1)""",
            (json.dumps({"razao_social": "Empresa sem relação"}), 1, now, now),
        )

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            status, searched = self.request("POST", "/api/assistant/query", {
                "question": "Mostre clientes Hospital Contextual",
            })
        self.assertEqual(status, 200, searched)
        record_sources = [item for item in searched["sources"] if item["module"] == "clientes"]
        self.assertEqual([item["id"] for item in record_sources], [focused_id])
        self.assertTrue(any(item["module"] == "ajuda" for item in searched["sources"]))

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            status, guidance = self.request("POST", "/api/assistant/query", {
                "question": "Como cadastrar novo serviço?",
            })
        self.assertEqual(status, 200, guidance)
        self.assertEqual(guidance["intent"], "assistant_help")
        self.assertEqual(guidance["model"], "deterministic-guidance")
        self.assertIn("Catálogo de serviços", guidance["answer"])

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            status, adjustment_guidance = self.request("POST", "/api/assistant/query", {
                "question": "Como registrar juros, desconto ou tarifa na baixa?",
            })
        self.assertEqual(status, 200, adjustment_guidance)
        self.assertEqual(adjustment_guidance["model"], "deterministic-guidance")
        self.assertIn("recusada por inteiro", adjustment_guidance["answer"])
        self.assertIn("guide:financial-accounting-adjustments", {
            item["id"] for item in adjustment_guidance["sources"]
        })

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            status, tax_guidance = self.request("POST", "/api/assistant/query", {
                "question": "Como calcular os tributos da NF-e com NCM e CFOP?",
            })
        self.assertEqual(status, 200, tax_guidance)
        self.assertEqual(tax_guidance["model"], "deterministic-guidance")
        self.assertIn("não gera XML", tax_guidance["answer"])
        self.assertIn("guide:fiscal-tax-rules-preview", {
            item["id"] for item in tax_guidance["sources"]
        })
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            status, draft_guidance = self.request("POST", "/api/assistant/query", {
                "question": "Como gerar um rascunho fiscal da venda?",
            })
        self.assertEqual(status, 200, draft_guidance)
        self.assertEqual(draft_guidance["model"], "deterministic-guidance")
        self.assertIn("não gera XML", draft_guidance["answer"])
        self.assertIn("guide:fiscal-sale-draft", {item["id"] for item in draft_guidance["sources"]})

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "configured-for-test"}), \
             patch.object(SIVSHandler, "openrouter_assistant") as generative_assistant:
            status, guided_with_ai_configured = self.request("POST", "/api/assistant/query", {
                "question": "como cadastrar novo serviço?",
            })
        self.assertEqual(status, 200, guided_with_ai_configured)
        self.assertEqual(guided_with_ai_configured["intent"], "assistant_help")
        self.assertEqual(guided_with_ai_configured["model"], "deterministic-guidance")
        self.assertIn("Catálogo de serviços", guided_with_ai_configured["answer"])
        generative_assistant.assert_not_called()

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            status, focused = self.request("POST", "/api/assistant/query", {
                "question": "Resuma este registro e diga a situação deste cadastro.",
                "context": {"module": "clientes", "recordId": focused_id,
                            "title": "Título adulterado pelo navegador"},
                "history": [{"role": "user", "content": "Fale do hospital"}],
            })
        self.assertEqual(status, 200, focused)
        self.assertEqual(focused["intent"], "record_summary")
        self.assertEqual(focused["context"]["title"], "Hospital Contextual")
        self.assertEqual(
            [item["id"] for item in focused["sources"] if item["module"] == "clientes"],
            [focused_id],
        )
        self.assertNotEqual(guidance["conversationId"], focused["conversationId"])
        history_rows = self.db.connection().execute(
            "SELECT role,content FROM assistant_messages WHERE conversation_id=? ORDER BY id",
            (focused["conversationId"],),
        ).fetchall()
        self.assertEqual([row["role"] for row in history_rows], ["user", "assistant"])
        self.assertIn("Hospital Contextual", history_rows[-1]["content"])

        class Response(io.StringIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        ai_payload = json.dumps({
            "model": "modelo-testado",
            "choices": [{"message": {"content": json.dumps({
                "answer": "O cadastro está ativo.", "confidence": "alta",
                "suggestions": ["Revise o próximo passo."],
                "source_ids": [str(focused_id)],
            })}}],
        })
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}), patch(
            "server.urllib.request.urlopen", return_value=Response(ai_payload)
        ) as urlopen:
            status, generated = self.request("POST", "/api/assistant/query", {
                "question": "Resuma este registro.",
                "context": {"recordId": focused_id},
                "history": [{"role": "user", "content": "Vamos analisar este cliente."}],
            })
        self.assertEqual(status, 200, generated)
        self.assertTrue(generated["aiEnabled"])
        self.assertEqual(generated["model"], "modelo-testado")
        request_body = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(
            request_body["provider"],
            {"require_parameters": True, "data_collection": "deny", "zdr": True},
        )
        self.assertNotIn("history", request_body)
        self.assertTrue(any("ESCOPO EFETIVO DO USUÁRIO:" in message["content"]
                            for message in request_body["messages"] if message["role"] == "system"))

        malformed = json.dumps({"choices": []})
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}), patch(
            "server.urllib.request.urlopen", return_value=Response(malformed)
        ):
            status, fallback = self.request("POST", "/api/assistant/query", {
                "question": "Resuma este registro.", "context": {"recordId": focused_id},
            })
        self.assertEqual(status, 200, fallback)
        self.assertEqual(fallback["model"], "deterministic-fallback")
        self.assertIn("orientação disponível", fallback["notice"])

        status, company = self.request("POST", "/api/companies", {"name": "Empresa isolada do assistente"})
        self.assertEqual(status, 201, company)
        status, _switched = self.request("POST", "/api/company/switch", {"company_id": company["id"]})
        self.assertEqual(status, 200)
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            status, isolated = self.request("POST", "/api/assistant/query", {
                "question": "Resuma este registro.", "context": {"recordId": focused_id},
            })
        self.assertEqual(status, 200, isolated)
        self.assertNotIn("recordId", isolated["context"])
        self.assertFalse(any(item["id"] == focused_id for item in isolated["sources"]
                             if isinstance(item["id"], int)))

    def test_assistant_redacts_sensitive_fields_without_the_explicit_operation(self):
        row = {
            "id": 77, "module": "clientes", "title": "Hospital Seguro", "status": "Ativo",
            "amount": 1250.0, "due_date": None, "updated_at": utc_now(),
            "payload": json.dumps({
                "razao_social": "Hospital Seguro", "documento": "12.345.678/0001-90",
                "email": "contato@hospital.test", "observacao": "Sala limpa",
            }),
        }
        redacted = SIVSHandler.assistant_record_context(row, set())
        self.assertEqual(redacted["fields"], {
            "razao_social": "Hospital Seguro", "observacao": "Sala limpa",
        })
        self.assertIsNone(redacted["amount"])
        visible = SIVSHandler.assistant_record_context(row, {"view_sensitive", "view_values"})
        self.assertEqual(visible["fields"]["documento"], "12.345.678/0001-90")
        self.assertEqual(visible["fields"]["email"], "contato@hospital.test")
        self.assertEqual(visible["amount"], 1250.0)

    def test_assistant_refuses_modules_and_operations_outside_effective_scope(self):
        handler = SIVSHandler.__new__(SIVSHandler)

        quality_session = {"id": 7, "company_id": 1, "role": "quality", "permissions": "{}"}
        blocked_plan = handler.assistant_plan("mostre as contas a pagar", quality_session)
        blocked = handler.assistant_permission_result(
            "mostre as contas a pagar", blocked_plan, quality_session
        )
        self.assertIsNotNone(blocked)
        self.assertEqual(blocked[1], "permission-filter")
        self.assertIn("Contas a pagar", blocked[0]["answer"])
        self.assertEqual(blocked[0]["source_ids"], [])

        viewer_session = {"id": 8, "company_id": 1, "role": "viewer", "permissions": "{}"}
        create_plan = handler.assistant_plan("como cadastrar um cliente", viewer_session)
        create_blocked = handler.assistant_permission_result(
            "como cadastrar um cliente", create_plan, viewer_session
        )
        self.assertIsNotNone(create_blocked)
        self.assertEqual(create_blocked[1], "permission-filter")
        self.assertIn("criar cadastros", create_blocked[0]["answer"])

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

    def test_contact_requires_and_persists_relational_partner_link(self):
        self.setup_admin()
        status, partner = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Parceiro do contato", "status": "Ativo",
            "payload": {
                "assunto": "Parceiro comercial",
                "tipo_cadastro": "C", "tipo_pessoa": "Pessoa jurídica",
                "documento": "04252011000110", "razao_social": "Parceiro do contato",
            },
        })
        self.assertEqual(status, 201, partner)
        partner_id = partner["item"]["id"]
        status, contact = self.request("POST", "/api/records", {
            "module": "contatos", "title": "Maria de Compras", "status": "Ativo",
            "payload": {
                "assunto": "Contato comercial",
                "cliente_fornecedor_id": partner_id,
                "cliente_fornecedor": "Nome que veio do cliente",
                "tipo_contato": "Comercial", "cargo": "Compras",
            },
        })
        self.assertEqual(status, 201, contact)
        saved = contact["item"]
        self.assertEqual(saved["payload"]["cliente_fornecedor_id"], partner_id)
        self.assertEqual(saved["payload"]["cliente_fornecedor"], "Parceiro do contato")
        self.assertTrue(any(
            relation["record"] == f"{partner['item']['module']}:{partner_id}"
            and relation["type"] == "Contato de"
            for relation in saved["payload"].get("relacionamentos", [])
        ))

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
            status, early_lookup = self.request(
                "GET", f"/api/partners/lookup?document={document}"
            )
            self.assertEqual(status, 200, early_lookup)
            self.assertTrue(early_lookup["exists"])
            self.assertTrue(early_lookup["accessible"])
            self.assertEqual(early_lookup["item"]["id"], created["item"]["id"])
            self.assertEqual(early_lookup["item"]["title"], title)
            self.assertNotIn("payload", early_lookup["item"])
            status, editing_lookup = self.request(
                "GET", f"/api/partners/lookup?document={document}&excludeId={created['item']['id']}"
            )
            self.assertEqual(status, 200, editing_lookup)
            self.assertFalse(editing_lookup["exists"])
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

        status, invalid_lookup = self.request(
            "GET", "/api/partners/lookup?document=11111111111"
        )
        self.assertEqual(status, 400, invalid_lookup)
        self.assertEqual(invalid_lookup["error"], "invalid_party_document")

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
    def fiscal_test_pfx(password, cnpj="11105408000144"):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.x509.oid import NameOID, ObjectIdentifier

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SECCOL TESTE"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"A1 HOMOLOGACAO {cnpj}"),
        ])
        now = datetime.now(timezone.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(subject).issuer_name(issuer).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName([
                x509.OtherName(ObjectIdentifier("2.16.76.1.3.3"), b"\x16\x0e" + cnpj.encode("ascii")),
            ]), critical=False)
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
            mismatch_pfx = self.fiscal_test_pfx(password, "45723174000110")
            status, mismatch = self.request("POST", "/api/fiscal/certificate", {
                "branchId": branch_id,
                "password": password,
                "contentBase64": base64.b64encode(mismatch_pfx).decode("ascii"),
            })
            self.assertEqual(status, 400, mismatch)
            self.assertIn("raiz empresarial", mismatch["message"])
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

    def test_tax_rules_are_company_scoped_versioned_and_calculate_without_assumptions(self):
        self.setup_admin()
        status, branches = self.request("GET", "/api/branches")
        self.assertEqual(status, 200, branches)
        branch_id = branches["items"][0]["id"]
        status, operation = self.request("POST", "/api/fiscal/tax-operations", {
            "code": "VENDA_INTERNA", "name": "Venda interna de mercadoria", "direction": "OUT",
            "validFrom": "2026-01-01",
        })
        self.assertEqual(status, 201, operation)
        operation_id = operation["operationId"]
        status, profile = self.request("POST", "/api/fiscal/tax-profiles", {
            "name": "Normal GO mercadoria", "taxRegime": "REGIME_NORMAL",
            "requiredTaxCodes": ["ICMS", "PIS", "COFINS"], "branchId": branch_id,
            "validFrom": "2026-01-01",
        })
        self.assertEqual(status, 201, profile)
        profile_id = profile["taxProfileId"]
        source = "https://www.nfe.fazenda.gov.br/portal/principal.aspx"
        common = {"originUf": "GO", "destinationUf": "GO", "ncmPrefix": "9031", "cfop": "5102", "merchandiseOrigin": "0"}
        rule_ids = {}
        for tax_code, result in {
            "ICMS": {"cst": "00", "rateBps": 1800, "baseReductionBps": 0},
            "PIS": {"cst": "01", "rateBps": 165, "baseReductionBps": 0},
            "COFINS": {"cst": "01", "rateBps": 760, "baseReductionBps": 0},
        }.items():
            status, created = self.request("POST", "/api/fiscal/tax-rules", {
                "operationId": operation_id, "taxProfileId": profile_id, "taxCode": tax_code,
                "priority": 10, "conditions": common, "result": result,
                "referenceUrl": source, "referenceNote": "Revisado com a contabilidade",
                "validFrom": "2026-01-01",
            })
            self.assertEqual(status, 201, created)
            rule_ids[tax_code] = created["taxRuleId"]

        preview_payload = {
            "operationId": operation_id, "taxProfileId": profile_id, "issueDate": "2026-08-26",
            "originUf": "GO", "destinationUf": "GO",
            "items": [{"ncm": "90318099", "cfop": "5102", "merchandiseOrigin": "0",
                       "itemValue": "100,00", "discount": "0", "freight": "0",
                       "insurance": "0", "otherExpenses": "0"}],
        }
        status, preview = self.request("POST", "/api/fiscal/tax-preview", preview_payload)
        self.assertEqual(status, 200, preview)
        self.assertTrue(preview["ready"])
        self.assertEqual(preview["totals"]["baseValueCents"], 10000)
        self.assertEqual(preview["totals"]["taxesCents"], 2725)
        self.assertEqual(
            {tax["taxCode"]: tax["amountCents"] for tax in preview["items"][0]["taxes"]},
            {"ICMS": 1800, "PIS": 165, "COFINS": 760},
        )
        self.assertEqual(preview["items"][0]["taxes"][0]["referenceUrl"], source)
        status, setup = self.request("GET", "/api/fiscal/tax-setup")
        self.assertEqual(status, 200, setup)
        self.assertTrue(setup["canManage"])
        self.assertEqual(setup["profiles"][0]["branchNames"], branches["items"][0]["name"])

        status, conflicting = self.request("POST", "/api/fiscal/tax-rules", {
            "operationId": operation_id, "taxProfileId": profile_id, "taxCode": "ICMS",
            "priority": 10, "conditions": common,
            "result": {"cst": "00", "rateBps": 1700, "baseReductionBps": 0},
            "referenceUrl": source, "validFrom": "2026-01-01",
        })
        self.assertEqual(status, 201, conflicting)
        status, ambiguous = self.request("POST", "/api/fiscal/tax-preview", preview_payload)
        self.assertEqual(status, 200, ambiguous)
        self.assertFalse(ambiguous["ready"])
        self.assertIsNone(ambiguous["totals"]["taxesCents"])
        self.assertEqual(ambiguous["blockingIssues"][0]["code"], "AMBIGUOUS_TAX_RULE")
        status, revised = self.request("PUT", f"/api/fiscal/tax-rules/{conflicting['taxRuleId']}", {
            "operationId": operation_id, "taxProfileId": profile_id, "taxCode": "ICMS",
            "priority": 20, "conditions": common,
            "result": {"cst": "00", "rateBps": 1700, "baseReductionBps": 0},
            "referenceUrl": source, "validFrom": "2026-01-01",
        })
        self.assertEqual(status, 200, revised)
        self.assertEqual(self.db.scalar(
            "SELECT active FROM tax_rules WHERE id=?", (conflicting["taxRuleId"],),
        ), 0)
        self.assertEqual(self.db.scalar(
            "SELECT version FROM tax_rules WHERE id=?", (revised["taxRuleId"],),
        ), 2)
        status, resolved = self.request("POST", "/api/fiscal/tax-preview", preview_payload)
        self.assertEqual(status, 200, resolved)
        self.assertTrue(resolved["ready"])

        status, incomplete_profile = self.request("POST", "/api/fiscal/tax-profiles", {
            "name": "Perfil sem cobertura", "taxRegime": "REGIME_NORMAL",
            "requiredTaxCodes": ["IPI"], "validFrom": "2026-01-01",
        })
        self.assertEqual(status, 201, incomplete_profile)
        incomplete_payload = dict(preview_payload, taxProfileId=incomplete_profile["taxProfileId"])
        status, incomplete = self.request("POST", "/api/fiscal/tax-preview", incomplete_payload)
        self.assertEqual(status, 200, incomplete)
        self.assertFalse(incomplete["ready"])
        self.assertIsNone(incomplete["totals"]["taxesCents"])
        self.assertEqual(incomplete["blockingIssues"][0]["code"], "MISSING_TAX_RULE")

        now = utc_now()
        foreign_company = self.db.execute(
            "INSERT INTO companies(name,created_at,updated_at) VALUES('Outra empresa',?,?)",
            (now, now),
        ).lastrowid
        foreign_operation = self.db.execute(
            """INSERT INTO fiscal_operations
               (company_id,code,name,direction,parameters_json,version,active,created_at,updated_at)
               VALUES(?,'OUTRA','Outra empresa','OUT','{}',1,1,?,?)""",
            (foreign_company, now, now),
        ).lastrowid
        status, foreign = self.request("POST", "/api/fiscal/tax-rules", {
            "operationId": foreign_operation, "taxProfileId": profile_id, "taxCode": "ICMS",
            "priority": 30, "conditions": common,
            "result": {"cst": "00", "rateBps": 1700, "baseReductionBps": 0},
            "referenceUrl": source,
        })
        self.assertEqual(status, 409, foreign)
        self.assertEqual(foreign["error"], "fiscal_scope_conflict")
        status, readiness = self.request("GET", "/api/fiscal/readiness")
        self.assertEqual(status, 200, readiness)
        self.assertFalse(readiness["canIssue"])

    def test_customer_followups_are_idempotent_audited_and_reset_by_purchase(self):
        self.setup_admin()
        old_anchor = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat(
            timespec="seconds"
        )
        customer_id = self.db.execute(
            """INSERT INTO records
               (module,title,status,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('clientes','Cliente inativo','Ativo',?,?,?, ?,1,1)""",
            (json.dumps({"tipo_cadastro": "C", "vendedor": "Administrador"}),
             1, old_anchor, old_anchor),
        ).lastrowid
        self.server._refresh_customer_followups()
        self.server._refresh_customer_followups()
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM customer_followups WHERE customer_record_id=?",
            (customer_id,),
        ), 1)
        status, queue = self.request("GET", "/api/crm/followups")
        self.assertEqual(status, 200, queue)
        self.assertEqual(queue["items"][0]["stage_days"], 90)
        followup_id = queue["items"][0]["id"]
        status, contacted = self.request(
            "POST", f"/api/crm/followups/{followup_id}/contact",
            {"channel": "PHONE", "notes": "Retorno combinado", "outcome": "Agendado"},
        )
        self.assertEqual(status, 200, contacted)
        self.server._refresh_customer_followups()
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM customer_followups WHERE customer_record_id=? AND status='PENDING'",
            (customer_id,),
        ), 0)
        purchase_anchor = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(
            timespec="seconds"
        )
        self.db.execute(
            """INSERT INTO records
               (module,title,status,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('vendas','Venda confirmada','Confirmado',?,?,?, ?,1,1)""",
            (json.dumps({"cliente_id": customer_id, "data_confirmacao": purchase_anchor}),
             1, purchase_anchor, purchase_anchor),
        )
        self.server._refresh_customer_followups()
        pending = self.db.connection().execute(
            """SELECT stage_days,purchase_anchor_at FROM customer_followups
               WHERE customer_record_id=? AND status='PENDING'""",
            (customer_id,),
        ).fetchone()
        self.assertEqual(pending["stage_days"], 30)
        self.assertEqual(pending["purchase_anchor_at"], purchase_anchor)
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE entity_type='customer_followup'",
        ), 3)

    def test_accounting_export_is_audited_exact_and_company_scoped(self):
        self.setup_admin()
        status, partner = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Parceiro contábil",
            "status": "Ativo", "payload": {
                "assunto": "Parceiro contábil", "tipo_cadastro": "A",
                "tipo_pessoa": "Pessoa jurídica", "documento": "04252011000110",
                "razao_social": "Parceiro contábil", "avaliacao": "Aprovado",
            },
        })
        self.assertEqual(status, 201, partner)
        status, categories = self.request("GET", "/api/financial/categories")
        self.assertEqual(status, 200, categories)
        category_id = next(
            item["id"] for item in categories["items"]
            if item["name"] == "Serviços técnicos"
        )
        status, created = self.request("POST", "/api/records", {
            "module": "financeiro", "title": "Título contábil agosto",
            "status": "Ativo", "amount": 1234.56,
            "due_date": "2026-08-30",
            "payload": {"assunto": "Competência agosto", "tipo_lancamento": "Receita",
                        "parceiro_id": partner["item"]["id"],
                        "parceiro": "texto não confiável", "categoria_id": category_id,
                        "categoria": "texto não confiável", "documento": "FIN-2026-08-01",
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

    def test_financial_categories_are_company_scoped_and_expense_evidence_is_atomic(self):
        self.setup_admin()
        status, categories = self.request("GET", "/api/financial/categories")
        self.assertEqual(status, 200, categories)
        income_id = next(item["id"] for item in categories["items"] if item["kind"] == "INCOME")

        status, custom = self.request("POST", "/api/financial/categories", {
            "name": "Energia elétrica", "kind": "EXPENSE",
        })
        self.assertEqual(status, 201, custom)
        expense_id = custom["item"]["id"]
        status, duplicate = self.request("POST", "/api/financial/categories", {
            "name": "  energia   ELETRICA ", "kind": "EXPENSE",
        })
        self.assertEqual(status, 409, duplicate)
        admin_cookie, admin_csrf = self.cookie, self.csrf
        status, user = self.request("POST", "/api/users", {
            "name": "Fiscal categorias", "email": "fiscal-categorias@seccol.test",
            "password": "Senha-Fiscal-123", "role": "fiscal",
        })
        self.assertEqual(status, 201, user)
        status, login = self.request("POST", "/api/login", {
            "email": "fiscal-categorias@seccol.test", "password": "Senha-Fiscal-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, visible = self.request("GET", "/api/financial/categories")
        self.assertEqual(status, 200, visible)
        status, forbidden = self.request("POST", "/api/financial/categories", {
            "name": "Categoria sem admin", "kind": "EXPENSE",
        })
        self.assertEqual(status, 403, forbidden)
        self.cookie, self.csrf = admin_cookie, admin_csrf

        status, supplier = self.request("POST", "/api/records", {
            "module": "clientes_fornecedores", "title": "Fornecedor de energia",
            "status": "Ativo", "payload": {
                "assunto": "Fornecedor de energia", "tipo_cadastro": "F",
                "tipo_pessoa": "Pessoa jurídica", "documento": "04252011000110",
                "razao_social": "Fornecedor de energia", "avaliacao": "Aprovado",
                "aprovado_compras": True,
            },
        })
        self.assertEqual(status, 201, supplier)
        pdf = b"%PDF-1.4\n% comprovante de teste\n"
        expense_payload = {
            "module": "contas_pagar", "title": "Conta de energia agosto",
            "status": "Em aberto", "amount": 345.67, "due_date": "2026-08-30",
            "payload": {
                "assunto": "Energia agosto", "fornecedor_id": supplier["item"]["id"],
                "fornecedor": "nome adulterado", "documento": "NF-ENERGIA-08",
                "parcela": "1/1", "categoria_id": expense_id,
                "categoria": "categoria adulterada", "centro_custo": "Administrativo",
            },
            "attachment": {
                "filename": "nota-energia.pdf", "mime_type": "application/pdf",
                "content": "data:application/pdf;base64," + base64.b64encode(pdf).decode("ascii"),
                "category": "Nota fiscal / comprovante de despesa",
            },
        }
        status, created = self.request("POST", "/api/records", expense_payload)
        self.assertEqual(status, 201, created)
        self.assertEqual(created["item"]["payload"]["categoria"], "Energia elétrica")
        self.assertEqual(created["item"]["payload"]["categoria_id"], expense_id)
        attachment = self.db.connection().execute(
            "SELECT * FROM attachments WHERE id=? AND record_id=?",
            (created["attachmentId"], created["item"]["id"]),
        ).fetchone()
        self.assertEqual(attachment["sha256"], hashlib.sha256(pdf).hexdigest())
        self.assertEqual(attachment["company_id"], 1)
        status, inactive = self.request("PUT", f"/api/financial/categories/{expense_id}", {
            "name": "Energia elétrica", "kind": "EXPENSE", "active": False,
        })
        self.assertEqual(status, 200, inactive)
        self.assertFalse(inactive["item"]["active"])
        status, updated = self.request("PUT", f"/api/records/{created['item']['id']}", {
            "module": "contas_pagar", "title": created["item"]["title"],
            "status": created["item"]["status"], "amount": created["item"]["amount"],
            "due_date": created["item"]["due_date"], "revision": created["item"]["revision"],
            "payload": {**created["item"]["payload"], "notes": "Conferência concluída"},
        })
        self.assertEqual(status, 200, updated)

        wrong_kind = json.loads(json.dumps(expense_payload))
        wrong_kind["title"] = "Categoria incompatível"
        wrong_kind["payload"]["documento"] = "NF-ENERGIA-09"
        wrong_kind["payload"]["categoria_id"] = income_id
        wrong_kind.pop("attachment")
        status, rejected = self.request("POST", "/api/records", wrong_kind)
        self.assertEqual(status, 400, rejected)
        self.assertIn("não pode ser usada em despesa", rejected["message"])

        raw_category = json.loads(json.dumps(wrong_kind))
        raw_category["payload"].pop("categoria_id")
        raw_category["payload"]["categoria"] = "Digitada manualmente"
        status, rejected = self.request("POST", "/api/records", raw_category)
        self.assertEqual(status, 400, rejected)
        self.assertIn("categoria", rejected["message"])

        status, company = self.request("POST", "/api/companies", {"name": "Empresa isolada"})
        self.assertEqual(status, 201, company)
        status, switched = self.request("POST", "/api/company/switch", {
            "company_id": company["id"],
        })
        self.assertEqual(status, 200, switched)
        status, isolated = self.request("GET", "/api/financial/categories")
        self.assertEqual(status, 200, isolated)
        self.assertNotIn(expense_id, {item["id"] for item in isolated["items"]})
        status, missing = self.request("PUT", f"/api/financial/categories/{expense_id}", {
            "name": "Tentativa cruzada", "kind": "EXPENSE", "active": True,
        })
        self.assertEqual(status, 404, missing)

    def test_payables_require_suppliers_and_receivables_require_customers(self):
        self.setup_admin()
        status, categories = self.request("GET", "/api/financial/categories")
        self.assertEqual(status, 200, categories)
        expense_id = next(item["id"] for item in categories["items"] if item["kind"] == "EXPENSE")
        income_id = next(item["id"] for item in categories["items"] if item["kind"] == "INCOME")

        def create_party(title, role, document):
            status, result = self.request("POST", "/api/records", {
                "module": "clientes_fornecedores", "title": title, "status": "Ativo",
                "payload": {
                    "assunto": title, "tipo_cadastro": role,
                    "tipo_pessoa": "Pessoa jurídica", "documento": document,
                    "razao_social": title, "avaliacao": "Aprovado",
                    "aprovado_compras": True, "aprovado_faturamento": True,
                    "bloqueado": False, "relacionamentos": [],
                },
            })
            self.assertEqual(status, 201, result)
            return result["item"]

        customer = create_party("Cliente financeiro", "C", "12345678000195")
        supplier = create_party("Fornecedor financeiro", "F", "11222333000181")
        payable = {
            "module": "contas_pagar", "title": "Conta de fornecedor", "status": "Em aberto",
            "amount": 100, "due_date": "2026-09-10", "payload": {
                "assunto": "Pagamento testado", "fornecedor_id": customer["id"],
                "documento": "CP-ROLE-1", "parcela": "1/1",
                "categoria_id": expense_id, "centro_custo": "Administrativo",
            },
        }
        status, rejected = self.request("POST", "/api/records", payable)
        self.assertEqual(status, 400, rejected)
        self.assertIn("fornecedor compatível", rejected["message"])
        payable["payload"]["fornecedor_id"] = supplier["id"]
        status, created_payable = self.request("POST", "/api/records", payable)
        self.assertEqual(status, 201, created_payable)
        self.assertEqual(created_payable["item"]["payload"]["fornecedor"], supplier["title"])
        self.assertEqual(created_payable["item"]["payload"]["tipo_parte"], "Fornecedor (F)")

        receivable = {
            "module": "contas_receber", "title": "Crédito de cliente", "status": "Em aberto",
            "amount": 150, "due_date": "2026-09-15", "payload": {
                "assunto": "Recebimento testado", "cliente_id": supplier["id"],
                "documento": "CR-ROLE-1", "parcela": "1/1",
                "categoria_id": income_id, "centro_custo": "Comercial",
            },
        }
        status, rejected = self.request("POST", "/api/records", receivable)
        self.assertEqual(status, 400, rejected)
        self.assertIn("cliente compatível", rejected["message"])
        receivable["payload"]["cliente_id"] = customer["id"]
        status, created_receivable = self.request("POST", "/api/records", receivable)
        self.assertEqual(status, 201, created_receivable)
        self.assertEqual(created_receivable["item"]["payload"]["cliente"], customer["title"])
        self.assertEqual(created_receivable["item"]["payload"]["tipo_parte"], "Cliente (C)")

        financial = {
            "module": "financeiro", "title": "Receita de cliente", "status": "Ativo",
            "amount": 200, "due_date": "2026-09-20", "payload": {
                "assunto": "Receita testada", "tipo_lancamento": "Receita",
                "parceiro_id": supplier["id"], "categoria_id": income_id,
                "documento": "FIN-ROLE-1", "conta": "Conta corrente",
                "centro_custo": "Comercial",
            },
        }
        status, rejected = self.request("POST", "/api/records", financial)
        self.assertEqual(status, 400, rejected)
        self.assertIn("cliente compatível", rejected["message"])
        financial["payload"]["parceiro_id"] = customer["id"]
        status, created_revenue = self.request("POST", "/api/records", financial)
        self.assertEqual(status, 201, created_revenue)
        self.assertEqual(created_revenue["item"]["payload"]["parceiro"], customer["title"])

        financial["title"] = "Despesa de fornecedor"
        financial["payload"].update({
            "assunto": "Despesa testada", "tipo_lancamento": "Despesa",
            "categoria_id": expense_id, "documento": "FIN-ROLE-2",
        })
        status, rejected = self.request("POST", "/api/records", financial)
        self.assertEqual(status, 400, rejected)
        self.assertIn("fornecedor compatível", rejected["message"])
        financial["payload"]["parceiro_id"] = supplier["id"]
        status, created_expense = self.request("POST", "/api/records", financial)
        self.assertEqual(status, 201, created_expense)
        self.assertEqual(created_expense["item"]["payload"]["parceiro"], supplier["title"])

    def test_accounting_foundation_is_scoped_permissioned_and_audited(self):
        self.setup_admin()
        status, account = self.request("POST", "/api/accounting/chart-accounts", {
            "code": "1.1.01", "name": "Banco operacional", "nature": "ASSET", "accountKind": "ANALYTICAL",
        })
        self.assertEqual(status, 200, account)
        self.assertEqual(account["accounts"][0]["code"], "1.1.01")
        status, center = self.request("POST", "/api/accounting/cost-centers", {"code": "ADM", "name": "Administracao"})
        self.assertEqual(status, 200, center)
        self.assertEqual(center["costCenters"][0]["code"], "ADM")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM audit_log WHERE entity_type='accounting_chart_account'"), 1)
        status, second = self.request("POST", "/api/companies", {"name": "Empresa contabil isolada"})
        self.assertEqual(status, 201, second)
        self.assertEqual(self.request("POST", "/api/company/switch", {"company_id": second["id"]})[0], 200)
        status, isolated = self.request("GET", "/api/accounting/foundation")
        self.assertEqual((status, isolated["accounts"], isolated["costCenters"]), (200, [], []))

    def test_accounting_journal_requires_balanced_analytical_entries_and_uses_reversal(self):
        self.setup_admin()
        self.request("POST", "/api/accounting/chart-accounts", {"code": "1.1", "name": "Banco", "nature": "ASSET", "accountKind": "ANALYTICAL"})
        self.request("POST", "/api/accounting/chart-accounts", {"code": "3.1", "name": "Receita", "nature": "REVENUE", "accountKind": "ANALYTICAL"})
        status, foundation = self.request("GET", "/api/accounting/foundation")
        self.assertEqual(status, 200)
        accounts = {item["code"]: item["id"] for item in foundation["accounts"]}
        payload = {"entryDate": "2026-08-26", "competenceDate": "2026-08-01", "memo": "Receita de servico", "lines": [
            {"accountId": accounts["1.1"], "debit": "100,00", "credit": "0"},
            {"accountId": accounts["3.1"], "debit": "0", "credit": "100,00"},
        ]}
        status, created = self.request("POST", "/api/accounting/journal-entries", payload)
        self.assertEqual(status, 201, created)
        status, entries = self.request("GET", "/api/accounting/journal-entries?period=2026-08")
        self.assertEqual((status, entries["items"][0]["debit_cents"], entries["items"][0]["credit_cents"]), (200, 10000, 10000))
        status, reversed_entry = self.request("POST", f"/api/accounting/journal-entries/{created['id']}/reverse", {"entryDate": "2026-08-27", "competenceDate": "2026-08-01", "memo": "Correcao de lancamento"})
        self.assertEqual(status, 201, reversed_entry)
        status, duplicate = self.request("POST", f"/api/accounting/journal-entries/{created['id']}/reverse", {"entryDate": "2026-08-27", "competenceDate": "2026-08-01", "memo": "Correcao de lancamento"})
        self.assertEqual(status, 409, duplicate)

    def test_accounting_chart_rejects_cycles_and_parent_downgrade(self):
        self.setup_admin()
        self.assertEqual(self.request("POST", "/api/accounting/chart-accounts", {
            "code": "1", "name": "Ativo", "nature": "ASSET", "accountKind": "GROUP",
        })[0], 200)
        status, foundation = self.request("GET", "/api/accounting/foundation")
        parent_id = next(item["id"] for item in foundation["accounts"] if item["code"] == "1")
        self.assertEqual(self.request("POST", "/api/accounting/chart-accounts", {
            "code": "1.1", "name": "Disponibilidades", "nature": "ASSET", "accountKind": "GROUP", "parentId": parent_id,
        })[0], 200)
        status, foundation = self.request("GET", "/api/accounting/foundation")
        child_id = next(item["id"] for item in foundation["accounts"] if item["code"] == "1.1")
        status, cycle = self.request("PUT", f"/api/accounting/chart-accounts/{parent_id}", {
            "code": "1", "name": "Ativo", "nature": "ASSET", "accountKind": "GROUP", "parentId": child_id,
        })
        self.assertEqual(status, 409, cycle)
        status, downgrade = self.request("PUT", f"/api/accounting/chart-accounts/{parent_id}", {
            "code": "1", "name": "Ativo", "nature": "ASSET", "accountKind": "ANALYTICAL",
        })
        self.assertEqual(status, 409, downgrade)

    def test_financial_accounting_mapping_requires_company_category_and_analytical_accounts(self):
        self.setup_admin()
        self.request("POST", "/api/accounting/chart-accounts", {"code": "1.1", "name": "Banco", "nature": "ASSET", "accountKind": "ANALYTICAL"})
        self.request("POST", "/api/accounting/chart-accounts", {"code": "2.1", "name": "Fornecedores", "nature": "LIABILITY", "accountKind": "ANALYTICAL"})
        status, categories = self.request("GET", "/api/financial/categories")
        self.assertEqual(status, 200)
        expense = next(item for item in categories["items"] if item["kind"] in {"EXPENSE", "BOTH"})
        status, foundation = self.request("GET", "/api/accounting/foundation")
        accounts = {item["code"]: item["id"] for item in foundation["accounts"]}
        status, result = self.request("POST", "/api/accounting/financial-mappings", {
            "financialModule": "contas_pagar", "categoryId": expense["id"],
            "debitAccountId": accounts["2.1"], "creditAccountId": accounts["1.1"],
        })
        self.assertEqual(status, 200, result)
        self.assertEqual(result["items"][0]["financial_module"], "contas_pagar")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM audit_log WHERE entity_type='accounting_financial_mapping'"), 1)
        now = utc_now()
        title_id = self.db.execute(
            """INSERT INTO records(module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('contas_pagar','Pagamento mapeado','Em aberto',50,'2026-08-30',?,1,?,?,1,1)""",
            (json.dumps({"fornecedor": "Fornecedor", "tipo_parte": "Fornecedor (F)", "documento": "MAP-1", "parcela": "1/1", "categoria_id": expense["id"], "categoria": expense["name"], "centro_custo": "ADM"}), now, now),
        ).lastrowid
        status, settlement = self.request("POST", f"/api/financial/titles/{title_id}/settlements", {
            "revision": 1, "principal": "50,00", "discount": "0", "interest": "0", "fee": "0",
            "date": "2026-08-26", "account": "Banco", "paymentMethod": "PIX", "note": "Baixa mapeada",
        })
        self.assertEqual(status, 201, settlement)
        self.assertIsNotNone(settlement["accountingEntryId"])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM accounting_journal_lines WHERE entry_id=?", (settlement["accountingEntryId"],)), 2)
        status, reversal = self.request("POST", f"/api/financial/settlements/{settlement['settlementId']}/reverse", {
            "revision": settlement["title"]["revision"], "date": "2026-08-27", "reason": "Pagamento registrado na conta incorreta",
        })
        self.assertEqual(status, 201, reversal)
        self.assertIsNotNone(reversal["accountingEntryId"])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM accounting_journal_lines WHERE entry_id=?", (reversal["accountingEntryId"],)), 2)

    def test_period_closure_blocks_mapped_financial_settlement_atomically(self):
        self.setup_admin()
        self.request("POST", "/api/accounting/chart-accounts", {"code": "1.1", "name": "Banco", "nature": "ASSET", "accountKind": "ANALYTICAL"})
        self.request("POST", "/api/accounting/chart-accounts", {"code": "2.1", "name": "Fornecedores", "nature": "LIABILITY", "accountKind": "ANALYTICAL"})
        status, categories = self.request("GET", "/api/financial/categories")
        self.assertEqual(status, 200)
        expense = next(item for item in categories["items"] if item["kind"] in {"EXPENSE", "BOTH"})
        status, foundation = self.request("GET", "/api/accounting/foundation")
        self.assertEqual(status, 200)
        accounts = {item["code"]: item["id"] for item in foundation["accounts"]}
        self.assertEqual(self.request("POST", "/api/accounting/financial-mappings", {
            "financialModule": "contas_pagar", "categoryId": expense["id"],
            "debitAccountId": accounts["2.1"], "creditAccountId": accounts["1.1"],
        })[0], 200)
        now = utc_now()
        title_id = self.db.execute(
            """INSERT INTO records(module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('contas_pagar','Baixa bloqueada por fechamento','Em aberto',50,'2026-08-30',?,1,?,?,1,1)""",
            (json.dumps({"fornecedor": "Fornecedor", "tipo_parte": "Fornecedor (F)", "documento": "CLOSE-MAP-1", "parcela": "1/1", "categoria_id": expense["id"], "categoria": expense["name"]}), now, now),
        ).lastrowid
        self.assertEqual(self.request("POST", "/api/accounting/periods/2026-08/close", {
            "reason": "Competencia conferida antes da publicacao contábil",
        })[0], 200)
        status, blocked = self.request("POST", f"/api/financial/titles/{title_id}/settlements", {
            "revision": 1, "principal": "50,00", "discount": "0", "interest": "0", "fee": "0",
            "date": "2026-08-26", "account": "Banco", "paymentMethod": "PIX", "note": "Baixa que deve ser recusada",
        })
        self.assertEqual(status, 409, blocked)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM financial_settlements WHERE financial_record_id=?", (title_id,)), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM records WHERE module='caixa' AND company_id=1"), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM accounting_journal_entries WHERE company_id=1"), 0)

    def test_financial_mapping_explicitly_allocates_exact_cents_by_cost_center(self):
        self.setup_admin()
        self.request("POST", "/api/accounting/chart-accounts", {"code": "1.1", "name": "Banco", "nature": "ASSET", "accountKind": "ANALYTICAL"})
        self.request("POST", "/api/accounting/chart-accounts", {"code": "2.1", "name": "Fornecedores", "nature": "LIABILITY", "accountKind": "ANALYTICAL"})
        self.assertEqual(self.request("POST", "/api/accounting/cost-centers", {"code": "ADM", "name": "Administracao"})[0], 200)
        self.assertEqual(self.request("POST", "/api/accounting/cost-centers", {"code": "COM", "name": "Comercial"})[0], 200)
        status, categories = self.request("GET", "/api/financial/categories")
        self.assertEqual(status, 200)
        expense = next(item for item in categories["items"] if item["kind"] in {"EXPENSE", "BOTH"})
        status, foundation = self.request("GET", "/api/accounting/foundation")
        self.assertEqual(status, 200)
        accounts = {item["code"]: item["id"] for item in foundation["accounts"]}
        centers = {item["code"]: item["id"] for item in foundation["costCenters"]}
        status, mapping = self.request("POST", "/api/accounting/financial-mappings", {
            "financialModule": "contas_pagar", "categoryId": expense["id"],
            "debitAccountId": accounts["2.1"], "creditAccountId": accounts["1.1"],
            "allocationSide": "DEBIT", "allocations": [
                {"costCenterId": centers["ADM"], "basisPoints": 6000},
                {"costCenterId": centers["COM"], "basisPoints": 4000},
            ],
        })
        self.assertEqual(status, 200, mapping)
        self.assertEqual([(row["cost_center_code"], row["basis_points"]) for row in mapping["items"][0]["allocations"]], [("ADM", 6000), ("COM", 4000)])
        invalid = self.request("PUT", f"/api/accounting/financial-mappings/{mapping['items'][0]['id']}", {
            "financialModule": "contas_pagar", "categoryId": expense["id"],
            "debitAccountId": accounts["2.1"], "creditAccountId": accounts["1.1"],
            "allocationSide": "DEBIT", "allocations": [
                {"costCenterId": centers["ADM"], "basisPoints": 6000},
                {"costCenterId": centers["COM"], "basisPoints": 3999},
            ],
        })
        self.assertEqual(invalid[0], 400, invalid)
        now = utc_now()
        title_id = self.db.execute(
            """INSERT INTO records(module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('contas_pagar','Rateio exato','Em aberto',99.99,'2026-08-30',?,1,?,?,1,1)""",
            (json.dumps({"fornecedor": "Fornecedor", "tipo_parte": "Fornecedor (F)", "documento": "ALLOC-1", "parcela": "1/1", "categoria_id": expense["id"], "categoria": expense["name"]}), now, now),
        ).lastrowid
        status, settlement = self.request("POST", f"/api/financial/titles/{title_id}/settlements", {
            "revision": 1, "principal": "99,99", "discount": "0", "interest": "0", "fee": "0",
            "date": "2026-08-26", "account": "Banco", "paymentMethod": "PIX", "note": "Baixa com rateio",
        })
        self.assertEqual(status, 201, settlement)
        lines = self.db.connection().execute(
            """SELECT a.code account_code,c.code cost_center_code,l.debit_cents,l.credit_cents
                 FROM accounting_journal_lines l
                 JOIN accounting_chart_accounts a ON a.id=l.account_id
                 LEFT JOIN cost_centers c ON c.id=l.cost_center_id
                WHERE l.entry_id=? ORDER BY l.id""", (settlement["accountingEntryId"],),
        ).fetchall()
        self.assertEqual([tuple(row) for row in lines], [
            ("2.1", "ADM", 5999, 0), ("2.1", "COM", 4000, 0), ("1.1", None, 0, 9999),
        ])
        status, reversed_entry = self.request("POST", f"/api/financial/settlements/{settlement['settlementId']}/reverse", {
            "revision": settlement["title"]["revision"], "date": "2026-08-27", "reason": "Rateio cancelado para nova conferencia",
        })
        self.assertEqual(status, 201, reversed_entry)
        reversed_lines = self.db.connection().execute(
            "SELECT cost_center_id,debit_cents,credit_cents FROM accounting_journal_lines WHERE entry_id=? ORDER BY id",
            (reversed_entry["accountingEntryId"],),
        ).fetchall()
        self.assertEqual([tuple(row) for row in reversed_lines], [
            (centers["ADM"], 0, 5999), (centers["COM"], 0, 4000), (None, 9999, 0),
        ])

    def test_financial_adjustments_require_explicit_accounts_and_keep_accounting_balanced(self):
        self.setup_admin()
        for code, name, nature in [
            ("1.1", "Banco", "ASSET"), ("1.2", "Clientes", "ASSET"),
            ("2.1", "Fornecedores", "LIABILITY"), ("3.1", "Juros recebidos", "REVENUE"),
            ("3.2", "Descontos obtidos", "REVENUE"), ("4.1", "Descontos concedidos", "EXPENSE"),
            ("4.2", "Juros pagos", "EXPENSE"), ("4.3", "Tarifas bancarias", "EXPENSE"),
        ]:
            self.assertEqual(self.request("POST", "/api/accounting/chart-accounts", {
                "code": code, "name": name, "nature": nature, "accountKind": "ANALYTICAL",
            })[0], 200)
        self.assertEqual(self.request("POST", "/api/accounting/cost-centers", {
            "code": "FIN", "name": "Financeiro",
        })[0], 200)
        status, foundation = self.request("GET", "/api/accounting/foundation")
        self.assertEqual(status, 200)
        accounts = {item["code"]: item["id"] for item in foundation["accounts"]}
        centers = {item["code"]: item["id"] for item in foundation["costCenters"]}
        status, categories = self.request("GET", "/api/financial/categories")
        self.assertEqual(status, 200)
        expense = next(item for item in categories["items"] if item["kind"] in {"EXPENSE", "BOTH"})
        income = next(item for item in categories["items"] if item["kind"] in {"INCOME", "BOTH"})
        payable_rules = [
            {"type": "DISCOUNT", "accountId": accounts["3.2"]},
            {"type": "INTEREST", "accountId": accounts["4.2"], "costCenterId": centers["FIN"]},
            {"type": "FEE", "accountId": accounts["4.3"], "costCenterId": centers["FIN"]},
        ]
        status, mapped_payable = self.request("POST", "/api/accounting/financial-mappings", {
            "financialModule": "contas_pagar", "categoryId": expense["id"],
            "debitAccountId": accounts["2.1"], "creditAccountId": accounts["1.1"],
            "adjustmentRules": payable_rules,
        })
        self.assertEqual(status, 200, mapped_payable)
        self.assertEqual(
            [(item["adjustment_type"], item["account_id"]) for item in mapped_payable["items"][0]["adjustmentRules"]],
            [("DISCOUNT", accounts["3.2"]), ("FEE", accounts["4.3"]), ("INTEREST", accounts["4.2"])],
        )
        status, mapped_receivable = self.request("POST", "/api/accounting/financial-mappings", {
            "financialModule": "contas_receber", "categoryId": income["id"],
            "debitAccountId": accounts["1.1"], "creditAccountId": accounts["1.2"],
            "adjustmentRules": [
                {"type": "DISCOUNT", "accountId": accounts["4.1"]},
                {"type": "INTEREST", "accountId": accounts["3.1"]},
                {"type": "FEE", "accountId": accounts["4.3"], "costCenterId": centers["FIN"]},
            ],
        })
        self.assertEqual(status, 200, mapped_receivable)
        now = utc_now()
        payable_id = self.db.execute(
            """INSERT INTO records(module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('contas_pagar','Pagamento com ajustes','Em aberto',100,'2026-08-30',?,1,?,?,1,1)""",
            (json.dumps({"fornecedor": "Fornecedor", "tipo_parte": "Fornecedor (F)", "documento": "ADJ-P-1", "parcela": "1/1", "categoria_id": expense["id"], "categoria": expense["name"]}), now, now),
        ).lastrowid
        receivable_id = self.db.execute(
            """INSERT INTO records(module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('contas_receber','Recebimento com ajustes','Em aberto',100,'2026-08-30',?,1,?,?,1,1)""",
            (json.dumps({"cliente": "Cliente", "tipo_parte": "Cliente (C)", "documento": "ADJ-R-1", "parcela": "1/1", "categoria_id": income["id"], "categoria": income["name"]}), now, now),
        ).lastrowid
        settlement_payload = {
            "revision": 1, "principal": "100,00", "discount": "10,00", "interest": "2,00", "fee": "3,00",
            "date": "2026-08-26", "account": "Banco", "paymentMethod": "PIX", "note": "Baixa com ajustes configurados",
        }
        status, payable = self.request("POST", f"/api/financial/titles/{payable_id}/settlements", settlement_payload)
        self.assertEqual(status, 201, payable)
        self.assertEqual(payable["entries"][0]["cash_amount_cents"], 9500)
        payable_lines = self.db.connection().execute(
            """SELECT a.code,c.code,l.debit_cents,l.credit_cents FROM accounting_journal_lines l
                 JOIN accounting_chart_accounts a ON a.id=l.account_id
                 LEFT JOIN cost_centers c ON c.id=l.cost_center_id
                WHERE l.entry_id=? ORDER BY l.id""", (payable["accountingEntryId"],),
        ).fetchall()
        self.assertEqual([tuple(line) for line in payable_lines], [
            ("2.1", None, 10000, 0), ("1.1", None, 0, 9500), ("3.2", None, 0, 1000),
            ("4.2", "FIN", 200, 0), ("4.3", "FIN", 300, 0),
        ])
        status, receivable = self.request("POST", f"/api/financial/titles/{receivable_id}/settlements", settlement_payload)
        self.assertEqual(status, 201, receivable)
        self.assertEqual(receivable["entries"][0]["cash_amount_cents"], 8900)
        receivable_lines = self.db.connection().execute(
            """SELECT a.code,c.code,l.debit_cents,l.credit_cents FROM accounting_journal_lines l
                 JOIN accounting_chart_accounts a ON a.id=l.account_id
                 LEFT JOIN cost_centers c ON c.id=l.cost_center_id
                WHERE l.entry_id=? ORDER BY l.id""", (receivable["accountingEntryId"],),
        ).fetchall()
        self.assertEqual([tuple(line) for line in receivable_lines], [
            ("1.1", None, 8900, 0), ("1.2", None, 0, 10000), ("4.1", None, 1000, 0),
            ("3.1", None, 0, 200), ("4.3", "FIN", 300, 0),
        ])
        status, reversed_payable = self.request("POST", f"/api/financial/settlements/{payable['settlementId']}/reverse", {
            "revision": payable["title"]["revision"], "date": "2026-08-27", "reason": "Estorno de baixa com ajustes",
        })
        self.assertEqual(status, 201, reversed_payable)
        self.assertEqual(self.db.scalar(
            "SELECT debit_cents FROM accounting_journal_lines WHERE entry_id=? AND account_id=?",
            (reversed_payable["accountingEntryId"], accounts["1.1"]),
        ), 9500)
        incomplete_mapping = self.request("PUT", f"/api/accounting/financial-mappings/{mapped_payable['items'][0]['id']}", {
            "financialModule": "contas_pagar", "categoryId": expense["id"],
            "debitAccountId": accounts["2.1"], "creditAccountId": accounts["1.1"],
            "adjustmentRules": payable_rules[:2],
        })
        self.assertEqual(incomplete_mapping[0], 200, incomplete_mapping)
        blocked_id = self.db.execute(
            """INSERT INTO records(module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('contas_pagar','Tarifa sem conta','Em aberto',100,'2026-08-30',?,1,?,?,1,1)""",
            (json.dumps({"fornecedor": "Fornecedor", "tipo_parte": "Fornecedor (F)", "documento": "ADJ-P-2", "parcela": "1/1", "categoria_id": expense["id"], "categoria": expense["name"]}), now, now),
        ).lastrowid
        status, blocked = self.request("POST", f"/api/financial/titles/{blocked_id}/settlements", settlement_payload)
        self.assertEqual(status, 409, blocked)
        self.assertIn("tarifa", blocked["message"])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM financial_settlements WHERE financial_record_id=?", (blocked_id,)), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM records WHERE module='caixa' AND payload LIKE ?", ("%ADJ-P-2%",)), 0)

    def test_accounting_reports_respect_competence_cash_and_balanced_statements(self):
        self.setup_admin()
        for code, name, nature in [
            ("1.1", "Banco", "ASSET"), ("2.1", "Fornecedores", "LIABILITY"),
            ("3.1", "Receita de servicos", "REVENUE"), ("4.1", "Despesa administrativa", "EXPENSE"),
        ]:
            self.assertEqual(self.request("POST", "/api/accounting/chart-accounts", {
                "code": code, "name": name, "nature": nature, "accountKind": "ANALYTICAL",
            })[0], 200)
        status, foundation = self.request("GET", "/api/accounting/foundation")
        self.assertEqual(status, 200)
        accounts = {item["code"]: item["id"] for item in foundation["accounts"]}
        status, first = self.request("POST", "/api/accounting/journal-entries", {
            "entryDate": "2026-08-05", "competenceDate": "2026-07-31", "memo": "Receita recebida em agosto", "lines": [
                {"accountId": accounts["1.1"], "debit": "100,00", "credit": "0"},
                {"accountId": accounts["3.1"], "debit": "0", "credit": "100,00"},
            ],
        })
        self.assertEqual(status, 201, first)
        status, second = self.request("POST", "/api/accounting/journal-entries", {
            "entryDate": "2026-07-31", "competenceDate": "2026-08-05", "memo": "Despesa de competencia agosto", "lines": [
                {"accountId": accounts["4.1"], "debit": "30,00", "credit": "0"},
                {"accountId": accounts["2.1"], "debit": "0", "credit": "30,00"},
            ],
        })
        self.assertEqual(status, 201, second)
        status, competence = self.request("GET", "/api/accounting/reports?period=2026-08&basis=competence")
        self.assertEqual(status, 200, competence)
        self.assertEqual([item["id"] for item in competence["journal"]["items"]], [second["id"]])
        self.assertEqual((competence["trialBalance"]["debitCents"], competence["trialBalance"]["creditCents"]), (3000, 3000))
        self.assertEqual((competence["incomeStatement"]["revenueCents"], competence["incomeStatement"]["expenseCents"], competence["incomeStatement"]["netIncomeCents"]), (0, 3000, -3000))
        self.assertEqual((competence["balanceSheet"]["assetCents"], competence["balanceSheet"]["liabilityCents"], competence["balanceSheet"]["accumulatedResultCents"], competence["balanceSheet"]["differenceCents"]), (10000, 3000, 7000, 0))
        status, cash = self.request("GET", f"/api/accounting/reports?period=2026-08&basis=cash&accountId={accounts['1.1']}")
        self.assertEqual(status, 200, cash)
        self.assertEqual([item["id"] for item in cash["journal"]["items"]], [first["id"]])
        self.assertEqual((cash["incomeStatement"]["revenueCents"], cash["incomeStatement"]["expenseCents"], cash["incomeStatement"]["netIncomeCents"]), (10000, 0, 10000))
        self.assertEqual(len(cash["ledger"]["items"]), 1)
        self.assertTrue(cash["trialBalance"]["balanced"])

    def test_opening_balances_and_period_closure_are_audited_and_lock_competence(self):
        self.setup_admin()
        self.request("POST", "/api/accounting/chart-accounts", {"code": "1.1", "name": "Caixa", "nature": "ASSET", "accountKind": "ANALYTICAL"})
        self.request("POST", "/api/accounting/chart-accounts", {"code": "2.1", "name": "Capital", "nature": "EQUITY", "accountKind": "ANALYTICAL"})
        status, foundation = self.request("GET", "/api/accounting/foundation")
        self.assertEqual(status, 200)
        accounts = {item["code"]: item["id"] for item in foundation["accounts"]}
        opening = {"date": "2026-08-01", "memo": "Abertura contábil agosto", "lines": [
            {"accountId": accounts["1.1"], "debit": "100,00", "credit": "0"},
            {"accountId": accounts["2.1"], "debit": "0", "credit": "100,00"},
        ]}
        status, created = self.request("POST", "/api/accounting/opening-balances", opening)
        self.assertEqual(status, 201, created)
        status, duplicate = self.request("POST", "/api/accounting/opening-balances", opening)
        self.assertEqual(status, 409, duplicate)
        invalid_opening = dict(opening, date="2026-08-02")
        self.assertEqual(self.request("POST", "/api/accounting/opening-balances", invalid_opening)[0], 400)
        status, closed = self.request("POST", "/api/accounting/periods/2026-08/close", {"reason": "Balancete conferido pelo responsável"})
        self.assertEqual(status, 200, closed)
        self.assertEqual(closed["items"][0]["status"], "CLOSED")
        manual = {"entryDate": "2026-08-15", "competenceDate": "2026-08-15", "memo": "Lançamento bloqueado", "lines": [
            {"accountId": accounts["1.1"], "debit": "10,00", "credit": "0"},
            {"accountId": accounts["2.1"], "debit": "0", "credit": "10,00"},
        ]}
        self.assertEqual(self.request("POST", "/api/accounting/journal-entries", manual)[0], 409)
        status, report = self.request("GET", "/api/accounting/reports?period=2026-08")
        self.assertEqual((status, report["periodStatus"]["status"]), (200, "CLOSED"))
        status, reopened = self.request("POST", "/api/accounting/periods/2026-08/reopen", {"reason": "Ajuste documentado pelo contador"})
        self.assertEqual(status, 200, reopened)
        self.assertEqual(reopened["items"][0]["status"], "REOPENED")
        self.assertEqual(self.request("POST", "/api/accounting/journal-entries", manual)[0], 201)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM audit_log WHERE entity_type='accounting_period'"), 2)

    def test_period_closure_requires_its_specific_fiscal_operation(self):
        self.setup_admin()
        status, user = self.request("POST", "/api/users", {
            "name": "Fiscal sem fechamento", "email": "fiscal-sem-fechamento@seccol.test",
            "password": "Senha-Fiscal-123", "role": "fiscal",
            "effectivePermissions": {"read": ["fiscal"], "write": ["fiscal"], "export": []},
            "effectiveActions": {"fiscal": []},
        })
        self.assertEqual(status, 201, user)
        self.cookie = None
        self.csrf = None
        status, login = self.request("POST", "/api/login", {
            "email": "fiscal-sem-fechamento@seccol.test", "password": "Senha-Fiscal-123",
        }, authenticated=False)
        self.assertEqual(status, 200, login)
        self.csrf = login["csrfToken"]
        status, denied = self.request("POST", "/api/accounting/periods/2026-08/close", {
            "reason": "Tentativa sem a função específica de fechamento",
        })
        self.assertEqual((status, denied["error"]), (403, "operation_forbidden"))
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM accounting_period_closures"), 0)

    def test_bank_accounts_are_unique_scoped_and_linked_to_settlements(self):
        self.setup_admin()
        status, created = self.request("POST", "/api/bank-accounts", {
            "name": "Conta operacional", "bankCode": "001", "bankName": "Banco Teste",
            "branchCode": "1234", "accountNumber": "987654321", "accountType": "CHECKING",
        })
        self.assertEqual(status, 200, created)
        self.assertEqual(created["items"][0]["account_last4"], "4321")
        self.assertNotIn("accountNumber", created["items"][0])
        status, duplicate = self.request("POST", "/api/bank-accounts", {
            "name": "Outra descrição", "bankCode": "001", "branchCode": "1234",
            "accountNumber": "987.654.321", "accountType": "CHECKING",
        })
        self.assertEqual(status, 409, duplicate)
        now = utc_now()
        title_id = self.db.execute(
            """INSERT INTO records(module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id,revision)
               VALUES('contas_pagar','Pagamento por banco','Em aberto',50,'2026-08-30',?,1,?,?,1,1)""",
            (json.dumps({"fornecedor": "Fornecedor", "tipo_parte": "Fornecedor (F)", "documento": "BANK-1", "parcela": "1/1", "categoria": "Compras"}), now, now),
        ).lastrowid
        status, settlement = self.request("POST", f"/api/financial/titles/{title_id}/settlements", {
            "revision": 1, "principal": "50,00", "discount": "0", "interest": "0", "fee": "0",
            "date": "2026-08-26", "account": "", "bankAccountId": created["items"][0]["id"],
            "paymentMethod": "PIX", "note": "Baixa com conta cadastrada",
        })
        self.assertEqual(status, 201, settlement)
        linked = self.db.connection().execute(
            "SELECT bank_account_id,account FROM financial_settlements WHERE id=?", (settlement["settlementId"],)
        ).fetchone()
        self.assertEqual((linked["bank_account_id"], linked["account"]), (created["items"][0]["id"], "Conta operacional · final 4321"))
        status, second_company = self.request("POST", "/api/companies", {"name": "Outra empresa bancária"})
        self.assertEqual(status, 201, second_company)
        self.assertEqual(self.request("POST", "/api/company/switch", {"company_id": second_company["id"]})[0], 200)
        status, isolated = self.request("GET", "/api/bank-accounts")
        self.assertEqual((status, isolated["items"]), (200, []))

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

    def test_fiscal_sale_draft_snapshots_product_classification_and_never_issues(self):
        self.setup_admin()
        now = utc_now()
        branch_id = self.db.scalar("SELECT id FROM branches WHERE company_id=1 ORDER BY id LIMIT 1")
        self.db.execute("UPDATE branches SET uf='GO' WHERE id=?", (branch_id,))
        customer_id = self.db.execute(
            """INSERT INTO records(module,title,status,payload,created_by,created_at,updated_at,company_id)
               VALUES('clientes','Cliente fiscal','Ativo',?,?,?, ?,1)""",
            (json.dumps({"tipo_cadastro": "C", "cidade": "Goiânia/GO", "bloqueado": False}), 1, now, now),
        ).lastrowid
        product_id = self.db.execute(
            """INSERT INTO records(module,title,status,payload,created_by,created_at,updated_at,company_id)
               VALUES('produtos','Produto fiscal','Ativo','{}',?,?,?,1)""", (1, now, now),
        ).lastrowid
        sale_id = self.db.execute(
            """INSERT INTO records(module,title,status,payload,created_by,created_at,updated_at,company_id)
               VALUES('vendas','Venda fiscal','Confirmado',?,?,?, ?,1)""",
            (json.dumps({"cliente_id": customer_id}), 1, now, now),
        ).lastrowid
        self.db.execute(
            """INSERT INTO document_items(company_id,record_id,item_kind,catalog_record_id,description,
                                             quantity_micros,unit_price_cents,discount_cents,total_cents,
                                             sort_order,revision,created_by,created_at,updated_at)
               VALUES(?,?, 'PRODUCT',?,'Produto fiscal',1000000,10000,0,10000,10,1,?,?,?)""",
            (1, sale_id, product_id, 1, now, now),
        )
        status, operation = self.request("POST", "/api/fiscal/tax-operations", {
            "code": "VENDA_RASCUNHO", "name": "Venda fiscal em rascunho", "direction": "OUT", "validFrom": "2026-01-01",
        })
        self.assertEqual(status, 201, operation)
        status, profile = self.request("POST", "/api/fiscal/tax-profiles", {
            "name": "Perfil do rascunho", "taxRegime": "REGIME_NORMAL", "branchId": branch_id,
            "requiredTaxCodes": ["ICMS", "PIS", "COFINS"], "validFrom": "2026-01-01",
        })
        self.assertEqual(status, 201, profile)
        source = "https://www.nfe.fazenda.gov.br/portal/principal.aspx"
        for code, result in {
            "ICMS": {"cst": "00", "rateBps": 1800, "baseReductionBps": 0},
            "PIS": {"cst": "01", "rateBps": 165, "baseReductionBps": 0},
            "COFINS": {"cst": "01", "rateBps": 760, "baseReductionBps": 0},
        }.items():
            status, rule = self.request("POST", "/api/fiscal/tax-rules", {
                "operationId": operation["operationId"], "taxProfileId": profile["taxProfileId"], "taxCode": code,
                "priority": 10, "conditions": {"originUf": "GO", "destinationUf": "GO", "ncmPrefix": "9031", "cfop": "5102", "merchandiseOrigin": "0"},
                "result": result, "referenceUrl": source, "validFrom": "2026-01-01",
            })
            self.assertEqual(status, 201, rule)
        status, classified = self.request("POST", "/api/fiscal/product-profiles", {
            "productRecordId": product_id, "taxProfileId": profile["taxProfileId"], "ncm": "90318099", "cfop": "5102",
            "merchandiseOrigin": "0", "referenceUrl": source, "validFrom": "2026-01-01",
        })
        self.assertEqual(status, 201, classified)
        payload = {"sourceRecordId": sale_id, "branchId": branch_id, "operationId": operation["operationId"], "issueDate": "2026-08-27"}
        status, drafted = self.request("POST", "/api/fiscal/drafts", payload)
        self.assertEqual(status, 201, drafted)
        self.assertEqual(drafted["calculation"]["totals"]["taxesCents"], 2725)
        draft_id = drafted["draftId"]
        self.assertEqual(self.db.scalar("SELECT status FROM fiscal_documents WHERE id=?", (draft_id,)), "DRAFT")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM fiscal_document_items WHERE fiscal_document_id=?", (draft_id,)), 1)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM xml_documents WHERE fiscal_document_id=?", (draft_id,)), 0)
        status, duplicate = self.request("POST", "/api/fiscal/drafts", payload)
        self.assertEqual(status, 409, duplicate)
        status, replacement = self.request("POST", "/api/fiscal/drafts", {**payload, "replaceDraft": True})
        self.assertEqual(status, 201, replacement)
        self.assertEqual(self.db.scalar("SELECT status FROM fiscal_documents WHERE id=?", (draft_id,)), "SUPERSEDED")
        status, setup = self.request("GET", "/api/fiscal/tax-setup")
        self.assertEqual(status, 200, setup)
        self.assertEqual(next(item for item in setup["products"] if item["id"] == product_id)["cfop"], "5102")
        status, drafts = self.request("GET", "/api/fiscal/drafts")
        self.assertEqual(status, 200, drafts)
        self.assertEqual(drafts["items"][0]["status"], "DRAFT")

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
        self.assertEqual(sale["financialModule"], "contas_receber")
        sale_receivable_id = sale["financialRecordId"]
        sale_receivable = self.db.connection().execute(
            "SELECT module,amount,payload FROM records WHERE id=?", (sale_receivable_id,),
        ).fetchone()
        self.assertEqual(sale_receivable["module"], "contas_receber")
        self.assertEqual(sale_receivable["amount"], 275)
        self.assertEqual(json.loads(sale_receivable["payload"])["cliente_id"],
                         customer["item"]["id"])
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
            "gerar_conta_pagar_ao_receber": True,
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

        status, composition = self.request("GET", f"/api/records/{purchase_id}/items")
        self.assertEqual(status, 200, composition)
        product_item = composition["items"][0]
        status, partial = self.request(
            "POST", f"/api/records/{purchase_id}/receive-items", {
                "items": [{"itemId": product_item["id"], "quantity": "0.5"}],
            },
        )
        self.assertEqual(status, 200, partial)
        self.assertEqual(partial["status"], "Recebido parcial")
        self.assertIsNone(partial["financialRecordId"])
        status, composition = self.request("GET", f"/api/records/{purchase_id}/items")
        self.assertEqual(status, 200, composition)
        self.assertEqual(composition["status"], "Recebido parcial")
        self.assertEqual(composition["items"][0]["receivedQuantity"], 0.5)
        self.assertEqual(composition["items"][0]["remainingQuantity"], 1.5)

        status, received = self.request(
            "POST", f"/api/records/{purchase_id}/receive-items", {},
        )
        self.assertEqual(status, 200, received)
        self.assertEqual(received["items"], 1)
        self.assertEqual(received["status"], "Recebido")
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
            "revision": composition["recordRevision"],
        })
        self.assertEqual(status, 400, cancellation)
        payable_id = received["financialRecordId"]
        self.assertTrue(payable_id)
        payable = self.db.connection().execute(
            "SELECT module,amount,payload FROM records WHERE id=?", (payable_id,),
        ).fetchone()
        self.assertEqual(payable["module"], "contas_pagar")
        self.assertEqual(payable["amount"], 50)
        self.assertEqual(json.loads(payable["payload"])["fornecedor_id"],
                         supplier["item"]["id"])
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM financial_document_origins WHERE source_record_id=?",
            (purchase_id,),
        ), 1)
        status, inventory = self.request("GET", "/api/inventory")
        balance = next(item for item in inventory["balances"] if item["lot"] == "LOTE-PC")
        self.assertEqual(balance["physicalQuantity"], 2)
        movement = next(item for item in inventory["movements"]
                        if item["movement_type"] == "PURCHASE_IN")
        self.assertEqual(movement["origin_type"], "PURCHASE_ORDER")
        self.assertEqual(movement["reference"], "Pedido de reposição")
        self.assertEqual(self.db.scalar(
            "SELECT COUNT(*) FROM audit_log WHERE entity_type='pedidos_compra' AND action='receive'",
        ), 2)

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
