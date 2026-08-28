(function initializeReportingCenter(global) {
  const reporting = global.SIVSReporting ||= {};
  let context;
  let catalog;
  let activeDataset;
  let currentResult;
  const reducedMotion = global.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  const escape = (value) => context.escapeHTML(String(value ?? ""));
  const format = (value, kind) => {
    if (value === null || value === undefined) return "—";
    if (kind === "money") return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value) / 100);
    if (kind === "integer") return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(Number(value));
    if (kind === "number") return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(Number(value));
    if (kind === "month" && /^\d{4}-\d{2}$/.test(String(value))) return `${String(value).slice(5)}/${String(value).slice(0, 4)}`;
    return String(value);
  };
  const dataset = () => catalog.datasets.find((item) => item.key === activeDataset);
  const selected = (name) => [...document.querySelectorAll(`[name="${name}"]:checked`)].map((input) => input.value);

  function exactDimensionFilters() {
    return Object.fromEntries([...document.querySelectorAll("[data-report-dimension-filter]")]
      .map((input) => [input.dataset.reportDimensionFilter, input.value.split(";").map((value) => value.trim()).filter(Boolean).slice(0, 20)])
      .filter(([, values]) => values.length));
  }

  function definition() {
    const modules = selected("reportModule");
    return {
      dataset: activeDataset,
      dimensions: selected("reportDimension"), metrics: selected("reportMetric"),
      filters: {
        start: document.querySelector("#reportStart")?.value || "",
        end: document.querySelector("#reportEnd")?.value || "",
        search: document.querySelector("#reportSearch")?.value.trim() || "",
        ...(dataset().moduleOptions.length ? { modules } : {}),
        dimensions: exactDimensionFilters(),
      },
      orderBy: document.querySelector("#reportOrder")?.value || selected("reportMetric")[0],
      order: document.querySelector("#reportDirection")?.value || "DESC",
    };
  }

  function configurationHTML(spec) {
    const dimensionSet = new Set(spec.defaultDimensions);
    const metricSet = new Set(spec.defaultMetrics);
    return `<section class="report-builder panel" aria-labelledby="reportBuilderTitle">
      <div class="panel-head"><div><p class="eyebrow gold">CONSTRUTOR SEGURO</p><h3 id="reportBuilderTitle">${escape(spec.title)}</h3><small>${escape(spec.description)}</small></div><span class="status">${spec.dimensions.length} dimensões · ${spec.metrics.length} métricas</span></div>
      <div class="panel-body report-builder-body">
        <div class="report-filters">
          <label class="field"><span>Data inicial</span><input id="reportStart" type="date"></label>
          <label class="field"><span>Data final</span><input id="reportEnd" type="date"></label>
          <label class="field report-search"><span>Pesquisar nesta fonte</span><input id="reportSearch" type="search" maxlength="120" placeholder="Nome, documento, item ou histórico"></label>
        </div>
        ${spec.moduleOptions.length ? `<fieldset class="report-module-filter"><legend>Módulos incluídos</legend><div class="report-checks">${spec.moduleOptions.map((item) => `<label><input type="checkbox" name="reportModule" value="${escape(item.value)}" checked><span>${escape(item.label)}</span></label>`).join("")}</div></fieldset>` : ""}
        <div class="report-choice-grid">
          <fieldset><legend>Como detalhar</legend><small>Escolha de uma a quatro dimensões.</small><div class="report-checks">${spec.dimensions.map((item) => `<label><input type="checkbox" name="reportDimension" value="${escape(item.key)}" ${dimensionSet.has(item.key) ? "checked" : ""}><span>${escape(item.label)}</span></label>`).join("")}</div></fieldset>
          <fieldset><legend>O que medir</legend><small>Os totais usam todos os dados filtrados.</small><div class="report-checks">${spec.metrics.map((item) => `<label><input type="checkbox" name="reportMetric" value="${escape(item.key)}" ${metricSet.has(item.key) ? "checked" : ""}><span>${escape(item.label)}</span></label>`).join("")}</div>${spec.valuesRestricted ? '<p class="report-restriction">Valores financeiros ocultados pelas permissões da fonte.</p>' : ""}</fieldset>
        </div>
        <details class="report-exact-filters"><summary>Filtros exatos por dimensão</summary><p>Opcional. Digite um ou mais valores separados por ponto e vírgula.</p><div>${spec.dimensions.map((item) => `<label class="field"><span>${escape(item.label)}</span><input type="text" maxlength="800" data-report-dimension-filter="${escape(item.key)}" placeholder="Ex.: valor 1; valor 2"></label>`).join("")}</div></details>
        <div class="report-runbar"><label class="field"><span>Ordenar por</span><select id="reportOrder">${[...spec.metrics, ...spec.dimensions].map((item) => `<option value="${escape(item.key)}">${escape(item.label)}</option>`).join("")}</select></label><label class="field"><span>Ordem</span><select id="reportDirection"><option value="DESC">Maior / mais recente</option><option value="ASC">Menor / mais antigo</option></select></label><button id="runReport" class="primary" type="button">Gerar relatório</button></div>
        <p id="reportError" class="form-error hidden" role="alert"></p>
      </div></section>`;
  }

  function shellHTML() {
    const areas = [...new Set(catalog.datasets.map((item) => item.area))];
    return `<section class="reports-hero"><div><p class="eyebrow gold">CENTRAL DE RELATÓRIOS</p><h2>Transforme os dados autorizados em decisões claras.</h2><p>Combine fontes, períodos, dimensões e indicadores sem planilhas paralelas. Toda consulta preserva empresa, perfil e trilha de auditoria.</p></div><div class="reports-hero-mark" aria-hidden="true"><span></span><span></span><span></span><span></span></div></section>
      <nav class="report-source-nav" aria-label="Fontes de relatório">${areas.map((area) => `<span>${escape(area)}</span>`).join("")}</nav>
      <section class="report-source-grid" aria-label="Escolha uma fonte">${catalog.datasets.map((item) => `<button type="button" data-report-dataset="${escape(item.key)}" class="report-source-card ${item.key === activeDataset ? "active" : ""}" aria-pressed="${item.key === activeDataset}"><span>${escape(item.area)}</span><strong>${escape(item.title)}</strong><small>${escape(item.description)}</small><b aria-hidden="true">→</b></button>`).join("")}</section>
      <div id="reportConfiguration">${configurationHTML(dataset())}</div>
      <section id="reportOutput" class="report-output" aria-live="polite"><div class="report-welcome"><span aria-hidden="true">◫</span><strong>Configure e gere seu primeiro recorte.</strong><p>Os indicadores, gráfico e tabela aparecerão aqui com a mesma fonte de verdade.</p></div></section>
      ${catalog.templates.length ? `<section class="panel report-templates"><div class="panel-head"><h3>Modelos salvos</h3><span class="status">${catalog.templates.length}</span></div><div class="panel-body">${catalog.templates.map((item) => `<article><button type="button" data-report-template="${item.id}"><span><strong>${escape(item.name)}</strong><small>${escape(item.ownerName)}${item.shared ? " · compartilhado" : ""}</small></span><b aria-hidden="true">→</b></button>${item.canDelete ? `<button type="button" class="icon-button" data-delete-report-template="${item.id}" aria-label="Excluir modelo ${escape(item.name)}">×</button>` : ""}</article>`).join("")}</div></section>` : ""}`;
  }

  function kpisHTML(result) {
    return result.columns.filter((column) => column.kind === "metric").map((column) => `<article><span>${escape(column.label)}</span><strong>${escape(format(result.totals[column.key], column.format))}</strong></article>`).join("");
  }

  function chartHTML(result) {
    const dimension = result.columns.find((column) => column.kind === "dimension");
    const metric = result.columns.find((column) => column.kind === "metric");
    if (!dimension || !metric || !result.rows.length) return "";
    const rows = result.rows.slice(0, 12);
    const maximum = Math.max(...rows.map((row) => Math.abs(Number(row[metric.key] || 0))), 1);
    return `<section class="panel report-chart" aria-labelledby="reportChartTitle"><div class="panel-head"><div><h3 id="reportChartTitle">${escape(metric.label)} por ${escape(dimension.label.toLowerCase())}</h3><small>Até 12 agrupamentos na ordem escolhida.</small></div></div><div class="panel-body" role="img" aria-label="Gráfico de ${escape(metric.label)} por ${escape(dimension.label)}">${rows.map((row) => { const width = Math.max(2, Math.round(Math.abs(Number(row[metric.key] || 0)) / maximum * 100)); return `<div class="report-bar"><span title="${escape(format(row[dimension.key], dimension.format))}">${escape(format(row[dimension.key], dimension.format))}</span><div><i style="--report-bar-width:${width}%"></i></div><strong>${escape(format(row[metric.key], metric.format))}</strong></div>`; }).join("")}</div></section>`;
  }

  function tableHTML(result) {
    return `<section class="panel report-table-panel"><div class="panel-head"><div><h3>Detalhamento</h3><small>${result.rowCount} agrupamento(s)${result.truncated ? " · exibição limitada aos primeiros 500" : ""}</small></div><div class="report-output-actions">${dataset().canExport ? '<button type="button" class="secondary" data-report-export="csv">CSV</button><button type="button" class="secondary" data-report-export="pdf">PDF</button>' : ""}${catalog.canSave ? '<button type="button" class="primary" id="saveReportTemplate">Salvar modelo</button>' : ""}</div></div><div class="table-wrap borderless"><table class="data-table report-table"><thead><tr>${result.columns.map((column) => `<th scope="col">${escape(column.label)}</th>`).join("")}</tr></thead><tbody>${result.rows.length ? result.rows.map((row) => `<tr>${result.columns.map((column) => `<td class="${column.kind === "metric" ? "numeric" : ""}">${escape(format(row[column.key], column.format))}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${result.columns.length}">Nenhum dado corresponde aos filtros.</td></tr>`}</tbody><tfoot><tr>${result.columns.map((column, index) => `<td class="${column.kind === "metric" ? "numeric" : ""}">${column.kind === "metric" ? escape(format(result.totals[column.key], column.format)) : index === 0 ? "Total geral" : ""}</td>`).join("")}</tr></tfoot></table></div></section>`;
  }

  function renderResult(result) {
    currentResult = result;
    const output = document.querySelector("#reportOutput");
    output.innerHTML = `<section class="report-kpis">${kpisHTML(result)}</section>${chartHTML(result)}${tableHTML(result)}`;
    bindOutput();
    output.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  }

  async function execute(request = definition()) {
    const error = document.querySelector("#reportError");
    error?.classList.add("hidden");
    const button = document.querySelector("#runReport");
    if (button) { button.disabled = true; button.textContent = "Calculando…"; }
    try {
      const result = await context.api("/api/reporting/run", { method: "POST", body: JSON.stringify(request) });
      renderResult(result);
    } catch (failure) {
      if (error) { error.textContent = failure.message; error.classList.remove("hidden"); }
    } finally {
      if (button) { button.disabled = false; button.textContent = "Gerar relatório"; }
    }
  }

  async function exportReport(fileFormat) {
    const response = await fetch("/api/reporting/export", { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": context.state.csrf },
      body: JSON.stringify({ ...currentResult.definition, format: fileFormat }) });
    if (!response.ok) { const failure = await response.json().catch(() => ({})); throw new Error(failure.message || "Não foi possível exportar"); }
    const blob = await response.blob(); const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url;
    link.download = response.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1] || `relatorio.${fileFormat}`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function bindOutput() {
    document.querySelectorAll("[data-report-export]").forEach((button) => button.addEventListener("click", async () => {
      button.disabled = true; try { await exportReport(button.dataset.reportExport); context.toast("Relatório exportado e auditado."); } catch (failure) { context.toast(failure.message); } finally { button.disabled = false; }
    }));
    document.querySelector("#saveReportTemplate")?.addEventListener("click", async () => {
      const name = global.prompt("Nome deste modelo de relatório:"); if (!name) return;
      const shared = catalog.canShare && global.confirm("Compartilhar este modelo com a empresa?");
      try { await context.api("/api/reporting/templates", { method: "POST", body: JSON.stringify({ name, shared, definition: currentResult.definition }) }); context.toast("Modelo de relatório salvo."); await reporting.load(context); } catch (failure) { context.toast(failure.message); }
    });
  }

  function bindConfiguration() {
    document.querySelector("#runReport")?.addEventListener("click", () => execute());
    document.querySelector("#reportSearch")?.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); execute(); } });
  }

  function bindShell() {
    document.querySelectorAll("[data-report-dataset]").forEach((button) => button.addEventListener("click", () => {
      activeDataset = button.dataset.reportDataset; currentResult = null;
      document.querySelectorAll("[data-report-dataset]").forEach((item) => { const active = item.dataset.reportDataset === activeDataset; item.classList.toggle("active", active); item.setAttribute("aria-pressed", String(active)); });
      document.querySelector("#reportConfiguration").innerHTML = configurationHTML(dataset());
      document.querySelector("#reportOutput").innerHTML = '<div class="report-welcome"><span aria-hidden="true">◫</span><strong>Nova fonte selecionada.</strong><p>Escolha o recorte desejado e gere o relatório.</p></div>';
      bindConfiguration();
    }));
    document.querySelectorAll("[data-report-template]").forEach((button) => button.addEventListener("click", async () => {
      const template = catalog.templates.find((item) => item.id === Number(button.dataset.reportTemplate)); if (!template) return;
      activeDataset = template.dataset;
      document.querySelector("#reportConfiguration").innerHTML = configurationHTML(dataset()); bindConfiguration();
      const request = template.definition;
      (request.dimensions || []).forEach((key) => { const input = document.querySelector(`[name="reportDimension"][value="${CSS.escape(key)}"]`); if (input) input.checked = true; });
      document.querySelectorAll('[name="reportDimension"]').forEach((input) => { if (!(request.dimensions || []).includes(input.value)) input.checked = false; });
      document.querySelectorAll('[name="reportMetric"]').forEach((input) => { input.checked = (request.metrics || []).includes(input.value); });
      if (request.filters?.start) document.querySelector("#reportStart").value = request.filters.start;
      if (request.filters?.end) document.querySelector("#reportEnd").value = request.filters.end;
      if (request.filters?.search) document.querySelector("#reportSearch").value = request.filters.search;
      document.querySelectorAll('[name="reportModule"]').forEach((input) => { input.checked = !request.filters?.modules || request.filters.modules.includes(input.value); });
      Object.entries(request.filters?.dimensions || {}).forEach(([key, values]) => { const input = document.querySelector(`[data-report-dimension-filter="${CSS.escape(key)}"]`); if (input) input.value = (Array.isArray(values) ? values : [values]).join("; "); });
      await execute(request);
    }));
    document.querySelectorAll("[data-delete-report-template]").forEach((button) => button.addEventListener("click", async () => {
      if (!global.confirm("Excluir este modelo de relatório?")) return;
      try { await context.api(`/api/reporting/templates/${button.dataset.deleteReportTemplate}`, { method: "DELETE" }); context.toast("Modelo excluído."); await reporting.load(context); } catch (failure) { context.toast(failure.message); }
    }));
    bindConfiguration();
  }

  reporting.load = async function load(nextContext) {
    context = nextContext;
    context.content.innerHTML = '<div class="empty">Preparando fontes, permissões e modelos de relatório…</div>';
    catalog = await context.api("/api/reporting/catalog");
    if (!catalog.datasets.length) throw new Error("Seu perfil não possui fontes de relatório autorizadas.");
    activeDataset = catalog.datasets.some((item) => item.key === activeDataset) ? activeDataset : catalog.datasets[0].key;
    context.content.innerHTML = shellHTML(); bindShell();
  };
})(window);
