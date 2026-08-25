#!/usr/bin/env python3
"""Simula os fluxos críticos do SIVS usando apenas bancos e servidores descartáveis.

Não lê nem altera o SQLite configurado da aplicação. Cada cenário cria seu próprio
ambiente temporário pelos contratos de integração existentes e o relatório final é
gravado em `.artifacts/full-operation-simulation.json`.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "sivs_2_2"
REPORT = ROOT / ".artifacts" / "full-operation-simulation.json"

STAGES = (
    ("jornada_unica_ponta_a_ponta", (
        "tests.test_server.APITests.test_complete_connected_business_journey_settles_cash_end_to_end",
    )),
    ("acesso_e_isolamento", (
        "tests.test_server.APITests.test_end_to_end_multi_company_norms_and_xml_security",
        "tests.test_server.APITests.test_admin_can_define_effective_company_permissions_and_capabilities",
    )),
    ("cadastros_e_relacionamentos", (
        "tests.test_server.APITests.test_registered_partners_are_shared_by_validated_relational_id",
        "tests.test_server.APITests.test_party_document_is_a_normalized_unique_company_key",
        "tests.test_server.APITests.test_customer_followups_are_idempotent_audited_and_reset_by_purchase",
    )),
    ("edital_ate_execucao", (
        "tests.test_server.APITests.test_tender_autonomy_enters_generic_notice_with_one_official_catalog_item",
        "tests.test_server.APITests.test_tender_extraction_feeds_checklist_and_requires_audited_exception_resolution",
        "tests.test_server.APITests.test_tender_document_vault_checklist_and_package_are_guarded",
        "tests.test_server.APITests.test_tender_commercial_proposal_is_versioned_segregated_and_packaged",
    )),
    ("estoque_compras_e_financeiro", (
        "tests.test_server.APITests.test_document_items_calculate_totals_and_reserve_stock_atomically",
        "tests.test_server.APITests.test_service_order_parts_leave_stock_through_the_audited_ledger",
        "tests.test_server.APITests.test_purchase_order_receiving_creates_one_audited_inventory_entry",
        "tests.test_server.APITests.test_xml_import_requires_the_active_company_as_recipient",
        "tests.test_server.APITests.test_controllership_consolidates_exact_values_privacy_and_company_isolation",
        "tests.test_server.APITests.test_partial_settlement_reconciliation_and_reversal_are_connected_and_isolated",
    )),
    ("fiscal_contabil_e_continuidade", (
        "tests.test_server.APITests.test_fiscal_readiness_encrypts_a1_and_checks_sefaz_homologation",
        "tests.test_server.APITests.test_accounting_export_is_audited_exact_and_company_scoped",
        "tests.test_server.APITests.test_encrypted_database_backup_is_complete_and_valid",
        "tests.test_server.APITests.test_control_center_tracks_sessions_changes_errors_and_remote_termination",
    )),
    ("interface_e_abas", (
        "tests.test_frontend_contract.FrontendContractTests.test_workspace_tabs_follow_navigation_permissions_and_accessibility",
        "tests.test_frontend_contract.FrontendContractTests.test_navigation_and_motion_keep_accessibility_contract",
    )),
)


def run_stage(loader: unittest.TestLoader, name: str, tests: tuple[str, ...]) -> dict[str, object]:
    suite = unittest.TestSuite(loader.loadTestsFromName(test) for test in tests)
    stream = io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    return {
        "stage": name,
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "seconds": round(time.perf_counter() - started, 3),
        "scenarios": list(tests),
        "diagnostic": stream.getvalue()[-4000:] if not result.wasSuccessful() else "",
    }


def main() -> int:
    sys.path.insert(0, str(APP_ROOT))
    loader = unittest.TestLoader()
    started = time.perf_counter()
    stages = [run_stage(loader, name, tests) for name, tests in STAGES]
    success = all(stage["status"] == "PASS" for stage in stages)
    report = {
        "simulation": "SIVS_FULL_OPERATION_2",
        "safeMode": True,
        "database": "temporary_per_scenario_with_one_continuous_end_to_end_database",
        "externalCalls": "mocked_or_blocked_by_design",
        "status": "PASS" if success else "FAIL",
        "tests": sum(int(stage["tests"]) for stage in stages),
        "seconds": round(time.perf_counter() - started, 3),
        "stages": stages,
        "continuousJourney": {
            "status": stages[0]["status"],
            "database": "single_temporary_database_from_setup_through_cash_settlement",
            "certificateExpected": "ABSENT_AND_BLOCKED",
            "steps": [
                "agente de portal preparado, lance shadow com piso e idempotencia",
                "worker assinado com lease, recibo e isolamento multiempresa",
                "setup e segregação entre responsável e aprovadora",
                "edital com itens oficiais e proposta comercial versionada",
                "checklist, conversão, aprovação independente e pacote",
                "homologação, contrato e ordem de serviço materializados",
                "reserva e baixa de produto no estoque",
                "conclusão da ordem e geração de conta a receber do cliente",
                "recebimento parcial/integral e entrada de caixa rastreável",
                "pedido de compra, entrada de estoque e conta a pagar do fornecedor",
                "pagamento e saída de caixa rastreável",
                "extrato CSV, conciliação confirmada, desconciliação e estorno rastreável",
                "controladoria com títulos zerados e saldo financeiro correto",
                "isolamento em segunda empresa e fiscal bloqueado sem A1",
            ],
        },
        "validatedJourney": [
            "agente de portal, guardrail de lance e contrato assinado do worker",
            "empresa e usuários com segregação de funções",
            "clientes e fornecedores relacionais",
            "captação de edital inclusive com um único item aderente",
            "extração/OCR controlado, exceções, checklist e pacote documental",
            "proposta versionada, aprovação independente e homologação",
            "contrato, ordem de serviço, estoque e conta a receber",
            "pedido de compra, recebimento e conta a pagar",
            "baixas parciais, ajustes, estorno, conciliação, controladoria e caixa",
            "fiscal, pacote contábil, backup e observabilidade",
            "abas, navegação, teclado, permissões e acessibilidade",
        ],
        "notExternallyHomologated": [
            "OCR real no contêiner com documentos SECCOL",
            "SEFAZ com certificado A1 real",
            "protocolo e lance em portal oficial",
            "restauração de backup em destino externo",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "tests": report["tests"],
        "seconds": report["seconds"], "report": str(REPORT),
    }, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
