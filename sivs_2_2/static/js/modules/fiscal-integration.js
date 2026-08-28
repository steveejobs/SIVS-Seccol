(function initializeFiscalIntegration(global) {
  const fiscal = global.SIVSFiscalIntegration ||= {};

  const regimeLabels = {
    SIMPLES_NACIONAL: "Simples Nacional",
    SIMPLES_EXCESSO: "Simples Nacional — excesso de sublimite",
    REGIME_NORMAL: "Regime normal",
  };

  function certificateHTML(certificate, escapeHTML, dateBR, abilities) {
    if (!certificate) {
      return `<div class="fiscal-empty"><span>◇</span><div><strong>Nenhum A1 ativo</strong><p>O arquivo e a senha nunca são enviados à SEFAZ antes de uma consulta solicitada. A senha abre o PFX uma vez e não é armazenada.</p></div></div>${abilities.certificate ? '<button type="button" class="secondary" id="openFiscalCertificate">Importar certificado A1</button>' : ""}`;
    }
    return `<div class="fiscal-certificate"><span class="fiscal-lock">▣</span><div><strong>${escapeHTML(certificate.subject || "Certificado A1")}</strong><p>Válido até ${escapeHTML(dateBR(certificate.validTo, true))}</p><small>SHA-256 ${escapeHTML(certificate.fingerprintSha256 || "")}</small></div><span class="status concluído">Ativo</span></div><div class="fiscal-inline-actions">${abilities.certificate ? '<button type="button" class="secondary" id="openFiscalCertificate">Substituir A1</button><button type="button" class="text-button danger-text" id="removeFiscalCertificate">Remover</button>' : ""}</div>`;
  }

  function statusHTML(configuration, escapeHTML, dateBR, abilities, canCheckStatus) {
    if (!configuration) {
      return `<div class="fiscal-empty"><span>↯</span><div><strong>Homologação não configurada</strong><p>Cadastre a unidade fiscal e use o endpoint oficial da SEFAZ/GO.</p></div></div>${abilities.configuration ? '<button type="button" class="secondary" id="openFiscalConfiguration">Configurar homologação</button>' : ""}`;
    }
    const operational = configuration.last_status_code === "107";
    return `<div class="fiscal-status-line"><span class="fiscal-signal ${operational ? "online" : ""}"></span><div><strong>${operational ? "Consulta SEFAZ respondida" : "Aguardando consulta real"}</strong><p>${escapeHTML(configuration.last_status_reason || "Consulta NF-e 4.00 em homologação")}</p><small>${configuration.last_checked_at ? `Consultado em ${escapeHTML(dateBR(configuration.last_checked_at, true))}` : "Ainda não consultado com o A1"}</small></div></div><div class="fiscal-inline-actions">${abilities.status ? `<button type="button" class="primary" id="checkSefazStatus" ${canCheckStatus ? "" : "disabled"}>Consultar SEFAZ agora</button>` : ""}${abilities.configuration ? '<button type="button" class="secondary" id="openFiscalConfiguration">Editar configuração</button>' : ""}</div>`;
  }

  function accountingMappingHTML({ foundation, mappings, categories, abilities, escapeHTML }) {
    const accounts = (foundation?.accounts || []).filter((item) => item.active && item.account_kind === "ANALYTICAL");
    const centers = (foundation?.costCenters || []).filter((item) => item.active);
    const rows = (mappings || []).length ? `<div class="accounting-mapping-list">${mappings.map((item) => {
      const allocations = item.allocations || [];
      const allocationText = allocations.length ? ` · rateio ${allocations[0].allocation_side === "DEBIT" ? "no débito" : "no crédito"}: ${allocations.map((row) => `${escapeHTML(row.cost_center_code)} ${accountingBasisToPercent(row.basis_points)}%`).join(", ")}` : (item.cost_center_code ? ` · centro padrão ${escapeHTML(item.cost_center_code)}` : "");
      const adjustmentText = (item.adjustmentRules || []).length ? ` · ajustes: ${(item.adjustmentRules || []).map((rule) => `${({ DISCOUNT: "desconto", INTEREST: "juros/multa", FEE: "tarifa" })[rule.adjustment_type]} → ${escapeHTML(rule.account_code)}${!rule.account_active || (rule.cost_center_id && !rule.cost_center_active) ? " (inativa)" : ""}`).join(", ")}` : "";
      const edit = abilities.accountingManagement ? `<button type="button" class="text-button" data-edit-accounting-mapping="${item.id}">Editar</button>` : "";
      return `<div><strong>${escapeHTML(item.financial_module === "contas_pagar" ? "Baixa a pagar" : "Baixa a receber")} · ${escapeHTML(item.category_name)}</strong><small>D ${escapeHTML(item.debit_account_code)} · C ${escapeHTML(item.credit_account_code)}${allocationText}${adjustmentText}${item.active ? "" : " · inativo"}</small>${edit}</div>`;
    }).join("")}</div>` : '<p class="fiscal-restricted">Nenhum mapeamento ativo. As baixas continuam sem lançamento contábil automático.</p>';
    if (!abilities.accountingManagement) return `<section class="panel fiscal-accounting fiscal-accounting-map"><div class="panel-head"><div><h3>Integração financeiro-contábil</h3><small class="muted">Mapeamento controlado</small></div></div><div class="panel-body">${rows}</div></section>`;
    const categoryOptions = (categories || []).filter((item) => item.active).map((item) => `<option value="${item.id}">${escapeHTML(item.name)} · ${item.kind}</option>`).join("");
    const accountOptions = accounts.map((item) => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join("");
    const centerOptions = centers.map((item) => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join("");
    const adjustmentRules = accountingAdjustmentRulesHTML(accounts, centers, escapeHTML);
    return `<section class="panel fiscal-accounting fiscal-accounting-map"><div class="panel-head"><div><h3>Integração financeiro-contábil</h3><small class="muted">Escolha as contas e o critério explícito; o sistema não presume débito, crédito, ajuste ou rateio.</small></div></div><div class="panel-body">${rows}<form id="accountingMappingForm" class="accounting-mapping-form"><label class="field"><span>Origem *</span><select name="financialModule"><option value="contas_pagar">Baixa a pagar</option><option value="contas_receber">Baixa a receber</option></select></label><label class="field"><span>Categoria *</span><select name="categoryId" required><option value="">Selecione</option>${categoryOptions}</select></label><label class="field"><span>Conta débito *</span><select name="debitAccountId" required><option value="">Selecione</option>${accountOptions}</select></label><label class="field"><span>Conta crédito *</span><select name="creditAccountId" required><option value="">Selecione</option>${accountOptions}</select></label><label class="field"><span>Centro de custo padrão</span><select name="costCenterId"><option value="">Sem padrão</option>${centerOptions}</select><small class="field-help">Use somente sem rateio.</small></label><fieldset class="accounting-allocation-editor"><legend>Rateio por centro de custo</legend><p>Opcional. O valor será dividido em centavos exatos no lado informado, sem alterar o outro lado da partida.</p><label class="field"><span>Lado rateado</span><select name="allocationSide" id="accountingAllocationSide"><option value="NONE">Sem rateio</option><option value="DEBIT">Débito</option><option value="CREDIT">Crédito</option></select></label><div id="accountingAllocationLines" class="accounting-allocation-lines" hidden></div><div id="accountingAllocationActions" class="accounting-allocation-actions" hidden><button type="button" class="secondary" id="addAccountingAllocation">Adicionar centro</button><output id="accountingAllocationTotal" aria-live="polite"></output></div></fieldset>${adjustmentRules}<div class="accounting-mapping-submit"><button type="button" class="secondary" id="resetAccountingMapping">Novo mapeamento</button><button type="submit" class="secondary" ${accounts.length < 2 ? "disabled" : ""}>Salvar mapeamento</button></div></form><p id="accountingMappingError" class="form-error hidden" role="alert"></p></div></section>`;
  }

  function accountingCurrency(cents) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(cents || 0) / 100);
  }

  function accountingBasisToPercent(basisPoints) {
    return (Number(basisPoints || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function accountingAdjustmentRulesHTML(accounts, centers, escapeHTML) {
    const accountOptions = accounts.map((item) => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join("");
    const centerOptions = centers.map((item) => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join("");
    const rows = [
      ["DISCOUNT", "Desconto"], ["INTEREST", "Juros ou multa"], ["FEE", "Tarifa"],
    ].map(([type, label]) => {
      const key = type.toLowerCase();
      return `<div class="accounting-adjustment-rule"><strong>${label}</strong><label class="field"><span>Conta própria</span><select name="${key}AccountId"><option value="">Não configurar</option>${accountOptions}</select></label><label class="field"><span>Centro de custo</span><select name="${key}CostCenterId"><option value="">Sem centro</option>${centerOptions}</select></label></div>`;
    }).join("");
    return `<fieldset class="accounting-adjustment-editor"><legend>Contas para ajustes da baixa</legend><p>Opcional enquanto o ajuste for zero. Ao informar desconto, juros/multa ou tarifa, a baixa exige a conta correspondente e nunca classifica o valor por conta própria.</p>${rows}</fieldset>`;
  }

  function accountingAllocationLineHTML(centers, escapeHTML, index, allocation = {}) {
    const options = centers.map((item) => `<option value="${item.id}" ${Number(item.id) === Number(allocation.cost_center_id || allocation.costCenterId) ? "selected" : ""}>${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join("");
    const percentage = allocation.basis_points ?? allocation.basisPoints;
    return `<div class="accounting-allocation-line" data-accounting-allocation><strong>${index + 1}</strong><label class="field"><span>Centro *</span><select name="allocationCenterId" required><option value="">Selecione</option>${options}</select></label><label class="field"><span>Percentual *</span><input name="allocationPercent" inputmode="decimal" value="${percentage == null ? "" : accountingBasisToPercent(percentage)}" placeholder="0,00" required></label><button type="button" class="icon-button" data-remove-accounting-allocation aria-label="Remover centro ${index + 1}">×</button></div>`;
  }

  function accountingLineHTML(accounts, centers, escapeHTML, index) {
    const accountOptions = accounts.map((item) => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join("");
    const centerOptions = centers.map((item) => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join("");
    return `<div class="accounting-entry-line" data-accounting-line><strong>${index + 1}</strong><label class="field"><span>Conta *</span><select name="accountId" required><option value="">Selecione</option>${accountOptions}</select></label><label class="field"><span>Centro de custo</span><select name="costCenterId"><option value="">Sem centro</option>${centerOptions}</select></label><label class="field"><span>Débito</span><input name="debit" inputmode="decimal" placeholder="0,00"></label><label class="field"><span>Crédito</span><input name="credit" inputmode="decimal" placeholder="0,00"></label><button type="button" class="icon-button" data-remove-accounting-line aria-label="Remover partida ${index + 1}">×</button></div>`;
  }

  function accountingWorkspaceHTML({ foundation, abilities, escapeHTML, currentPeriod, currentDate }) {
    const accounts = (foundation?.accounts || []).filter((item) => item.active && item.account_kind === "ANALYTICAL");
    const reportAccounts = (foundation?.accounts || []).filter((item) => item.account_kind === "ANALYTICAL");
    const centers = (foundation?.costCenters || []).filter((item) => item.active);
    const entry = abilities.accountingPosting ? `<section class="panel fiscal-accounting accounting-entry-panel"><div class="panel-head"><div><h3>Lançamento contábil</h3><small class="muted">Partidas dobradas, imutáveis e auditadas.</small></div></div><div class="panel-body">${accounts.length >= 2 ? `<form id="accountingJournalForm" class="accounting-journal-form"><label class="field"><span>Tipo do lançamento *</span><select name="entryMode"><option value="MANUAL">Lançamento manual</option><option value="OPENING_BALANCE">Saldo inicial da competência</option></select><small class="field-help">Saldo inicial só pode usar o primeiro dia da competência e uma única vez por data.</small></label><div class="accounting-journal-meta"><label class="field"><span>Data do lançamento *</span><input name="entryDate" type="date" value="${currentDate}" required></label><label class="field"><span>Competência *</span><input name="competenceDate" type="date" value="${currentDate}" required></label><label class="field full"><span>Histórico *</span><input name="memo" maxlength="1000" minlength="3" required placeholder="Descreva o fato contábil"></label></div><div class="accounting-entry-lines" id="accountingEntryLines">${accountingLineHTML(accounts, centers, escapeHTML, 0)}${accountingLineHTML(accounts, centers, escapeHTML, 1)}</div><div class="accounting-entry-actions"><button type="button" class="secondary" id="addAccountingLine">Adicionar partida</button><output id="accountingJournalTotals" aria-live="polite"></output></div><p id="accountingJournalError" class="form-error hidden" role="alert"></p><button type="submit" class="primary">Registrar lançamento</button></form>` : '<p class="fiscal-restricted">Cadastre ao menos duas contas analíticas ativas antes de lançar partidas.</p>'}</div></section>` : `<section class="panel fiscal-accounting accounting-entry-panel"><div class="panel-head"><div><h3>Lançamento contábil</h3><small class="muted">Partidas dobradas e auditadas</small></div></div><div class="panel-body"><p class="fiscal-restricted">Seu perfil pode consultar, mas não registrar partidas contábeis.</p></div></section>`;
    const reportOptions = reportAccounts.map((item) => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join("");
    const reports = abilities.accountingReports ? `<section class="panel fiscal-accounting accounting-reports-panel"><div class="panel-head"><div><h3>Relatórios contábeis</h3><small class="muted">Diário, razão, balancete, DRE e balanço — sem números paralelos.</small></div></div><div class="panel-body"><div class="accounting-report-controls"><label class="field"><span>Período *</span><input id="accountingReportPeriod" type="month" value="${currentPeriod}" max="${currentPeriod}" required></label><label class="field"><span>Base *</span><select id="accountingReportBasis"><option value="competence">Competência</option><option value="cash">Caixa</option></select></label><label class="field"><span>Conta para razão</span><select id="accountingLedgerAccount"><option value="">Selecione</option>${reportOptions}</select></label><button type="button" class="primary" id="loadAccountingReports">Consultar relatórios</button></div><p class="accounting-report-note">Competência usa a data de competência; caixa usa a data do lançamento. O balanço inclui o resultado acumulado ainda não encerrado para conferir a igualdade patrimonial.</p><div class="accounting-report-tabs" role="tablist" aria-label="Tipo de relatório"><button type="button" class="active" data-accounting-report="trial" role="tab" aria-selected="true">Balancete</button><button type="button" data-accounting-report="income" role="tab" aria-selected="false">DRE</button><button type="button" data-accounting-report="balance" role="tab" aria-selected="false">Balanço</button><button type="button" data-accounting-report="journal" role="tab" aria-selected="false">Diário</button><button type="button" data-accounting-report="ledger" role="tab" aria-selected="false">Razão</button></div><div id="accountingReportOutput" class="accounting-report-output" aria-live="polite"><div class="financial-empty">Escolha período e base para consultar os lançamentos já registrados.</div></div></div></section>` : `<section class="panel fiscal-accounting accounting-reports-panel"><div class="panel-head"><div><h3>Relatórios contábeis</h3><small class="muted">Consulta protegida por valores</small></div></div><div class="panel-body"><p class="fiscal-restricted">Seu perfil não pode consultar valores contábeis.</p></div></section>`;
    return `<section class="accounting-workspace" aria-label="Escrituração e relatórios contábeis">${entry}${reports}</section>`;
  }

  function taxBasisPoints(value) {
    const normalized = String(value || "").trim().replace(/\s/g, "").replace(".", ",");
    if (!/^\d{1,3}(?:,\d{1,2})?$/.test(normalized)) return null;
    const [whole, decimals = ""] = normalized.split(",");
    const basisPoints = Number(whole) * 100 + Number(decimals.padEnd(2, "0"));
    return basisPoints <= 10000 ? basisPoints : null;
  }

  function taxRuleLabel(rule, escapeHTML) {
    const conditions = rule.conditions || {};
    const conditionText = Object.entries(conditions).map(([key, value]) => ({
      originUf: `origem ${value}`, destinationUf: `destino ${value}`, ncmPrefix: `NCM ${value}*`,
      cest: `CEST ${value}`, cfop: `CFOP ${value}`, merchandiseOrigin: `origem mercadoria ${value}`,
    })[key]).join(" · ") || "Todas as classificações";
    const result = rule.result || {};
    const classification = result.csosn ? `CSOSN ${result.csosn}` : `CST ${result.cst || "—"}`;
    return `<strong>${escapeHTML(rule.operation_code)} · ${escapeHTML(rule.profile_name)} · ${escapeHTML(rule.tax_code)}</strong><small>${escapeHTML(conditionText)} · ${classification} · ${(Number(result.rateBps || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}% · redução ${(Number(result.baseReductionBps || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}% · prioridade ${rule.priority}${rule.active ? "" : " · revisão inativa"}</small>`;
  }

  function taxPreviewHTML(preview, escapeHTML) {
    if (!preview) return '<div class="tax-preview-empty">A prévia não gera XML, numeração ou transmissão. Ela exige todas as regras do perfil para ficar conferida.</div>';
    const issues = (preview.blockingIssues || []).map((issue) => `<li>${escapeHTML(issue.message)}</li>`).join("");
    const lines = (preview.items || []).map((item) => `<article class="tax-preview-line ${item.ready ? "ready" : "pending"}"><div><strong>Item ${item.line} · NCM ${escapeHTML(item.classification.ncm)} · CFOP ${escapeHTML(item.classification.cfop)}</strong><small>Base: ${accountingCurrency(item.baseValueCents)}</small></div>${item.taxes.map((tax) => `<div class="tax-preview-tax"><span>${escapeHTML(tax.taxCode)} · ${escapeHTML(tax.csosn ? `CSOSN ${tax.csosn}` : `CST ${tax.cst || "—"}`)}</span><strong>${accountingCurrency(tax.amountCents)}</strong><small>base ${accountingCurrency(tax.taxableBaseCents)} · ${(tax.rateBps / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}% · regra #${tax.ruleId} v${tax.ruleVersion}</small></div>`).join("")}</article>`).join("");
    return `<div class="tax-preview-result ${preview.ready ? "ready" : "pending"}"><div class="tax-preview-summary"><strong>${preview.ready ? "Prévia conferida" : "Prévia bloqueada"}</strong><span>${preview.ready ? `Tributos calculados: ${accountingCurrency(preview.totals.taxesCents)}` : "Não use esta prévia para emissão"}</span></div>${issues ? `<ul class="tax-preview-issues">${issues}</ul>` : ""}${lines}<p>${escapeHTML(preview.notice || "")}</p></div>`;
  }

  function taxWorkspaceHTML({ taxSetup, branches, abilities, escapeHTML, currentDate }) {
    const operations = (taxSetup?.operations || []).filter((item) => item.active);
    const profiles = (taxSetup?.profiles || []).filter((item) => item.active);
    const rules = (taxSetup?.rules || []).filter((item) => item.active);
    const operationOptions = operations.map((item) => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)} (${item.direction})</option>`).join("");
    const profileOptions = profiles.map((item) => `<option value="${item.id}">${escapeHTML(item.name)} · ${escapeHTML(regimeLabels[item.tax_regime] || item.tax_regime)} · ${(item.parameters?.requiredTaxCodes || []).join(", ")}</option>`).join("");
    const branchOptions = (branches || []).map((item) => `<option value="${item.id}">${escapeHTML(item.name)}</option>`).join("");
    const ruleList = rules.length ? `<div class="tax-rule-list">${rules.map((rule) => `<div>${taxRuleLabel(rule, escapeHTML)}${abilities.taxManagement ? `<button type="button" class="text-button" data-edit-tax-rule="${rule.id}">Criar revisão</button>` : ""}</div>`).join("")}</div>` : '<p class="fiscal-restricted">Nenhuma regra ativa. A prévia continuará bloqueada até que cada tributo exigido tenha uma regra válida.</p>';
    if (!abilities.taxManagement) {
      return `<section class="tax-workspace panel"><div class="panel-head"><div><h3>Motor tributário</h3><small class="muted">Configuração por empresa, vigência e fonte normativa</small></div><span class="status">${rules.length} regras</span></div><div class="panel-body"><p class="fiscal-restricted">Seu perfil não pode configurar ou calcular regras tributárias.</p></div></section>`;
    }
    return `<section class="tax-workspace panel" aria-label="Configuração e prévia tributária"><div class="panel-head"><div><h3>Motor tributário determinístico</h3><small class="muted">${operations.length} operações · ${profiles.length} perfis vinculados · ${rules.length} regras ativas</small></div><span class="status pendente">Sem emissão</span></div><div class="panel-body"><p class="tax-workspace-note">Cadastre somente regras revisadas pela contabilidade. O sistema não completa alíquota, CST/CSOSN ou fonte normativa por conta própria; conflito ou cobertura incompleta bloqueiam a prévia.</p><div class="tax-config-grid"><details class="tax-config-section"><summary>1. Operação fiscal</summary><form id="taxOperationForm" class="tax-config-form"><label class="field"><span>Código *</span><input name="code" maxlength="40" pattern="[A-Za-z0-9._-]{2,40}" required placeholder="VENDA_INTERNA"></label><label class="field"><span>Nome *</span><input name="name" maxlength="160" minlength="3" required placeholder="Venda interna de mercadoria"></label><label class="field"><span>Direção *</span><select name="direction"><option value="OUT">Saída</option><option value="IN">Entrada</option><option value="BOTH">Entrada e saída</option></select></label><label class="field"><span>Vigente desde</span><input name="validFrom" type="date" value="${currentDate}"></label><label class="field"><span>Vigente até</span><input name="validTo" type="date"></label><button type="submit" class="secondary">Salvar operação</button></form></details><details class="tax-config-section"><summary>2. Perfil fiscal vinculado</summary><form id="taxProfileForm" class="tax-config-form"><label class="field"><span>Nome *</span><input name="name" maxlength="160" minlength="3" required placeholder="Normal GO · mercadorias"></label><label class="field"><span>Regime *</span><select name="taxRegime">${Object.entries(regimeLabels).map(([key, label]) => `<option value="${key}">${label}</option>`).join("")}</select></label><label class="field"><span>Unidade</span><select name="branchId"><option value="">Toda a empresa</option>${branchOptions}</select></label><fieldset class="tax-code-options"><legend>Tributos exigidos *</legend>${["ICMS", "IPI", "PIS", "COFINS"].map((code) => `<label><input name="requiredTaxCodes" type="checkbox" value="${code}" ${code !== "IPI" ? "checked" : ""}> ${code}</label>`).join("")}</fieldset><label class="field"><span>Vigente desde</span><input name="validFrom" type="date" value="${currentDate}"></label><label class="field"><span>Vigente até</span><input name="validTo" type="date"></label><button type="submit" class="secondary">Salvar perfil e vínculo</button></form></details><details class="tax-config-section" open><summary>3. Regra tributária revisada</summary><form id="taxRuleForm" class="tax-config-form"><input name="ruleId" type="hidden"><label class="field"><span>Operação *</span><select name="operationId" required><option value="">Selecione</option>${operationOptions}</select></label><label class="field"><span>Perfil *</span><select name="taxProfileId" required><option value="">Selecione</option>${profileOptions}</select></label><label class="field"><span>Tributo *</span><select name="taxCode"><option>ICMS</option><option>IPI</option><option>PIS</option><option>COFINS</option></select></label><label class="field"><span>Prioridade *</span><input name="priority" type="number" min="1" max="100000" value="100" required><small class="field-help">Menor número prevalece; empate com a mesma especificidade bloqueia.</small></label><div class="tax-condition-fields"><label class="field"><span>UF origem</span><input name="originUf" maxlength="2" placeholder="GO"></label><label class="field"><span>UF destino</span><input name="destinationUf" maxlength="2" placeholder="GO"></label><label class="field"><span>Prefixo NCM</span><input name="ncmPrefix" inputmode="numeric" maxlength="8"></label><label class="field"><span>CEST</span><input name="cest" inputmode="numeric" maxlength="7"></label><label class="field"><span>CFOP</span><input name="cfop" inputmode="numeric" maxlength="4"></label><label class="field"><span>Origem mercadoria</span><input name="merchandiseOrigin" inputmode="numeric" maxlength="1" placeholder="0"></label></div><div class="tax-result-fields"><label class="field"><span>CST</span><input name="cst" inputmode="numeric" maxlength="2" placeholder="00"></label><label class="field"><span>CSOSN</span><input name="csosn" inputmode="numeric" maxlength="3" placeholder="101"></label><label class="field"><span>Alíquota (%) *</span><input name="rate" inputmode="decimal" value="0,00" required></label><label class="field"><span>Redução de base (%) *</span><input name="baseReduction" inputmode="decimal" value="0,00" required></label></div><label class="field full"><span>Fonte normativa HTTPS *</span><input name="referenceUrl" type="url" maxlength="1200" required placeholder="https://..."></label><label class="field full"><span>Observação da revisão</span><textarea name="referenceNote" rows="2" maxlength="1000" placeholder="Convênio, lei, nota técnica ou orientação conferida"></textarea></label><label class="field"><span>Vigente desde</span><input name="validFrom" type="date" value="${currentDate}"></label><label class="field"><span>Vigente até</span><input name="validTo" type="date"></label><div class="tax-form-actions"><button type="button" class="secondary" id="resetTaxRule">Nova regra</button><button type="submit" class="primary">Salvar regra</button></div></form><p id="taxRuleError" class="form-error hidden" role="alert"></p>${ruleList}</details></div><details class="tax-preview-section"><summary>Prévia técnica de um item</summary><p>Use os dados fiscais reais do item. Esta consulta não cria documento fiscal e será bloqueada se faltar regra ou houver conflito.</p><form id="taxPreviewForm" class="tax-preview-form"><label class="field"><span>Operação *</span><select name="operationId" required><option value="">Selecione</option>${operationOptions}</select></label><label class="field"><span>Perfil *</span><select name="taxProfileId" required><option value="">Selecione</option>${profileOptions}</select></label><label class="field"><span>Data *</span><input name="issueDate" type="date" value="${currentDate}" required></label><label class="field"><span>UF origem *</span><input name="originUf" maxlength="2" value="GO" required></label><label class="field"><span>UF destino *</span><input name="destinationUf" maxlength="2" value="GO" required></label><label class="field"><span>NCM *</span><input name="ncm" inputmode="numeric" maxlength="8" required></label><label class="field"><span>CFOP *</span><input name="cfop" inputmode="numeric" maxlength="4" required></label><label class="field"><span>Origem mercadoria *</span><input name="merchandiseOrigin" inputmode="numeric" maxlength="1" value="0" required></label><label class="field"><span>CEST</span><input name="cest" inputmode="numeric" maxlength="7"></label><label class="field"><span>Valor do item *</span><input name="itemValue" inputmode="decimal" required placeholder="0,00"></label><label class="field"><span>Desconto</span><input name="discount" inputmode="decimal" value="0,00"></label><label class="field"><span>Frete</span><input name="freight" inputmode="decimal" value="0,00"></label><label class="field"><span>Seguro</span><input name="insurance" inputmode="decimal" value="0,00"></label><label class="field"><span>Outras despesas</span><input name="otherExpenses" inputmode="decimal" value="0,00"></label><button type="submit" class="primary">Calcular prévia</button></form><p id="taxPreviewError" class="form-error hidden" role="alert"></p><div id="taxPreviewOutput" aria-live="polite">${taxPreviewHTML(null, escapeHTML)}</div></details></div></section>`;
  }

  function fiscalDraftWorkspaceHTML({ taxSetup, drafts, branches, abilities, escapeHTML, currentDate }) {
    if (!abilities.taxManagement) return "";
    const products = taxSetup?.products || [];
    const profiles = (taxSetup?.profiles || []).filter((item) => item.active);
    const sales = taxSetup?.saleSources || [];
    const productOptions = products.map((item) => `<option value="${item.id}">${escapeHTML(item.code ? `${item.code} · ${item.title}` : item.title)}</option>`).join("");
    const profileOptions = profiles.map((item) => `<option value="${item.id}">${escapeHTML(item.name)} · ${escapeHTML(regimeLabels[item.tax_regime] || item.tax_regime)}</option>`).join("");
    const saleOptions = sales.map((item) => `<option value="${item.id}">${escapeHTML(item.title)} · ${escapeHTML(item.status)}</option>`).join("");
    const branchOptions = branches.map((item) => `<option value="${item.id}">${escapeHTML(item.name)}${item.uf ? ` · ${escapeHTML(item.uf)}` : " · UF pendente"}</option>`).join("");
    const classified = products.filter((item) => item.fiscal_profile_id);
    const classifications = classified.length ? `<div class="fiscal-product-list">${classified.map((item) => `<div><strong>${escapeHTML(item.code ? `${item.code} · ${item.title}` : item.title)}</strong><small>NCM ${escapeHTML(item.ncm)} · CFOP ${escapeHTML(item.cfop)} · origem ${escapeHTML(item.merchandise_origin)} · perfil #${item.tax_profile_id} · revisão v${item.version}</small><button type="button" class="text-button" data-edit-product-fiscal-profile="${item.fiscal_profile_id}">Criar revisão</button></div>`).join("")}</div>` : '<p class="fiscal-restricted">Nenhum produto possui classificação fiscal vigente.</p>';
    const draftAction = (item) => {
      if (abilities.issueNfe && ["DRAFT", "REJECTED"].includes(item.status)) return `<button type="button" class="primary" data-issue-fiscal-draft="${item.id}" data-draft-revision="${item.revision}" data-draft-series="${item.series || 1}">${item.status === "REJECTED" ? "Corrigir e retransmitir" : "Emitir em homologação"}</button>`;
      if (abilities.issueNfe && item.status === "PENDING_RECEIPT") return `<button type="button" class="secondary" data-query-fiscal-receipt="${item.id}">Consultar recibo SEFAZ</button>`;
      if (item.status === "AUTHORIZED") return `<span class="fiscal-inline-actions"><a class="secondary" href="/api/fiscal/documents/${item.id}/danfe" target="_blank" rel="noopener">Abrir DANFE</a><a class="secondary" href="/api/fiscal/documents/${item.id}/xml">Baixar XML</a></span>`;
      return "<em>Sem ação disponível</em>";
    };
    const draftItems = (drafts?.items || []).length ? `<div class="fiscal-draft-list">${drafts.items.map((item) => `<div><strong>NF-e #${item.id} · ${escapeHTML(item.source_title)}</strong><small>${escapeHTML(item.branch_name)} · ${escapeHTML(item.operation_code)} · ${escapeHTML(item.profile_name)} · itens ${item.totals?.itemCount || 0} · tributos ${accountingCurrency(item.totals?.taxesCents)} · ${escapeHTML(item.status)}${item.document_number ? ` · ${item.document_number}/${item.series}` : ""}${item.last_sefaz_reason ? ` · ${escapeHTML(item.last_sefaz_reason)}` : ""}</small>${draftAction(item)}</div>`).join("")}</div>` : '<p class="fiscal-restricted">Ainda não há rascunhos fiscais integrados a vendas.</p>';
    const operationOptions = (taxSetup?.operations || []).filter((item) => item.active && item.direction !== "IN").map((item) => `<option value="${item.id}">${escapeHTML(item.code)} · ${escapeHTML(item.name)}</option>`).join("");
    return `<section class="fiscal-draft-workspace panel" aria-label="Classificação fiscal de produtos e rascunhos NF-e"><div class="panel-head"><div><h3>Rascunho fiscal de venda</h3><small class="muted">Fotografia de itens, cliente, unidade e regras vigentes para emissão controlada.</small></div><span class="status pendente">Emissão em homologação</span></div><div class="panel-body"><p class="tax-workspace-note">Classifique cada produto e depois selecione uma venda confirmada. O servidor deriva perfil, NCM, CFOP, origem e UFs dos cadastros e interrompe o fluxo se algum elo estiver ausente.</p><div class="fiscal-draft-grid"><details class="tax-config-section" open><summary>4. Classificação fiscal por produto</summary><form id="productFiscalProfileForm" class="tax-config-form"><input name="profileId" type="hidden"><label class="field full"><span>Produto *</span><select name="productRecordId" required><option value="">Selecione</option>${productOptions}</select></label><label class="field full"><span>Perfil fiscal *</span><select name="taxProfileId" required><option value="">Selecione</option>${profileOptions}</select></label><label class="field"><span>NCM *</span><input name="ncm" inputmode="numeric" maxlength="8" required></label><label class="field"><span>CFOP *</span><input name="cfop" inputmode="numeric" maxlength="4" required></label><label class="field"><span>CEST</span><input name="cest" inputmode="numeric" maxlength="7"></label><label class="field"><span>Origem *</span><input name="merchandiseOrigin" inputmode="numeric" maxlength="1" value="0" required></label><label class="field full"><span>Fonte HTTPS *</span><input name="referenceUrl" type="url" maxlength="1200" required placeholder="https://..."></label><label class="field full"><span>Observação da revisão</span><textarea name="referenceNote" rows="2" maxlength="1000"></textarea></label><label class="field"><span>Vigente desde *</span><input name="validFrom" type="date" value="${currentDate}" required></label><label class="field"><span>Vigente até</span><input name="validTo" type="date"></label><div class="tax-form-actions"><button type="button" class="secondary" id="resetProductFiscalProfile">Nova classificação</button><button type="submit" class="primary">Salvar classificação</button></div></form><p id="productFiscalProfileError" class="form-error hidden" role="alert"></p>${classifications}</details><details class="tax-preview-section" open><summary>5. Gerar rascunho de uma venda</summary><p>Exige venda confirmada, cliente com UF, unidade com UF, somente produtos, classificação vigente e cobertura tributária completa. O rascunho não transmite sozinho; a emissão em homologação exige confirmação explícita.</p><form id="fiscalDraftForm" class="tax-preview-form"><label class="field full"><span>Venda de origem *</span><select name="sourceRecordId" required><option value="">Selecione</option>${saleOptions}</select></label><label class="field"><span>Unidade emissora *</span><select name="branchId" required><option value="">Selecione</option>${branchOptions}</select></label><label class="field"><span>Operação de saída *</span><select name="operationId" required><option value="">Selecione</option>${operationOptions}</select></label><label class="field"><span>Data *</span><input name="issueDate" type="date" value="${currentDate}" required></label><label class="fiscal-checkbox full"><input name="replaceDraft" type="checkbox"><span>Substituir o rascunho anterior desta venda, preservando auditoria</span></label><button type="submit" class="primary" ${sales.length ? "" : "disabled"}>Conferir e gravar rascunho</button></form><p id="fiscalDraftError" class="form-error hidden" role="alert"></p><div id="fiscalDraftOutput" aria-live="polite"><div class="tax-preview-empty">Nenhuma venda foi selecionada para conferência.</div></div></details></div><h4 class="fiscal-draft-history-title">Rascunhos fiscais</h4>${draftItems}</div></section>`;
  }

  fiscal.render = function renderFiscalIntegration({ readiness, branches, abilities, escapeHTML, dateBR, foundation, mappings, categories, taxSetup, drafts }) {
    const homologation = readiness.configurations.find((item) => item.environment === "HOMOLOGATION" && item.enabled);
    const readyPercent = Math.round((readiness.readyCount / Math.max(readiness.totalChecks, 1)) * 100);
    const company = readiness.company || {};
    const branch = readiness.branch || branches[0] || {};
    const today = new Date();
    const currentPeriod = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
    const endpointFields = [
      ["status", "Status do serviço"], ["authorization", "Autorização"],
      ["authorization_return", "Retorno da autorização"], ["protocol", "Consulta protocolo"],
      ["events", "Recepção de eventos"], ["invalidation", "Inutilização"],
    ];
    return `<section class="fiscal-readiness" aria-labelledby="fiscalReadinessTitle"><header><div><p class="eyebrow gold">HOMOLOGAÇÃO CONTROLADA</p><h3 id="fiscalReadinessTitle">Prontidão para integração SEFAZ</h3><p>Consulta e emissão em homologação usam a SEFAZ real. Produção bloqueada até concluir credenciamento, eventos fiscais, regras e validação contábil.</p></div><div class="fiscal-readiness-score"><strong>${readiness.readyCount}/${readiness.totalChecks}</strong><span>${readyPercent}% pronto</span></div></header><div class="fiscal-check-grid">${readiness.checks.map((item) => `<article class="${item.ready ? "ready" : "pending"}"><span>${item.ready ? "✓" : "○"}</span><strong>${escapeHTML(item.label)}</strong></article>`).join("")}</div><p class="fiscal-issue-block">${escapeHTML(readiness.issueBlockReason)}</p></section>
      <div class="fiscal-integration-grid"><section class="panel"><div class="panel-head"><div><h3>SEFAZ/GO · NF-e 4.00</h3><small class="muted">Ambiente sem validade fiscal</small></div><span class="status pendente">Homologação</span></div><div class="panel-body">${statusHTML(homologation, escapeHTML, dateBR, abilities, readiness.canCheckStatus)}</div></section><section class="panel"><div class="panel-head"><div><h3>Certificado digital</h3><small class="muted">Cofre AES-256-GCM · escopo da unidade</small></div></div><div class="panel-body">${certificateHTML(readiness.certificate, escapeHTML, dateBR, abilities)}</div></section><section class="panel fiscal-accounting"><div class="panel-head"><div><h3>Pacote para a contabilidade</h3><small class="muted">CSV, XML e manifesto com SHA-256</small></div></div><div class="panel-body"><p>Gera um ZIP mensal por CNPJ com lançamentos, itens, movimentos de estoque e XML disponíveis. O escritório continua responsável pela escrituração e obrigações acessórias.</p><label class="field"><span>Competência</span><input id="accountingPeriod" type="month" value="${currentPeriod}" max="${currentPeriod}"></label>${abilities.accounting ? '<button type="button" class="primary" id="downloadAccountingPackage">Gerar pacote contábil</button>' : '<p class="fiscal-restricted">Sem permissão para exportar valores fiscais.</p>'}<output id="accountingExportStatus" class="fiscal-export-status" aria-live="polite"></output></div></section></div>
      ${taxWorkspaceHTML({ taxSetup, branches, abilities, escapeHTML, currentDate: today.toISOString().slice(0, 10) })}<dialog id="fiscalConfigurationDialog" class="dialog fiscal-setup-dialog" aria-labelledby="fiscalConfigurationTitle"><form id="fiscalConfigurationForm"><div class="dialog-head"><div><p class="eyebrow gold">UNIDADE EMISSORA</p><h2 id="fiscalConfigurationTitle">Configurar homologação</h2></div><button type="button" class="icon-button" data-fiscal-close aria-label="Fechar">×</button></div><p class="compliance-note compact">Confira estes dados com a contabilidade. O sistema não presume inscrição estadual, regime ou classificação tributária.</p><div class="form-grid"><label class="field full"><span>Unidade *</span><select name="branchId" required>${branches.map((item) => `<option value="${item.id}" ${Number(item.id) === Number(branch.id) ? "selected" : ""}>${escapeHTML(item.name)} · ${escapeHTML(item.cnpj || "sem CNPJ")}</option>`).join("")}</select></label><label class="field full"><span>Razão social *</span><input name="legalName" required maxlength="200" value="${escapeHTML(company.legal_name || company.name || "")}"></label><label class="field"><span>CNPJ *</span><input name="cnpj" required inputmode="numeric" value="${escapeHTML(branch.cnpj || company.cnpj || "")}"></label><label class="field"><span>Inscrição estadual *</span><input name="stateRegistration" required maxlength="30" value="${escapeHTML(branch.state_registration || company.state_registration || "")}"></label><label class="field"><span>Inscrição municipal</span><input name="municipalRegistration" maxlength="30" value="${escapeHTML(branch.municipal_registration || company.municipal_registration || "")}"></label><label class="field"><span>UF *</span><select name="uf" required><option value="GO" ${(branch.uf || company.uf || "GO") === "GO" ? "selected" : ""}>Goiás</option></select></label><label class="field"><span>Código IBGE do município *</span><input name="municipalityCode" required inputmode="numeric" pattern="\\d{7}" maxlength="7" value="${escapeHTML(branch.municipality_code || company.municipality_code || "5208707")}"></label><label class="field"><span>Regime tributário *</span><select name="taxRegime" required>${Object.entries(regimeLabels).map(([value, label]) => `<option value="${value}" ${company.tax_regime === value ? "selected" : ""}>${label}</option>`).join("")}</select></label><label class="field"><span>Ambiente</span><select name="environment"><option value="HOMOLOGATION">Homologação</option></select></label><label class="fiscal-checkbox full"><input name="enabled" type="checkbox" checked><span>Habilitar consulta de homologação</span></label><label class="fiscal-checkbox full"><input name="useOfficialPreset" type="checkbox" checked><span>Usar endpoints oficiais publicados para Goiás</span></label></div><details class="fiscal-advanced"><summary>Endpoints avançados</summary><p>Somente domínios governamentais HTTPS são aceitos. Para Goiás, mantenha o catálogo oficial selecionado.</p>${endpointFields.map(([name, label]) => `<label class="field"><span>${label}</span><input name="endpoint_${name}" type="url" placeholder="https://...gov.br/..."></label>`).join("")}</details><p id="fiscalConfigurationError" class="form-error hidden" role="alert"></p><div class="dialog-actions"><button type="button" class="secondary" data-fiscal-close>Cancelar</button><button type="submit" class="primary">Salvar homologação</button></div></form></dialog>
      <dialog id="fiscalCertificateDialog" class="dialog small fiscal-certificate-dialog" aria-labelledby="fiscalCertificateTitle"><form id="fiscalCertificateForm"><div class="dialog-head"><div><p class="eyebrow gold">COFRE FISCAL</p><h2 id="fiscalCertificateTitle">Importar certificado A1</h2></div><button type="button" class="icon-button" data-fiscal-close aria-label="Fechar">×</button></div><p class="compliance-note compact">Use exclusivamente o arquivo A1 da empresa ativa. A senha abre o PFX nesta operação e não é armazenada.</p><label class="field"><span>Unidade *</span><select name="branchId" required>${branches.map((item) => `<option value="${item.id}" ${Number(item.id) === Number(branch.id) ? "selected" : ""}>${escapeHTML(item.name)}</option>`).join("")}</select></label><label class="field"><span>Arquivo .pfx ou .p12 *</span><input name="certificate" type="file" accept=".pfx,.p12,application/x-pkcs12" required></label><label class="field"><span>Senha do certificado *</span><input name="password" type="password" autocomplete="off" maxlength="512" required></label><p id="fiscalCertificateError" class="form-error hidden" role="alert"></p><div class="dialog-actions"><button type="button" class="secondary" data-fiscal-close>Cancelar</button><button type="submit" class="primary">Criptografar e ativar</button></div></form></dialog>`;
  };

  function closeDialogs() {
    document.querySelectorAll("[data-fiscal-close]").forEach((button) => {
      button.onclick = () => button.closest("dialog")?.close();
    });
  }

  function bytesToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
    }
    return btoa(binary);
  }

  function accountingDecimal(value) {
    const text = String(value || "").trim().replace(/\s/g, "");
    if (!text) return 0;
    const normalized = text.includes(",") ? text.replace(/\./g, "").replace(",", ".") : text;
    const amount = Number(normalized);
    return Number.isFinite(amount) ? amount : 0;
  }

  function accountingReportTable(headers, rows) {
    return rows.length ? `<div class="table-wrap accounting-report-table"><table class="data-table"><thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>` : '<div class="financial-empty">Nenhum lançamento para este recorte.</div>';
  }

  function accountingReportHTML(report, type, escapeHTML, dateBR) {
    const periodState = report.periodStatus?.status === "CLOSED" ? "Competência encerrada" : "Competência aberta";
    const summary = `<div class="accounting-report-summary"><span>${escapeHTML(report.period)} · ${escapeHTML(report.basisLabel)}</span><strong>${report.trialBalance.balanced ? "Partidas conferidas" : "Atenção: partidas divergentes"}</strong><small>${periodState} · Débitos ${accountingCurrency(report.trialBalance.debitCents)} · Créditos ${accountingCurrency(report.trialBalance.creditCents)}</small></div>`;
    if (type === "income") {
      const income = report.incomeStatement;
      const rows = [
        ...income.revenueItems.map((item) => `<tr><td>${escapeHTML(item.code)} · ${escapeHTML(item.name)}</td><td>Receita</td><td>${accountingCurrency(item.movement_balance_cents)}</td></tr>`),
        ...income.expenseItems.map((item) => `<tr><td>${escapeHTML(item.code)} · ${escapeHTML(item.name)}</td><td>Despesa</td><td>${accountingCurrency(item.movement_balance_cents)}</td></tr>`),
      ];
      return `${summary}<div class="accounting-statement-total"><span>Receitas</span><strong>${accountingCurrency(income.revenueCents)}</strong><span>Despesas</span><strong>${accountingCurrency(income.expenseCents)}</strong><span>Resultado do período</span><strong class="${income.netIncomeCents < 0 ? "negative" : ""}">${accountingCurrency(income.netIncomeCents)}</strong></div>${accountingReportTable(["Conta", "Natureza", "Movimento"], rows)}`;
    }
    if (type === "balance") {
      const balance = report.balanceSheet;
      const list = (items) => items.length ? items.map((item) => `<div><span>${escapeHTML(item.code)} · ${escapeHTML(item.name)}</span><strong>${accountingCurrency(item.closing_balance_cents)}</strong></div>`).join("") : '<p>Nenhuma conta com saldo.</p>';
      return `${summary}<div class="accounting-balance-sheet"><section><h4>Ativo</h4>${list(balance.assetItems)}<footer><span>Total do ativo</span><strong>${accountingCurrency(balance.assetCents)}</strong></footer></section><section><h4>Passivo e patrimônio líquido</h4>${list(balance.liabilityItems)}${list(balance.equityItems)}<div><span>Resultado acumulado não encerrado</span><strong>${accountingCurrency(balance.accumulatedResultCents)}</strong></div><footer><span>Total passivo + PL</span><strong>${accountingCurrency(balance.liabilitiesAndEquityCents)}</strong></footer></section></div><p class="accounting-balance-check ${balance.differenceCents ? "error" : ""}">${balance.differenceCents ? `Diferença patrimonial: ${accountingCurrency(balance.differenceCents)}. Revise as partidas cadastradas.` : "Balanço conferido: ativo igual a passivo mais patrimônio líquido."}</p>`;
    }
    if (type === "journal") {
      const rows = report.journal.items.map((item) => `<tr><td>${escapeHTML(dateBR(report.basis === "competence" ? item.competence_date : item.entry_date))}</td><td><strong>#${item.id}</strong> · ${escapeHTML(item.memo)}</td><td>${item.line_count}</td><td>${accountingCurrency(item.debit_cents)}</td><td>${accountingCurrency(item.credit_cents)}</td></tr>`);
      return `${summary}${report.journal.truncated ? '<p class="accounting-report-note">Exibindo os primeiros 500 lançamentos. Refine o período para consultar o restante.</p>' : ""}${accountingReportTable(["Data", "Histórico", "Partidas", "Débitos", "Créditos"], rows)}`;
    }
    if (type === "ledger") {
      const ledger = report.ledger;
      if (!ledger.account) return `${summary}<div class="financial-empty">Selecione uma conta e consulte novamente para abrir o razão.</div>`;
      const account = report.trialBalance.items.find((item) => Number(item.id) === Number(ledger.accountId));
      let balance = Number(account?.opening_balance_cents || 0);
      const debitNormal = ["ASSET", "EXPENSE"].includes(ledger.account.nature);
      const rows = ledger.items.map((item) => {
        balance += debitNormal ? Number(item.debit_cents) - Number(item.credit_cents) : Number(item.credit_cents) - Number(item.debit_cents);
        return `<tr><td>${escapeHTML(dateBR(report.basis === "competence" ? item.competence_date : item.entry_date))}</td><td><strong>#${item.entry_id}</strong> · ${escapeHTML(item.entry_memo)}</td><td>${escapeHTML(item.cost_center_code || "—")}</td><td>${accountingCurrency(item.debit_cents)}</td><td>${accountingCurrency(item.credit_cents)}</td><td>${accountingCurrency(balance)}</td></tr>`;
      });
      return `${summary}<p class="accounting-report-note">Razão de ${escapeHTML(ledger.account.code)} · ${escapeHTML(ledger.account.name)}. Saldo inicial do período: ${accountingCurrency(account?.opening_balance_cents || 0)}.</p>${ledger.truncated ? '<p class="accounting-report-note">Exibindo as primeiras 500 partidas. Refine o período para consultar o restante.</p>' : ""}${accountingReportTable(["Data", "Histórico", "Centro", "Débito", "Crédito", "Saldo"], rows)}`;
    }
    const rows = report.trialBalance.items.map((item) => `<tr class="${item.account_kind === "GROUP" ? "accounting-group-row" : ""}"><td>${escapeHTML(item.code)} · ${escapeHTML(item.name)}</td><td>${accountingCurrency(item.opening_balance_cents)}</td><td>${accountingCurrency(item.debit_cents)}</td><td>${accountingCurrency(item.credit_cents)}</td><td>${accountingCurrency(item.closing_balance_cents)}</td></tr>`);
    return `${summary}${accountingReportTable(["Conta", "Saldo anterior", "Débitos", "Créditos", "Saldo final"], rows)}`;
  }

  fiscal.bind = function bindFiscalIntegration({ readiness, foundation, mappings, categories, taxSetup, drafts, branches, abilities, escapeHTML, dateBR, api, toast, reload }) {
    closeDialogs();
    const currentDate = new Date().toISOString().slice(0, 10);
    const currentPeriod = currentDate.slice(0, 7);
    document.querySelector(".tax-workspace")?.insertAdjacentHTML(
      "afterend", fiscalDraftWorkspaceHTML({ taxSetup, drafts, branches: branches || [], abilities, escapeHTML, currentDate }),
    );
    const draftPanel = document.querySelector(".fiscal-draft-workspace");
    if (draftPanel) {
      draftPanel.querySelector(".panel-head h3").textContent = "NF-e de venda";
      draftPanel.querySelector(".panel-head small").textContent = "Fotografia imutável, assinatura A1 e transmissão controlada.";
      draftPanel.querySelector(".panel-head .status").textContent = "Homologação";
    }
    if (abilities.issueNfe && document.querySelector(".fiscal-draft-workspace")) {
      document.querySelector(".fiscal-draft-workspace").insertAdjacentHTML("afterend", `
        <dialog id="fiscalIssueDialog" class="dialog small" aria-labelledby="fiscalIssueTitle">
          <form id="fiscalIssueForm">
            <div class="dialog-head"><div><p class="eyebrow gold">NF-e 4.00</p><h2 id="fiscalIssueTitle">Emitir em homologação</h2></div><button type="button" class="icon-button" data-issue-close aria-label="Fechar">×</button></div>
            <p class="compliance-note compact">A ação reserva número, assina o XML com o A1, valida o XSD oficial e transmite à SEFAZ. O documento não tem valor fiscal.</p>
            <input name="documentId" type="hidden"><input name="revision" type="hidden">
            <label class="field"><span>Série *</span><input name="series" type="number" min="1" max="999" value="1" required></label>
            <label class="field"><span>Confirmação *</span><input name="confirmation" required autocomplete="off" placeholder="Digite HOMOLOGAR" pattern="HOMOLOGAR"></label>
            <p id="fiscalIssueError" class="form-error hidden" role="alert"></p>
            <div class="dialog-actions"><button type="button" class="secondary" data-issue-close>Cancelar</button><button type="submit" class="primary">Assinar e transmitir</button></div>
          </form>
        </dialog>`);
      const issueDialog = document.querySelector("#fiscalIssueDialog");
      const issueForm = document.querySelector("#fiscalIssueForm");
      document.querySelectorAll("[data-issue-fiscal-draft]").forEach((button) => button.addEventListener("click", () => {
        issueForm.reset();
        issueForm.elements.documentId.value = button.dataset.issueFiscalDraft;
        issueForm.elements.revision.value = button.dataset.draftRevision;
        issueForm.elements.series.value = button.dataset.draftSeries || "1";
        issueDialog.showModal();
        issueForm.elements.series.focus();
      }));
      issueDialog.querySelectorAll("[data-issue-close]").forEach((button) => button.addEventListener("click", () => issueDialog.close()));
      issueForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const error = issueForm.querySelector("#fiscalIssueError");
        const submit = issueForm.querySelector("[type=submit]");
        const values = new FormData(issueForm);
        error.classList.add("hidden"); submit.disabled = true;
        try {
          const result = await api(`/api/fiscal/drafts/${Number(values.get("documentId"))}/issue-homologation`, {
            method: "POST", body: JSON.stringify({ revision: Number(values.get("revision")), series: Number(values.get("series")), confirmation: values.get("confirmation") }),
          });
          issueDialog.close();
          toast(`NF-e ${result.number}/${result.series}: ${result.reason}`);
          await reload();
        } catch (failure) {
          error.textContent = failure.message; error.classList.remove("hidden");
        } finally { submit.disabled = false; }
      });
    }
    document.querySelectorAll("[data-query-fiscal-receipt]").forEach((button) => button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const result = await api(`/api/fiscal/documents/${Number(button.dataset.queryFiscalReceipt)}/receipt`, {
          method: "POST", body: JSON.stringify({}),
        });
        toast(result.status === "PENDING_RECEIPT" ? "O lote ainda está em processamento na SEFAZ." : result.reason);
        await reload();
      } catch (failure) {
        toast(failure.message); button.disabled = false;
      }
    }));
    document.querySelector(".fiscal-integration-grid")?.insertAdjacentHTML(
      "afterend", accountingMappingHTML({ foundation, mappings, categories, abilities, escapeHTML })
        + accountingWorkspaceHTML({ foundation, abilities, escapeHTML, currentPeriod, currentDate }),
    );
    const taxOperationForm = document.querySelector("#taxOperationForm");
    const taxProfileForm = document.querySelector("#taxProfileForm");
    const taxRuleForm = document.querySelector("#taxRuleForm");
    const taxPreviewForm = document.querySelector("#taxPreviewForm");
    const productFiscalProfileForm = document.querySelector("#productFiscalProfileForm");
    const fiscalDraftForm = document.querySelector("#fiscalDraftForm");
    function showTaxError(target, message) {
      const error = document.querySelector(target);
      if (!error) return;
      error.textContent = message || "";
      error.classList.toggle("hidden", !message);
    }
    function taxConditions(form) {
      const values = new FormData(form);
      return Object.fromEntries([
        ["originUf", values.get("originUf")], ["destinationUf", values.get("destinationUf")],
        ["ncmPrefix", values.get("ncmPrefix")], ["cest", values.get("cest")],
        ["cfop", values.get("cfop")], ["merchandiseOrigin", values.get("merchandiseOrigin")],
      ].filter(([, value]) => String(value || "").trim()));
    }
    function resetTaxRuleForm() {
      if (!taxRuleForm) return;
      taxRuleForm.reset();
      taxRuleForm.elements.priority.value = "100";
      taxRuleForm.elements.rate.value = "0,00";
      taxRuleForm.elements.baseReduction.value = "0,00";
      taxRuleForm.elements.ruleId.value = "";
      taxRuleForm.querySelector("[type=submit]").textContent = "Salvar regra";
      showTaxError("#taxRuleError", "");
    }
    function resetProductFiscalProfileForm() {
      if (!productFiscalProfileForm) return;
      productFiscalProfileForm.reset();
      productFiscalProfileForm.elements.profileId.value = "";
      productFiscalProfileForm.elements.merchandiseOrigin.value = "0";
      productFiscalProfileForm.elements.validFrom.value = currentDate;
      productFiscalProfileForm.querySelector("[type=submit]").textContent = "Salvar classificação";
      showTaxError("#productFiscalProfileError", "");
    }
    taxOperationForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const submit = form.querySelector("[type=submit]");
      submit.disabled = true;
      try {
        const values = new FormData(form);
        await api("/api/fiscal/tax-operations", { method: "POST", body: JSON.stringify({
          code: values.get("code"), name: values.get("name"), direction: values.get("direction"),
          validFrom: values.get("validFrom") || null, validTo: values.get("validTo") || null,
        }) });
        toast("Operação tributária salva e auditada.");
        await reload();
      } catch (failure) { toast(failure.message); }
      finally { submit.disabled = false; }
    });
    taxProfileForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const submit = form.querySelector("[type=submit]");
      submit.disabled = true;
      try {
        const values = new FormData(form);
        const requiredTaxCodes = values.getAll("requiredTaxCodes");
        if (!requiredTaxCodes.length) throw new Error("Selecione ao menos um tributo exigido pelo perfil.");
        await api("/api/fiscal/tax-profiles", { method: "POST", body: JSON.stringify({
          name: values.get("name"), taxRegime: values.get("taxRegime"),
          branchId: values.get("branchId") ? Number(values.get("branchId")) : null,
          requiredTaxCodes, validFrom: values.get("validFrom") || null, validTo: values.get("validTo") || null,
        }) });
        toast("Perfil fiscal vinculado e auditado.");
        await reload();
      } catch (failure) { toast(failure.message); }
      finally { submit.disabled = false; }
    });
    document.querySelector("#resetTaxRule")?.addEventListener("click", resetTaxRuleForm);
    document.querySelectorAll("[data-edit-tax-rule]").forEach((button) => button.addEventListener("click", () => {
      const rule = (taxSetup?.rules || []).find((item) => Number(item.id) === Number(button.dataset.editTaxRule));
      if (!rule || !taxRuleForm) return;
      const conditions = rule.conditions || {};
      const result = rule.result || {};
      taxRuleForm.elements.ruleId.value = String(rule.id);
      taxRuleForm.elements.operationId.value = String(rule.fiscal_operation_id);
      taxRuleForm.elements.taxProfileId.value = String(rule.tax_profile_id);
      taxRuleForm.elements.taxCode.value = rule.tax_code;
      taxRuleForm.elements.priority.value = String(rule.priority);
      ["originUf", "destinationUf", "ncmPrefix", "cest", "cfop", "merchandiseOrigin"].forEach((key) => { taxRuleForm.elements[key].value = conditions[key] || ""; });
      taxRuleForm.elements.cst.value = result.cst || "";
      taxRuleForm.elements.csosn.value = result.csosn || "";
      taxRuleForm.elements.rate.value = accountingBasisToPercent(result.rateBps || 0);
      taxRuleForm.elements.baseReduction.value = accountingBasisToPercent(result.baseReductionBps || 0);
      taxRuleForm.elements.referenceUrl.value = rule.reference_url || "";
      taxRuleForm.elements.referenceNote.value = rule.reference_note || "";
      taxRuleForm.elements.validFrom.value = rule.valid_from || "";
      taxRuleForm.elements.validTo.value = rule.valid_to || "";
      taxRuleForm.querySelector("[type=submit]").textContent = `Salvar revisão da regra #${rule.id}`;
      taxRuleForm.closest("details").open = true;
      taxRuleForm.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
      taxRuleForm.elements.operationId.focus();
    }));
    taxRuleForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const submit = form.querySelector("[type=submit]");
      showTaxError("#taxRuleError", "");
      const values = new FormData(form);
      const rateBps = taxBasisPoints(values.get("rate"));
      const baseReductionBps = taxBasisPoints(values.get("baseReduction"));
      if (rateBps == null || baseReductionBps == null) {
        showTaxError("#taxRuleError", "Informe alíquota e redução entre 0,00% e 100,00%.");
        return;
      }
      submit.disabled = true;
      try {
        const ruleId = values.get("ruleId");
        await api(ruleId ? `/api/fiscal/tax-rules/${encodeURIComponent(ruleId)}` : "/api/fiscal/tax-rules", {
          method: ruleId ? "PUT" : "POST", body: JSON.stringify({
            operationId: Number(values.get("operationId")), taxProfileId: Number(values.get("taxProfileId")),
            taxCode: values.get("taxCode"), priority: Number(values.get("priority")), conditions: taxConditions(form),
            result: { cst: values.get("cst"), csosn: values.get("csosn"), rateBps, baseReductionBps },
            referenceUrl: values.get("referenceUrl"), referenceNote: values.get("referenceNote"),
            validFrom: values.get("validFrom") || null, validTo: values.get("validTo") || null,
          }),
        });
        toast(ruleId ? "Revisão da regra salva e auditada." : "Regra tributária salva e auditada.");
        await reload();
      } catch (failure) { showTaxError("#taxRuleError", failure.message); }
      finally { submit.disabled = false; }
    });
    document.querySelector("#resetProductFiscalProfile")?.addEventListener("click", resetProductFiscalProfileForm);
    document.querySelectorAll("[data-edit-product-fiscal-profile]").forEach((button) => button.addEventListener("click", () => {
      const item = (taxSetup?.products || []).find((product) => Number(product.fiscal_profile_id) === Number(button.dataset.editProductFiscalProfile));
      if (!item || !productFiscalProfileForm) return;
      productFiscalProfileForm.elements.profileId.value = String(item.fiscal_profile_id);
      productFiscalProfileForm.elements.productRecordId.value = String(item.id);
      productFiscalProfileForm.elements.taxProfileId.value = String(item.tax_profile_id);
      productFiscalProfileForm.elements.ncm.value = item.ncm || "";
      productFiscalProfileForm.elements.cfop.value = item.cfop || "";
      productFiscalProfileForm.elements.cest.value = item.cest || "";
      productFiscalProfileForm.elements.merchandiseOrigin.value = item.merchandise_origin || "0";
      productFiscalProfileForm.elements.referenceUrl.value = item.reference_url || "";
      productFiscalProfileForm.elements.referenceNote.value = item.reference_note || "";
      productFiscalProfileForm.elements.validFrom.value = item.valid_from || currentDate;
      productFiscalProfileForm.elements.validTo.value = item.valid_to || "";
      productFiscalProfileForm.querySelector("[type=submit]").textContent = `Salvar revisão da classificação #${item.fiscal_profile_id}`;
      productFiscalProfileForm.closest("details").open = true;
      productFiscalProfileForm.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
      productFiscalProfileForm.elements.productRecordId.focus();
    }));
    productFiscalProfileForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const submit = form.querySelector("[type=submit]");
      const values = new FormData(form);
      showTaxError("#productFiscalProfileError", "");
      submit.disabled = true;
      try {
        const profileId = values.get("profileId");
        await api(profileId ? `/api/fiscal/product-profiles/${encodeURIComponent(profileId)}` : "/api/fiscal/product-profiles", {
          method: profileId ? "PUT" : "POST", body: JSON.stringify({
            productRecordId: Number(values.get("productRecordId")), taxProfileId: Number(values.get("taxProfileId")),
            ncm: values.get("ncm"), cfop: values.get("cfop"), cest: values.get("cest"),
            merchandiseOrigin: values.get("merchandiseOrigin"), referenceUrl: values.get("referenceUrl"),
            referenceNote: values.get("referenceNote"), validFrom: values.get("validFrom"), validTo: values.get("validTo") || null,
          }),
        });
        toast(profileId ? "Revisão da classificação fiscal salva e auditada." : "Classificação fiscal salva e auditada.");
        await reload();
      } catch (failure) { showTaxError("#productFiscalProfileError", failure.message); }
      finally { submit.disabled = false; }
    });
    fiscalDraftForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const submit = form.querySelector("[type=submit]");
      const output = document.querySelector("#fiscalDraftOutput");
      const values = new FormData(form);
      showTaxError("#fiscalDraftError", "");
      submit.disabled = true;
      output.innerHTML = '<div class="tax-preview-empty">Conferindo venda, cliente, unidade, classificação e regras sem transmitir documento…</div>';
      try {
        const result = await api("/api/fiscal/drafts", { method: "POST", body: JSON.stringify({
          sourceRecordId: Number(values.get("sourceRecordId")), branchId: Number(values.get("branchId")),
          operationId: Number(values.get("operationId")), issueDate: values.get("issueDate"),
          replaceDraft: values.get("replaceDraft") === "on",
        }) });
        output.innerHTML = `${taxPreviewHTML(result.calculation, escapeHTML)}<p class="fiscal-draft-success">Rascunho #${result.draftId} gravado e pronto para a conferência da emissão em homologação.</p>`;
        toast(`Rascunho fiscal #${result.draftId} conferido e auditado.`);
        await reload();
      } catch (failure) {
        const calculation = failure?.calculation;
        showTaxError("#fiscalDraftError", failure.message);
        output.innerHTML = calculation ? taxPreviewHTML(calculation, escapeHTML) : '<div class="tax-preview-empty">Nenhum rascunho foi gravado.</div>';
      } finally { submit.disabled = false; }
    });
    taxPreviewForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const submit = form.querySelector("[type=submit]");
      const output = document.querySelector("#taxPreviewOutput");
      showTaxError("#taxPreviewError", "");
      submit.disabled = true;
      output.innerHTML = '<div class="tax-preview-empty">Conferindo regras e classificação sem gerar documento…</div>';
      try {
        const values = new FormData(form);
        const result = await api("/api/fiscal/tax-preview", { method: "POST", body: JSON.stringify({
          operationId: Number(values.get("operationId")), taxProfileId: Number(values.get("taxProfileId")),
          issueDate: values.get("issueDate"), originUf: values.get("originUf"), destinationUf: values.get("destinationUf"),
          items: [{ ncm: values.get("ncm"), cfop: values.get("cfop"), cest: values.get("cest"),
            merchandiseOrigin: values.get("merchandiseOrigin"), itemValue: values.get("itemValue"),
            discount: values.get("discount"), freight: values.get("freight"), insurance: values.get("insurance"),
            otherExpenses: values.get("otherExpenses") }],
        }) });
        output.innerHTML = taxPreviewHTML(result, escapeHTML);
      } catch (failure) {
        showTaxError("#taxPreviewError", failure.message);
        output.innerHTML = taxPreviewHTML(null, escapeHTML);
      } finally { submit.disabled = false; }
    });
    if (abilities.accountingPeriodManagement) {
      document.querySelector(".accounting-reports-panel .panel-body")?.insertAdjacentHTML("beforeend", `
        <div class="accounting-period-actions"><span>Encerrar bloqueia novos lançamentos na competência selecionada; reabrir exige justificativa e deixa auditoria.</span><div><button type="button" class="secondary" data-accounting-period-action="close">Encerrar competência</button><button type="button" class="secondary" data-accounting-period-action="reopen">Reabrir competência</button></div></div>
        <dialog id="accountingPeriodDialog" class="dialog small form-drawer" aria-labelledby="accountingPeriodDialogTitle"><form id="accountingPeriodForm" method="dialog"><div class="dialog-head"><div><p class="eyebrow gold">GOVERNANÇA CONTÁBIL</p><h2 id="accountingPeriodDialogTitle">Encerrar competência</h2><small id="accountingPeriodDialogHint">A ação será registrada na auditoria.</small></div><button type="button" class="icon-button" data-close aria-label="Fechar">×</button></div><input name="action" type="hidden"><label class="field"><span>Competência</span><input name="period" type="month" readonly></label><label class="field"><span>Justificativa *</span><textarea name="reason" rows="4" minlength="10" maxlength="1000" required placeholder="Descreva a conferência ou o motivo da reabertura"></textarea></label><p id="accountingPeriodError" class="form-error hidden" role="alert"></p><div class="dialog-actions"><button type="button" class="secondary" data-close>Cancelar</button><button type="submit" class="primary">Confirmar</button></div></form></dialog>`,
      );
    }
    const configurationDialog = document.querySelector("#fiscalConfigurationDialog");
    const certificateDialog = document.querySelector("#fiscalCertificateDialog");
    document.querySelector("#openFiscalConfiguration")?.addEventListener("click", () => configurationDialog.showModal());
    document.querySelector("#openFiscalCertificate")?.addEventListener("click", () => certificateDialog.showModal());

    const configurationForm = document.querySelector("#fiscalConfigurationForm");
    const issuerAddress = readiness.branch?.address || readiness.company?.address || {};
    const regimeField = configurationForm?.elements.taxRegime?.closest("label");
    regimeField?.insertAdjacentHTML("beforebegin", `
      <label class="field full"><span>Logradouro fiscal *</span><input name="street" required maxlength="60" value="${escapeHTML(issuerAddress.street || "")}"></label>
      <label class="field"><span>Número *</span><input name="addressNumber" required maxlength="60" value="${escapeHTML(issuerAddress.number || "")}"></label>
      <label class="field"><span>Complemento</span><input name="addressComplement" maxlength="60" value="${escapeHTML(issuerAddress.complement || "")}"></label>
      <label class="field"><span>Bairro *</span><input name="district" required maxlength="60" value="${escapeHTML(issuerAddress.district || "")}"></label>
      <label class="field"><span>Município *</span><input name="municipality" required maxlength="60" value="${escapeHTML(issuerAddress.municipality || "")}"></label>
      <label class="field"><span>CEP *</span><input name="postalCode" required inputmode="numeric" pattern="\\d{8}" maxlength="8" value="${escapeHTML(issuerAddress.postal_code || "")}"></label>
      <label class="field"><span>Telefone</span><input name="phone" type="tel" maxlength="14" value="${escapeHTML(issuerAddress.phone || "")}"></label>`);
    configurationForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const error = document.querySelector("#fiscalConfigurationError");
      error.classList.add("hidden");
      const form = new FormData(configurationForm);
      const endpoints = Object.fromEntries(["status", "authorization", "authorization_return", "protocol", "events", "invalidation"].map((key) => [key, form.get(`endpoint_${key}`)]));
      const submit = configurationForm.querySelector("[type=submit]");
      submit.disabled = true;
      try {
        await api("/api/fiscal/configuration", { method: "PUT", body: JSON.stringify({
          branchId: Number(form.get("branchId")), legalName: form.get("legalName"),
          cnpj: form.get("cnpj"), stateRegistration: form.get("stateRegistration"),
          municipalRegistration: form.get("municipalRegistration"), uf: form.get("uf"),
          municipalityCode: form.get("municipalityCode"), taxRegime: form.get("taxRegime"),
          street: form.get("street"), addressNumber: form.get("addressNumber"),
          addressComplement: form.get("addressComplement"), district: form.get("district"),
          municipality: form.get("municipality"), postalCode: form.get("postalCode"), phone: form.get("phone"),
          environment: form.get("environment"), enabled: form.get("enabled") === "on",
          useOfficialPreset: form.get("useOfficialPreset") === "on", endpoints,
        }) });
        configurationDialog.close();
        toast("Homologação fiscal configurada e auditada.");
        await reload();
      } catch (failure) {
        error.textContent = failure.message;
        error.classList.remove("hidden");
      } finally { submit.disabled = false; }
    });

    const mappingForm = document.querySelector("#accountingMappingForm");
    const mappingCenters = (foundation?.costCenters || []).filter((item) => item.active);
    const allocationSide = document.querySelector("#accountingAllocationSide");
    const allocationLines = document.querySelector("#accountingAllocationLines");
    const allocationActions = document.querySelector("#accountingAllocationActions");
    const defaultCostCenter = mappingForm?.elements.costCenterId;
    function allocationBasisPoints(value) {
      const normalized = String(value || "").trim().replace(/\s/g, "").replace(".", ",");
      if (!/^\d{1,3}(?:,\d{1,2})?$/.test(normalized)) return null;
      const [whole, decimals = ""] = normalized.split(",");
      return Number(whole) * 100 + Number(decimals.padEnd(2, "0"));
    }
    function updateAllocationLines() {
      if (!allocationLines) return;
      const rows = Array.from(allocationLines.querySelectorAll("[data-accounting-allocation]"));
      const total = rows.reduce((sum, row, index) => {
        row.querySelector("strong").textContent = String(index + 1);
        const remove = row.querySelector("[data-remove-accounting-allocation]");
        remove.setAttribute("aria-label", `Remover centro ${index + 1}`);
        remove.disabled = rows.length <= 2;
        return sum + (allocationBasisPoints(row.querySelector('[name="allocationPercent"]').value) || 0);
      }, 0);
      const output = document.querySelector("#accountingAllocationTotal");
      if (output) output.textContent = `Total: ${accountingBasisToPercent(total)}%${total === 10000 ? " · conferido" : " · deve totalizar 100,00%"}`;
    }
    function bindAllocationLine(row) {
      row.querySelectorAll("input,select").forEach((field) => field.addEventListener("input", updateAllocationLines));
      row.querySelector("[data-remove-accounting-allocation]")?.addEventListener("click", () => {
        if (allocationLines.children.length > 2) { row.remove(); updateAllocationLines(); }
      });
    }
    function appendAllocationLine(allocation = {}) {
      if (!allocationLines || allocationLines.children.length >= 20) return toast("O limite é de 20 centros no rateio.");
      allocationLines.insertAdjacentHTML("beforeend", accountingAllocationLineHTML(mappingCenters, escapeHTML, allocationLines.children.length, allocation));
      bindAllocationLine(allocationLines.lastElementChild);
    }
    function setAllocationLines(allocations = []) {
      if (!allocationLines) return;
      allocationLines.replaceChildren();
      (allocations.length ? allocations : [{}, {}]).forEach(appendAllocationLine);
      updateAllocationLines();
    }
    function syncAllocationEditor() {
      if (!allocationLines || !allocationSide) return;
      const enabled = allocationSide.value !== "NONE";
      allocationLines.hidden = !enabled;
      allocationActions.hidden = !enabled;
      if (defaultCostCenter) defaultCostCenter.disabled = enabled;
      allocationLines.querySelectorAll("input,select,button").forEach((field) => { field.disabled = !enabled; });
      if (enabled && !allocationLines.children.length) setAllocationLines();
      updateAllocationLines();
    }
    function resetMappingForm() {
      if (!mappingForm) return;
      mappingForm.reset();
      delete mappingForm.dataset.mappingId;
      mappingForm.querySelector("[type=submit]").textContent = "Salvar mapeamento";
      setAllocationLines();
      syncAllocationEditor();
    }
    allocationSide?.addEventListener("change", syncAllocationEditor);
    document.querySelector("#addAccountingAllocation")?.addEventListener("click", () => appendAllocationLine());
    document.querySelector("#resetAccountingMapping")?.addEventListener("click", resetMappingForm);
    document.querySelectorAll("[data-edit-accounting-mapping]").forEach((button) => button.addEventListener("click", () => {
      const mapping = (mappings || []).find((item) => Number(item.id) === Number(button.dataset.editAccountingMapping));
      if (!mapping || !mappingForm) return;
      mappingForm.elements.financialModule.value = mapping.financial_module;
      mappingForm.elements.categoryId.value = String(mapping.financial_category_id);
      mappingForm.elements.debitAccountId.value = String(mapping.debit_account_id);
      mappingForm.elements.creditAccountId.value = String(mapping.credit_account_id);
      ["DISCOUNT", "INTEREST", "FEE"].forEach((type) => {
        const rule = (mapping.adjustmentRules || []).find((item) => item.adjustment_type === type);
        const key = type.toLowerCase();
        mappingForm.elements[`${key}AccountId`].value = rule ? String(rule.account_id) : "";
        mappingForm.elements[`${key}CostCenterId`].value = rule?.cost_center_id ? String(rule.cost_center_id) : "";
      });
      const allocations = mapping.allocations || [];
      allocationSide.value = allocations[0]?.allocation_side || "NONE";
      defaultCostCenter.value = String(mapping.cost_center_id || "");
      setAllocationLines(allocations);
      mappingForm.dataset.mappingId = String(mapping.id);
      mappingForm.querySelector("[type=submit]").textContent = "Atualizar mapeamento";
      syncAllocationEditor();
      mappingForm.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
      mappingForm.elements.financialModule.focus();
    }));
    setAllocationLines();
    syncAllocationEditor();
    mappingForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const error = document.querySelector("#accountingMappingError");
      const submit = form.querySelector("[type=submit]");
      error.classList.add("hidden"); submit.disabled = true;
      try {
        const values = new FormData(form);
        const side = values.get("allocationSide");
        const allocations = side === "NONE" ? [] : Array.from(allocationLines.querySelectorAll("[data-accounting-allocation]")).map((row) => ({
          costCenterId: Number(row.querySelector('[name="allocationCenterId"]').value),
          basisPoints: allocationBasisPoints(row.querySelector('[name="allocationPercent"]').value),
        }));
        if (side !== "NONE") {
          if (allocations.length < 2 || allocations.some((row) => !row.costCenterId || !Number.isInteger(row.basisPoints) || row.basisPoints < 1)
              || new Set(allocations.map((row) => row.costCenterId)).size !== allocations.length
              || allocations.reduce((sum, row) => sum + row.basisPoints, 0) !== 10000) {
            throw new Error("Informe centros distintos e percentuais positivos que totalizem exatamente 100,00%.");
          }
        }
        const adjustmentRules = ["DISCOUNT", "INTEREST", "FEE"].flatMap((type) => {
          const key = type.toLowerCase();
          const accountId = values.get(`${key}AccountId`);
          const costCenterId = values.get(`${key}CostCenterId`);
          if (!accountId && !costCenterId) return [];
          if (!accountId) {
            throw new Error(`Escolha a conta própria para ${({ DISCOUNT: "desconto", INTEREST: "juros ou multa", FEE: "tarifa" })[type]} ou retire o centro de custo.`);
          }
          return [{ type, accountId: Number(accountId), costCenterId: costCenterId ? Number(costCenterId) : null }];
        });
        const mappingId = form.dataset.mappingId;
        await api(mappingId ? `/api/accounting/financial-mappings/${mappingId}` : "/api/accounting/financial-mappings", { method: mappingId ? "PUT" : "POST", body: JSON.stringify({
          financialModule: values.get("financialModule"), categoryId: Number(values.get("categoryId")),
          debitAccountId: Number(values.get("debitAccountId")), creditAccountId: Number(values.get("creditAccountId")),
          costCenterId: side === "NONE" && values.get("costCenterId") ? Number(values.get("costCenterId")) : null,
          allocationSide: side, allocations, adjustmentRules,
        }) });
        toast(mappingId ? "Mapeamento contábil, ajustes e rateio atualizados e auditados." : "Mapeamento contábil salvo e auditado.");
        await reload();
      } catch (failure) { error.textContent = failure.message; error.classList.remove("hidden"); }
      finally { submit.disabled = false; }
    });

    const journalForm = document.querySelector("#accountingJournalForm");
    const journalLines = document.querySelector("#accountingEntryLines");
    const journalAccounts = (foundation?.accounts || []).filter((item) => item.active && item.account_kind === "ANALYTICAL");
    const journalCenters = (foundation?.costCenters || []).filter((item) => item.active);
    function updateJournalTotals() {
      if (!journalLines) return;
      const rows = Array.from(journalLines.querySelectorAll("[data-accounting-line]"));
      let debit = 0; let credit = 0;
      rows.forEach((row, index) => {
        row.querySelector("strong").textContent = String(index + 1);
        const remove = row.querySelector("[data-remove-accounting-line]");
        remove.setAttribute("aria-label", `Remover partida ${index + 1}`);
        remove.disabled = rows.length <= 2;
        debit += accountingDecimal(row.querySelector('[name="debit"]').value);
        credit += accountingDecimal(row.querySelector('[name="credit"]').value);
      });
      const totals = document.querySelector("#accountingJournalTotals");
      if (totals) totals.textContent = `Débitos: ${accountingCurrency(Math.round(debit * 100))} · Créditos: ${accountingCurrency(Math.round(credit * 100))}${Math.abs(debit - credit) < 0.005 ? " · conferido" : " · divergente"}`;
    }
    function bindJournalLine(row) {
      row.querySelectorAll("input,select").forEach((field) => field.addEventListener("input", updateJournalTotals));
      row.querySelector("[data-remove-accounting-line]")?.addEventListener("click", () => {
        if (journalLines.children.length > 2) { row.remove(); updateJournalTotals(); }
      });
    }
    journalLines?.querySelectorAll("[data-accounting-line]").forEach(bindJournalLine);
    updateJournalTotals();
    function syncJournalMode() {
      if (!journalForm) return;
      const opening = journalForm.elements.entryMode.value === "OPENING_BALANCE";
      const entryDate = journalForm.elements.entryDate;
      const competenceDate = journalForm.elements.competenceDate;
      if (opening && entryDate.value) {
        entryDate.value = `${entryDate.value.slice(0, 7)}-01`;
        competenceDate.value = entryDate.value;
      }
      competenceDate.readOnly = opening;
      competenceDate.setAttribute("aria-readonly", String(opening));
    }
    journalForm?.elements.entryMode?.addEventListener("change", syncJournalMode);
    journalForm?.elements.entryDate?.addEventListener("change", syncJournalMode);
    document.querySelector("#addAccountingLine")?.addEventListener("click", () => {
      if (!journalLines || journalLines.children.length >= 200) return toast("O limite é de 200 partidas por lançamento.");
      journalLines.insertAdjacentHTML("beforeend", accountingLineHTML(journalAccounts, journalCenters, escapeHTML, journalLines.children.length));
      bindJournalLine(journalLines.lastElementChild);
      updateJournalTotals();
    });
    journalForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const error = document.querySelector("#accountingJournalError");
      const submit = journalForm.querySelector("[type=submit]");
      error.classList.add("hidden"); submit.disabled = true;
      const lines = Array.from(journalLines.querySelectorAll("[data-accounting-line]")).map((row) => ({
        accountId: Number(row.querySelector('[name="accountId"]').value),
        costCenterId: row.querySelector('[name="costCenterId"]').value || null,
        debit: row.querySelector('[name="debit"]').value,
        credit: row.querySelector('[name="credit"]').value,
      }));
      try {
        const opening = journalForm.elements.entryMode.value === "OPENING_BALANCE";
        await api(opening ? "/api/accounting/opening-balances" : "/api/accounting/journal-entries", {
          method: "POST", body: JSON.stringify(opening ? {
            date: journalForm.elements.entryDate.value, memo: journalForm.elements.memo.value, lines,
          } : {
            entryDate: journalForm.elements.entryDate.value,
            competenceDate: journalForm.elements.competenceDate.value,
            memo: journalForm.elements.memo.value, lines,
          }),
        });
        toast(opening ? "Saldo inicial registrado e auditado." : "Lançamento contábil registrado e auditado.");
        await reload();
      } catch (failure) {
        error.textContent = failure.message;
        error.classList.remove("hidden");
      } finally { submit.disabled = false; }
    });

    let accountingReport = null;
    let accountingReportType = "trial";
    const reportOutput = document.querySelector("#accountingReportOutput");
    function renderAccountingReport() {
      if (!reportOutput || !accountingReport) return;
      reportOutput.innerHTML = accountingReportHTML(accountingReport, accountingReportType, escapeHTML, dateBR);
    }
    document.querySelectorAll("[data-accounting-report]").forEach((button) => {
      button.addEventListener("click", () => {
        accountingReportType = button.dataset.accountingReport;
        document.querySelectorAll("[data-accounting-report]").forEach((item) => {
          const selected = item === button;
          item.classList.toggle("active", selected);
          item.setAttribute("aria-selected", String(selected));
        });
        renderAccountingReport();
      });
    });
    document.querySelector("#loadAccountingReports")?.addEventListener("click", async (event) => {
      const period = document.querySelector("#accountingReportPeriod")?.value;
      const basis = document.querySelector("#accountingReportBasis")?.value;
      const accountId = document.querySelector("#accountingLedgerAccount")?.value;
      if (!period) return;
      const button = event.currentTarget;
      button.disabled = true;
      reportOutput.innerHTML = '<div class="financial-empty">Consolidando somente partidas registradas…</div>';
      try {
        const search = new URLSearchParams({ period, basis });
        if (accountId) search.set("accountId", accountId);
        accountingReport = await api(`/api/accounting/reports?${search.toString()}`);
        renderAccountingReport();
      } catch (failure) {
        reportOutput.innerHTML = `<div class="financial-empty">${escapeHTML(failure.message)}</div>`;
      } finally { button.disabled = false; }
    });
    const periodDialog = document.querySelector("#accountingPeriodDialog");
    const periodForm = document.querySelector("#accountingPeriodForm");
    document.querySelectorAll("[data-accounting-period-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const period = document.querySelector("#accountingReportPeriod")?.value;
        if (!period || !periodDialog || !periodForm) return;
        const action = button.dataset.accountingPeriodAction;
        periodForm.reset();
        periodForm.elements.action.value = action;
        periodForm.elements.period.value = period;
        document.querySelector("#accountingPeriodDialogTitle").textContent = action === "close" ? "Encerrar competência" : "Reabrir competência";
        document.querySelector("#accountingPeriodDialogHint").textContent = action === "close"
          ? "Novos lançamentos desta competência serão bloqueados após a confirmação."
          : "A reabertura ficará registrada na auditoria antes de permitir novos lançamentos.";
        document.querySelector("#accountingPeriodError").classList.add("hidden");
        periodDialog.showModal();
        periodForm.elements.reason.focus();
      });
    });
    periodDialog?.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => periodDialog.close()));
    periodForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const action = periodForm.elements.action.value;
      const error = document.querySelector("#accountingPeriodError");
      const submit = periodForm.querySelector("[type=submit]");
      error.classList.add("hidden"); submit.disabled = true;
      try {
        await api(`/api/accounting/periods/${encodeURIComponent(periodForm.elements.period.value)}/${action}`, {
          method: "POST", body: JSON.stringify({ reason: periodForm.elements.reason.value }),
        });
        periodDialog.close();
        toast(action === "close" ? "Competência encerrada e auditada." : "Competência reaberta e auditada.");
        document.querySelector("#loadAccountingReports")?.click();
      } catch (failure) {
        error.textContent = failure.message;
        error.classList.remove("hidden");
      } finally { submit.disabled = false; }
    });

    const certificateForm = document.querySelector("#fiscalCertificateForm");
    certificateForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const error = document.querySelector("#fiscalCertificateError");
      error.classList.add("hidden");
      const form = new FormData(certificateForm);
      const file = form.get("certificate");
      if (!(file instanceof File) || !file.size || file.size > 2 * 1024 * 1024) {
        error.textContent = "Selecione um certificado A1 de até 2 MB.";
        error.classList.remove("hidden");
        return;
      }
      const submit = certificateForm.querySelector("[type=submit]");
      submit.disabled = true;
      try {
        await api("/api/fiscal/certificate", { method: "POST", body: JSON.stringify({
          branchId: Number(form.get("branchId")), password: form.get("password"),
          contentBase64: bytesToBase64(await file.arrayBuffer()),
        }) });
        certificateForm.reset();
        certificateDialog.close();
        toast("Certificado A1 criptografado e ativado.");
        await reload();
      } catch (failure) {
        error.textContent = failure.message;
        error.classList.remove("hidden");
      } finally { submit.disabled = false; }
    });

    document.querySelector("#checkSefazStatus")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = "Consultando…";
      try {
        const homologation = readiness.configurations.find((item) => item.environment === "HOMOLOGATION" && item.enabled);
        const result = await api("/api/fiscal/sefaz/status", { method: "POST", body: JSON.stringify({
          branchId: homologation?.branch_id || readiness.certificate?.branchId || readiness.branch.id,
          environment: "HOMOLOGATION",
        }) });
        toast(`${result.reason} · código ${result.statusCode}`);
        await reload();
      } catch (failure) { toast(failure.message); }
      finally { button.disabled = false; button.textContent = "Consultar SEFAZ agora"; }
    });

    document.querySelector("#removeFiscalCertificate")?.addEventListener("click", async () => {
      if (!global.confirm("Remover o certificado A1 da empresa ativa? A operação será auditada.")) return;
      try {
        await api(`/api/fiscal/certificate/${readiness.certificate.id}`, { method: "DELETE" });
        toast("Certificado A1 removido do cofre fiscal.");
        await reload();
      } catch (failure) { toast(failure.message); }
    });

    document.querySelector("#downloadAccountingPackage")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const output = document.querySelector("#accountingExportStatus");
      const period = document.querySelector("#accountingPeriod")?.value;
      if (!period) return;
      button.disabled = true;
      output.textContent = "Consolidando registros e XML…";
      try {
        const response = await fetch(`/api/accounting/export?period=${encodeURIComponent(period)}`, { credentials: "same-origin" });
        if (!response.ok) {
          const failure = await response.json().catch(() => ({}));
          throw new Error(failure.message || "Não foi possível gerar o pacote contábil");
        }
        const blob = await response.blob();
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `seccol-contabilidade-${period}.zip`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        output.textContent = `Pacote ${period} gerado e registrado na auditoria.`;
      } catch (failure) { output.textContent = failure.message; }
      finally { button.disabled = false; }
    });
  };
})(window);
