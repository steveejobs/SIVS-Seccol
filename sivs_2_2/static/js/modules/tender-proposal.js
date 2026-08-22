(() => {
  "use strict";

  const money = (value) => new Intl.NumberFormat("pt-BR", {
    style: "currency", currency: "BRL",
  }).format(Number(value || 0));
  const number = (value) => Number(String(value ?? "").replace(",", ".")) || 0;
  const escapeFallback = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
  let context = null;

  const statusLabels = {
    DRAFT: "Rascunho", PENDING_APPROVAL: "Aguardando aprovação",
    APPROVED: "Aprovada", REJECTED: "Devolvida para revisão",
  };
  const decisionLabels = {
    SUBMITTED: "Enviada para aprovação", APPROVED: "Aprovada",
    REJECTED: "Devolvida para revisão", WITHDRAWN: "Retirada da aprovação",
    REOPENED: "Revisão reaberta",
  };
  const sourceLabels = {
    PNCP: "Item oficial PNCP", AI_REVIEW_REQUIRED: "Extraído pela IA — conferir",
    MANUAL: "Incluído manualmente",
  };

  function catalogOptions(selectedId, escape) {
    return `<option value="">Sem vínculo com o catálogo</option>${(context?.catalog || []).map((item) => (
      `<option value="${item.id}" ${Number(selectedId) === Number(item.id) ? "selected" : ""}>${escape(`${item.code ? `${item.code} · ` : ""}${item.title}`)}</option>`
    )).join("")}`;
  }

  function itemRow(item, index, escape, editable) {
    const referencePrice = item.referencePrice == null ? "Não publicado" : money(item.referencePrice);
    return `<fieldset class="tender-proposal-item" data-proposal-item data-source-kind="${escape(item.sourceKind || "MANUAL")}" data-reference-price="${item.referencePrice ?? ""}">
      <legend><span>Item ${escape(item.sourceItemNumber || index + 1)}</span><small>${escape(sourceLabels[item.sourceKind] || sourceLabels.MANUAL)}</small></legend>
      <input type="hidden" data-source-number value="${escape(item.sourceItemNumber || index + 1)}">
      <div class="tender-proposal-item-grid">
        <label class="field proposal-description"><span>Descrição *</span><textarea data-description rows="2" maxlength="500" required ${editable ? "" : "disabled"}>${escape(item.description || "")}</textarea></label>
        <label class="field"><span>Produto ou serviço do catálogo</span><select data-catalog ${editable ? "" : "disabled"}>${catalogOptions(item.catalogRecordId || item.suggestedCatalogRecordId, escape)}</select></label>
        <label class="field"><span>Quantidade *</span><input data-quantity type="number" min="0.000001" step="0.000001" value="${escape(item.quantity || 1)}" required ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Unidade *</span><input data-unit maxlength="30" value="${escape(item.unit || "UN")}" required ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Custo unitário *</span><input data-cost type="number" min="0" step="0.01" value="${item.unitCost ?? ""}" placeholder="0,00" ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Piso unitário *</span><input data-floor type="number" min="0" step="0.01" value="${item.minimumUnitPrice ?? ""}" placeholder="Nunca abaixo do custo" ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Preço proposto *</span><input data-price type="number" min="0" step="0.01" value="${item.unitPrice ?? ""}" placeholder="0,00" ${editable ? "" : "disabled"}></label>
        <div class="proposal-reference-price"><span>Referência publicada</span><strong>${referencePrice}</strong></div>
        <label class="field proposal-reference"><span>Item/página ou origem no edital *</span><input data-source-reference maxlength="240" value="${escape(item.sourceReference || "")}" required ${editable ? "" : "disabled"}></label>
        <div class="proposal-line-total"><span>Total calculado</span><strong data-line-total>${money(number(item.quantity || 1) * number(item.unitPrice))}</strong></div>
        ${editable ? '<button class="secondary proposal-remove-item" type="button" data-remove-proposal-item aria-label="Remover item da proposta">Remover item</button>' : ""}
      </div>
    </fieldset>`;
  }

  function detailHTML(data, tenderId, helpers) {
    if (!data) return "";
    const escape = helpers.escapeHTML || escapeFallback;
    if (data.valuesRestricted) return `<section id="tenderCommercialProposal" class="tender-detail-section tender-commercial-proposal"><div class="panel-head"><div><p class="eyebrow gold">PROPOSTA COMERCIAL</p><h3>Valores protegidos por permissão</h3></div><span class="tender-proposal-status restricted">Restrito</span></div><p class="muted">${escape(data.message)}</p></section>`;
    const proposal = data.proposal;
    const status = proposal?.status || "DRAFT";
    const editable = Boolean(data.canEdit);
    const items = proposal?.items?.length
      ? proposal.items
      : (data.suggestedItems?.length ? data.suggestedItems : [{
        sourceKind: "MANUAL", sourceItemNumber: "1", sourceReference: "",
        description: "", unit: "UN", quantity: 1, referencePrice: null,
      }]);
    const commercial = proposal?.commercial || {
      validityDays: 30, deliveryTerms: "", paymentTerms: "", warrantyTerms: "", notes: "",
    };
    const blockers = (data.blockers || []).map((item) => `<li>${escape(item)}</li>`).join("");
    const totals = proposal?.totals || { cost: 0, price: 0, margin: 0, marginPercent: null };
    const decisions = (data.decisions || []).map((item) => `<li><strong>${escape(decisionLabels[item.action] || item.action)}</strong><span>${escape(item.actor_name || "Sistema")} · ${escape(item.created_at || "")}</span>${item.comment ? `<p>${escape(item.comment)}</p>` : ""}</li>`).join("");
    context = { catalog: data.catalog || [], escape, editable };
    return `<section id="tenderCommercialProposal" class="tender-detail-section tender-commercial-proposal" aria-labelledby="tenderCommercialProposalTitle">
      <div class="panel-head"><div><p class="eyebrow gold">PROPOSTA COMERCIAL</p><h3 id="tenderCommercialProposalTitle">Composição, piso e aprovação</h3><small class="muted">${escape(data.notice || "Revisão humana obrigatória.")}</small></div><span class="tender-proposal-status ${status.toLowerCase()}">${escape(statusLabels[status] || status)}</span></div>
      ${data.suggestedItems?.length && !proposal ? `<div class="proposal-extraction-note"><strong>${data.suggestedItems.length} item(ns) sugerido(s)</strong><span>Descrição, quantidade e referência vieram dos dados oficiais ou da leitura assistida. Confirme cada linha antes de salvar.</span></div>` : ""}
      <form id="tenderCommercialProposalForm" data-tender-id="${tenderId}" data-version="${proposal?.version || 0}">
        <div id="tenderProposalItems" class="tender-proposal-items">${items.map((item, index) => itemRow(item, index, escape, editable)).join("")}</div>
        ${editable ? '<button id="addTenderProposalItem" class="secondary" type="button">＋ Adicionar item manual</button>' : ""}
        <div class="tender-proposal-commercial-grid">
          <label class="field"><span>Validade da proposta (dias) *</span><input name="validityDays" type="number" min="1" max="365" value="${escape(commercial.validityDays || 30)}" ${editable ? "" : "disabled"}></label>
          <label class="field"><span>Entrega ou execução *</span><input name="deliveryTerms" maxlength="500" value="${escape(commercial.deliveryTerms || "")}" placeholder="Ex.: até 15 dias após empenho" ${editable ? "" : "disabled"}></label>
          <label class="field"><span>Condições de pagamento *</span><input name="paymentTerms" maxlength="500" value="${escape(commercial.paymentTerms || "")}" placeholder="Ex.: 30 dias após aceite" ${editable ? "" : "disabled"}></label>
          <label class="field"><span>Garantia</span><input name="warrantyTerms" maxlength="500" value="${escape(commercial.warrantyTerms || "")}" ${editable ? "" : "disabled"}></label>
          <label class="field full"><span>Observações comerciais</span><textarea name="notes" rows="3" maxlength="1600" ${editable ? "" : "disabled"}>${escape(commercial.notes || "")}</textarea></label>
        </div>
        <div class="tender-proposal-totals" aria-live="polite"><div><span>Custo</span><strong data-proposal-total-cost>${money(totals.cost)}</strong></div><div><span>Proposta</span><strong data-proposal-total-price>${money(totals.price)}</strong></div><div><span>Margem</span><strong data-proposal-margin>${money(totals.margin)}${totals.marginPercent == null ? "" : ` · ${Number(totals.marginPercent).toFixed(2)}%`}</strong></div></div>
        ${blockers ? `<div class="proposal-blockers"><strong>Pendências antes da aprovação</strong><ul>${blockers}</ul></div>` : ""}
        <p id="tenderProposalStatus" class="form-error hidden" role="alert"></p>
        <div class="tender-proposal-actions">
          ${editable ? '<button class="primary" type="submit">Salvar nova versão</button>' : ""}
          ${data.canSubmit ? '<button class="secondary" type="button" data-proposal-action="submit">Solicitar aprovação independente</button>' : ""}
          ${data.canWithdraw ? '<button class="secondary" type="button" data-proposal-action="withdraw">Retirar da aprovação</button>' : ""}
          ${data.canReopen ? '<button class="secondary" type="button" data-proposal-action="reopen">Abrir nova revisão</button>' : ""}
          ${data.canDownload ? '<button class="primary" type="button" data-proposal-package>Baixar pacote comercial aprovado</button>' : ""}
        </div>
      </form>
      ${data.canDecide ? `<section class="proposal-decision" aria-labelledby="proposalDecisionTitle"><h4 id="proposalDecisionTitle">Decisão independente</h4><p>Quem preparou ou enviou esta versão não pode aprová-la.</p><label class="field"><span>Parecer obrigatório</span><textarea id="tenderProposalDecisionComment" rows="3" maxlength="1000"></textarea></label><div><button class="secondary" type="button" data-proposal-decision="REJECTED">Devolver para revisão</button><button class="primary" type="button" data-proposal-decision="APPROVED">Aprovar esta versão</button></div></section>` : ""}
      ${decisions ? `<details class="proposal-history"><summary>Histórico de decisões e versões</summary><ol>${decisions}</ol></details>` : ""}
    </section>`;
  }

  function bindDetail(actions) {
    const form = document.getElementById("tenderCommercialProposalForm");
    if (!form) return;
    const itemsRoot = document.getElementById("tenderProposalItems");
    const status = document.getElementById("tenderProposalStatus");
    const showError = (failure) => {
      if (!status) return;
      status.textContent = failure.message || String(failure);
      status.classList.remove("hidden");
      status.scrollIntoView({ block: "center" });
    };
    const recalculate = () => {
      let cost = 0;
      let price = 0;
      itemsRoot.querySelectorAll("[data-proposal-item]").forEach((row) => {
        const quantity = number(row.querySelector("[data-quantity]").value);
        const rowCost = quantity * number(row.querySelector("[data-cost]").value);
        const rowPrice = quantity * number(row.querySelector("[data-price]").value);
        cost += rowCost;
        price += rowPrice;
        row.querySelector("[data-line-total]").textContent = money(rowPrice);
      });
      const margin = price - cost;
      const percent = price > 0 ? ` · ${(margin * 100 / price).toFixed(2)}%` : "";
      form.querySelector("[data-proposal-total-cost]").textContent = money(cost);
      form.querySelector("[data-proposal-total-price]").textContent = money(price);
      form.querySelector("[data-proposal-margin]").textContent = `${money(margin)}${percent}`;
    };
    const bindRow = (row) => {
        if (row.dataset.proposalBound === "true") return;
        row.dataset.proposalBound = "true";
        row.querySelectorAll("input,select,textarea").forEach((input) => input.addEventListener("input", recalculate));
        row.querySelector("[data-catalog]")?.addEventListener("change", (event) => {
          const selected = context.catalog.find((item) => Number(item.id) === Number(event.target.value));
          if (!selected) return;
          if (!row.querySelector("[data-description]").value.trim()) row.querySelector("[data-description]").value = selected.title;
          if (!row.querySelector("[data-unit]").value.trim()) row.querySelector("[data-unit]").value = selected.unit || "UN";
          const cost = row.querySelector("[data-cost]");
          const floor = row.querySelector("[data-floor]");
          const price = row.querySelector("[data-price]");
          if (!cost.value && selected.defaultCost != null) cost.value = selected.defaultCost;
          if (!floor.value && selected.defaultCost != null) floor.value = selected.defaultCost;
          if (!price.value && number(selected.defaultPrice) > 0) price.value = selected.defaultPrice;
          recalculate();
        });
        row.querySelector("[data-remove-proposal-item]")?.addEventListener("click", () => {
          row.remove();
          recalculate();
        });
    };
    const bindRows = () => {
      itemsRoot.querySelectorAll("[data-proposal-item]").forEach(bindRow);
    };
    bindRows();
    recalculate();
    document.getElementById("addTenderProposalItem")?.addEventListener("click", () => {
      const index = itemsRoot.querySelectorAll("[data-proposal-item]").length;
      itemsRoot.insertAdjacentHTML("beforeend", itemRow({
        sourceKind: "MANUAL", sourceItemNumber: index + 1,
        sourceReference: "Inclusão manual — conferir no edital", description: "",
        unit: "UN", quantity: 1, referencePrice: null,
      }, index, context.escape, true));
      const row = itemsRoot.lastElementChild;
      bindRow(row);
      row.querySelector("[data-description]")?.focus();
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      status?.classList.add("hidden");
      const submit = form.querySelector('[type="submit"]');
      if (submit) submit.disabled = true;
      const items = [...itemsRoot.querySelectorAll("[data-proposal-item]")].map((row) => ({
        sourceKind: row.dataset.sourceKind,
        sourceItemNumber: row.querySelector("[data-source-number]").value,
        sourceReference: row.querySelector("[data-source-reference]").value,
        catalogRecordId: row.querySelector("[data-catalog]").value || null,
        description: row.querySelector("[data-description]").value,
        unit: row.querySelector("[data-unit]").value,
        quantity: row.querySelector("[data-quantity]").value,
        referencePrice: row.dataset.referencePrice || null,
        unitCost: row.querySelector("[data-cost]").value,
        minimumUnitPrice: row.querySelector("[data-floor]").value,
        unitPrice: row.querySelector("[data-price]").value,
      }));
      try {
        await actions.api(`/api/tenders/results/${form.dataset.tenderId}/commercial-proposal`, {
          method: "PUT", body: JSON.stringify({
            expectedVersion: Number(form.dataset.version), items,
            commercial: {
              validityDays: form.elements.validityDays.value,
              deliveryTerms: form.elements.deliveryTerms.value,
              paymentTerms: form.elements.paymentTerms.value,
              warrantyTerms: form.elements.warrantyTerms.value,
              notes: form.elements.notes.value,
            },
          }),
        });
        actions.toast("Nova versão da proposta salva.");
        await actions.reload();
      } catch (failure) { showError(failure); }
      finally { if (submit) submit.disabled = false; }
    });
    const postAction = async (action, payload = {}) => {
      status?.classList.add("hidden");
      try {
        await actions.api(`/api/tenders/results/${form.dataset.tenderId}/commercial-proposal/${action}`, {
          method: "POST", body: JSON.stringify({ expectedVersion: Number(form.dataset.version), ...payload }),
        });
        actions.toast("Fluxo da proposta atualizado.");
        await actions.reload();
      } catch (failure) { showError(failure); }
    };
    form.querySelector('[data-proposal-action="submit"]')?.addEventListener("click", () => postAction("submit"));
    form.querySelector('[data-proposal-action="withdraw"]')?.addEventListener("click", () => {
      if (confirm("Retirar esta versão da fila de aprovação?")) postAction("withdraw", { comment: "Retirada para revisão" });
    });
    form.querySelector('[data-proposal-action="reopen"]')?.addEventListener("click", () => {
      if (confirm("Abrir uma nova revisão? A versão aprovada permanecerá no histórico.")) postAction("reopen", { comment: "Nova revisão aberta" });
    });
    document.querySelectorAll("[data-proposal-decision]").forEach((button) => {
      button.addEventListener("click", () => {
        const comment = document.getElementById("tenderProposalDecisionComment")?.value.trim() || "";
        if (comment.length < 3) return showError(new Error("Registre um parecer antes de decidir."));
        const decision = button.dataset.proposalDecision;
        const verb = decision === "APPROVED" ? "aprovar" : "devolver";
        if (confirm(`Confirma ${verb} exatamente esta versão da proposta?`)) postAction("decision", { decision, comment });
      });
    });
    form.querySelector("[data-proposal-package]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const response = await fetch(`/api/tenders/results/${form.dataset.tenderId}/commercial-proposal-package`, { credentials: "same-origin" });
        if (!response.ok) {
          const failure = await response.json().catch(() => ({}));
          throw new Error(failure.message || "Não foi possível gerar o pacote comercial.");
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `licitacao-${form.dataset.tenderId}-proposta-v${form.dataset.version}.zip`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        actions.toast("Pacote comercial aprovado gerado.");
      } catch (failure) { showError(failure); }
      finally { button.disabled = false; }
    });
  }

  window.SIVSTenderProposal = { detailHTML, bindDetail };
})();
