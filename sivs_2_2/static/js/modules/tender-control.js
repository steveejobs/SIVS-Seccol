(() => {
  "use strict";

  let context = null;
  // GO/NO-GO é um código interno de processo, não uma instrução para quem opera.
  // A interface sempre mostra a decisão por extenso e explica sua consequência.
  const decisionLabels = {
    PENDING: "Ainda não decidido",
    GO: "Participar desta licitação",
    NO_GO: "Não participar desta licitação",
  };
  const decisionGuidance = {
    PENDING: "Avalie prazo, documentos, riscos e capacidade antes de decidir.",
    GO: "A empresa seguirá com esta oportunidade. Registre o motivo, responsável e próximos prazos.",
    NO_GO: "A empresa não seguirá com esta oportunidade. Registre o motivo para manter a decisão rastreável.",
  };
  const milestoneLabels = {
    PROPOSAL: "Proposta", CLARIFICATION: "Esclarecimento", SITE_VISIT: "Visita tecnica",
    SESSION: "Sessão", APPEAL: "Recurso", QUALIFICATION: "Habilitação",
    CONTRACT: "Contrato", DELIVERY: "Entrega", OTHER: "Outro",
  };
  const riskLabels = {
    DOCUMENTAL: "Documental", TECHNICAL: "Técnico", COMMERCIAL: "Comercial",
    CAPACITY: "Capacidade", FINANCIAL: "Financeiro", PORTAL: "Portal",
    CONTRACTUAL: "Contratual", OTHER: "Outro",
  };
  const eventLabels = {
    PROPOSAL: "Proposta", CLARIFICATION: "Esclarecimento", APPEAL: "Recurso",
    QUALIFICATION: "Habilitação", CONTRACT: "Contrato", BID: "Lance", OTHER: "Outro",
  };

  const optionList = (entries, selected, escape) => Object.entries(entries).map(([value, label]) => (
    `<option value="${value}" ${value === selected ? "selected" : ""}>${escape(label)}</option>`
  )).join("");

  function localDateTime(value) {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value).slice(0, 16);
    return new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }

  function serverDateTime(value) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "" : parsed.toISOString();
  }

  function userOptions(users, selected, escape) {
    return `<option value="">Sem atribuicao</option>${(users || []).map((user) => (
      `<option value="${escape(user.id)}" ${Number(user.id) === Number(selected) ? "selected" : ""}>${escape(user.name)}</option>`
    )).join("")}`;
  }

  function milestoneRow(item, users, editable, escape) {
    return `<article class="tender-control-row milestone-row" data-tender-milestone>
      <div class="tender-control-row-head"><strong>Marco operacional</strong>${editable ? '<button class="text-button" type="button" data-remove-control-row aria-label="Remover marco">Remover</button>' : ""}</div>
      <div class="tender-control-fields">
        <label class="field"><span>Tipo</span><select data-control-field="type" ${editable ? "" : "disabled"}>${optionList(milestoneLabels, item.type || "OTHER", escape)}</select></label>
        <label class="field control-wide"><span>Titulo</span><input data-control-field="title" maxlength="240" value="${escape(item.title || "")}" required ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Prazo e horário</span><input data-control-field="dueAt" type="datetime-local" value="${escape(localDateTime(item.dueAt))}" required ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Status</span><select data-control-field="status" ${editable ? "" : "disabled"}><option value="PENDING" ${item.status === "PENDING" ? "selected" : ""}>Pendente</option><option value="COMPLETED" ${item.status === "COMPLETED" ? "selected" : ""}>Concluido</option><option value="CANCELLED" ${item.status === "CANCELLED" ? "selected" : ""}>Cancelado</option></select></label>
        <label class="field"><span>Responsavel</span><select data-control-field="responsibleUserId" ${editable ? "" : "disabled"}>${userOptions(users, item.responsibleUserId, escape)}</select></label>
        <label class="field control-wide"><span>Referencia no edital/portal</span><input data-control-field="sourceReference" maxlength="500" value="${escape(item.sourceReference || "")}" ${editable ? "" : "disabled"}></label>
        <label class="field control-full"><span>Observacoes</span><textarea data-control-field="notes" maxlength="1500" rows="2" ${editable ? "" : "disabled"}>${escape(item.notes || "")}</textarea></label>
      </div>
    </article>`;
  }

  function riskRow(item, users, editable, escape) {
    const score = Number(item.probability || 3) * Number(item.impact || 3);
    return `<article class="tender-control-row risk-row" data-tender-risk>
      <div class="tender-control-row-head"><strong>Risco <span class="risk-score ${score >= 15 ? "critical" : score >= 8 ? "attention" : "controlled"}" data-risk-score>${score}</span></strong>${editable ? '<button class="text-button" type="button" data-remove-control-row aria-label="Remover risco">Remover</button>' : ""}</div>
      <div class="tender-control-fields">
        <label class="field"><span>Categoria</span><select data-control-field="category" ${editable ? "" : "disabled"}>${optionList(riskLabels, item.category || "OTHER", escape)}</select></label>
        <label class="field control-wide"><span>Risco identificado</span><input data-control-field="title" maxlength="240" value="${escape(item.title || "")}" required ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Probabilidade (1-5)</span><input data-control-field="probability" type="number" min="1" max="5" value="${escape(item.probability || 3)}" required ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Impacto (1-5)</span><input data-control-field="impact" type="number" min="1" max="5" value="${escape(item.impact || 3)}" required ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Status</span><select data-control-field="status" ${editable ? "" : "disabled"}><option value="OPEN" ${item.status === "OPEN" ? "selected" : ""}>Aberto</option><option value="MITIGATED" ${item.status === "MITIGATED" ? "selected" : ""}>Mitigado</option><option value="ACCEPTED" ${item.status === "ACCEPTED" ? "selected" : ""}>Aceito</option></select></label>
        <label class="field"><span>Responsavel</span><select data-control-field="ownerUserId" ${editable ? "" : "disabled"}>${userOptions(users, item.ownerUserId, escape)}</select></label>
        <label class="field control-full"><span>Mitigacao / justificativa</span><textarea data-control-field="mitigation" maxlength="2000" rows="2" ${editable ? "" : "disabled"}>${escape(item.mitigation || "")}</textarea></label>
      </div>
    </article>`;
  }

  function evidenceHTML(items, tenderId, escape) {
    if (!items.length) return '<p class="muted">Nenhum comprovante registrado. O histórico começa no primeiro protocolo anexado.</p>';
    return `<ol class="tender-evidence-list">${items.map((item) => `<li>
      <div><strong>${escape(eventLabels[item.eventType] || item.eventType)}${item.protocol ? ` - ${escape(item.protocol)}` : ""}</strong><span>${escape(item.portal || "Portal não informado")} - ${escape(new Date(item.occurredAt).toLocaleString("pt-BR"))}</span><small>${escape(item.filename)} · identificação de integridade (SHA-256): ${escape(String(item.sha256 || "").slice(0, 16))}...</small></div>
      <a class="secondary" download href="${escape(item.downloadUrl || `/api/tenders/results/${tenderId}/control/evidence/${item.id}/download`)}">Baixar</a>
    </li>`).join("")}</ol>`;
  }

  function detailHTML(data, tenderId, helpers = {}) {
    if (!data) return "";
    const escape = helpers.escapeHTML || ((value) => String(value ?? ""));
    const editable = Boolean(data.canEdit);
    const profile = data.profile || { decision: "PENDING", revision: 0 };
    const summary = data.summary || {};
    const milestones = data.milestones?.length ? data.milestones : (data.suggestedMilestones || []);
    const risks = data.risks || [];
    const deadlinePassed = Boolean(data.deadlinePassed);
    const deadlineAlert = deadlinePassed ? `<div class="form-error" role="alert"><strong>Prazo de participação encerrado.</strong> O prazo oficial terminou em ${escape(new Date(data.deadline).toLocaleString("pt-BR"))}. Não é possível voltar no tempo nem enviar proposta ou lance. Registre abaixo por que a empresa deixou de participar desta licitação.</div>` : "";
    return `<section class="tender-detail-section tender-control" aria-labelledby="tenderControlTitle-${tenderId}">
      ${deadlineAlert}
      <div class="panel-head"><div><p class="eyebrow gold">CONTROLE DA PARTICIPAÇÃO</p><h3 id="tenderControlTitle-${tenderId}">Decida se a empresa vai participar</h3><small class="muted">Registre a decisão, quem é responsável, os prazos e os riscos. Os comprovantes ficam preservados no histórico.</small></div><span class="status ${profile.decision === "GO" ? "ativo" : profile.decision === "NO_GO" ? "erro" : "pendente"}">${escape(decisionLabels[profile.decision] || profile.decision)}</span></div>
      <div class="tender-control-summary" aria-label="Resumo do controle"><div><span>Prazos a tratar</span><strong>${escape(summary.pendingMilestones || 0)}</strong></div><div><span>Riscos sem solução</span><strong>${escape(summary.openRisks || 0)}</strong></div><div><span>Riscos que impedem avançar</span><strong>${escape(summary.criticalRisks || 0)}</strong></div><div><span>Comprovantes guardados</span><strong>${escape(summary.evidenceCount || 0)}</strong></div></div>
      <form data-tender-control-form="${tenderId}" data-revision="${escape(profile.revision || 0)}" data-deadline-passed="${deadlinePassed}">
        <div class="tender-control-decision">
          <label class="field"><span>O que a empresa decidiu?</span><select data-control-decision ${editable ? "" : "disabled"}>${optionList(decisionLabels, profile.decision || "PENDING", escape)}</select></label>
          <label class="field"><span>Quem vai conduzir este item?</span><select data-control-responsible ${editable ? "" : "disabled"}>${userOptions(data.users, profile.responsibleUserId, escape)}</select></label>
          <p class="decision-guidance" data-decision-guidance role="status">${escape(decisionGuidance[profile.decision] || decisionGuidance.PENDING)}</p>
          <label class="field control-decision-reason"><span>Por que essa decisão foi tomada?</span><textarea data-control-decision-reason maxlength="2000" rows="3" placeholder="Explique os fatores que levaram a participar ou não participar." ${editable ? "" : "disabled"}>${escape(profile.decisionReason || "")}</textarea><small>Obrigatório ao decidir participar ou não participar.</small></label>
        </div>
        <div class="tender-control-group"><div class="tender-control-group-head"><div><h4>Agenda crítica</h4><small>Prazos com fonte e responsável definidos.</small></div>${editable ? '<button class="secondary" type="button" data-add-tender-milestone>Adicionar marco</button>' : ""}</div><div data-tender-milestones>${milestones.map((item) => milestoneRow(item, data.users, editable, escape)).join("") || '<p class="muted" data-empty-control-list>Nenhum marco cadastrado.</p>'}</div></div>
        <div class="tender-control-group"><div class="tender-control-group-head"><div><h4>Riscos que precisam de acompanhamento</h4><small>Probabilidade x impacto. Pontuação 15 ou maior precisa de uma ação de redução antes de participar.</small></div>${editable ? '<button class="secondary" type="button" data-add-tender-risk>Adicionar risco</button>' : ""}</div><div data-tender-risks>${risks.map((item) => riskRow(item, data.users, editable, escape)).join("") || '<p class="muted" data-empty-control-list>Nenhum risco cadastrado.</p>'}</div></div>
        ${editable ? '<div class="tender-control-save"><button class="primary" type="submit">Salvar controle</button><output role="status" aria-live="polite" data-tender-control-status></output></div>' : ""}
      </form>
      <div class="tender-control-evidence"><div class="tender-control-group-head"><div><h4>Comprovantes de protocolo</h4><small>O arquivo, sua identificação de integridade, o portal, o horário e a pessoa responsável ficam preservados para conferência.</small></div></div>${evidenceHTML(data.evidence || [], tenderId, escape)}
        ${editable ? `<form data-tender-evidence-form="${tenderId}" class="tender-evidence-form"><label class="field"><span>Evento</span><select name="eventType">${optionList(eventLabels, "PROPOSAL", escape)}</select></label><label class="field"><span>Portal</span><input name="portal" maxlength="180" placeholder="Ex.: Compras.gov.br"></label><label class="field"><span>Protocolo</span><input name="protocol" maxlength="240" placeholder="Número ou referência"></label><label class="field"><span>Data e horário</span><input name="occurredAt" type="datetime-local" value="${escape(localDateTime(new Date().toISOString()))}" required></label><label class="field evidence-file"><span>Arquivo (até 10 MB)</span><input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.zip,.docx,.xlsx,.xml,.json,.csv,.txt" required></label><label class="field evidence-notes"><span>Observações</span><input name="notes" maxlength="1500"></label><button class="secondary" type="submit">Registrar comprovante</button><output role="status" aria-live="polite"></output></form>` : ""}
      </div>
    </section>`;
  }

  const fieldValue = (row, name) => row.querySelector(`[data-control-field="${name}"]`)?.value || "";

  function bindRiskScores(root) {
    root.querySelectorAll("[data-tender-risk]").forEach((row) => {
      const update = () => {
        const score = Number(fieldValue(row, "probability")) * Number(fieldValue(row, "impact"));
        const badge = row.querySelector("[data-risk-score]");
        if (!badge) return;
        badge.textContent = String(score || 0);
        badge.className = `risk-score ${score >= 15 ? "critical" : score >= 8 ? "attention" : "controlled"}`;
      };
      row.querySelectorAll('[data-control-field="probability"], [data-control-field="impact"]').forEach((field) => { field.oninput = update; });
    });
  }

  function bindRemoveButtons(root) {
    root.querySelectorAll("[data-remove-control-row]").forEach((button) => {
      button.onclick = () => button.closest("[data-tender-milestone], [data-tender-risk]")?.remove();
    });
  }

  function fileContent(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || "").split(",", 2)[1] || "");
      reader.onerror = () => reject(new Error("Não foi possível ler o comprovante."));
      reader.readAsDataURL(file);
    });
  }

  function bindDetail(nextContext) {
    context = nextContext;
    document.querySelectorAll("[data-tender-control-form]").forEach((form) => {
      const tenderId = form.dataset.tenderControlForm;
      const users = context.controlData?.users || [];
      const escape = context.escapeHTML || ((value) => String(value ?? ""));
      const milestoneList = form.querySelector("[data-tender-milestones]");
      const riskList = form.querySelector("[data-tender-risks]");
      form.querySelector("[data-add-tender-milestone]")?.addEventListener("click", () => {
        milestoneList.querySelector("[data-empty-control-list]")?.remove();
        milestoneList.insertAdjacentHTML("beforeend", milestoneRow({ type: "OTHER", status: "PENDING" }, users, true, escape));
        bindRemoveButtons(milestoneList);
      });
      form.querySelector("[data-add-tender-risk]")?.addEventListener("click", () => {
        riskList.querySelector("[data-empty-control-list]")?.remove();
        riskList.insertAdjacentHTML("beforeend", riskRow({ category: "OTHER", status: "OPEN", probability: 3, impact: 3 }, users, true, escape));
        bindRemoveButtons(riskList);
        bindRiskScores(riskList);
      });
      bindRemoveButtons(form);
      bindRiskScores(form);
      const decisionField = form.querySelector("[data-control-decision]");
      const decisionGuidanceElement = form.querySelector("[data-decision-guidance]");
      const deadlinePassed = form.dataset.deadlinePassed === "true";
      if (deadlinePassed && decisionField) {
        decisionField.value = "NO_GO";
        [...decisionField.options].forEach((option) => { option.disabled = option.value !== "NO_GO"; });
        decisionGuidanceElement.textContent = "O prazo encerrou. Registre por que a empresa deixou de participar desta licitação.";
        const reasonLabel = form.querySelector("[data-control-decision-reason]")?.closest("label")?.querySelector("span");
        if (reasonLabel) reasonLabel.textContent = "Por que a empresa deixou de participar desta licitação?";
      }
      decisionField?.addEventListener("change", () => {
        decisionGuidanceElement.textContent = decisionGuidance[decisionField.value] || decisionGuidance.PENDING;
      });
      form.onsubmit = async (event) => {
        event.preventDefault();
        const submit = form.querySelector('[type="submit"]');
        const output = form.querySelector("[data-tender-control-status]");
        submit.disabled = true;
        output.textContent = "Validando e salvando...";
        const milestones = [...form.querySelectorAll("[data-tender-milestone]")].map((row) => ({
          type: fieldValue(row, "type"), title: fieldValue(row, "title"),
          dueAt: serverDateTime(fieldValue(row, "dueAt")), status: fieldValue(row, "status"),
          responsibleUserId: fieldValue(row, "responsibleUserId") || null,
          sourceReference: fieldValue(row, "sourceReference"), notes: fieldValue(row, "notes"),
        }));
        const risks = [...form.querySelectorAll("[data-tender-risk]")].map((row) => ({
          category: fieldValue(row, "category"), title: fieldValue(row, "title"),
          probability: Number(fieldValue(row, "probability")), impact: Number(fieldValue(row, "impact")),
          status: fieldValue(row, "status"), ownerUserId: fieldValue(row, "ownerUserId") || null,
          mitigation: fieldValue(row, "mitigation"),
        }));
        try {
          await context.api(`/api/tenders/results/${tenderId}/control`, {
            method: "PUT", body: JSON.stringify({
              expectedRevision: Number(form.dataset.revision || 0),
              decision: form.querySelector("[data-control-decision]").value,
              decisionReason: form.querySelector("[data-control-decision-reason]").value,
              responsibleUserId: form.querySelector("[data-control-responsible]").value || null,
              milestones, risks,
            }),
          });
          context.toast("Controle da licitação salvo e auditado.");
          await context.reload();
        } catch (failure) {
          output.textContent = failure.message;
          context.toast(failure.message);
          submit.disabled = false;
        }
      };
    });

    document.querySelectorAll("[data-tender-evidence-form]").forEach((form) => {
      form.onsubmit = async (event) => {
        event.preventDefault();
        const tenderId = form.dataset.tenderEvidenceForm;
        const submit = form.querySelector('[type="submit"]');
        const output = form.querySelector("output");
        const values = Object.fromEntries(new FormData(form).entries());
        const file = values.file;
        if (!(file instanceof File) || !file.size) return;
        submit.disabled = true;
        output.textContent = "Calculando hash e registrando...";
        try {
          await context.api(`/api/tenders/results/${tenderId}/control/evidence`, {
            method: "POST", body: JSON.stringify({
              eventType: values.eventType, portal: values.portal, protocol: values.protocol,
              occurredAt: serverDateTime(values.occurredAt), notes: values.notes,
              filename: file.name, content: await fileContent(file),
            }),
          });
          context.toast("Comprovante registrado e preservado para conferência.");
          await context.reload();
        } catch (failure) {
          output.textContent = failure.message;
          context.toast(failure.message);
          submit.disabled = false;
        }
      };
    });
  }

  window.SIVSTenderControl = { detailHTML, bindDetail };
})();
