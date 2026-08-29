import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from reporting import ReportingError, catalog, run_report


class ReportingEngineTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE records (
              id INTEGER PRIMARY KEY,
              company_id INTEGER NOT NULL,
              module TEXT NOT NULL,
              title TEXT NOT NULL,
              status TEXT NOT NULL,
              amount REAL,
              due_date TEXT,
              created_at TEXT NOT NULL
            );
            CREATE INDEX idx_reporting_records_company_module
              ON records(company_id,module,created_at);
            CREATE INDEX idx_reporting_records_grouped
              ON records(company_id,module,status,created_at,amount);
            WITH RECURSIVE seq(n) AS (
              VALUES(1) UNION ALL SELECT n+1 FROM seq WHERE n<100000
            )
            INSERT INTO records(id,company_id,module,title,status,amount,due_date,created_at)
            SELECT n,1,
                   CASE WHEN n%2=0 THEN 'vendas' ELSE 'propostas' END,
                   printf('Registro %06d',n),
                   printf('Situação %02d',n%20),
                   (n%10000)/100.0,
                   printf('2026-08-%02d',(n%28)+1),
                   printf('2026-08-%02dT12:00:00+00:00',(n%28)+1)
              FROM seq;
            WITH RECURSIVE seq(n) AS (
              VALUES(1) UNION ALL SELECT n+1 FROM seq WHERE n<20000
            )
            INSERT INTO records(id,company_id,module,title,status,amount,due_date,created_at)
            SELECT 100000+n,2,'vendas',printf('Registro alheio %06d',n),
                   'Situação alheia',999999.99,'2026-08-01','2026-08-01T12:00:00+00:00'
              FROM seq;
            """
        )
        self.access = {
            "records": {"modules": ["propostas", "vendas"], "values": True, "export": True},
        }

    def tearDown(self):
        self.connection.close()

    def test_catalog_hides_sensitive_metrics_without_source_value_permission(self):
        restricted = catalog({
            "records": {"modules": ["vendas"], "values": False, "export": False},
        }, {"vendas": "Vendas"})[0]
        self.assertEqual({metric["key"] for metric in restricted["metrics"]}, {"count"})
        self.assertTrue(restricted["valuesRestricted"])
        self.assertFalse(restricted["canExport"])
        self.assertEqual(restricted["moduleOptions"], [{"value": "vendas", "label": "Vendas"}])
        with self.assertRaises(ReportingError):
            run_report(self.connection, 1, {
                "dataset": "records", "metrics": ["amount"],
            }, {"records": {"modules": ["vendas"], "values": False}})

    def test_large_report_is_exact_company_scoped_bounded_and_fast(self):
        started = time.perf_counter()
        detailed = run_report(self.connection, 1, {
            "dataset": "records", "dimensions": ["title"],
            "metrics": ["count", "amount"],
            "filters": {"modules": ["vendas"], "start": "2026-08-01", "end": "2026-08-31"},
            "orderBy": "title", "order": "ASC",
        }, self.access)
        grouped = run_report(self.connection, 1, {
            "dataset": "records", "dimensions": ["module", "status"],
            "metrics": ["count", "amount", "averageAmount"],
            "filters": {"start": "2026-08-01", "end": "2026-08-31"},
        }, self.access)
        pinpoint = run_report(self.connection, 1, {
            "dataset": "records", "dimensions": ["title"], "metrics": ["count", "amount"],
            "filters": {"modules": ["vendas"], "search": "Registro 099998"},
        }, self.access)
        elapsed_ms = (time.perf_counter() - started) * 1000

        expected_sales_cents = sum(n % 10000 for n in range(2, 100001, 2))
        expected_all_cents = sum(n % 10000 for n in range(1, 100001))
        self.assertTrue(detailed["truncated"])
        self.assertEqual(detailed["rowCount"], 500)
        self.assertEqual(detailed["totals"], {"count": 50000, "amount": expected_sales_cents})
        self.assertEqual(grouped["totals"]["count"], 100000)
        self.assertEqual(grouped["totals"]["amount"], expected_all_cents)
        self.assertNotIn(99999999, {row["amount"] for row in detailed["rows"]})
        self.assertEqual(pinpoint["rows"], [{"title": "Registro 099998", "count": 1, "amount": 9998}])
        self.assertLess(elapsed_ms, 3000, f"Três consultas levaram {elapsed_ms:.1f} ms")
        print(f"REPORTING_BENCHMARK rows=120000 queries=3 elapsed_ms={elapsed_ms:.1f}")

    def test_concurrent_readers_keep_the_same_exact_result(self):
        request = {
            "dataset": "records", "dimensions": ["module", "status"],
            "metrics": ["count", "amount"],
            "filters": {"start": "2026-08-01", "end": "2026-08-31"},
        }
        expected_cents = sum(n % 10000 for n in range(1, 100001))
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "reporting-load.db"
            target = sqlite3.connect(database_path)
            self.connection.backup(target)
            target.close()

            def execute_reader(_index):
                connection = sqlite3.connect(database_path, timeout=5)
                connection.row_factory = sqlite3.Row
                try:
                    return run_report(connection, 1, request, self.access)["totals"]
                finally:
                    connection.close()

            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=8) as executor:
                totals = list(executor.map(execute_reader, range(8)))
            elapsed_ms = (time.perf_counter() - started) * 1000

        self.assertEqual(totals, [{"count": 100000, "amount": expected_cents}] * 8)
        self.assertLess(elapsed_ms, 5000, f"Oito consultas concorrentes levaram {elapsed_ms:.1f} ms")
        print(f"REPORTING_CONCURRENCY readers=8 rows_each=100000 elapsed_ms={elapsed_ms:.1f}")


class ReportingDatasetPrecisionTests(unittest.TestCase):
    def test_every_dataset_calculates_known_metrics_individually(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE records (
              id INTEGER PRIMARY KEY,company_id INTEGER,module TEXT,title TEXT,status TEXT,
              amount REAL,due_date TEXT,payload TEXT,created_at TEXT,updated_at TEXT,deleted_at TEXT
            );
            CREATE TABLE financial_settlements (
              id INTEGER PRIMARY KEY,company_id INTEGER,financial_record_id INTEGER,
              entry_type TEXT,principal_cents INTEGER
            );
            CREATE TABLE document_items (
              id INTEGER PRIMARY KEY,company_id INTEGER,record_id INTEGER,catalog_record_id INTEGER,
              item_kind TEXT,quantity_micros INTEGER,total_cents INTEGER,discount_cents INTEGER
            );
            CREATE TABLE warehouses (id INTEGER PRIMARY KEY,company_id INTEGER,name TEXT);
            CREATE TABLE inventory_balances (
              id INTEGER PRIMARY KEY,company_id INTEGER,warehouse_id INTEGER,product_record_id INTEGER,
              lot_key TEXT,updated_at TEXT,physical_quantity_micros INTEGER,
              reserved_quantity_micros INTEGER,inventory_value_cents INTEGER
            );
            CREATE TABLE branches (id INTEGER PRIMARY KEY,company_id INTEGER,name TEXT);
            CREATE TABLE hr_employments (
              id INTEGER PRIMARY KEY,company_id INTEGER,employee_record_id INTEGER,branch_id INTEGER,
              department TEXT,job_title TEXT
            );
            CREATE TABLE hr_payroll_runs (
              id INTEGER PRIMARY KEY,company_id INTEGER,period TEXT,status TEXT,calculated_at TEXT
            );
            CREATE TABLE hr_payroll_items (
              id INTEGER PRIMARY KEY,company_id INTEGER,payroll_run_id INTEGER,employment_id INTEGER,
              gross_cents INTEGER,deductions_cents INTEGER,net_cents INTEGER,fgts_cents INTEGER
            );
            CREATE TABLE tender_results (
              id INTEGER PRIMARY KEY,company_id INTEGER,published_at TEXT,created_at TEXT,status TEXT,
              uf TEXT,agency TEXT,modality TEXT,title TEXT,object_text TEXT,
              estimated_value REAL,relevance_score REAL
            );
            CREATE TABLE accounting_chart_accounts (
              id INTEGER PRIMARY KEY,company_id INTEGER,code TEXT,name TEXT,nature TEXT
            );
            CREATE TABLE cost_centers (id INTEGER PRIMARY KEY,company_id INTEGER,code TEXT,name TEXT);
            CREATE TABLE accounting_journal_entries (
              id INTEGER PRIMARY KEY,company_id INTEGER,competence_date TEXT,source_type TEXT,memo TEXT
            );
            CREATE TABLE accounting_journal_lines (
              id INTEGER PRIMARY KEY,company_id INTEGER,entry_id INTEGER,account_id INTEGER,
              cost_center_id INTEGER,debit_cents INTEGER,credit_cents INTEGER
            );
            CREATE TABLE users (id INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE audit_log (
              id INTEGER PRIMARY KEY,company_id INTEGER,user_id INTEGER,created_at TEXT,
              action TEXT,entity_type TEXT
            );

            INSERT INTO records VALUES
              (1,1,'contas_receber','Título Alpha','Aberto',100.50,'2026-08-20','{"cliente":"Alice"}','2026-08-01','2026-08-01',NULL),
              (2,1,'vendas','Venda 1','Faturada',NULL,NULL,'{}','2026-08-02','2026-08-02',NULL),
              (3,1,'produtos','Produto A','Ativo',NULL,NULL,'{}','2026-08-02','2026-08-02',NULL),
              (4,1,'colaboradores','Joana','Ativo',NULL,NULL,'{}','2026-08-02','2026-08-02',NULL);
            INSERT INTO financial_settlements VALUES (1,1,1,'SETTLEMENT',4000);
            INSERT INTO document_items VALUES (1,1,2,3,'PRODUCT',2000000,10000,500);
            INSERT INTO warehouses VALUES (1,1,'Principal');
            INSERT INTO inventory_balances VALUES (1,1,1,3,'L1','2026-08-03',10000000,3000000,12345);
            INSERT INTO branches VALUES (1,1,'Matriz');
            INSERT INTO hr_employments VALUES (1,1,4,1,'Operações','Analista');
            INSERT INTO hr_payroll_runs VALUES (1,1,'2026-08','CLOSED','2026-08-31');
            INSERT INTO hr_payroll_items VALUES (1,1,1,1,500000,100000,400000,40000);
            INSERT INTO tender_results VALUES
              (1,1,'2026-08-04','2026-08-04','Novo','SP','Prefeitura','Pregão','Edital A','Objeto A',1000.25,87.5);
            INSERT INTO accounting_chart_accounts VALUES
              (1,1,'1.1','Caixa','ASSET'),(2,1,'2.1','Receita','REVENUE');
            INSERT INTO cost_centers VALUES (1,1,'OP','Operações');
            INSERT INTO accounting_journal_entries VALUES (1,1,'2026-08-05','MANUAL','Partida teste');
            INSERT INTO accounting_journal_lines VALUES
              (1,1,1,1,1,10000,0),(2,1,1,2,NULL,0,10000);
            INSERT INTO users VALUES (1,'Administradora');
            INSERT INTO audit_log VALUES (1,1,1,'2026-08-06','create','record');
            """
        )
        access = {
            "records": {"modules": ["contas_receber", "vendas", "produtos", "colaboradores"], "values": True},
            "financial": {"modules": ["contas_receber"], "values": True},
            "commercial": {"modules": ["vendas"], "values": True},
            "inventory": {"modules": ["estoque"], "values": True},
            "payroll": {"modules": ["rh"], "values": True},
            "tenders": {"modules": ["editais"], "values": True},
            "accounting": {"modules": ["fiscal"], "values": True},
            "audit": {"modules": [], "values": False},
        }
        expected = {
            "records": {"count": 4, "amount": 10050},
            "financial": {"count": 1, "amount": 10050, "outstanding": 6050},
            "commercial": {"count": 1, "quantity": 2.0, "total": 10000},
            "inventory": {"physical": 10.0, "reserved": 3.0, "available": 7.0, "value": 12345},
            "payroll": {"count": 1, "gross": 500000, "deductions": 100000, "net": 400000, "fgts": 40000},
            "tenders": {"count": 1, "estimatedValue": 100025, "averageScore": 87.5},
            "accounting": {"debit": 10000, "credit": 10000, "balance": 0},
            "audit": {"count": 1},
        }
        try:
            for dataset, totals in expected.items():
                with self.subTest(dataset=dataset):
                    result = run_report(connection, 1, {
                        "dataset": dataset, "metrics": list(totals),
                    }, access)
                    self.assertEqual({key: result["totals"][key] for key in totals}, totals)
                    self.assertGreaterEqual(result["rowCount"], 1)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
