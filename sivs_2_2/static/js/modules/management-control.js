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

  management.load = async function loadManagementOverview({ api, escapeHTML, dateBR }) {
    const content = document.querySelector("#content");
    content.innerHTML = '<div class="empty">Consolidando faturamento, caixa e estoque…</div>';
    const data = await api("/api/management/overview");
    const billing = data.billing;
    const cashflow = data.cashflow;
    const inventory = data.inventory;
    const overdue = data.overdue;
    content.innerHTML = `<section class="management-hero"><div><p class="eyebrow gold">CONTROLADORIA · EMPRESA ATIVA</p><h2>Decisões com a mesma fonte operacional</h2><p>Faturamento, caixa, títulos e valor em estoque consolidados sem planilhas paralelas.</p></div><div class="management-asof"><span>Atualizado em</span><strong>${escapeHTML(dateBR(data.asOf, true))}</strong></div></section>
      <section class="management-kpis">${data.visibility.billing ? `${metric("Faturamento acumulado", currency(billing.totalCents), `${billing.count} pedido(s) faturado(s)`, "billing")}${metric("Pedidos a faturar", currency(billing.openOrdersCents), `${billing.openOrdersCount} confirmado(s) ou em separação`)}${metric("Custo das baixas", currency(billing.costOfSalesCents), "Saídas rastreadas pelo ledger")}${metric("Contribuição bruta", currency(billing.grossContributionCents), "Faturamento menos custo rastreado", Number(billing.grossContributionCents) < 0 ? "negative" : "positive")}` : restricted("Faturamento")}</section>
      <div class="management-layout"><section class="panel management-panel"><div class="panel-head"><div><h3>Fluxo de caixa</h3><small class="muted">Realizado e compromissos em aberto</small></div><button class="text-button" type="button" data-management-go="caixa">Abrir caixa →</button></div><div class="panel-body">${data.visibility.cashflow ? `<div class="management-balance"><span>Saldo realizado</span><strong class="${Number(cashflow.balanceCents) < 0 ? "negative" : ""}">${currency(cashflow.balanceCents)}</strong><small>${currency(cashflow.cashInCents)} em entradas · ${currency(cashflow.cashOutCents)} em saídas</small></div><div class="management-split"><button type="button" data-management-go="contas_receber"><span>A receber em aberto</span><strong>${currency(cashflow.receivableOpenCents)}</strong><small>${cashflow.receivableCount} título(s)</small></button><button type="button" data-management-go="contas_pagar"><span>A pagar em aberto</span><strong>${currency(cashflow.payableOpenCents)}</strong><small>${cashflow.payableCount} título(s)</small></button></div>` : restricted("Fluxo de caixa")}</div></section>
      <section class="panel management-panel"><div class="panel-head"><div><h3>Valor em estoque</h3><small class="muted">Custo médio móvel do ledger</small></div><button class="text-button" type="button" data-management-go="estoque">Abrir estoque →</button></div><div class="panel-body">${data.visibility.inventoryValue ? `<div class="management-balance"><span>Valor físico total</span><strong>${currency(inventory.totalValueCents)}</strong><small>${currency(inventory.availableValueCents)} disponível</small></div><div class="management-stock-split"><span><b>${currency(inventory.reservedValueCents)}</b><small>Reservado</small></span><span class="${inventory.unvaluedBalances ? "warning" : ""}"><b>${inventory.unvaluedBalances}</b><small>Saldos sem custo</small></span></div>` : restricted("Valor em estoque")}</div></section></div>
      <section class="panel management-overdue"><div class="panel-head"><div><h3>Títulos vencidos</h3><small class="muted">Prazo anterior a hoje e ainda não liquidado</small></div></div><div class="panel-body">${data.visibility.overdue ? `<div class="management-overdue-grid"><button type="button" data-management-go="contas_receber"><span>A receber vencido</span><strong>${currency(overdue.receivableCents)}</strong><small>${overdue.receivableCount} título(s)</small></button><button type="button" data-management-go="contas_pagar"><span>A pagar vencido</span><strong>${currency(overdue.payableCents)}</strong><small>${overdue.payableCount} título(s)</small></button></div>` : restricted("Títulos vencidos")}</div></section>
      <section class="panel management-series"><div class="panel-head"><div><h3>Evolução dos últimos seis meses</h3><small class="muted">Faturamento pelo mês da última atualização do pedido; caixa pelo mês do lançamento</small></div></div><div class="panel-body">${seriesHTML(data)}</div></section>
      <p class="management-method">Indicadores gerenciais usam somente dados persistidos na empresa ativa. A contribuição bruta não inclui impostos, fretes ou despesas sem movimento de estoque e não substitui DRE contábil.</p>`;
    bindNavigation();
  };
})(window);
