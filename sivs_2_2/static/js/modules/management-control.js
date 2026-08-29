(function initializeManagementControl(global) {
  const management = global.SIVSManagementControl ||= {};

  function currency(cents) {
    if (cents == null) return "Acesso restrito";
    return new Intl.NumberFormat("pt-BR", {
      style: "currency", currency: "BRL", maximumFractionDigits: 2,
    }).format(Number(cents || 0) / 100);
  }

  function metric(label, value, hint, tone = "") {
    return `<article class="management-metric ${tone}"><span>${label}</span><strong>${value}</strong><small>${hint}</small></article>`;
  }

  function restricted(title) {
    return `<div class="management-restricted"><span>◇</span><div><strong>${title}</strong><p>Esta informação depende de uma função individual e da permissão para visualizar valores no módulo de origem.</p></div></div>`;
  }

  function monthLabel(month) {
    const [year, monthNumber] = String(month).split("-");
    return `${["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"][Number(monthNumber) - 1]}/${String(year).slice(-2)}`;
  }

  function seriesHTML(data) {
    const values = data.series.flatMap((item) => [
      item.billingCents, item.cashInCents, item.cashOutCents,
    ]).filter((value) => value != null);
    if (!values.length) return restricted("Série financeira");
    const ceiling = Math.max(...values.map(Number), 1);
    return `<div class="management-chart" role="img" aria-label="Comparação mensal de faturamento, entradas e saídas"><div class="management-chart-legend"><span class="billing">Faturamento</span><span class="cash-in">Entradas</span><span class="cash-out">Saídas</span></div><div class="management-chart-bars">${data.series.map((item) => `<div class="management-chart-month"><div class="management-bar-set">${item.billingCents == null ? "" : `<i class="billing" style="--bar:${Math.max(Number(item.billingCents) / ceiling * 100, item.billingCents ? 3 : 0)}%" title="Faturamento ${currency(item.billingCents)}"></i>`}${item.cashInCents == null ? "" : `<i class="cash-in" style="--bar:${Math.max(Number(item.cashInCents) / ceiling * 100, item.cashInCents ? 3 : 0)}%" title="Entradas ${currency(item.cashInCents)}"></i>`}${item.cashOutCents == null ? "" : `<i class="cash-out" style="--bar:${Math.max(Number(item.cashOutCents) / ceiling * 100, item.cashOutCents ? 3 : 0)}%" title="Saídas ${currency(item.cashOutCents)}"></i>`}</div><b>${monthLabel(item.month)}</b></div>`).join("")}</div></div><div class="table-wrap management-series-table"><table class="data-table"><thead><tr><th>Mês</th><th>Faturamento</th><th>Entradas</th><th>Saídas</th></tr></thead><tbody>${data.series.map((item) => `<tr><td>${monthLabel(item.month)}</td><td>${currency(item.billingCents)}</td><td>${currency(item.cashInCents)}</td><td>${currency(item.cashOutCents)}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function bindNavigation() {
    document.querySelectorAll("[data-management-go]").forEach((button) => {
      button.onclick = () => document.querySelector(`[data-nav="${button.dataset.managementGo}"]`)?.click();
    });
  }

  function automationHTML(data, escapeHTML, dateBR) {
    const areas = {
      finance: "Financeiro", purchasing: "Compras", inventory: "Estoque",
      fiscal: "Fiscal/contábil", hr: "RH", quality: "Qualidade/técnico",
      tenders: "Licitações",
    };
    const findings = data.items || [];
    return `<section class="panel management-automation" aria-labelledby="automationTitle"><div class="panel-head"><div><p class="eyebrow gold">AUTOMAÇÃO SUPERVISIONADA</p><h3 id="automationTitle">Diagnóstico diário da empresa</h3><small class="muted">7h, de segunda a sábado · próxima execução ${data.policy.nextRunAt ? escapeHTML(dateBR(data.policy.nextRunAt, true)) : "aguardando agenda"}</small></div><span class="status ${data.policy.enabled ? "ativo" : "inativo"}">${data.policy.enabled ? "Ativa" : "Pausada"}</span></div><div class="panel-body"><div class="automation-summary" aria-live="polite"><strong>${data.latestRun ? escapeHTML(data.latestRun.summary || "Execução concluída") : "A primeira execução ocorrerá no próximo horário programado."}</strong><small>${data.latestRun ? `${data.latestRun.findings_count} sinal(is) em ${escapeHTML(data.latestRun.local_date)}` : "Nenhum histórico ainda"}${data.latestRun?.ai_model ? " · resumo priorizado por IA com dados agregados" : " · resumo determinístico"}</small></div>${findings.length ? `<div class="automation-findings">${findings.map((item) => `<article class="automation-finding ${String(item.severity).toLowerCase()}"><div><span>${escapeHTML(areas[item.area] || item.area)}</span><strong>${escapeHTML(item.title)}</strong><p>${escapeHTML(item.message)}</p><small>${escapeHTML(item.recommendation)}</small></div><div class="automation-actions">${item.status === "OPEN" ? `<button type="button" class="secondary" data-automation-finding="${item.id}" data-action="acknowledge">Ciente</button>` : `<span class="status pendente">Em acompanhamento</span>`}<button type="button" class="text-button" data-automation-finding="${item.id}" data-action="resolve">Resolver</button></div></article>`).join("")}</div>` : '<div class="empty compact">Nenhum sinal operacional pendente visível para seu perfil.</div>'}<details class="automation-guardrails"><summary>Limites obrigatórios da automação</summary><ul>${data.policy.guardrails.map((item) => `<li>${escapeHTML(item)}</li>`).join("")}</ul></details></div></section>`;
  }

  management.load = async function loadManagementOverview({ api, escapeHTML, dateBR }) {
    const content = document.querySelector("#content");
    content.innerHTML = '<div class="empty">Consolidando faturamento, caixa e estoque…</div>';
    const [data, automation] = await Promise.all([
      api("/api/management/overview"), api("/api/automation-center"),
    ]);
    const billing = data.billing;
    const cashflow = data.cashflow;
    const inventory = data.inventory;
    const overdue = data.overdue;
    content.innerHTML = `<section class="management-hero"><div><p class="eyebrow gold">CONTROLADORIA · EMPRESA ATIVA</p><h2>Decisões com a mesma fonte operacional</h2><p>Faturamento, caixa, títulos e valor em estoque consolidados sem planilhas paralelas.</p></div><div class="management-asof"><span>Atualizado em</span><strong>${escapeHTML(dateBR(data.asOf, true))}</strong></div></section>
      <section class="management-kpis">${data.visibility.billing ? `${metric("Faturamento acumulado", currency(billing.totalCents), `${billing.count} pedido(s) faturado(s)`, "billing")}${metric("Pedidos a faturar", currency(billing.openOrdersCents), `${billing.openOrdersCount} confirmado(s) ou em separação`)}${metric("Custo dos produtos vendidos", currency(billing.costOfSalesCents), "Saídas registradas no histórico de estoque")}${metric("Resultado bruto", currency(billing.grossContributionCents), "Faturamento menos o custo dos produtos vendidos", Number(billing.grossContributionCents) < 0 ? "negative" : "positive")}` : restricted("Faturamento")}</section>
      <div class="management-layout"><section class="panel management-panel"><div class="panel-head"><div><h3>Fluxo de caixa</h3><small class="muted">Realizado e compromissos em aberto</small></div><button class="text-button" type="button" data-management-go="caixa">Abrir caixa →</button></div><div class="panel-body">${data.visibility.cashflow ? `<div class="management-balance"><span>Saldo realizado</span><strong class="${Number(cashflow.balanceCents) < 0 ? "negative" : ""}">${currency(cashflow.balanceCents)}</strong><small>${currency(cashflow.cashInCents)} em entradas · ${currency(cashflow.cashOutCents)} em saídas</small></div><div class="management-split"><button type="button" data-management-go="contas_receber"><span>A receber em aberto</span><strong>${currency(cashflow.receivableOpenCents)}</strong><small>${cashflow.receivableCount} título(s)</small></button><button type="button" data-management-go="contas_pagar"><span>A pagar em aberto</span><strong>${currency(cashflow.payableOpenCents)}</strong><small>${cashflow.payableCount} título(s)</small></button></div>` : restricted("Fluxo de caixa")}</div></section>
      <section class="panel management-panel"><div class="panel-head"><div><h3>Valor em estoque</h3><small class="muted">Calculado pelo custo médio das entradas registradas</small></div><button class="text-button" type="button" data-management-go="estoque">Abrir estoque →</button></div><div class="panel-body">${data.visibility.inventoryValue ? `<div class="management-balance"><span>Valor físico total</span><strong>${currency(inventory.totalValueCents)}</strong><small>${currency(inventory.availableValueCents)} disponível</small></div><div class="management-stock-split"><span><b>${currency(inventory.reservedValueCents)}</b><small>Reservado</small></span><span class="${inventory.unvaluedBalances ? "warning" : ""}"><b>${inventory.unvaluedBalances}</b><small>Saldos sem custo</small></span></div>` : restricted("Valor em estoque")}</div></section></div>
      <section class="panel management-overdue"><div class="panel-head"><div><h3>Títulos vencidos</h3><small class="muted">Prazo anterior a hoje e ainda não liquidado</small></div></div><div class="panel-body">${data.visibility.overdue ? `<div class="management-overdue-grid"><button type="button" data-management-go="contas_receber"><span>A receber vencido</span><strong>${currency(overdue.receivableCents)}</strong><small>${overdue.receivableCount} título(s)</small></button><button type="button" data-management-go="contas_pagar"><span>A pagar vencido</span><strong>${currency(overdue.payableCents)}</strong><small>${overdue.payableCount} título(s)</small></button></div>` : restricted("Títulos vencidos")}</div></section>
      ${automationHTML(automation, escapeHTML, dateBR)}
      <section class="panel management-series"><div class="panel-head"><div><h3>Evolução dos últimos seis meses</h3><small class="muted">Faturamento pelo mês da última atualização do pedido; caixa pelo mês do lançamento</small></div></div><div class="panel-body">${seriesHTML(data)}</div></section>
      <p class="management-method">Indicadores gerenciais usam somente dados persistidos na empresa ativa. A contribuição bruta não inclui impostos, fretes ou despesas sem movimento de estoque e não substitui DRE contábil.</p>`;
    bindNavigation();
    document.querySelectorAll("[data-automation-finding]").forEach((button) => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(`/api/automation-center/findings/${Number(button.dataset.automationFinding)}/${button.dataset.action}`, { method: "POST", body: "{}" });
          await management.load({ api, escapeHTML, dateBR });
        } catch (error) {
          button.disabled = false;
          global.showToast?.(error.message || "Não foi possível atualizar o achado.", "error");
        }
      };
    });
  };
})(window);
