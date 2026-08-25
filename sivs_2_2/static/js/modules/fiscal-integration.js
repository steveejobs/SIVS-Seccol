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
    return `<div class="fiscal-status-line"><span class="fiscal-signal ${operational ? "online" : ""}"></span><div><strong>${operational ? "Serviço em operação" : "Aguardando consulta real"}</strong><p>${escapeHTML(configuration.last_status_reason || "NF-e 4.00 · homologação")}</p><small>${configuration.last_checked_at ? `Consultado em ${escapeHTML(dateBR(configuration.last_checked_at, true))}` : "Ainda não consultado com o A1"}</small></div></div><div class="fiscal-inline-actions">${abilities.status ? `<button type="button" class="primary" id="checkSefazStatus" ${canCheckStatus ? "" : "disabled"}>Consultar SEFAZ agora</button>` : ""}${abilities.configuration ? '<button type="button" class="secondary" id="openFiscalConfiguration">Editar configuração</button>' : ""}</div>`;
  }

  fiscal.render = function renderFiscalIntegration({ readiness, branches, abilities, escapeHTML, dateBR }) {
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
    return `<section class="fiscal-readiness" aria-labelledby="fiscalReadinessTitle"><header><div><p class="eyebrow gold">HOMOLOGAÇÃO CONTROLADA</p><h3 id="fiscalReadinessTitle">Prontidão para integração SEFAZ</h3><p>A conexão de status é real. Emissão e produção permanecem bloqueadas enquanto regras e schemas não estiverem homologados.</p></div><div class="fiscal-readiness-score"><strong>${readiness.readyCount}/${readiness.totalChecks}</strong><span>${readyPercent}% pronto</span></div></header><div class="fiscal-check-grid">${readiness.checks.map((item) => `<article class="${item.ready ? "ready" : "pending"}"><span>${item.ready ? "✓" : "○"}</span><strong>${escapeHTML(item.label)}</strong></article>`).join("")}</div><p class="fiscal-issue-block">${escapeHTML(readiness.issueBlockReason)}</p></section>
      <div class="fiscal-integration-grid"><section class="panel"><div class="panel-head"><div><h3>SEFAZ/GO · NF-e 4.00</h3><small class="muted">Ambiente sem validade fiscal</small></div><span class="status pendente">Homologação</span></div><div class="panel-body">${statusHTML(homologation, escapeHTML, dateBR, abilities, readiness.canCheckStatus)}</div></section><section class="panel"><div class="panel-head"><div><h3>Certificado digital</h3><small class="muted">Cofre AES-256-GCM · escopo da unidade</small></div></div><div class="panel-body">${certificateHTML(readiness.certificate, escapeHTML, dateBR, abilities)}</div></section><section class="panel fiscal-accounting"><div class="panel-head"><div><h3>Pacote para a contabilidade</h3><small class="muted">CSV, XML e manifesto com SHA-256</small></div></div><div class="panel-body"><p>Gera um ZIP mensal por CNPJ com lançamentos, itens, movimentos de estoque e XML disponíveis. O escritório continua responsável pela escrituração e obrigações acessórias.</p><label class="field"><span>Competência</span><input id="accountingPeriod" type="month" value="${currentPeriod}" max="${currentPeriod}"></label>${abilities.accounting ? '<button type="button" class="primary" id="downloadAccountingPackage">Gerar pacote contábil</button>' : '<p class="fiscal-restricted">Sem permissão para exportar valores fiscais.</p>'}<output id="accountingExportStatus" class="fiscal-export-status" aria-live="polite"></output></div></section></div>
      <dialog id="fiscalConfigurationDialog" class="dialog fiscal-setup-dialog" aria-labelledby="fiscalConfigurationTitle"><form id="fiscalConfigurationForm"><div class="dialog-head"><div><p class="eyebrow gold">UNIDADE EMISSORA</p><h2 id="fiscalConfigurationTitle">Configurar homologação</h2></div><button type="button" class="icon-button" data-fiscal-close aria-label="Fechar">×</button></div><p class="compliance-note compact">Confira estes dados com a contabilidade. O sistema não presume inscrição estadual, regime ou classificação tributária.</p><div class="form-grid"><label class="field full"><span>Unidade *</span><select name="branchId" required>${branches.map((item) => `<option value="${item.id}" ${Number(item.id) === Number(branch.id) ? "selected" : ""}>${escapeHTML(item.name)} · ${escapeHTML(item.cnpj || "sem CNPJ")}</option>`).join("")}</select></label><label class="field full"><span>Razão social *</span><input name="legalName" required maxlength="200" value="${escapeHTML(company.legal_name || company.name || "")}"></label><label class="field"><span>CNPJ *</span><input name="cnpj" required inputmode="numeric" value="${escapeHTML(branch.cnpj || company.cnpj || "")}"></label><label class="field"><span>Inscrição estadual *</span><input name="stateRegistration" required maxlength="30" value="${escapeHTML(branch.state_registration || company.state_registration || "")}"></label><label class="field"><span>Inscrição municipal</span><input name="municipalRegistration" maxlength="30" value="${escapeHTML(branch.municipal_registration || company.municipal_registration || "")}"></label><label class="field"><span>UF *</span><select name="uf" required><option value="GO" ${(branch.uf || company.uf || "GO") === "GO" ? "selected" : ""}>Goiás</option></select></label><label class="field"><span>Código IBGE do município *</span><input name="municipalityCode" required inputmode="numeric" pattern="\\d{7}" maxlength="7" value="${escapeHTML(branch.municipality_code || company.municipality_code || "5208707")}"></label><label class="field"><span>Regime tributário *</span><select name="taxRegime" required>${Object.entries(regimeLabels).map(([value, label]) => `<option value="${value}" ${company.tax_regime === value ? "selected" : ""}>${label}</option>`).join("")}</select></label><label class="field"><span>Ambiente</span><select name="environment"><option value="HOMOLOGATION">Homologação</option></select></label><label class="fiscal-checkbox full"><input name="enabled" type="checkbox" checked><span>Habilitar consulta de homologação</span></label><label class="fiscal-checkbox full"><input name="useOfficialPreset" type="checkbox" checked><span>Usar endpoints oficiais publicados para Goiás</span></label></div><details class="fiscal-advanced"><summary>Endpoints avançados</summary><p>Somente domínios governamentais HTTPS são aceitos. Para Goiás, mantenha o catálogo oficial selecionado.</p>${endpointFields.map(([name, label]) => `<label class="field"><span>${label}</span><input name="endpoint_${name}" type="url" placeholder="https://...gov.br/..."></label>`).join("")}</details><p id="fiscalConfigurationError" class="form-error hidden" role="alert"></p><div class="dialog-actions"><button type="button" class="secondary" data-fiscal-close>Cancelar</button><button type="submit" class="primary">Salvar homologação</button></div></form></dialog>
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

  fiscal.bind = function bindFiscalIntegration({ readiness, api, toast, reload }) {
    closeDialogs();
    const configurationDialog = document.querySelector("#fiscalConfigurationDialog");
    const certificateDialog = document.querySelector("#fiscalCertificateDialog");
    document.querySelector("#openFiscalConfiguration")?.addEventListener("click", () => configurationDialog.showModal());
    document.querySelector("#openFiscalCertificate")?.addEventListener("click", () => certificateDialog.showModal());

    const configurationForm = document.querySelector("#fiscalConfigurationForm");
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
