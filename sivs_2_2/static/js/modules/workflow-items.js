(function workflowItemsModule(global) {
  "use strict";

  const SUPPORTED = new Set([
    "propostas", "vendas", "solicitacoes_compra", "pedidos_compra", "ordens_servico",
  ]);
  const $ = (selector) => document.querySelector(selector);
  let context = null;
  let snapshot = null;

  function supports(module) {
    return SUPPORTED.has(module);
  }

  function quantity(value) {
    return Number(value || 0).toLocaleString("pt-BR", { maximumFractionDigits: 6 });
  }

  function setFeedback(message = "", kind = "") {
    const area = $("#documentItemsFeedback");
    if (!area) return;
    area.textContent = message;
    area.className = `document-items-feedback${kind ? ` ${kind}` : ""}`;
  }

  function syncRecord(totals, revision) {
    if (!context?.record || !totals) return;
    const amount = totals.itemCount ? totals.totalCents / 100 : null;
    context.record.revision = revision;
    context.record.amount = amount;
    if (context.state.currentRecord?.id === context.record.id) {
      context.state.currentRecord.revision = revision;
      context.state.currentRecord.amount = amount;
    }
    const amountField = $("#recordForm")?.elements.amount;
    if (amountField) {
      amountField.value = amount == null ? "" : Number(amount).toLocaleString("pt-BR", {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      });
      amountField.readOnly = totals.itemCount > 0;
      amountField.title = totals.itemCount > 0
        ? "Total calculado automaticamente pelos itens" : "";
    }
  }

  function renderItems() {
    if (!snapshot || !context) return;
    const { escapeHTML, money } = context;
    const list = $("#documentItemsList");
    const canManage = snapshot.canManage;
    list.innerHTML = snapshot.items.length ? snapshot.items.map((item) => {
      const reserved = item.reservationStatus === "ACTIVE";
      const fulfilled = item.reservationStatus === "FULFILLED";
      const received = Boolean(item.receiptMovementId);
      const stockLocked = reserved || fulfilled || received;
      const kind = item.itemKind === "PRODUCT" ? "Produto" : "Serviço";
      const storage = item.itemKind === "PRODUCT"
        ? `${item.warehouseName || "Depósito a definir"}${item.lot ? ` · lote ${item.lot}` : ""}`
        : "Sem movimentação de estoque";
      return `<article class="document-item-row">
        <span class="document-item-kind ${item.itemKind.toLowerCase()}">${kind}</span>
        <div class="document-item-description"><strong>${escapeHTML(item.description)}</strong><small>${escapeHTML(item.catalog_title || "Catálogo")} · ${escapeHTML(storage)}</small></div>
        <div class="document-item-quantity"><span>${quantity(item.quantity)} × ${money(item.unitPrice)}</span>${item.discount ? `<small>− ${money(item.discount)} desconto</small>` : ""}</div>
        <strong class="document-item-value">${money(item.total)}</strong>
        <div class="document-item-state">${received ? `<span class="status green">${Number(item.remainingQuantity || 0) ? `Recebido ${quantity(item.receivedQuantity)}/${quantity(item.quantity)}` : "Recebido"}</span>` : fulfilled ? '<span class="status green">Baixado</span>' : reserved ? '<span class="status pendente">Reservado</span>' : item.itemKind === "PRODUCT" ? '<span class="status">Não movimentado</span>' : ""}</div>
        ${canManage ? `<div class="document-item-actions"><button type="button" class="text-button" data-edit-document-item="${item.id}" ${stockLocked ? "disabled" : ""}>Editar</button><button type="button" class="text-button danger" data-delete-document-item="${item.id}" ${stockLocked ? "disabled" : ""}>Excluir</button></div>` : ""}
      </article>`;
    }).join("") : '<div class="document-items-empty"><strong>Nenhum item incluído.</strong><span>Adicione produtos e serviços para formar o total deste documento.</span></div>';
    $("#documentItemsSubtotal").textContent = money(snapshot.totals.subtotalCents / 100);
    $("#documentItemsDiscount").textContent = money(snapshot.totals.discountCents / 100);
    $("#documentItemsTotal").textContent = money(snapshot.totals.totalCents / 100);
    $("#addDocumentItem").classList.toggle("hidden", !canManage);
    const productCount = snapshot.items.filter((item) => item.itemKind === "PRODUCT").length;
    const fulfilledCount = snapshot.fulfilledReservations || 0;
    const receivedCount = snapshot.receivedItems || 0;
    const actions = $("#documentInventoryActions");
    if (snapshot.module === "pedidos_compra" && productCount) {
      const pendingProducts = snapshot.items.filter((item) => item.itemKind === "PRODUCT" && Number(item.remainingQuantity || 0) > 0);
      actions.innerHTML = `
        ${snapshot.canReceive && pendingProducts.length ? `<div class="receipt-quantities"><strong>Recebimento físico</strong><small>Informe somente o que chegou. O saldo continua pendente no pedido.</small>${pendingProducts.map((item) => `<label>${escapeHTML(item.description)}<input type="number" inputmode="decimal" min="0.000001" max="${item.remainingQuantity}" step="0.000001" value="${item.remainingQuantity}" data-receipt-quantity="${item.id}"><small>Saldo: ${quantity(item.remainingQuantity)}</small></label>`).join("")}</div><button type="button" class="primary" data-document-stock="receive-items">Registrar recebimento</button>` : ""}
        <small>${receivedCount}/${productCount} produto(s) já registrados no histórico de estoque</small>`;
    } else if ((snapshot.canReserve || snapshot.canRelease || snapshot.canFulfill) && productCount) {
      actions.innerHTML = `
      ${snapshot.canReserveNow && !fulfilledCount && snapshot.activeReservations < productCount ? '<button type="button" class="primary" data-document-stock="reserve-items">Reservar estoque</button>' : ""}
      ${snapshot.canFulfill && snapshot.activeReservations === productCount ? '<button type="button" class="primary" data-document-stock="fulfill-items">Baixar estoque</button>' : ""}
      ${snapshot.canRelease && snapshot.activeReservations ? '<button type="button" class="secondary" data-document-stock="release-items">Liberar reservas</button>' : ""}
      <small>${fulfilledCount ? `${fulfilledCount}/${productCount} produto(s) baixado(s)` : `${snapshot.activeReservations}/${productCount} produto(s) reservado(s)`}</small>`;
    } else {
      actions.innerHTML = productCount
        ? '<small>A movimentação ocorrerá no pedido de compra, venda ou O.S. correspondente.</small>' : "";
    }
    list.querySelectorAll("[data-edit-document-item]").forEach((button) => {
      button.onclick = () => openItem(snapshot.items.find((item) => item.id === Number(button.dataset.editDocumentItem)));
    });
    list.querySelectorAll("[data-delete-document-item]").forEach((button) => {
      button.onclick = () => removeItem(snapshot.items.find((item) => item.id === Number(button.dataset.deleteDocumentItem)));
    });
    actions.querySelectorAll("[data-document-stock]").forEach((button) => {
      button.onclick = () => changeReservations(button.dataset.documentStock);
    });
    syncRecord(snapshot.totals, snapshot.recordRevision);
  }

  function populateCatalog(selectedId = "") {
    const form = $("#documentItemForm");
    const kind = form.elements.itemKind.value;
    const module = kind === "PRODUCT" ? "produtos" : "catalogo_servicos";
    const options = (snapshot?.catalog || []).filter((item) => item.module === module);
    form.elements.catalogRecordId.innerHTML = '<option value="">Selecione no catálogo autorizado</option>'
      + options.map((item) => `<option value="${item.id}" ${Number(selectedId) === item.id ? "selected" : ""}>${context.escapeHTML(item.code ? `${item.code} · ${item.title}` : item.title)}</option>`).join("");
    const product = kind === "PRODUCT";
    $("#documentItemWarehouseField").classList.toggle("hidden", !product);
    $("#documentItemLotField").classList.toggle("hidden", !product);
    form.elements.warehouseId.disabled = !product;
    form.elements.lot.disabled = !product;
  }

  function populateWarehouses(selectedId = "") {
    const select = $("#documentItemForm").elements.warehouseId;
    select.innerHTML = '<option value="">Definir antes da reserva</option>'
      + (snapshot?.warehouses || []).map((warehouse) => `<option value="${warehouse.id}" ${Number(selectedId) === warehouse.id ? "selected" : ""}>${context.escapeHTML(`${warehouse.code} · ${warehouse.name}`)}</option>`).join("");
  }

  function selectedCatalogChanged() {
    const form = $("#documentItemForm");
    const selected = snapshot?.catalog.find((item) => item.id === Number(form.elements.catalogRecordId.value));
    if (!selected) return;
    if (!form.elements.description.value.trim()) form.elements.description.value = selected.title;
    if (!form.elements.unitPrice.value.trim() && Number(selected.defaultUnitPrice || 0) > 0) {
      form.elements.unitPrice.value = Number(selected.defaultUnitPrice).toLocaleString("pt-BR", {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      });
    }
  }

  function openItem(item = null) {
    if (!snapshot?.canManage) return;
    const form = $("#documentItemForm");
    form.reset();
    form.elements.itemId.value = item?.id || "";
    form.elements.itemRevision.value = item?.revision || "";
    form.elements.itemKind.value = item?.itemKind || "PRODUCT";
    populateCatalog(item?.catalogRecordId || "");
    populateWarehouses(item?.warehouseId || "");
    form.elements.description.value = item?.description || "";
    form.elements.quantity.value = item?.quantity || 1;
    form.elements.unitPrice.value = item ? Number(item.unitPrice).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "";
    form.elements.discount.value = item?.discount ? Number(item.discount).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "";
    form.elements.lot.value = item?.lot || "";
    form.elements.notes.value = item?.notes || "";
    $("#documentItemDialogTitle").textContent = item ? "Editar item do documento" : "Adicionar produto ou serviço";
    $("#documentItemError").classList.add("hidden");
    $("#documentItemDialog").showModal();
    requestAnimationFrame(() => form.elements.itemKind.focus());
  }

  async function saveItem(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const error = $("#documentItemError");
    if (!form.reportValidity()) return;
    const itemId = Number(form.elements.itemId.value || 0);
    const body = {
      recordRevision: context.record.revision,
      itemRevision: Number(form.elements.itemRevision.value || 0) || undefined,
      itemKind: form.elements.itemKind.value,
      catalogRecordId: Number(form.elements.catalogRecordId.value),
      description: form.elements.description.value.trim(),
      quantity: form.elements.quantity.value,
      unitPrice: form.elements.unitPrice.value,
      discount: form.elements.discount.value || "0",
      warehouseId: form.elements.warehouseId.disabled ? null : (Number(form.elements.warehouseId.value) || null),
      lot: form.elements.lot.disabled ? "" : form.elements.lot.value.trim(),
      notes: form.elements.notes.value.trim(),
    };
    error.classList.add("hidden");
    try {
      const result = await context.api(
        itemId ? `/api/records/${context.record.id}/items/${itemId}` : `/api/records/${context.record.id}/items`,
        { method: itemId ? "PUT" : "POST", body: JSON.stringify(body) },
      );
      syncRecord(result.totals, result.recordRevision);
      context.dismissDialog($("#documentItemDialog"));
      context.toast(itemId ? "Item atualizado e total recalculado." : "Item adicionado e total recalculado.");
      await refresh();
    } catch (failure) {
      error.textContent = failure.message;
      error.classList.remove("hidden");
    }
  }

  async function removeItem(item) {
    if (!item || !global.confirm(`Excluir “${item.description}” deste documento?`)) return;
    try {
      const result = await context.api(`/api/records/${context.record.id}/items/${item.id}`, {
        method: "DELETE",
        body: JSON.stringify({ recordRevision: context.record.revision, itemRevision: item.revision }),
      });
      syncRecord(result.totals, result.recordRevision);
      context.toast("Item excluído e total recalculado.");
      await refresh();
    } catch (failure) {
      context.toast(failure.message);
    }
  }

  async function changeReservations(action) {
    const verbs = {
      "reserve-items": "reservar", "release-items": "liberar",
      "fulfill-items": "baixar definitivamente",
      "receive-items": "receber",
    };
    const verb = verbs[action];
    const receiptItems = action === "receive-items" ? Array.from(
      document.querySelectorAll("[data-receipt-quantity]"),
    ).filter((input) => Number(input.value) > 0).map((input) => ({
      itemId: Number(input.dataset.receiptQuantity), quantity: input.value,
    })) : null;
    if (action === "receive-items" && !receiptItems.length) {
      setFeedback("Informe ao menos uma quantidade recebida.", "error");
      return;
    }
    const confirmation = action === "receive-items"
      ? "Confirmar a entrada física informada? Esta operação atualiza estoque e custo médio."
      : `Deseja ${verb} o estoque de todos os produtos deste documento?`;
    if (!global.confirm(confirmation)) return;
    const feedback = {
      "reserve-items": "Reservando produtos em uma transação única…",
      "release-items": "Liberando reservas…",
      "fulfill-items": "Registrando a saída dos produtos no estoque…",
      "receive-items": "Registrando a entrada dos produtos no estoque…",
    };
    setFeedback(feedback[action]);
    try {
      const result = await context.api(`/api/records/${context.record.id}/${action}`, {
        method: "POST", body: action === "receive-items" ? JSON.stringify({ items: receiptItems }) : "{}",
      });
      if (action === "receive-items" && result.recordRevision) {
        context.record.revision = result.recordRevision;
        context.record.status = result.status;
        if (context.state.currentRecord?.id === context.record.id) {
          context.state.currentRecord.revision = result.recordRevision;
          context.state.currentRecord.status = result.status;
        }
      }
      context.toast(`${result.items} item(ns) processado(s) no estoque.`);
      await refresh();
    } catch (failure) {
      setFeedback(failure.message, "error");
    }
  }

  async function refresh() {
    if (!context?.record) return;
    snapshot = await context.api(`/api/records/${context.record.id}/items`);
    renderItems();
    setFeedback("");
  }

  async function render(record, options) {
    const section = $("#recordDocumentItems");
    if (!section) return;
    if (!record || !supports(record.module)) {
      section.classList.add("hidden");
      const amountField = $("#recordForm")?.elements.amount;
      if (amountField) {
        amountField.readOnly = false;
        amountField.title = "";
      }
      return;
    }
    context = { ...options, record };
    snapshot = null;
    section.classList.remove("hidden");
    $("#documentItemsList").innerHTML = '<div class="document-items-empty">Carregando composição…</div>';
    $("#addDocumentItem").onclick = () => openItem();
    try {
      await refresh();
    } catch (failure) {
      setFeedback(failure.message, "error");
      $("#documentItemsList").innerHTML = '<div class="document-items-empty">Não foi possível carregar os itens.</div>';
    }
  }

  function bind() {
    const form = $("#documentItemForm");
    if (!form || form.dataset.workflowBound) return;
    form.dataset.workflowBound = "1";
    form.addEventListener("submit", saveItem);
    form.elements.itemKind.addEventListener("change", () => populateCatalog());
    form.elements.catalogRecordId.addEventListener("change", selectedCatalogChanged);
  }

  document.addEventListener("DOMContentLoaded", bind, { once: true });
  global.SIVSWorkflowItems = { render, supports };
})(window);
