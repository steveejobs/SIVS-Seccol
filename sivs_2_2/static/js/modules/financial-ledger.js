(function financialLedgerModule(global) {
  "use strict";

  const SUPPORTED = new Set(["contas_pagar", "contas_receber"]);
  const ADJUSTMENT_LABELS = { DISCOUNT: "desconto", INTEREST: "juros ou multa", FEE: "tarifa" };
  const $ = (selector) => document.querySelector(selector);
  let context = null;
  let snapshot = null;
  let reversalEntryId = null;

  function supports(module) { return SUPPORTED.has(module); }
  function today() { return new Date().toISOString().slice(0, 10); }
  function cents(value) { return Number(value || 0) / 100; }

  function decimal(value) {
    const text = String(value || "").trim().replace(/\s/g, "");
    if (!text) return 0;
    const normalized = text.includes(",") ? text.replace(/\./g, "").replace(",", ".") : text;
    const number = Number(normalized);
    return Number.isFinite(number) ? number : 0;
  }

  function adjustmentText(entry) {
    const parts = [];
    if (entry.discount_cents) parts.push(`desconto ${context.money(cents(entry.discount_cents))}`);
    if (entry.interest_cents) parts.push(`juros ${context.money(cents(entry.interest_cents))}`);
    if (entry.fee_cents) parts.push(`tarifa ${context.money(cents(entry.fee_cents))}`);
    return parts.length ? ` · ${parts.join(" · ")}` : "";
  }

  function entryHTML(entry) {
    const reversal = entry.entry_type === "REVERSAL";
    const label = reversal ? "Estorno" : (snapshot.title.module === "contas_receber" ? "Recebimento" : "Pagamento");
    const reconcile = entry.reconciled
      ? '<span class="status green">Conciliado</span>'
      : '<span class="status">Não conciliado</span>';
    const canReverse = !reversal && !entry.reversed && context.canAction(snapshot.title.module, "reverse_financial");
    const reverseButton = canReverse
      ? `<button type="button" class="text-button" data-reverse-settlement="${entry.id}" ${entry.reconciled ? 'disabled title="Desfaça a conciliação antes de estornar"' : ""}>Estornar</button>` : "";
    return `<article class="financial-entry${reversal ? " reversal" : ""}">
      <div class="financial-entry-head">
        <div><strong>${label} · ${context.money(cents(entry.principal_cents))}</strong><small>${context.dateBR(entry.settled_at)} · ${context.escapeHTML(entry.account)} · ${context.escapeHTML(entry.payment_method)}${adjustmentText(entry)}</small></div>
        <div class="financial-entry-values"><strong>${context.money(cents(entry.cash_amount_cents))} no caixa</strong>${reconcile}${reverseButton}</div>
      </div>
      ${entry.note ? `<small>${context.escapeHTML(entry.note)}</small>` : ""}
      <small>Evento #${entry.id} · ${context.escapeHTML(entry.created_by_name || "Usuário do sistema")}${entry.reversed ? " · estornado" : ""}</small>
    </article>`;
  }

  function renderSnapshot() {
    const root = $("#recordFinancialLedger");
    if (!root || !snapshot) return;
    const canSettle = context.canAction(snapshot.title.module, "settle_financial")
      && snapshot.remainingCents > 0 && !["Cancelado", "Parcelado"].includes(snapshot.title.status);
    const canSplit = context.canAction(snapshot.title.module, "split_financial")
      && snapshot.settledCents === 0 && ["Em aberto", "Vencido"].includes(snapshot.title.status);
    const canReconcile = context.canAction("caixa", "reconcile_cash");
    const canManageBankAccounts = Boolean(snapshot.bankAccountsCanManage);
    root.innerHTML = `
      <header class="financial-ledger-head">
        <div><span class="eyebrow">MOVIMENTAÇÃO FINANCEIRA</span><h4 id="recordFinancialLedgerTitle">Saldo, baixas e caixa</h4><p>Eventos imutáveis; correções são feitas por estorno.</p></div>
        <div class="financial-ledger-actions">${canSettle ? '<button type="button" class="primary" data-open-settlement>Registrar baixa</button>' : ""}${canSplit ? '<button type="button" class="secondary" data-open-split>Parcelar tÃ­tulo</button>' : ""}${canReconcile ? '<button type="button" class="secondary" data-open-reconciliation>Conciliar extrato</button>' : ""}</div>
      </header>
      <div class="financial-summary-grid">
        <div><span>Valor do título</span><strong>${context.money(cents(snapshot.titleCents))}</strong></div>
        <div><span>Principal liquidado</span><strong>${context.money(cents(snapshot.settledCents))}</strong></div>
        <div><span>Saldo em aberto</span><strong>${context.money(cents(snapshot.remainingCents))}</strong></div>
      </div>
      <div class="financial-entry-list">${snapshot.entries.length ? snapshot.entries.map(entryHTML).join("") : '<div class="financial-empty">Nenhuma baixa registrada. O título ainda não movimentou o caixa.</div>'}</div>`;
    if (canManageBankAccounts) {
      root.querySelector(".financial-ledger-actions")?.insertAdjacentHTML(
        "beforeend", '<button type="button" class="secondary" data-open-bank-accounts>Contas bancárias</button>',
      );
    }
    root.querySelector("[data-open-settlement]")?.addEventListener("click", openSettlement);
    root.querySelector("[data-open-split]")?.addEventListener("click", openSplit);
    root.querySelector("[data-open-reconciliation]")?.addEventListener("click", openReconciliation);
    root.querySelector("[data-open-bank-accounts]")?.addEventListener("click", openBankAccounts);
    root.querySelectorAll("[data-reverse-settlement]").forEach((button) => {
      button.addEventListener("click", () => openReversal(Number(button.dataset.reverseSettlement)));
    });
  }

  function installmentRow(index) {
    return `<div class="financial-installment-row" data-installment-row><strong>${index + 1}</strong><label class="field"><span>Vencimento *</span><input name="dueDate" type="date" required></label><label class="field"><span>Valor *</span><input name="amount" inputmode="decimal" placeholder="0,00" required></label><button type="button" class="icon-button" data-remove-installment aria-label="Remover parcela ${index + 1}">Ã—</button></div>`;
  }

  function refreshInstallmentRows() {
    const rows = Array.from($("#financialInstallmentRows").children);
    rows.forEach((row, index) => {
      row.querySelector("strong").textContent = String(index + 1);
      row.querySelector("[data-remove-installment]").setAttribute("aria-label", `Remover parcela ${index + 1}`);
      row.querySelector("[data-remove-installment]").disabled = rows.length <= 2;
    });
    const entered = rows.reduce((total, row) => total + decimal(row.querySelector('[name="amount"]').value), 0);
    $("#financialSplitEntered").textContent = context.money(entered);
    const difference = cents(snapshot.titleCents) - entered;
    $("#financialSplitDifference").textContent = Math.abs(difference) < 0.005
      ? "Total conferido. As parcelas podem ser criadas."
      : `${difference > 0 ? "Falta distribuir" : "Excede em"} ${context.money(Math.abs(difference))}.`;
  }

  function appendInstallment() {
    const list = $("#financialInstallmentRows");
    if (list.children.length >= 60) return context.toast("O limite Ã© de 60 parcelas.");
    list.insertAdjacentHTML("beforeend", installmentRow(list.children.length));
    const row = list.lastElementChild;
    row.querySelector("[data-remove-installment]").addEventListener("click", () => { row.remove(); refreshInstallmentRows(); });
    row.querySelectorAll("input").forEach((input) => input.addEventListener("input", refreshInstallmentRows));
    refreshInstallmentRows();
  }

  function openSplit() {
    const form = $("#financialSplitForm");
    form.reset();
    $("#financialInstallmentRows").innerHTML = "";
    $("#financialSplitTotal").textContent = context.money(cents(snapshot.titleCents));
    $("#financialSplitError").classList.add("hidden");
    appendInstallment(); appendInstallment();
    $("#financialSplitDialog").showModal();
    $("#financialInstallmentRows input").focus();
  }

  async function submitSplit(event) {
    event.preventDefault();
    const error = $("#financialSplitError");
    error.classList.add("hidden");
    const installments = Array.from($("#financialInstallmentRows").children).map((row) => ({
      dueDate: row.querySelector('[name="dueDate"]').value, amount: row.querySelector('[name="amount"]').value,
    }));
    try {
      const result = await context.api(`/api/financial/titles/${snapshot.title.id}/installments`, {
        method: "POST", body: JSON.stringify({ revision: snapshot.title.revision, installments }),
      });
      context.dismissDialog($("#financialSplitDialog"));
      context.toast(`${result.installmentIds.length} parcelas criadas com auditoria.`);
      await refreshLedger();
    } catch (failure) {
      error.textContent = failure.message;
      error.classList.remove("hidden");
    }
  }

  function updateNetPreview() {
    const form = $("#financialSettlementForm");
    if (!form || !snapshot) return;
    const principal = decimal(form.elements.principal.value);
    const discount = decimal(form.elements.discount.value);
    const interest = decimal(form.elements.interest.value);
    const fee = decimal(form.elements.fee.value);
    const net = snapshot.title.module === "contas_receber"
      ? principal - discount + interest - fee
      : principal - discount + interest + fee;
    $("#financialNetValue").textContent = context.money(Math.max(0, net));
  }

  function openSettlement() {
    const form = $("#financialSettlementForm");
    form.reset();
    form.elements.principal.value = cents(snapshot.remainingCents).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    form.elements.date.value = today();
    form.elements.account.value = snapshot.title.payload?.conta || "Banco operacional";
    const bankSelect = form.elements.bankAccountId;
    if (bankSelect) {
      const accounts = Array.isArray(snapshot.bankAccounts) ? snapshot.bankAccounts : [];
      bankSelect.innerHTML = "";
      const manual = document.createElement("option");
      manual.value = "";
      manual.textContent = accounts.length ? "Usar descrição manual" : "Nenhuma conta cadastrada — usar descrição manual";
      bankSelect.appendChild(manual);
      accounts.forEach((account) => {
        const option = document.createElement("option");
        option.value = String(account.id);
        option.dataset.displayAccount = `${account.name} · final ${account.account_last4}`;
        option.textContent = `${account.name} · ${account.bank_name || `Banco ${account.bank_code}`} · agência ${account.branch_code} · final ${account.account_last4}`;
        bankSelect.appendChild(option);
      });
      const linked = snapshot.title.payload?.conta_bancaria_id;
      bankSelect.value = linked && accounts.some((account) => String(account.id) === String(linked)) ? String(linked) : "";
      const syncAccountField = () => {
        const option = bankSelect.selectedOptions[0];
        if (bankSelect.value && option?.dataset.displayAccount) {
          form.elements.account.value = option.dataset.displayAccount;
          form.elements.account.readOnly = true;
        } else {
          form.elements.account.readOnly = false;
        }
      };
      bankSelect.onchange = syncAccountField;
      syncAccountField();
    }
    form.elements.paymentMethod.value = snapshot.title.payload?.forma_pagamento || "PIX";
    $("#financialRemainingValue").textContent = context.money(cents(snapshot.remainingCents));
    $("#financialSettlementHint").textContent = snapshot.title.module === "contas_receber"
      ? "Desconto e tarifa reduzem a entrada; juros aumentam o recebimento."
      : "Desconto reduz a saída; juros e tarifa aumentam o pagamento.";
    const accountingHint = $("#financialAccountingAdjustmentHint");
    if (accountingHint) {
      const accounting = snapshot.accounting || {};
      const configured = new Set(accounting.adjustmentTypes || []);
      const missing = Object.keys(ADJUSTMENT_LABELS).filter((type) => !configured.has(type))
        .map((type) => ADJUSTMENT_LABELS[type]);
      if (!accounting.mapped) {
        accountingHint.textContent = "Sem mapeamento contábil ativo para esta categoria: a baixa movimenta financeiro e caixa, sem partida automática.";
      } else if (missing.length) {
        accountingHint.textContent = `Para usar ${missing.join(", ")}, configure contas próprias no mapeamento financeiro-contábil. Com ajuste sem conta, a baixa será recusada para não deixar o razão incompleto.`;
      } else {
        accountingHint.textContent = "As contas próprias de desconto, juros/multa e tarifa estão configuradas. A baixa e o estorno manterão financeiro, caixa e razão vinculados.";
      }
    }
    $("#financialSettlementError").classList.add("hidden");
    updateNetPreview();
    $("#financialSettlementDialog").showModal();
    form.elements.principal.focus();
  }

  async function submitSettlement(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const error = $("#financialSettlementError");
    error.classList.add("hidden");
    try {
      const result = await context.api(`/api/financial/titles/${snapshot.title.id}/settlements`, {
        method: "POST",
        body: JSON.stringify({
          revision: snapshot.title.revision,
          principal: form.elements.principal.value,
          discount: form.elements.discount.value,
          interest: form.elements.interest.value,
          fee: form.elements.fee.value,
          date: form.elements.date.value,
          account: form.elements.account.value,
          bankAccountId: form.elements.bankAccountId?.value || null,
          paymentMethod: form.elements.paymentMethod.value,
          note: form.elements.note.value,
        }),
      });
      snapshot = result;
      syncCurrentTitle(result.title);
      context.dismissDialog($("#financialSettlementDialog"));
      renderSnapshot();
      context.toast(result.remainingCents ? "Baixa parcial registrada; saldo atualizado." : "Título liquidado e caixa atualizado.");
    } catch (failure) {
      error.textContent = failure.message;
      error.classList.remove("hidden");
    }
  }

  function openReversal(entryId) {
    reversalEntryId = entryId;
    const form = $("#financialReversalForm");
    form.reset();
    form.elements.date.value = today();
    $("#financialReversalError").classList.add("hidden");
    $("#financialReversalDialog").showModal();
    form.elements.reason.focus();
  }

  async function submitReversal(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const error = $("#financialReversalError");
    error.classList.add("hidden");
    try {
      const result = await context.api(`/api/financial/settlements/${reversalEntryId}/reverse`, {
        method: "POST",
        body: JSON.stringify({ revision: snapshot.title.revision,
          date: form.elements.date.value, reason: form.elements.reason.value }),
      });
      snapshot = result;
      syncCurrentTitle(result.title);
      context.dismissDialog($("#financialReversalDialog"));
      renderSnapshot();
      context.toast("Baixa estornada; saldo e caixa foram recompostos.");
    } catch (failure) {
      error.textContent = failure.message;
      error.classList.remove("hidden");
    }
  }

  function syncCurrentTitle(title) {
    context.record = title;
    if (context.state.currentRecord?.id === title.id) context.state.currentRecord = title;
    const form = $("#recordForm");
    if (form) form.elements.status.value = title.status;
  }

  async function loadBankAccounts() {
    const list = $("#bankAccountList");
    if (!list) return;
    list.innerHTML = '<div class="financial-empty">Carregando contas…</div>';
    try {
      const data = await context.api("/api/bank-accounts");
      list.innerHTML = data.items.length ? data.items.map((account) => `
        <article class="bank-account-item"><div><strong>${context.escapeHTML(account.name)}</strong><small>${context.escapeHTML(account.bank_name || `Banco ${account.bank_code}`)} · agência ${context.escapeHTML(account.branch_code)} · final ${context.escapeHTML(account.account_last4)}</small></div><span class="status ${account.active ? "green" : ""}">${account.active ? "Ativa" : "Inativa"}</span></article>`).join("")
        : '<div class="financial-empty">Nenhuma conta cadastrada para esta empresa.</div>';
    } catch (failure) {
      list.innerHTML = `<div class="financial-empty">${context.escapeHTML(failure.message)}</div>`;
    }
  }

  async function openBankAccounts() {
    const dialog = $("#bankAccountDialog");
    const form = $("#bankAccountForm");
    if (!dialog || !form) return;
    form.reset();
    $("#bankAccountError").classList.add("hidden");
    dialog.showModal();
    await loadBankAccounts();
    form.elements.name.focus();
  }

  async function submitBankAccount(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const error = $("#bankAccountError");
    error.classList.add("hidden");
    try {
      await context.api("/api/bank-accounts", {
        method: "POST",
        body: JSON.stringify({
          name: form.elements.name.value,
          bankCode: form.elements.bankCode.value,
          bankName: form.elements.bankName.value,
          branchCode: form.elements.branchCode.value,
          accountNumber: form.elements.accountNumber.value,
          accountType: form.elements.accountType.value,
        }),
      });
      context.toast("Conta bancária cadastrada com proteção contra duplicidade.");
      context.dismissDialog($("#bankAccountDialog"));
      await refreshLedger();
    } catch (failure) {
      error.textContent = failure.message;
      error.classList.remove("hidden");
      await loadBankAccounts();
    }
  }

  async function openReconciliation() {
    $("#bankReconciliationDialog").showModal();
    await loadReconciliation();
  }

  async function loadReconciliation() {
    const list = $("#bankReconciliationList");
    list.innerHTML = '<div class="financial-empty">Carregando lançamentos…</div>';
    try {
      const data = await context.api("/api/bank-reconciliation");
      $("#bankReconciliationSummary").textContent = `${data.summary.matched} conciliado(s) · ${data.summary.pending} pendente(s)`;
      list.innerHTML = data.items.length ? data.items.map((item) => {
        const options = item.candidates.map((candidate) => `<option value="${candidate.id}">${context.escapeHTML(candidate.title)} · ${context.dateBR(candidate.due_date)}</option>`).join("");
        const actions = item.matched_cash_record_id
          ? `<div class="bank-statement-actions"><span class="status green">Conciliado</span><button type="button" class="secondary" data-unmatch-statement="${item.id}">Desfazer</button></div>`
          : options
            ? `<div class="bank-statement-actions"><select aria-label="Movimento de caixa para conciliar"><option value="">Selecione</option>${options}</select><button type="button" class="primary" data-match-statement="${item.id}">Confirmar</button></div>`
            : '<small>Nenhum caixa com mesmo valor, direção e data próxima.</small>';
        return `<article class="bank-statement-row"><div><strong>${context.dateBR(item.booking_date)}</strong><small>${item.direction === "IN" ? "Entrada" : "Saída"}</small></div><div><strong>${context.escapeHTML(item.memo || "Sem descrição")}</strong><small>${context.escapeHTML(item.external_id)}</small></div><strong>${context.money(cents(item.amount_cents))}</strong>${actions}</article>`;
      }).join("") : '<div class="financial-empty">Importe um extrato CSV para começar a conciliação.</div>';
      bindReconciliationRows();
    } catch (failure) {
      list.innerHTML = `<div class="financial-empty">${context.escapeHTML(failure.message)}</div>`;
    }
  }

  function bindReconciliationRows() {
    $("#bankReconciliationList").querySelectorAll("[data-match-statement]").forEach((button) => {
      button.onclick = async () => {
        const cashRecordId = Number(button.parentElement.querySelector("select").value);
        if (!cashRecordId) return context.toast("Selecione um movimento de caixa.");
        try {
          await context.api(`/api/bank-reconciliation/${button.dataset.matchStatement}/match`, {
            method: "POST", body: JSON.stringify({ cashRecordId }),
          });
          context.toast("Movimento conciliado.");
          await loadReconciliation();
          await refreshLedger();
        } catch (failure) { context.toast(failure.message); }
      };
    });
    $("#bankReconciliationList").querySelectorAll("[data-unmatch-statement]").forEach((button) => {
      button.onclick = async () => {
        try {
          await context.api(`/api/bank-reconciliation/${button.dataset.unmatchStatement}/unmatch`, { method: "POST", body: "{}" });
          context.toast("Conciliação desfeita com auditoria.");
          await loadReconciliation();
          await refreshLedger();
        } catch (failure) { context.toast(failure.message); }
      };
    });
  }

  async function importStatement(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const feedback = $("#bankReconciliationFeedback");
    feedback.className = "financial-feedback";
    feedback.textContent = "Validando e importando extrato…";
    try {
      const result = await context.api("/api/bank-reconciliation/import", {
        method: "POST", body: JSON.stringify({ filename: file.name, content: await file.text() }),
      });
      feedback.textContent = `${result.imported} lançamento(s) importado(s); ${result.duplicates} duplicado(s) ignorado(s).`;
      await loadReconciliation();
    } catch (failure) {
      feedback.textContent = failure.message;
      feedback.className = "financial-feedback error";
    }
  }

  async function refreshLedger() {
    if (!context?.record) return;
    snapshot = await context.api(`/api/financial/titles/${context.record.id}/settlements`);
    syncCurrentTitle(snapshot.title);
    renderSnapshot();
  }

  async function render(record, options) {
    const root = $("#recordFinancialLedger");
    if (!root) return;
    if (!record || !supports(record.module)) {
      root.classList.add("hidden");
      root.innerHTML = "";
      return;
    }
    context = { ...options, record };
    root.classList.remove("hidden");
    root.innerHTML = '<div class="financial-empty">Carregando histórico financeiro…</div>';
    try { await refreshLedger(); }
    catch (failure) { root.innerHTML = `<div class="financial-empty">${context.escapeHTML(failure.message)}</div>`; }
  }

  function bind() {
    const settlement = $("#financialSettlementForm");
    if (!settlement || settlement.dataset.bound) return;
    settlement.dataset.bound = "1";
    settlement.addEventListener("submit", submitSettlement);
    settlement.querySelectorAll("input").forEach((input) => input.addEventListener("input", updateNetPreview));
    $("#financialSplitForm").addEventListener("submit", submitSplit);
    $("#addFinancialInstallment").addEventListener("click", appendInstallment);
    $("#financialReversalForm").addEventListener("submit", submitReversal);
    $("#bankAccountForm").addEventListener("submit", submitBankAccount);
    $("#bankStatementFile").addEventListener("change", importStatement);
  }

  document.addEventListener("DOMContentLoaded", bind, { once: true });
  global.SIVSFinancialLedger = { render, supports };
})(window);
