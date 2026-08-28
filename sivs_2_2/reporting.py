"""Motor seguro e extensível da Central de Relatórios.

O cliente escolhe apenas chaves publicadas no catálogo. Expressões SQL, joins,
escopo de empresa e formatos permanecem definidos no servidor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class ReportingError(ValueError):
    pass


@dataclass(frozen=True)
class Field:
    label: str
    expression: str
    format: str = "text"


@dataclass(frozen=True)
class Dataset:
    title: str
    description: str
    area: str
    source: str
    company_expression: str
    date_expression: str
    dimensions: dict[str, Field]
    metrics: dict[str, Field]
    required_modules: tuple[str, ...] = ()
    module_expression: str | None = None
    search_expression: str | None = None
    sensitive_metrics: tuple[str, ...] = ()
    default_dimensions: tuple[str, ...] = ()
    default_metrics: tuple[str, ...] = ("count",)


DATASETS = {
    "records": Dataset(
        "Cadastros e operações", "Volume, situação, prazos e valores dos cadastros autorizados.",
        "Gestão", "records r", "r.company_id", "r.created_at",
        {
            "month": Field("Mês", "substr(r.created_at,1,7)", "month"),
            "module": Field("Cadastro", "r.module"), "status": Field("Situação", "r.status"),
            "dueMonth": Field("Mês do prazo", "COALESCE(substr(r.due_date,1,7),'Sem prazo')", "month"),
            "title": Field("Registro", "r.title"),
        },
        {
            "count": Field("Registros", "COUNT(*)", "integer"),
            "amount": Field("Valor total", "SUM(COALESCE(CAST(ROUND(r.amount*100) AS INTEGER),0))", "money"),
            "averageAmount": Field("Valor médio", "CAST(ROUND(AVG(COALESCE(r.amount,0))*100) AS INTEGER)", "money"),
        }, module_expression="r.module", search_expression="r.title",
        sensitive_metrics=("amount", "averageAmount"), default_dimensions=("module", "status"),
    ),
    "financial": Dataset(
        "Títulos financeiros", "Contas a pagar/receber, baixas, saldo aberto e vencimentos.",
        "Financeiro",
        """(SELECT r.id,r.company_id,r.module,r.title,r.status,r.amount,r.due_date,r.created_at,
                    json_extract(r.payload,'$.categoria') category,
                    COALESCE(json_extract(r.payload,'$.fornecedor'),json_extract(r.payload,'$.cliente'),'Não informado') partner,
                    COALESCE(SUM(CASE WHEN s.entry_type='SETTLEMENT' THEN s.principal_cents
                                      WHEN s.entry_type='REVERSAL' THEN -s.principal_cents ELSE 0 END),0) settled_cents
               FROM records r LEFT JOIN financial_settlements s
                 ON s.financial_record_id=r.id AND s.company_id=r.company_id
              WHERE r.deleted_at IS NULL AND r.module IN ('contas_pagar','contas_receber')
              GROUP BY r.id) f""",
        "f.company_id", "COALESCE(f.due_date,f.created_at)",
        {
            "month": Field("Vencimento", "COALESCE(substr(f.due_date,1,7),'Sem prazo')", "month"),
            "direction": Field("Tipo", "CASE f.module WHEN 'contas_pagar' THEN 'A pagar' ELSE 'A receber' END"),
            "status": Field("Situação", "f.status"), "category": Field("Categoria", "COALESCE(f.category,'Sem categoria')"),
            "partner": Field("Parceiro", "f.partner"), "title": Field("Título", "f.title"),
        },
        {
            "count": Field("Títulos", "COUNT(*)", "integer"),
            "amount": Field("Valor nominal", "SUM(COALESCE(CAST(ROUND(f.amount*100) AS INTEGER),0))", "money"),
            "settled": Field("Valor baixado", "SUM(f.settled_cents)", "money"),
            "outstanding": Field("Saldo aberto", "SUM(MAX(0,COALESCE(CAST(ROUND(f.amount*100) AS INTEGER),0)-f.settled_cents))", "money"),
        }, required_modules=("contas_pagar", "contas_receber"), module_expression="f.module",
        search_expression="f.title", sensitive_metrics=("amount", "settled", "outstanding"),
        default_dimensions=("direction", "status"), default_metrics=("count", "amount", "outstanding"),
    ),
    "commercial": Dataset(
        "Itens comerciais e operacionais", "Produtos e serviços em propostas, vendas, compras e ordens.",
        "Comercial",
        """document_items i JOIN records d ON d.id=i.record_id AND d.company_id=i.company_id
             JOIN records c ON c.id=i.catalog_record_id AND c.company_id=i.company_id""",
        "i.company_id", "d.created_at",
        {
            "month": Field("Mês", "substr(d.created_at,1,7)", "month"),
            "module": Field("Documento", "d.module"), "status": Field("Situação", "d.status"),
            "itemKind": Field("Natureza", "CASE i.item_kind WHEN 'PRODUCT' THEN 'Produto' ELSE 'Serviço' END"),
            "catalogItem": Field("Item", "c.title"), "document": Field("Documento", "d.title"),
        },
        {
            "count": Field("Linhas", "COUNT(*)", "integer"),
            "quantity": Field("Quantidade", "SUM(i.quantity_micros)/1000000.0", "number"),
            "total": Field("Valor total", "SUM(i.total_cents)", "money"),
            "discount": Field("Descontos", "SUM(i.discount_cents)", "money"),
        }, required_modules=("propostas", "vendas", "solicitacoes_compra", "pedidos_compra", "ordens_servico"),
        module_expression="d.module", search_expression="d.title || ' ' || c.title",
        sensitive_metrics=("total", "discount"), default_dimensions=("module", "itemKind"),
        default_metrics=("count", "quantity", "total"),
    ),
    "inventory": Dataset(
        "Posição de estoque", "Saldo físico, reservado, disponível e valor por depósito, produto ou lote.",
        "Estoque",
        """inventory_balances b JOIN warehouses w ON w.id=b.warehouse_id AND w.company_id=b.company_id
             JOIN records p ON p.id=b.product_record_id AND p.company_id=b.company_id""",
        "b.company_id", "b.updated_at",
        {
            "warehouse": Field("Depósito", "w.name"), "product": Field("Produto", "p.title"),
            "lot": Field("Lote", "CASE WHEN b.lot_key='' THEN 'Sem lote' ELSE b.lot_key END"),
            "updatedMonth": Field("Atualização", "substr(b.updated_at,1,7)", "month"),
        },
        {
            "count": Field("Posições", "COUNT(*)", "integer"),
            "physical": Field("Quantidade física", "SUM(b.physical_quantity_micros)/1000000.0", "number"),
            "reserved": Field("Quantidade reservada", "SUM(b.reserved_quantity_micros)/1000000.0", "number"),
            "available": Field("Quantidade disponível", "SUM(b.physical_quantity_micros-b.reserved_quantity_micros)/1000000.0", "number"),
            "value": Field("Valor do estoque", "SUM(b.inventory_value_cents)", "money"),
        }, required_modules=("estoque",), search_expression="p.title || ' ' || w.name || ' ' || b.lot_key",
        sensitive_metrics=("value",), default_dimensions=("warehouse", "product"),
        default_metrics=("physical", "reserved", "available", "value"),
    ),
    "payroll": Dataset(
        "Folha de pagamento", "Bruto, descontos, líquido e FGTS por competência, área ou colaborador.",
        "Pessoas",
        """hr_payroll_items i JOIN hr_payroll_runs r ON r.id=i.payroll_run_id AND r.company_id=i.company_id
             JOIN hr_employments e ON e.id=i.employment_id AND e.company_id=i.company_id
             JOIN records p ON p.id=e.employee_record_id AND p.company_id=e.company_id
             JOIN branches b ON b.id=e.branch_id AND b.company_id=e.company_id""",
        "i.company_id", "r.calculated_at",
        {
            "period": Field("Competência", "r.period", "month"), "status": Field("Situação", "r.status"),
            "branch": Field("Unidade", "b.name"), "department": Field("Setor", "e.department"),
            "employee": Field("Colaborador", "p.title"), "jobTitle": Field("Cargo", "e.job_title"),
        },
        {
            "count": Field("Colaboradores", "COUNT(*)", "integer"),
            "gross": Field("Bruto", "SUM(i.gross_cents)", "money"),
            "deductions": Field("Descontos", "SUM(i.deductions_cents)", "money"),
            "net": Field("Líquido", "SUM(i.net_cents)", "money"),
            "fgts": Field("FGTS", "SUM(i.fgts_cents)", "money"),
        }, required_modules=("rh",), search_expression="p.title || ' ' || e.department || ' ' || e.job_title",
        sensitive_metrics=("gross", "deductions", "net", "fgts"), default_dimensions=("period", "department"),
        default_metrics=("count", "gross", "deductions", "net", "fgts"),
    ),
    "tenders": Dataset(
        "Editais e oportunidades", "Publicação, prazo, localidade, relevância e valor estimado.",
        "Licitações", "tender_results t", "t.company_id", "COALESCE(t.published_at,t.created_at)",
        {
            "month": Field("Publicação", "substr(COALESCE(t.published_at,t.created_at),1,7)", "month"),
            "status": Field("Situação", "t.status"), "uf": Field("UF", "COALESCE(t.uf,'Não informada')"),
            "agency": Field("Órgão", "COALESCE(t.agency,'Não informado')"),
            "modality": Field("Modalidade", "COALESCE(t.modality,'Não informada')"),
            "title": Field("Edital", "t.title"),
        },
        {
            "count": Field("Editais", "COUNT(*)", "integer"),
            "estimatedValue": Field("Valor estimado", "SUM(COALESCE(CAST(ROUND(t.estimated_value*100) AS INTEGER),0))", "money"),
            "averageScore": Field("Aderência média", "ROUND(AVG(t.relevance_score),1)", "number"),
        }, required_modules=("editais",), search_expression="t.title || ' ' || t.object_text || ' ' || COALESCE(t.agency,'')",
        sensitive_metrics=("estimatedValue",), default_dimensions=("status", "uf"),
        default_metrics=("count", "estimatedValue", "averageScore"),
    ),
    "accounting": Dataset(
        "Movimentação contábil", "Débitos e créditos por conta, natureza, centro de custo e origem.",
        "Contabilidade",
        """accounting_journal_lines l JOIN accounting_journal_entries e ON e.id=l.entry_id AND e.company_id=l.company_id
             JOIN accounting_chart_accounts a ON a.id=l.account_id AND a.company_id=l.company_id
             LEFT JOIN cost_centers c ON c.id=l.cost_center_id AND c.company_id=l.company_id""",
        "l.company_id", "e.competence_date",
        {
            "month": Field("Competência", "substr(e.competence_date,1,7)", "month"),
            "nature": Field("Natureza", "a.nature"), "account": Field("Conta", "a.code || ' — ' || a.name"),
            "costCenter": Field("Centro de custo", "COALESCE(c.code || ' — ' || c.name,'Sem centro')"),
            "source": Field("Origem", "e.source_type"), "memo": Field("Histórico", "e.memo"),
        },
        {
            "count": Field("Lançamentos", "COUNT(DISTINCT e.id)", "integer"),
            "debit": Field("Débitos", "SUM(l.debit_cents)", "money"),
            "credit": Field("Créditos", "SUM(l.credit_cents)", "money"),
            "balance": Field("Saldo", "SUM(l.debit_cents-l.credit_cents)", "money"),
        }, required_modules=("fiscal",), search_expression="e.memo || ' ' || a.code || ' ' || a.name",
        sensitive_metrics=("debit", "credit", "balance"), default_dimensions=("month", "nature"),
        default_metrics=("debit", "credit", "balance"),
    ),
    "audit": Dataset(
        "Auditoria do sistema", "Ações por data, pessoa, entidade e operação.",
        "Governança", "audit_log a LEFT JOIN users u ON u.id=a.user_id", "a.company_id", "a.created_at",
        {
            "day": Field("Data", "substr(a.created_at,1,10)", "date"),
            "action": Field("Ação", "a.action"), "entity": Field("Entidade", "a.entity_type"),
            "user": Field("Pessoa", "COALESCE(u.name,'Sistema')"),
        }, {"count": Field("Eventos", "COUNT(*)", "integer")},
        search_expression="a.action || ' ' || a.entity_type || ' ' || COALESCE(u.name,'')",
        default_dimensions=("day", "action"),
    ),
}


def catalog(available: dict[str, dict], module_labels: dict[str, str] | None = None) -> list[dict]:
    module_labels = module_labels or {}
    result = []
    for key, access in available.items():
        spec = DATASETS.get(key)
        if not spec:
            continue
        blocked = set(spec.sensitive_metrics) if not access.get("values") else set()
        metrics = {name: field for name, field in spec.metrics.items() if name not in blocked}
        result.append({
            "key": key, "title": spec.title, "description": spec.description, "area": spec.area,
            "dimensions": [{"key": name, "label": field.label, "format": field.format}
                           for name, field in spec.dimensions.items()],
            "metrics": [{"key": name, "label": field.label, "format": field.format}
                        for name, field in metrics.items()],
            "defaultDimensions": [name for name in spec.default_dimensions if name in spec.dimensions],
            "defaultMetrics": [name for name in spec.default_metrics if name in metrics],
            "canExport": bool(access.get("export")), "valuesRestricted": bool(blocked),
            "moduleOptions": [
                {"value": module, "label": module_labels.get(module, module.replace("_", " ").title())}
                for module in access.get("modules") or ()
            ] if spec.module_expression else [],
        })
    return result


def _valid_date(value, label):
    text = str(value or "").strip()
    if text and not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", text):
        raise ReportingError(f"{label} inválida")
    return text


def run_report(connection, company_id: int, request: dict, access: dict) -> dict:
    if not isinstance(request, dict):
        raise ReportingError("Definição do relatório inválida")
    key = str(request.get("dataset") or "")
    spec = DATASETS.get(key)
    if not spec or key not in access:
        raise ReportingError("Fonte de relatório indisponível para este perfil")
    dimensions = request.get("dimensions") or list(spec.default_dimensions)
    metrics = request.get("metrics") or list(spec.default_metrics)
    if not isinstance(dimensions, list) or not 1 <= len(dimensions) <= 4 or len(set(dimensions)) != len(dimensions):
        raise ReportingError("Selecione de uma a quatro dimensões distintas")
    if not isinstance(metrics, list) or not 1 <= len(metrics) <= 6 or len(set(metrics)) != len(metrics):
        raise ReportingError("Selecione de uma a seis métricas distintas")
    if any(name not in spec.dimensions for name in dimensions) or any(name not in spec.metrics for name in metrics):
        raise ReportingError("Campo de relatório desconhecido")
    if not access[key].get("values") and any(name in spec.sensitive_metrics for name in metrics):
        raise ReportingError("Seu perfil não pode consultar valores nesta fonte")

    filters = request.get("filters") or {}
    if not isinstance(filters, dict):
        raise ReportingError("Filtros inválidos")
    start = _valid_date(filters.get("start"), "Data inicial")
    end = _valid_date(filters.get("end"), "Data final")
    if start and end and start > end:
        raise ReportingError("Data inicial deve ser anterior à final")
    clauses = [f"{spec.company_expression}=?"]
    params = [int(company_id)]
    if start:
        clauses.append(f"date({spec.date_expression})>=date(?)")
        params.append(start)
    if end:
        clauses.append(f"date({spec.date_expression})<=date(?)")
        params.append(end)
    search = str(filters.get("search") or "").strip()
    if search:
        if len(search) > 120:
            raise ReportingError("Pesquisa muito longa")
        if not spec.search_expression:
            raise ReportingError("Esta fonte não oferece pesquisa textual")
        clauses.append(f"LOWER({spec.search_expression}) LIKE ? ESCAPE '\\'")
        escaped = search.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    modules = tuple(access[key].get("modules") or ())
    if spec.module_expression and modules:
        requested_modules = filters["modules"] if "modules" in filters else list(modules)
        if not isinstance(requested_modules, list):
            raise ReportingError("Filtro de módulos inválido")
        selected_modules = sorted(set(str(item) for item in requested_modules) & set(modules))
        if not selected_modules:
            raise ReportingError("Nenhum módulo autorizado foi selecionado")
        clauses.append(f"{spec.module_expression} IN ({','.join('?' for _ in selected_modules)})")
        params.extend(selected_modules)
    dimension_filters = filters.get("dimensions") or {}
    if not isinstance(dimension_filters, dict) or len(dimension_filters) > 4:
        raise ReportingError("Filtros por dimensão inválidos")
    for name, raw_values in dimension_filters.items():
        if name not in spec.dimensions:
            raise ReportingError("Filtro usa dimensão desconhecida")
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        values = [str(value)[:160] for value in values if str(value) != ""]
        if not values or len(values) > 20:
            continue
        clauses.append(f"{spec.dimensions[name].expression} IN ({','.join('?' for _ in values)})")
        params.extend(values)

    dim_select = [f"{spec.dimensions[name].expression} AS \"{name}\"" for name in dimensions]
    metric_select = [f"{spec.metrics[name].expression} AS \"{name}\"" for name in metrics]
    where = " AND ".join(clauses)
    group = ",".join(spec.dimensions[name].expression for name in dimensions)
    order_key = str(request.get("orderBy") or metrics[0])
    if order_key not in set(dimensions) | set(metrics):
        order_key = metrics[0]
    direction = "ASC" if str(request.get("order") or "DESC").upper() == "ASC" else "DESC"
    sql = (f"SELECT {','.join(dim_select + metric_select)} FROM {spec.source} WHERE {where} "
           f"GROUP BY {group} ORDER BY \"{order_key}\" {direction},1 ASC LIMIT 501")
    rows = [dict(row) for row in connection.execute(sql, params).fetchall()]
    truncated = len(rows) > 500
    rows = rows[:500]
    total_sql = f"SELECT {','.join(metric_select)} FROM {spec.source} WHERE {where}"
    totals = dict(connection.execute(total_sql, params).fetchone())
    columns = ([{"key": name, "label": spec.dimensions[name].label, "format": spec.dimensions[name].format,
                 "kind": "dimension"} for name in dimensions] +
               [{"key": name, "label": spec.metrics[name].label, "format": spec.metrics[name].format,
                 "kind": "metric"} for name in metrics])
    return {"dataset": key, "title": spec.title, "columns": columns, "rows": rows,
            "totals": totals, "truncated": truncated, "rowCount": len(rows),
            "definition": {"dataset": key, "dimensions": dimensions, "metrics": metrics,
                           "filters": filters, "orderBy": order_key, "order": direction}}
