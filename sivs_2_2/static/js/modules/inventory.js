(function initializeInventory(global) {
  const inventory = global.SIVSInventory ||= {};
  const movementLabels = {
    PURCHASE_IN: "Entrada por compra",
    SALE_OUT: "Saída por venda",
    SERVICE_ORDER_OUT: "Saída para ordem de serviço",
    RESERVE: "Reserva",
    RELEASE_RESERVATION: "Liberação de reserva",
    TRANSFER_IN: "Entrada por transferência",
    TRANSFER_OUT: "Transferência entre depósitos",
    RETURN_IN: "Entrada por devolução",
    RETURN_OUT: "Saída por devolução",
    ADJUSTMENT_IN: "Ajuste de entrada",
    ADJUSTMENT_OUT: "Ajuste de saída",
  };
  const originOptions = [
    ["PURCHASE_ORDER", "Pedido de compra"],
    ["SALES_ORDER", "Pedido de venda"],
    ["SERVICE_ORDER", "Ordem de serviço"],
    ["RETURN", "Devolução"],
    ["TRANSFER", "Transferência"],
    ["INVENTORY_ADJUSTMENT", "Ajuste inventariado"],
    ["INITIAL_BALANCE", "Saldo inicial conferido"],
  ];
  const editableMovements = [
    "PURCHASE_IN", "SALE_OUT", "SERVICE_ORDER_OUT", "TRANSFER_OUT",
    "RETURN_IN", "RETURN_OUT", "ADJUSTMENT_IN", "ADJUSTMENT_OUT",
  ];

  function quantity(value) {
    return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 6 }).format(Number(value || 0));
  }

  function currency(cents) {
    if (cents == null) return "—";
    return new Intl.NumberFormat("pt-BR", {
      style: "currency", currency: "BRL",
    }).format(Number(cents || 0) / 100);
  }

  function optionList(items, valueKey, label) {
    return items.map((item) => `<option value="${Number(item[valueKey])}">${label(item)}</option>`).join("");
  }

  function closeDialog(dialog) {
    if (global.SIVSUI?.closeDialog) global.SIVSUI.closeDialog(dialog);
    else dialog?.close();
  }

  function balanceTable(data, escapeHTML) {
    if (!data.balances.length) {
      return '<div class="empty">Nenhum saldo registrado. Faça uma entrada conferida para iniciar o ledger.</div>';
    }
    const valueHead = data.valueVisible ? "<th>Custo médio</th><th>Valor em estoque</th>" : "";
    return `<div class="table-wrap borderless"><table class="data-table inventory-table"><thead><tr><th>Produto</th><th>Depósito</th><th>Lote</th><th>Físico</th><th>Reservado</th><th>Disponível</th>${valueHead}</tr></thead><tbody>${data.balances.map((item) => `<tr><td class="title-cell"><strong>${escapeHTML(item.product_name)}</strong><small>${escapeHTML(item.product_code || "Sem código")} · ${escapeHTML(item.unit)}</small></td><td>${escapeHTML(item.warehouse_name)}</td><td>${escapeHTML(item.lot || "Sem lote")}</td><td>${quantity(item.physicalQuantity)}</td><td>${quantity(item.reservedQuantity)}</td><td><strong class="inventory-available">${quantity(item.availableQuantity)}</strong></td>${data.valueVisible ? `<td>${currency(item.averageUnitCostCents)}</td><td><strong>${currency(item.inventoryValueCents)}</strong><small>${currency(item.availableValueCents)} disponível</small></td>` : ""}</tr>`).join("")}</tbody></table></div>`;
  }

  function reservationRows(data, escapeHTML, canRelease) {
    const active = data.reservations.filter((item) => item.status === "ACTIVE");
    if (!active.length) return '<div class="empty">Nenhuma reserva ativa.</div>';
    return active.map((item) => `<div class="inventory-reservation"><span><strong>${escapeHTML(item.product_name)}</strong><small>${escapeHTML(item.warehouse_name)} · ${escapeHTML(item.lot || "Sem lote")} · ${escapeHTML(item.origin_type)} ${escapeHTML(item.origin_id)}</small></span><span><b>${quantity(item.quantity)}</b><small>${item.expires_at ? `Expira em ${escapeHTML(item.expires_at)}` : "Sem expiração"}</small></span>${canRelease ? `<button class="secondary" type="button" data-release-reservation="${Number(item.id)}">Liberar</button>` : ""}</div>`).join("");
  }

  function movementTable(data, escapeHTML, dateBR) {
    if (!data.movements.length) return '<div class="empty">O histórico de movimentações está vazio.</div>';
    const valueHead = data.valueVisible ? "<th>Custo</th><th>Efeito no valor</th>" : "";
    return `<div class="table-wrap borderless"><table class="data-table inventory-table inventory-history"><thead><tr><th>Data</th><th>Movimento</th><th>Produto</th><th>Depósito</th><th>Quantidade</th>${valueHead}<th>Origem</th><th>Responsável</th></tr></thead><tbody>${data.movements.map((item) => `<tr><td>${escapeHTML(dateBR(item.created_at, true))}</td><td><span class="status">${escapeHTML(movementLabels[item.movement_type] || item.movement_type)}</span>${item.reason ? `<small>${escapeHTML(item.reason)}</small>` : ""}</td><td class="title-cell"><strong>${escapeHTML(item.product_name)}</strong><small>${escapeHTML(item.product_code || "Sem código")} · ${escapeHTML(item.lot || "Sem lote")}</small></td><td>${escapeHTML(item.warehouse_name)}${item.counterpart_warehouse_name ? `<small>↔ ${escapeHTML(item.counterpart_warehouse_name)}</small>` : ""}</td><td>${quantity(item.quantity)}</td>${data.valueVisible ? `<td>${currency(item.unitCostCents)}</td><td class="${Number(item.valueDeltaCents) < 0 ? "inventory-value-out" : "inventory-value-in"}">${Number(item.valueDeltaCents) > 0 ? "+" : ""}${currency(item.valueDeltaCents)}<small>Saldo ${currency(item.balanceValueCents)}</small></td>` : ""}<td>${escapeHTML(item.origin_type)}<small>${escapeHTML(item.origin_id)}${item.reference ? ` · ${escapeHTML(item.reference)}` : ""}</small></td><td>${escapeHTML(item.created_by_name || "Sistema")}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function dialogs(data, escapeHTML) {
    const productOptions = optionList(data.products, "id", (item) => `${escapeHTML(item.code || "—")} · ${escapeHTML(item.title)}`);
    const warehouseOptions = optionList(data.warehouses.filter((item) => item.active), "id", (item) => `${escapeHTML(item.code)} · ${escapeHTML(item.name)}`);
    const branchOptions = optionList(data.branches.filter((item) => item.active), "id", (item) => `${escapeHTML(item.code)} · ${escapeHTML(item.name)}`);
    const reservationOptions = data.reservations.filter((item) => item.status === "ACTIVE").map((item) => `<option value="${Number(item.id)}" data-product="${Number(item.product_record_id)}" data-warehouse="${Number(item.warehouse_id)}" data-lot="${escapeHTML(item.lot || "")}" data-quantity="${Number(item.quantity)}" data-origin-type="${escapeHTML(item.origin_type)}" data-origin-id="${escapeHTML(item.origin_id)}">#${Number(item.id)} · ${escapeHTML(item.product_name)} · ${quantity(item.quantity)}</option>`).join("");
    const origins = originOptions.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
    const movements = editableMovements
      .filter((value) => data.valueVisible || !["PURCHASE_IN", "RETURN_IN", "ADJUSTMENT_IN"].includes(value))
      .map((value) => `<option value="${value}">${movementLabels[value]}</option>`).join("");
    return `
      <dialog id="inventoryWarehouseDialog" class="dialog small form-drawer" aria-labelledby="inventoryWarehouseTitle"><form id="inventoryWarehouseForm"><div class="dialog-head"><div><p class="eyebrow gold">ESTRUTURA</p><h2 id="inventoryWarehouseTitle">Novo depósito</h2></div><button type="button" class="icon-button" data-inventory-close aria-label="Fechar">×</button></div><div class="inventory-form-grid"><label class="field"><span>Unidade *</span><select name="branchId" required><option value="">Selecione</option>${branchOptions}</select></label><label class="field"><span>Código *</span><input name="code" maxlength="40" required placeholder="EX.: PECAS"></label><label class="field"><span>Nome *</span><input name="name" maxlength="160" required></label><label class="field"><span>Localização</span><input name="location" maxlength="240"></label></div><div class="dialog-actions"><button type="button" class="secondary" data-inventory-close>Cancelar</button><button type="submit" class="primary">Criar depósito</button></div></form></dialog>
      <dialog id="inventoryMovementDialog" class="dialog form-drawer" aria-labelledby="inventoryMovementTitle"><form id="inventoryMovementForm"><div class="dialog-head"><div><p class="eyebrow gold">LEDGER IMUTÁVEL</p><h2 id="inventoryMovementTitle">Registrar movimento</h2></div><button type="button" class="icon-button" data-inventory-close aria-label="Fechar">×</button></div><p class="compliance-note compact">O saldo não é editado diretamente. Esta operação cria um movimento auditável e atualiza quantidade e valor na mesma transação.</p><div class="inventory-form-grid"><label class="field"><span>Tipo *</span><select name="movementType" required>${movements}</select></label><label class="field"><span>Reserva a consumir</span><select name="reservationId"><option value="">Sem reserva</option>${reservationOptions}</select></label><label class="field"><span>Produto *</span><select name="productId" required><option value="">Selecione</option>${productOptions}</select></label><label class="field"><span>Depósito *</span><select name="warehouseId" required><option value="">Selecione</option>${warehouseOptions}</select></label><label class="field hidden" data-transfer-destination><span>Depósito de destino *</span><select name="counterpartWarehouseId"><option value="">Selecione</option>${warehouseOptions}</select></label><label class="field"><span>Lote</span><input name="lot" maxlength="120"></label><label class="field"><span>Quantidade *</span><input name="quantity" type="number" min="0.000001" step="0.000001" required></label><label class="field hidden" data-unit-cost><span>Custo unitário *</span><input name="unitCost" inputmode="decimal" placeholder="0,00"></label><label class="field"><span>Tipo de origem *</span><select name="originType" required><option value="">Selecione</option>${origins}</select></label><label class="field"><span>ID da origem *</span><input name="originId" maxlength="120" required placeholder="Ex.: PC-2026-0042"></label><label class="field"><span>Referência</span><input name="reference" maxlength="240"></label><label class="field full"><span>Justificativa do ajuste</span><textarea name="reason" rows="3" maxlength="500"></textarea></label></div><div class="dialog-actions"><button type="button" class="secondary" data-inventory-close>Cancelar</button><button type="submit" class="primary">Registrar movimento</button></div></form></dialog>
      <dialog id="inventoryReservationDialog" class="dialog form-drawer" aria-labelledby="inventoryReservationTitle"><form id="inventoryReservationForm"><div class="dialog-head"><div><p class="eyebrow gold">DISPONIBILIDADE</p><h2 id="inventoryReservationTitle">Nova reserva</h2></div><button type="button" class="icon-button" data-inventory-close aria-label="Fechar">×</button></div><div class="inventory-form-grid"><label class="field"><span>Produto *</span><select name="productId" required><option value="">Selecione</option>${productOptions}</select></label><label class="field"><span>Depósito *</span><select name="warehouseId" required><option value="">Selecione</option>${warehouseOptions}</select></label><label class="field"><span>Lote</span><input name="lot" maxlength="120"></label><label class="field"><span>Quantidade *</span><input name="quantity" type="number" min="0.000001" step="0.000001" required></label><label class="field"><span>Tipo de origem *</span><select name="originType" required><option value="SALES_ORDER">Pedido de venda</option><option value="SERVICE_ORDER">Ordem de serviço</option><option value="QUOTE">Orçamento aprovado</option></select></label><label class="field"><span>ID da origem *</span><input name="originId" maxlength="120" required></label><label class="field"><span>Expiração</span><input name="expiresAt" type="date"></label><label class="field"><span>Referência</span><input name="reference" maxlength="240"></label></div><div class="dialog-actions"><button type="button" class="secondary" data-inventory-close>Cancelar</button><button type="submit" class="primary">Reservar estoque</button></div></form></dialog>`;
  }

  function formBody(form) {
    return Object.fromEntries(new FormData(form));
  }

  inventory.load = async function loadInventory({ api, state, writable, canAction, escapeHTML, dateBR, toast }) {
    const content = document.querySelector("#content");
    const data = await api("/api/inventory");
    const abilities = {
      warehouse: canAction("estoque", "manage_warehouses"),
      movement: canAction("estoque", "move_stock"),
      reserve: canAction("estoque", "reserve_stock"),
      release: canAction("estoque", "release_stock"),
      values: data.valueVisible,
    };
    const activeReservations = data.reservations.filter((item) => item.status === "ACTIVE").length;
    const stockedItems = data.balances.filter((item) => Number(item.physicalQuantity) > 0).length;
    content.innerHTML = `<section class="inventory-hero"><div><p class="eyebrow gold">FONTE OPERACIONAL DE VERDADE</p><h2>Estoque por movimentação auditável</h2><p>Saldo físico, reservas, disponibilidade e custeio médio por produto, lote, depósito, unidade e empresa ativa.</p></div><div class="inventory-hero-actions">${abilities.warehouse ? '<button id="inventoryNewWarehouse" class="secondary" type="button">＋ Depósito</button>' : ""}${abilities.reserve ? '<button id="inventoryNewReservation" class="secondary" type="button">＋ Reserva</button>' : ""}${abilities.movement ? '<button id="inventoryNewMovement" class="primary" type="button">＋ Movimento</button>' : ""}</div></section>
      ${data.legacyRecordCount ? `<p class="compliance-note"><strong>Atenção:</strong> existem ${Number(data.legacyRecordCount)} registro(s) do estoque antigo preservados apenas para migração e consulta histórica. Eles não alteram os saldos do ledger.</p>` : ""}
      <section class="summary-strip inventory-summary"><div class="summary-item"><span>Depósitos ativos</span><strong>${data.warehouses.filter((item) => item.active).length}</strong></div><div class="summary-item"><span>Itens com saldo físico</span><strong>${stockedItems}</strong></div><div class="summary-item"><span>Reservas ativas</span><strong>${activeReservations}</strong></div>${abilities.values ? `<div class="summary-item"><span>Valor físico</span><strong>${currency(data.valuation.inventoryValueCents)}</strong></div><div class="summary-item"><span>Valor reservado</span><strong>${currency(data.valuation.reservedValueCents)}</strong></div><div class="summary-item"><span>Valor disponível</span><strong>${currency(data.valuation.availableValueCents)}</strong></div>` : ""}</section>
      ${abilities.values && data.valuation.unvaluedBalances ? `<p class="compliance-note"><strong>Custeio pendente:</strong> ${Number(data.valuation.unvaluedBalances)} saldo(s) físico(s) ainda não possuem valor. Revise entradas históricas antes de usar a margem gerencial.</p>` : ""}
      <section class="panel"><div class="panel-head"><div><h3>Saldos por depósito e lote</h3><small class="muted">Disponível = físico − reservado</small></div><span class="status">${data.balances.length} saldo(s)</span></div>${balanceTable(data, escapeHTML)}</section>
      <div class="inventory-grid"><section class="panel"><div class="panel-head"><div><h3>Reservas ativas</h3><small class="muted">Ligadas à origem comercial ou ordem de serviço</small></div><span class="status">${activeReservations}</span></div><div class="panel-body">${reservationRows(data, escapeHTML, abilities.release)}</div></section><section class="panel"><div class="panel-head"><div><h3>Depósitos</h3><small class="muted">Cada depósito pertence a uma unidade da empresa</small></div><span class="status">${data.warehouses.length}</span></div><div class="panel-body">${data.warehouses.map((item) => `<div class="inventory-warehouse"><span><strong>${escapeHTML(item.name)}</strong><small>${escapeHTML(item.code)} · ${escapeHTML(item.branch_name)}</small></span><span>${escapeHTML(item.location || "Localização não informada")}</span></div>`).join("")}</div></section></div>
      <section class="panel inventory-history-panel"><div class="panel-head"><div><h3>Histórico imutável</h3><small class="muted">Origem, responsável e efeitos em quantidade${abilities.values ? " e valor" : ""}</small></div><span class="status">Últimos ${data.movements.length}</span></div>${movementTable(data, escapeHTML, dateBR)}</section>
      ${writable ? dialogs(data, escapeHTML) : ""}`;

    if (!writable) return;
    const warehouseDialog = document.querySelector("#inventoryWarehouseDialog");
    const movementDialog = document.querySelector("#inventoryMovementDialog");
    const reservationDialog = document.querySelector("#inventoryReservationDialog");
    if (document.querySelector("#inventoryNewWarehouse")) document.querySelector("#inventoryNewWarehouse").onclick = () => warehouseDialog.showModal();
    if (document.querySelector("#inventoryNewMovement")) document.querySelector("#inventoryNewMovement").onclick = () => movementDialog.showModal();
    if (document.querySelector("#inventoryNewReservation")) document.querySelector("#inventoryNewReservation").onclick = () => reservationDialog.showModal();
    document.querySelectorAll("[data-inventory-close]").forEach((button) => {
      button.onclick = () => closeDialog(button.closest("dialog"));
    });

    const movementForm = document.querySelector("#inventoryMovementForm");
    const updateMovementFields = () => {
      const transfer = movementForm.movementType.value === "TRANSFER_OUT";
      const inbound = ["PURCHASE_IN", "RETURN_IN", "ADJUSTMENT_IN"].includes(movementForm.movementType.value);
      const target = movementForm.querySelector("[data-transfer-destination]");
      const cost = movementForm.querySelector("[data-unit-cost]");
      target.classList.toggle("hidden", !transfer);
      movementForm.counterpartWarehouseId.required = transfer;
      cost.classList.toggle("hidden", !inbound);
      movementForm.unitCost.required = inbound;
    };
    movementForm.movementType.onchange = updateMovementFields;
    movementForm.reservationId.onchange = () => {
      const selected = movementForm.reservationId.selectedOptions[0];
      if (!selected?.value) return;
      movementForm.productId.value = selected.dataset.product;
      movementForm.warehouseId.value = selected.dataset.warehouse;
      movementForm.lot.value = selected.dataset.lot;
      movementForm.quantity.value = selected.dataset.quantity;
      movementForm.originType.value = selected.dataset.originType;
      movementForm.originId.value = selected.dataset.originId;
    };
    updateMovementFields();

    document.querySelector("#inventoryWarehouseForm").onsubmit = async (event) => {
      event.preventDefault();
      try {
        await api("/api/inventory/warehouses", { method: "POST", body: JSON.stringify(formBody(event.currentTarget)) });
        closeDialog(warehouseDialog);
        toast("Depósito criado na unidade selecionada.");
        await inventory.load({ api, state, writable, canAction, escapeHTML, dateBR, toast });
      } catch (failure) { toast(failure.message); }
    };
    movementForm.onsubmit = async (event) => {
      event.preventDefault();
      try {
        await api("/api/inventory/movements", { method: "POST", body: JSON.stringify(formBody(event.currentTarget)) });
        closeDialog(movementDialog);
        toast("Movimento registrado e saldo atualizado.");
        await inventory.load({ api, state, writable, canAction, escapeHTML, dateBR, toast });
      } catch (failure) { toast(failure.message); }
    };
    document.querySelector("#inventoryReservationForm").onsubmit = async (event) => {
      event.preventDefault();
      try {
        await api("/api/inventory/reservations", { method: "POST", body: JSON.stringify(formBody(event.currentTarget)) });
        closeDialog(reservationDialog);
        toast("Estoque reservado com origem rastreável.");
        await inventory.load({ api, state, writable, canAction, escapeHTML, dateBR, toast });
      } catch (failure) { toast(failure.message); }
    };
    document.querySelectorAll("[data-release-reservation]").forEach((button) => {
      button.onclick = async () => {
        if (!global.confirm("Liberar esta reserva devolverá a quantidade ao saldo disponível. Continuar?")) return;
        try {
          await api(`/api/inventory/reservations/${button.dataset.releaseReservation}/release`, { method: "POST", body: "{}" });
          toast("Reserva liberada e histórico atualizado.");
          await inventory.load({ api, state, writable, canAction, escapeHTML, dateBR, toast });
        } catch (failure) { toast(failure.message); }
      };
    });
  };
})(window);
