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
  const supplyLabels = {
    UNDEFINED: "Defina o atendimento", STOCK: "Estoque disponível",
    PURCHASE: "Compra de fornecedor", MANUFACTURE: "Fabricação interna",
    MIXED: "Estoque + compra/fabricação", SERVICE_CAPACITY: "Capacidade de serviço",
    EXCEPTION: "Exceção justificada",
  };
  const costSourceLabels = {
    INVENTORY_AVERAGE: "custo médio do estoque",
    CATALOG_REFERENCE: "custo interno do catálogo",
    MANUAL_VALIDATED: "custo informado e sujeito à validação",
  };

  function catalogOptions(selectedId, escape) {
    return `<option value="">Sem vínculo com o catálogo</option>${(context?.catalog || []).map((item) => (
      `<option value="${item.id}" ${Number(selectedId) === Number(item.id) ? "selected" : ""}>${escape(`${item.code ? `${item.code} · ` : ""}${item.title} · ${item.module === "catalogo_servicos" ? "Serviço" : "Produto"}`)}</option>`
    )).join("")}`;
  }

  function supplyOptions(selected, escape) {
    return Object.entries(supplyLabels).map(([value, label]) => (
      `<option value="${value}" ${selected === value ? "selected" : ""}>${escape(label)}</option>`
    )).join("");
  }

  function catalogEvidence(item, escape) {
    if (!item.catalogRecordId && !item.suggestedCatalogRecordId) {
      return "Sem vínculo: exige justificativa explícita antes da aprovação.";
    }
    const catalog = (context?.catalog || []).find((entry) => (
      Number(entry.id) === Number(item.catalogRecordId || item.suggestedCatalogRecordId)
    ));
    const module = item.catalogModule || catalog?.module;
    const available = item.availableQuantity ?? catalog?.availableQuantity;
    const source = item.costSource || catalog?.costSource || "MANUAL_VALIDATED";
    if (module === "produtos") {
      return `Produto · disponível: ${available ?? 0} · ${costSourceLabels[source] || source}`;
    }
    return `Serviço · ${catalog?.category || "capacidade a confirmar"} · ${costSourceLabels[source] || source}`;
  }

  function itemRow(item, index, escape, editable) {
    const referencePrice = item.referencePrice == null ? "Não publicado" : money(item.referencePrice);
    return `<fieldset class="tender-proposal-item" data-proposal-item data-source-kind="${escape(item.sourceKind || "MANUAL")}" data-reference-price="${item.referencePrice ?? ""}">
      <legend><span>Item ${escape(item.sourceItemNumber || index + 1)}</span><small>${escape(sourceLabels[item.sourceKind] || sourceLabels.MANUAL)}</small></legend>
      <input type="hidden" data-source-number value="${escape(item.sourceItemNumber || index + 1)}">
      <div class="tender-proposal-item-grid">
        <label class="field proposal-description"><span>Descrição *</span><textarea data-description rows="2" maxlength="500" required ${editable ? "" : "disabled"}>${escape(item.description || "")}</textarea></label>
        <label class="field"><span>Produto ou serviço do catálogo</span><select data-catalog ${editable ? "" : "disabled"}>${catalogOptions(item.catalogRecordId || item.suggestedCatalogRecordId, escape)}</select><small data-catalog-evidence>${escape(catalogEvidence(item, escape))}</small></label>
        <label class="field"><span>Quantidade *</span><input data-quantity type="number" min="0.000001" step="0.000001" value="${escape(item.quantity || 1)}" required ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Unidade *</span><input data-unit maxlength="30" value="${escape(item.unit || "UN")}" required ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Custo unitário *</span><input data-cost type="number" min="0" step="0.01" value="${item.unitCost ?? ""}" placeholder="0,00" ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Piso unitário *</span><input data-floor type="number" min="0" step="0.01" value="${item.minimumUnitPrice ?? ""}" placeholder="Nunca abaixo do custo" ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Preço proposto *</span><input data-price type="number" min="0" step="0.01" value="${item.unitPrice ?? ""}" placeholder="0,00" ${editable ? "" : "disabled"}></label>
        <label class="field"><span>Forma de atendimento *</span><select data-supply-mode ${editable ? "" : "disabled"}>${supplyOptions(item.supplyMode || "UNDEFINED", escape)}</select></label>
        <label class="field proposal-supply-notes"><span>Plano de atendimento</span><input data-supply-notes maxlength="500" value="${escape(item.supplyNotes || "")}" placeholder="Compra, fabricação, equipe e prazo" ${editable ? "" : "disabled"}></label>
        <label class="field proposal-catalog-exception"><span>Justificativa se não houver catálogo</span><textarea data-catalog-exception rows="2" maxlength="500" ${editable ? "" : "disabled"}>${escape(item.catalogExceptionReason || "")}</textarea></label>
        <div class="proposal-reference-price"><span>Referência publicada</span><strong>${referencePrice}</strong></div>
        <label class="field proposal-reference"><span>Item/página ou origem no edital *</span><input data-source-reference maxlength="240" value="${escape(item.sourceReference || "")}" required ${editable ? "" : "disabled"}></label>
        <div class="proposal-line-total"><span>Total calculado</span><strong data-line-total>${money(number(item.quantity || 1) * number(item.unitPrice))}</strong></div>
        ${editable ? '<button class="secondary proposal-remove-item" type="button" data-remove-proposal-item aria-label="Remover item da proposta">Remover item</button>' : ""}
      </div>
    </fieldset>`;
  }

  function operationalHandoffHTML(data, tenderId, escape) {
    const handoff = data.operationalHandoff;
    if (handoff) {
      const purchase = handoff.purchaseRequestRecordId
        ? `<li><strong>Solicitação de compra #${escape(handoff.purchaseRequestRecordId)}</strong><span>${escape(handoff.purchaseRequestTitle)} · ${escape(handoff.purchaseRequestStatus)}</span></li>`
        : "";
      return `<section class="proposal-handoff completed" aria-labelledby="proposalHandoffTitle">
        <div><p class="eyebrow gold">EXECUÇÃO CONECTADA</p><h4 id="proposalHandoffTitle">A versão ${escape(handoff.proposalVersion)} já virou operação</h4><p>Os vínculos abaixo são imutáveis e preservam a fotografia aprovada.</p></div>
        <ul><li><strong>Cliente</strong><span>${escape(handoff.customerTitle)}</span></li><li><strong>Contrato #${escape(handoff.contractRecordId)}</strong><span>${escape(handoff.contractTitle)}</span></li><li><strong>${handoff.executionModule === "vendas" ? "Venda" : "Ordem de serviço"} #${escape(handoff.executionRecordId)}</strong><span>${escape(handoff.executionTitle)} · ${escape(handoff.executionStatus)}</span></li>${purchase}</ul>
        <small>Ao faturar a venda ou concluir a O.S., o sistema gera a conta a receber vinculada ao cliente e à origem.</small>
      </section>`;
    }
    const preparation = data.handoffPreparation || {};
    const handoffBlockers = (preparation.blockers || []).map((item) => `<li>${escape(item)}</li>`).join("");
    if (!preparation.canCreate) {
      return `<section class="proposal-handoff pending" aria-labelledby="proposalHandoffTitle"><div><p class="eyebrow gold">PRÓXIMA ETAPA</p><h4 id="proposalHandoffTitle">Contrato e execução ainda não materializados</h4><p>O sistema não cria documentos soltos: primeiro resolva estes marcos.</p></div>${handoffBlockers ? `<ul class="proposal-handoff-blockers">${handoffBlockers}</ul>` : ""}</section>`;
    }
    const customers = (preparation.customers || []).filter((item) => item.billingApproved);
    const customerOptions = customers.map((item) => `<option value="${item.id}">${escape(`${item.title}${item.document ? ` · ${item.document}` : ""}`)}</option>`).join("");
    const isService = preparation.executionModule === "ordens_servico";
    return `<section class="proposal-handoff ready" aria-labelledby="proposalHandoffTitle"><div><p class="eyebrow gold">LICITAÇÃO HOMOLOGADA</p><h4 id="proposalHandoffTitle">Gerar contrato e execução a partir da versão aprovada</h4><p>Uma única transação criará o contrato, ${isService ? "a O.S." : "a venda"}${preparation.needsPurchaseRequest ? " e a solicitação de compra" : ""}. Nenhum item será redigitado.</p></div>
      <form id="tenderOperationalHandoffForm" data-tender-id="${tenderId}" class="proposal-handoff-form">
        <label class="field"><span>Órgão/cliente validado *</span><select name="customerRecordId" required><option value="">Selecione o cadastro aprovado</option>${customerOptions}</select></label>
        <label class="field"><span>Número do contrato, ata ou empenho *</span><input name="instrumentNumber" maxlength="120" required placeholder="Número oficial do instrumento"></label>
        <label class="field"><span>Gestor do contrato *</span><input name="manager" maxlength="240" required></label>
        ${isService ? '<label class="field"><span>Responsável técnico inicial *</span><input name="technicalOwner" maxlength="240" required></label>' : '<input name="technicalOwner" type="hidden" value="">'}
        <label class="field"><span>Início da vigência *</span><input name="startDate" type="date" required></label>
        <label class="field"><span>Fim da vigência *</span><input name="endDate" type="date" required></label>
        <label class="field"><span>Primeiro vencimento previsto *</span><input name="billingDueDate" type="date" required><small>Poderá ser ajustado antes do faturamento conforme aceite ou medição.</small></label>
        <label class="field full"><span>Local de entrega ou execução *</span><input name="executionLocation" maxlength="500" required></label>
        <p class="form-error hidden full" data-handoff-error role="alert"></p>
        <div class="tender-proposal-actions full"><button class="primary" type="submit">Gerar fluxo operacional conectado</button></div>
      </form>
    </section>`;
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
    const operational = data.operationalLink || {};
    return `<section id="tenderCommercialProposal" class="tender-detail-section tender-commercial-proposal" aria-labelledby="tenderCommercialProposalTitle">
      <div class="panel-head"><div><p class="eyebrow gold">PROPOSTA COMERCIAL</p><h3 id="tenderCommercialProposalTitle">Composição, piso e aprovação</h3><small class="muted">${escape(data.notice || "Revisão humana obrigatória.")}</small></div><span class="tender-proposal-status ${status.toLowerCase()}">${escape(statusLabels[status] || status)}</span></div>
      <div class="proposal-operational-link ${operational.connected ? "connected" : "pending"}"><strong>${operational.connected ? `Conectada à Licitação #${escape(operational.recordId)}` : "Integração operacional pendente"}</strong><span>${operational.connected ? `${escape(operational.title)} · ${escape(operational.status)}` : "Converta esta oportunidade em Licitação antes de solicitar aprovação."}</span></div>
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
      ${operationalHandoffHTML(data, tenderId, escape)}
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
          if (!selected) {
            row.querySelector("[data-supply-mode]").value = "EXCEPTION";
            row.querySelector("[data-catalog-evidence]").textContent = "Sem vínculo: exige justificativa explícita antes da aprovação.";
            return;
          }
          if (!row.querySelector("[data-description]").value.trim()) row.querySelector("[data-description]").value = selected.title;
          if (!row.querySelector("[data-unit]").value.trim()) row.querySelector("[data-unit]").value = selected.unit || "UN";
          const cost = row.querySelector("[data-cost]");
          const floor = row.querySelector("[data-floor]");
          const price = row.querySelector("[data-price]");
          if (!cost.value && selected.defaultCost != null) cost.value = selected.defaultCost;
          if (!floor.value && selected.defaultCost != null) floor.value = selected.defaultCost;
          if (!price.value && number(selected.defaultPrice) > 0) price.value = selected.defaultPrice;
          row.querySelector("[data-supply-mode]").value = selected.module === "catalogo_servicos"
            ? "SERVICE_CAPACITY" : "UNDEFINED";
          row.querySelector("[data-catalog-evidence]").textContent = catalogEvidence({
            catalogRecordId: selected.id, catalogModule: selected.module,
            availableQuantity: selected.availableQuantity, costSource: selected.costSource,
          }, context.escape);
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
        supplyMode: row.querySelector("[data-supply-mode]").value,
        supplyNotes: row.querySelector("[data-supply-notes]").value,
        catalogExceptionReason: row.querySelector("[data-catalog-exception]").value,
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
    const handoffForm = document.getElementById("tenderOperationalHandoffForm");
    handoffForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const error = handoffForm.querySelector("[data-handoff-error]");
      const submit = handoffForm.querySelector('[type="submit"]');
      error?.classList.add("hidden");
      if (!confirm("Gerar contrato e documentos operacionais exatamente a partir desta versão aprovada? Esses vínculos não poderão ser trocados.")) return;
      submit.disabled = true;
      try {
        const payload = Object.fromEntries(new FormData(handoffForm).entries());
        const result = await actions.api(`/api/tenders/results/${handoffForm.dataset.tenderId}/operational-handoff`, {
          method: "POST", body: JSON.stringify(payload),
        });
        actions.toast(result.alreadyCreated
          ? "O fluxo operacional já estava criado; nenhum documento foi duplicado."
          : "Contrato e execução gerados com rastreabilidade integral.");
        await actions.reload();
      } catch (failure) {
        if (error) {
          error.textContent = failure.message || String(failure);
          error.classList.remove("hidden");
          error.scrollIntoView({ block: "center" });
        }
      } finally { submit.disabled = false; }
    });
  }

  window.SIVSTenderProposal = { detailHTML, bindDetail };
})();
