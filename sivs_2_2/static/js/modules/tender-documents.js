(function tenderDocumentsModule() {
  "use strict";

  const stageLabels = {
    INITIAL_PROPOSAL: "Proposta inicial",
    ADJUSTED_PROPOSAL: "Proposta ajustada",
    QUALIFICATION: "Habilitação",
    CONTRACTING: "Contratação",
  };
  const validityLabels = {
    VALID: "Válido",
    EXPIRING: "Vence em até 30 dias",
    EXPIRED: "Vencido",
    NO_EXPIRY: "Sem validade informada",
    ARCHIVED: "Arquivado",
  };
  const scopeLabels = {
    ALL: "Todos os objetos",
    GOODS: "Bens",
    SERVICES: "Serviços",
    ENGINEERING: "Engenharia",
  };
  let activeDetailContext = null;

  function escapeText(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
  }

  function options(values, selected) {
    return values.map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`).join("");
  }

  function settingsHTML(data, helpers) {
    const escape = helpers.escapeHTML;
    const readiness = data?.readiness || {};
    const items = data?.items || [];
    const catalog = data?.catalog || [];
    const rows = items.map((item) => `<tr>
      <td><strong>${escape(item.title)}</strong><small>${escape(item.filename)} · ${scopeLabels[item.scope] || item.scope}</small></td>
      <td>${escape(item.issuer || "Não informado")}</td>
      <td>${item.expires_at ? helpers.dateBR(item.expires_at) : "—"}</td>
      <td><span class="tender-doc-status ${String(item.validityStatus).toLowerCase()}">${validityLabels[item.validityStatus] || item.validityStatus}</span></td>
      <td><div class="mini-actions"><a class="secondary" href="${item.downloadUrl}" download>Baixar</a>${item.status === "ACTIVE" ? `<button class="secondary" type="button" data-tender-document-archive="${item.id}">Arquivar</button>` : `<button class="secondary" type="button" data-tender-document-restore="${item.id}">Reativar</button>`}</div></td>
    </tr>`).join("");
    const catalogOptions = catalog.map((item) => `<option value="${escape(item.key)}" data-expires="${item.expires ? "1" : "0"}">${escape(item.group)} — ${escape(item.label)}</option>`).join("");
    return `<section id="tenderDocumentVault" class="panel tender-document-vault screen-enter-item">
      <div class="panel-head"><div><p class="eyebrow gold">LICITAÇÕES</p><h3>Cofre de documentos da empresa</h3><small class="muted">Base reutilizável para montar checklists por edital, com validade e auditoria.</small></div><button id="addTenderDocument" class="primary" type="button">＋ Adicionar documento</button></div>
      <div class="panel-body">
        <div class="tender-readiness" aria-label="Prontidão documental"><div><strong>${readiness.coveredCount || 0}/${readiness.catalogCount || catalog.length}</strong><span>tipos com arquivo atual</span></div><div><strong>${readiness.expiringCount || 0}</strong><span>vencendo em 30 dias</span></div><div><strong>${readiness.expiredCount || 0}</strong><span>vencidos</span></div></div>
        <p class="compliance-note compact"><strong>O edital é a fonte da verdade.</strong> Este catálogo cobre as categorias recorrentes dos arts. 62 a 70 da Lei 14.133/2021. SICAF, objeto, modalidade e inversão de fases podem alterar o que será solicitado e quando.</p>
        <div class="table-wrap"><table class="data-table tender-document-table"><thead><tr><th>Documento</th><th>Emissor</th><th>Validade</th><th>Situação</th><th>Ações</th></tr></thead><tbody>${rows || '<tr><td colspan="5"><div class="empty">Nenhum documento cadastrado. Adicione os arquivos recorrentes da empresa para iniciar.</div></td></tr>'}</tbody></table></div>
      </div>
      <dialog id="tenderDocumentDialog" class="dialog small form-drawer" aria-labelledby="tenderDocumentDialogTitle">
        <form id="tenderDocumentForm" method="dialog">
          <div class="dialog-head"><div><p class="eyebrow gold">COFRE DOCUMENTAL</p><h2 id="tenderDocumentDialogTitle">Adicionar documento</h2></div><button type="button" class="icon-button" data-tender-document-close aria-label="Fechar">×</button></div>
          <label class="field"><span>Tipo *</span><select name="documentType" required><option value="">Selecione</option>${catalogOptions}</select></label>
          <label class="field"><span>Título</span><input name="title" maxlength="240" placeholder="Usa o nome do catálogo se ficar vazio"></label>
          <label class="field"><span>Órgão ou entidade emissora</span><input name="issuer" maxlength="180"></label>
          <div class="form-grid two"><label class="field"><span>Emissão</span><input name="issueDate" type="date"></label><label class="field"><span id="tenderDocumentExpiryLabel">Validade</span><input name="expiresAt" type="date" aria-labelledby="tenderDocumentExpiryLabel"></label></div>
          <label class="field"><span>Escopo</span><select name="scope">${options(Object.entries(scopeLabels), "ALL")}</select></label>
          <label class="field"><span>Arquivo *</span><input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.zip,.docx,.xlsx,.xml,.json,.csv,.txt" required></label>
          <label class="field"><span>Observações</span><textarea name="notes" rows="3" maxlength="1200"></textarea></label>
          <p id="tenderDocumentFormError" class="form-error hidden" role="alert"></p>
          <div class="dialog-actions"><button type="button" class="secondary" data-tender-document-close>Cancelar</button><button type="submit" class="primary">Guardar documento</button></div>
        </form>
      </dialog>
    </section>`;
  }

  function fileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || "").split(",", 2)[1] || "");
      reader.onerror = () => reject(new Error("Não foi possível ler o arquivo."));
      reader.readAsDataURL(file);
    });
  }

  function bindSettings(actions) {
    const dialog = document.getElementById("tenderDocumentDialog");
    const form = document.getElementById("tenderDocumentForm");
    const documentType = form?.elements.namedItem("documentType");
    const expiresAt = form?.elements.namedItem("expiresAt");
    const expiryLabel = document.getElementById("tenderDocumentExpiryLabel");
    const syncExpiryRequirement = () => {
      const needsExpiry = documentType?.selectedOptions?.[0]?.dataset.expires === "1";
      if (expiresAt) expiresAt.required = needsExpiry;
      if (expiryLabel) expiryLabel.textContent = needsExpiry ? "Validade *" : "Validade";
    };
    documentType?.addEventListener("change", syncExpiryRequirement);
    document.getElementById("addTenderDocument")?.addEventListener("click", () => {
      form?.reset();
      syncExpiryRequirement();
      dialog?.showModal();
    });
    dialog?.querySelectorAll("[data-tender-document-close]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const error = document.getElementById("tenderDocumentFormError");
      const submit = form.querySelector('[type="submit"]');
      const values = new FormData(form);
      const file = values.get("file");
      if (!(file instanceof File) || !file.size) return;
      error?.classList.add("hidden");
      submit.disabled = true;
      const submitLabel = submit.textContent;
      submit.textContent = "Guardando…";
      try {
        const content = await fileAsBase64(file);
        await actions.api("/api/tender-documents", { method: "POST", body: JSON.stringify({
          documentType: values.get("documentType"), title: values.get("title"),
          issuer: values.get("issuer"), issueDate: values.get("issueDate"),
          expiresAt: values.get("expiresAt"), scope: values.get("scope"),
          notes: values.get("notes"), filename: file.name, mimeType: file.type, content,
        }) });
        dialog.close();
        actions.toast("Documento guardado no cofre da empresa.");
        await actions.reload();
      } catch (failure) {
        if (error) { error.textContent = failure.message; error.classList.remove("hidden"); }
      } finally { submit.disabled = false; submit.textContent = submitLabel; }
    });
    document.querySelectorAll("[data-tender-document-archive],[data-tender-document-restore]").forEach((button) => {
      button.addEventListener("click", async () => {
        const id = button.dataset.tenderDocumentArchive || button.dataset.tenderDocumentRestore;
        const status = button.dataset.tenderDocumentArchive ? "ARCHIVED" : "ACTIVE";
        if (status === "ARCHIVED" && !window.confirm("Arquivar este documento? Checklists confirmados que dependam dele voltarão para rascunho.")) return;
        try {
          await actions.api(`/api/tender-documents/${id}`, { method: "PUT", body: JSON.stringify({ status }) });
          actions.toast(status === "ACTIVE" ? "Documento reativado." : "Documento arquivado.");
          await actions.reload();
        } catch (failure) { actions.toast(failure.message); }
      });
    });
  }

  function requirementRow(requirement, escape, editable, inversion) {
    const catalog = requirement.catalog || {};
    const stages = Object.entries(stageLabels);
    const defaultStage = inversion && !requirement.id && requirement.stage === "QUALIFICATION" ? "INITIAL_PROPOSAL" : requirement.stage;
    const candidates = requirement.candidates || [];
    const selectedIds = new Set((requirement.selected_document_ids || (requirement.selected_document_id ? [requirement.selected_document_id] : [])).map(Number));
    const portal = Boolean(requirement.portal_declaration || catalog.portalDeclaration);
    const custom = Boolean(requirement.is_custom);
    const fileChoices = candidates.length ? candidates.map((item) => {
      const unavailable = item.validityStatus === "EXPIRED" || item.validityStatus === "ARCHIVED";
      return `<label class="tender-document-choice ${unavailable ? "unavailable" : ""}"><input type="checkbox" data-document-choice value="${item.id}" ${selectedIds.has(Number(item.id)) ? "checked" : ""} ${editable && !unavailable ? "" : "disabled"}><span><strong>${escape(item.title)}</strong><small>${validityLabels[item.validityStatus] || item.validityStatus}${item.expires_at ? ` · validade ${escape(item.expires_at)}` : ""}</small></span></label>`;
    }).join("") : `<p class="tender-no-candidate">${portal ? "Arquivo opcional; confirme se a declaração é preenchida no portal." : custom ? "Cadastre em Configurações um “Documento específico solicitado pelo edital”." : "Nenhum arquivo deste tipo está disponível no cofre."}</p>`;
    return `<div class="tender-requirement ${custom ? "is-custom" : ""}" data-tender-requirement data-document-type="${escape(requirement.document_type)}" data-custom="${custom ? "1" : "0"}" data-title="${escape(requirement.title)}" data-portal-declaration="${portal ? "1" : "0"}">
      <label class="tender-requirement-check"><input type="checkbox" data-required ${requirement.required ? "checked" : ""} ${editable ? "" : "disabled"}><span><strong>${escape(requirement.title)}</strong><small>${escape(catalog.group || "Documento do edital")}${portal ? " · normalmente preenchida no portal" : ""}</small></span></label>
      <label class="field compact"><span>Fase</span><select data-stage ${editable ? "" : "disabled"}>${options(stages, defaultStage)}</select></label>
      <label class="field compact"><span>Item/página do edital *</span><input data-source maxlength="240" value="${escape(requirement.source_reference || "")}" placeholder="Ex.: item 8.4, pág. 17" ${editable ? "" : "disabled"}></label>
      ${custom && editable ? '<button class="secondary tender-remove-requirement" type="button" data-remove-custom aria-label="Remover exigência específica">Remover</button>' : ""}
      <fieldset class="tender-document-choices"><legend>${portal ? "Arquivos, somente se exigidos" : "Arquivos do cofre"}</legend><div>${fileChoices}</div></fieldset>
    </div>`;
  }

  function detailHTML(data, tenderId, helpers) {
    if (!data) return "";
    const escape = helpers.escapeHTML;
    const profile = data.profile || {};
    const editable = Boolean(helpers.editable);
    const confirmed = profile.checklistStatus === "CONFIRMED";
    const inversion = Boolean(profile.qualificationWithInitialProposal);
    const standardRequirements = (data.requirements || []).filter((item) => !item.is_custom);
    const customRequirements = (data.requirements || []).filter((item) => item.is_custom);
    const groups = new Map();
    standardRequirements.forEach((item) => {
      const group = item.catalog?.group || "Exigências específicas";
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(item);
    });
    const groupHTML = [...groups.entries()].map(([group, requirements]) => `<details class="tender-requirement-group" ${requirements.some((item) => item.required) ? "open" : ""}><summary><strong>${escape(group)}</strong><span>${requirements.filter((item) => item.required).length} marcado(s)</span></summary>${requirements.map((item) => requirementRow(item, escape, editable, inversion)).join("")}</details>`).join("");
    const requiredStages = new Set((data.requirements || []).filter((item) => item.required).map((item) => item.stage));
    const packageButtons = confirmed ? Object.entries(stageLabels).filter(([stage]) => requiredStages.has(stage)).map(([stage, label]) => `<button class="secondary" type="button" data-tender-package="${stage}">Baixar pacote: ${label}</button>`).join("") : "";
    activeDetailContext = { escape, editable, inversion, customCandidates: data.customDocumentCandidates || [] };
    return `<section id="tenderParticipationDocuments" class="tender-detail-section tender-participation-documents">
      <div class="panel-head"><div><p class="eyebrow gold">DOCUMENTOS DA PARTICIPAÇÃO</p><h3>Checklist conferido no edital</h3><small class="muted">${escape(data.legalNotice || "Confirme as exigências antes do envio.")}</small></div><span class="tender-doc-status ${confirmed ? "valid" : "expiring"}">${confirmed ? "Confirmado" : "Rascunho"}</span></div>
      <div class="tender-flow-note"><strong>Fluxo informado</strong><span>${inversion ? "Habilitação junto com a proposta inicial (inversão de fases)." : "Habilitação após o julgamento, em regra apenas do vencedor."}</span></div>
      <form id="tenderParticipationForm" data-tender-id="${tenderId}">
        <label class="tender-inversion"><input type="checkbox" name="qualificationWithInitialProposal" ${inversion ? "checked" : ""} ${editable ? "" : "disabled"}> <span><strong>O edital inverte as fases</strong><small>Marque somente se o edital exigir habilitação junto com a proposta inicial.</small></span></label>
        <div class="tender-requirement-groups">${groupHTML}</div>
        <section class="tender-custom-requirements" aria-labelledby="tenderCustomRequirementsTitle"><div class="tender-custom-head"><div><h4 id="tenderCustomRequirementsTitle">Exigências específicas deste edital</h4><small>Inclua anexos, declarações, fichas, garantias ou comprovações que não existem no catálogo recorrente.</small></div>${editable ? '<button id="addTenderCustomRequirement" class="secondary" type="button">＋ Adicionar exigência</button>' : ""}</div><div id="tenderCustomRequirementRows">${customRequirements.map((item) => requirementRow(item, escape, editable, inversion)).join("") || '<p class="tender-custom-empty">Nenhuma exigência específica adicionada.</p>'}</div></section>
        <label class="field"><span>Notas da conferência</span><textarea name="notes" rows="3" maxlength="1600" ${editable ? "" : "disabled"}>${escape(profile.notes || "")}</textarea></label>
        ${editable ? `<label class="tender-confirm-check"><input type="checkbox" name="confirmed" ${confirmed ? "checked" : ""}> Li o edital e confirmei as exigências, fases e referências marcadas.</label><div class="dialog-actions tender-checklist-actions"><button class="primary" type="submit">Salvar checklist</button></div>` : '<p class="muted">Seu perfil pode consultar, mas não alterar este checklist.</p>'}
        <p id="tenderParticipationStatus" class="form-error hidden" role="alert"></p>
      </form>
      ${packageButtons ? `<div class="tender-package-actions"><strong>Pacotes permitidos pelo checklist</strong><div>${packageButtons}</div><small>O ZIP contém somente arquivos marcados para a fase e um manifesto com hash e referência.</small></div>` : ""}
      ${editable ? `<dialog id="tenderCustomRequirementDialog" class="dialog small form-drawer" aria-labelledby="tenderCustomRequirementDialogTitle"><form id="tenderCustomRequirementForm" method="dialog"><div class="dialog-head"><div><p class="eyebrow gold">EXIGÊNCIA DO EDITAL</p><h2 id="tenderCustomRequirementDialogTitle">Adicionar exigência específica</h2></div><button class="icon-button" type="button" data-custom-requirement-close aria-label="Fechar">×</button></div><label class="field"><span>Nome da exigência *</span><input name="title" required minlength="3" maxlength="240" placeholder="Ex.: declaração conforme Anexo VII"></label><label class="field"><span>Fase</span><select name="stage">${options(Object.entries(stageLabels), inversion ? "INITIAL_PROPOSAL" : "QUALIFICATION")}</select></label><label class="tender-inversion"><input name="portalDeclaration" type="checkbox"><span><strong>Preenchida diretamente no portal</strong><small>Marque somente quando o edital dispensar o envio de um arquivo.</small></span></label><div class="dialog-actions"><button class="secondary" type="button" data-custom-requirement-close>Cancelar</button><button class="primary" type="submit">Adicionar ao checklist</button></div></form></dialog>` : ""}
    </section>`;
  }

  function bindDetail(actions) {
    const form = document.getElementById("tenderParticipationForm");
    if (!form) return;
    const inversion = form.elements.qualificationWithInitialProposal;
    inversion?.addEventListener("change", () => {
      if (!inversion.checked) return;
      form.querySelectorAll('[data-tender-requirement] [data-stage]').forEach((select) => {
        if (select.value === "QUALIFICATION") select.value = "INITIAL_PROPOSAL";
      });
    });
    const customDialog = document.getElementById("tenderCustomRequirementDialog");
    const customForm = document.getElementById("tenderCustomRequirementForm");
    document.getElementById("addTenderCustomRequirement")?.addEventListener("click", () => {
      customForm.reset();
      customDialog.showModal();
      customForm.elements.title.focus();
    });
    customDialog?.querySelectorAll("[data-custom-requirement-close]").forEach((button) => {
      button.addEventListener("click", () => customDialog.close());
    });
    const bindCustomRemoval = (root = form) => root.querySelectorAll("[data-remove-custom]").forEach((button) => {
      button.onclick = () => {
        button.closest("[data-tender-requirement]")?.remove();
        if (!document.querySelector("#tenderCustomRequirementRows [data-tender-requirement]")) {
          document.getElementById("tenderCustomRequirementRows").innerHTML = '<p class="tender-custom-empty">Nenhuma exigência específica adicionada.</p>';
        }
        if (form.elements.confirmed) form.elements.confirmed.checked = false;
      };
    });
    bindCustomRemoval();
    customForm?.addEventListener("submit", (event) => {
      event.preventDefault();
      const title = customForm.elements.title.value.trim();
      if (title.length < 3) return;
      const identifier = `custom:${globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(36).slice(2)}`}`.toLowerCase();
      const requirement = {
        id: null, document_type: identifier, title, stage: customForm.elements.stage.value,
        required: true, is_custom: true,
        portal_declaration: customForm.elements.portalDeclaration.checked,
        source_reference: "", selected_document_ids: [],
        candidates: activeDetailContext?.customCandidates || [],
        catalog: { group: "Exigências específicas", multiple: true,
          portalDeclaration: customForm.elements.portalDeclaration.checked },
      };
      const target = document.getElementById("tenderCustomRequirementRows");
      target.querySelector(".tender-custom-empty")?.remove();
      target.insertAdjacentHTML("beforeend", requirementRow(requirement, escapeText, true, inversion.checked));
      bindCustomRemoval(target);
      if (form.elements.confirmed) form.elements.confirmed.checked = false;
      customDialog.close();
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = document.getElementById("tenderParticipationStatus");
      const submit = form.querySelector('[type="submit"]');
      const requirements = [...form.querySelectorAll("[data-tender-requirement]")].map((row) => ({
        documentType: row.dataset.documentType,
        title: row.dataset.title,
        custom: row.dataset.custom === "1",
        portalDeclaration: row.dataset.portalDeclaration === "1",
        required: row.querySelector("[data-required]").checked,
        stage: row.querySelector("[data-stage]").value,
        selectedDocumentIds: [...row.querySelectorAll("[data-document-choice]:checked")].map((input) => Number(input.value)),
        sourceReference: row.querySelector("[data-source]").value,
      }));
      status?.classList.add("hidden");
      submit.disabled = true;
      try {
        await actions.api(`/api/tenders/results/${form.dataset.tenderId}/participation-documents`, {
          method: "PUT", body: JSON.stringify({
            qualificationWithInitialProposal: inversion.checked,
            confirmed: form.elements.confirmed.checked,
            notes: form.elements.notes.value, requirements,
          }),
        });
        actions.toast("Checklist documental salvo.");
        await actions.reload();
      } catch (failure) {
        if (status) { status.textContent = failure.message; status.classList.remove("hidden"); status.scrollIntoView({ block: "center" }); }
      } finally { submit.disabled = false; }
    });
    document.querySelectorAll("[data-tender-package]").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const response = await fetch(`/api/tenders/results/${form.dataset.tenderId}/participation-package?stage=${encodeURIComponent(button.dataset.tenderPackage)}`, { credentials: "same-origin" });
          if (!response.ok) {
            const failure = await response.json().catch(() => ({}));
            throw new Error(failure.message || "Não foi possível gerar o pacote.");
          }
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = `licitacao-${form.dataset.tenderId}-${button.dataset.tenderPackage.toLowerCase()}.zip`;
          link.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
          actions.toast("Pacote documental gerado.");
        } catch (failure) { actions.toast(failure.message); }
        finally { button.disabled = false; }
      });
    });
  }

  window.SIVSTenderDocuments = { settingsHTML, bindSettings, detailHTML, bindDetail };
})();
