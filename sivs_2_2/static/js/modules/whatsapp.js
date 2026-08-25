(function initializeWhatsAppWorkspace(global) {
  "use strict";

  const text = (value) => global.SIVSCore.escapeHTML(String(value ?? ""));
  const operations = (data) => new Set(data.operations || []);
  let pollTimer = null;
  let qrCode = "";

  function isWindowOpen(conversation) {
    if (!conversation?.customer_window_expires_at) return false;
    return new Date(conversation.customer_window_expires_at).getTime() > Date.now();
  }

  function conversationList(items, selectedId, dateBR) {
    if (!items.length) return '<div class="whatsapp-empty"><strong>Nenhuma conversa acessível.</strong><p>Novos contatos aparecerão após a conexão do webhook oficial e respeitarão a sua fila de atendimento.</p></div>';
    return items.map((item) => `<button class="whatsapp-conversation ${item.id === selectedId ? "is-active" : ""}" type="button" data-whatsapp-conversation="${Number(item.id)}" aria-pressed="${item.id === selectedId}">
      <span class="whatsapp-avatar" aria-hidden="true">${text((item.contact_name || "W").slice(0, 1).toUpperCase())}</span>
      <span><strong>${text(item.contact_name || item.contact_wa_id)}</strong><small>${text(item.assigned_user_name || "Sem responsável")} · ${text(item.team)}</small><time>${text(dateBR(item.last_message_at, true))}</time></span>
      <i class="whatsapp-dot ${item.status === "OPEN" ? "is-open" : ""}" aria-label="${text(item.status)}"></i>
    </button>`).join("");
  }

  function messageList(items, dateBR) {
    if (!items.length) return '<div class="whatsapp-empty compact">A conversa ainda não possui mensagens armazenadas.</div>';
    return items.map((item) => `<article class="whatsapp-message ${item.direction === "OUTBOUND" ? "is-outbound" : "is-inbound"}">
      <p>${text(item.body)}</p>
      <footer><span>${item.direction === "OUTBOUND" ? text(item.sent_by_name || "SECCOL") : "Cliente"}</span><time>${text(dateBR(item.occurred_at, true))}</time>${item.direction === "OUTBOUND" ? `<span>${text(item.status)}</span>` : ""}</footer>
    </article>`).join("");
  }

  function quickReplyButtons(items) {
    if (!items.length) return '<span class="muted">Nenhuma resposta rápida ativa.</span>';
    return items.filter((item) => item.active).map((item) => `<button type="button" class="whatsapp-quick-button" data-quick-reply="${Number(item.id)}" data-quick-body="${text(item.body)}"><span>${text(item.category)}</span>${text(item.name)}</button>`).join("");
  }

  function templateManager(items) {
    return `<details class="whatsapp-template-manager"><summary>Biblioteca de respostas rápidas</summary>
      <div class="whatsapp-template-grid">
        <form id="whatsappQuickReplyForm" class="whatsapp-template-form">
          <label><span>Nome</span><input name="name" required maxlength="80" placeholder="Ex.: Primeiro contato"></label>
          <label><span>Categoria</span><select name="category"><option>COMERCIAL</option><option>ATENDIMENTO</option><option>FINANCEIRO</option></select></label>
          <label class="is-wide"><span>Texto</span><textarea name="body" required maxlength="1200" placeholder="Olá, {{nome}}! Sou {{vendedor}}…"></textarea></label>
          <p class="muted is-wide">Variáveis aceitas: {{nome}}, {{vendedor}} e {{referencia}}. Respostas rápidas não autorizam contato em massa: confirme finalidade, consentimento e pedido de descadastro.</p>
          <button class="primary" type="submit">Salvar resposta rápida</button>
        </form>
        <div class="whatsapp-template-list">${items.map((item) => `<article><div><span>${text(item.category)}</span><strong>${text(item.name)}</strong><p>${text(item.body)}</p></div><button class="secondary" type="button" data-toggle-quick="${Number(item.id)}" data-quick-active="${item.active ? "1" : "0"}" data-quick-name="${text(item.name)}" data-quick-category="${text(item.category)}" data-quick-body="${text(item.body)}">${item.active ? "Arquivar" : "Reativar"}</button></article>`).join("")}</div>
      </div>
    </details>`;
  }

  function integrationManager(data, allowed) {
    const instance = data.integration.instance;
    const canManage = allowed.has("manage_whatsapp_integration");
    if (!instance) return `<section class="whatsapp-setup" aria-labelledby="whatsappSetupTitle">
      <div><p class="eyebrow">CONEXÃO POR QR CODE</p><h3 id="whatsappSetupTitle">Conectar uma conta WhatsApp Business</h3><p>A instância será exclusiva desta empresa. O token permanece cifrado no servidor e nunca é enviado ao navegador.</p></div>
      ${canManage ? '<button id="whatsappCreateInstance" class="primary" type="button">Criar conexão</button>' : '<p class="muted">Solicite a conexão a um administrador.</p>'}
    </section>`;
    const statusLabel = { connected: "Conectada", connecting: "Aguardando leitura do QR", disconnected: "Desconectada", hibernated: "Hibernada", error: "Requer atenção", created: "Criada" }[instance.status] || instance.status;
    const qrSource = qrCode ? (qrCode.startsWith("data:image/") ? qrCode : `data:image/png;base64,${qrCode}`) : "";
    return `<section class="whatsapp-setup ${instance.isConnected ? "is-connected" : ""}" aria-labelledby="whatsappSetupTitle">
      <div class="whatsapp-setup-copy"><p class="eyebrow">INSTÂNCIA DA EMPRESA</p><h3 id="whatsappSetupTitle">${text(statusLabel)}</h3><p>${text(instance.profileName || instance.instanceName)}${instance.displayPhone ? ` · ${text(instance.displayPhone)}` : ""}</p>${instance.lastError ? `<small class="whatsapp-error">${text(instance.lastError)}</small>` : ""}</div>
      ${qrSource ? `<figure class="whatsapp-qr"><img src="${text(qrSource)}" alt="QR Code para conectar o WhatsApp"><figcaption>No celular: WhatsApp → Aparelhos conectados → Conectar aparelho.</figcaption></figure>` : ""}
      ${canManage ? `<div class="whatsapp-setup-actions">
        ${instance.isConnected ? '<button id="whatsappRefreshStatus" class="secondary" type="button">Atualizar status</button><button id="whatsappDisconnect" class="secondary" type="button">Desconectar</button>' : '<button id="whatsappConnect" class="primary" type="button">Gerar ou atualizar QR</button>'}
        ${instance.lastError ? '<button id="whatsappRetryWebhook" class="secondary" type="button">Tentar webhook</button>' : ""}
        <button id="whatsappDeleteInstance" class="danger" type="button">Remover instância</button>
      </div>` : ""}
    </section>`;
  }

  async function render(context, conversationId = null) {
    const { api, state, setHeader, dateBR, toast } = context;
    setHeader("CRM E ATENDIMENTO", "WhatsApp");
    const suffix = conversationId ? `?conversation=${encodeURIComponent(conversationId)}` : "";
    const data = await api(`/api/whatsapp/workspace${suffix}`);
    if (state.screen !== "whatsapp") return;
    if (pollTimer) { global.clearInterval(pollTimer); pollTimer = null; }
    const allowed = operations(data);
    const selected = data.selected;
    const windowOpen = isWindowOpen(selected);
    const integrationLabel = data.integration.connected ? "WhatsApp conectado" : (data.integration.configured ? "Conexão pendente" : "Aguardando configuração");
    const integrationClass = data.integration.connected ? "is-connected" : "is-pending";
    const assignedOptions = data.agents.map((item) => `<option value="${Number(item.id)}" ${selected?.assigned_user_id === item.id ? "selected" : ""}>${text(item.name)} · ${text(item.role)}</option>`).join("");

    document.getElementById("content").innerHTML = `<section class="whatsapp-workspace" aria-labelledby="whatsappWorkspaceTitle">
      <header class="whatsapp-hero">
        <div><p class="eyebrow gold">CAIXA DE ENTRADA COMPARTILHADA</p><h2 id="whatsappWorkspaceTitle">Conversas ligadas ao CRM</h2><p>Atenda, distribua e acompanhe contatos sem compartilhar senha ou aparelho. Cada ação respeita empresa, função e responsável.</p></div>
        <div class="whatsapp-integration ${integrationClass}"><i aria-hidden="true"></i><span><strong>${text(integrationLabel)}</strong><small>${text(data.integration.displayPhone || "uazapi · instância isolada por empresa")}</small></span></div>
      </header>
      ${integrationManager(data, allowed)}
      <div class="whatsapp-policy" role="note"><strong>Uso responsável</strong><span>Atendimento individual e esperado pelo cliente.</span><span>Marketing exige opt-in e descadastro.</span><span>Conexão por QR usa provedor intermediário; não é a Cloud API oficial da Meta.</span></div>
      <div class="whatsapp-layout">
        <aside class="whatsapp-inbox" aria-label="Conversas"><header><div><strong>Minha fila</strong><small>${data.conversations.length} conversa(s) acessível(is)</small></div><span class="status">CRM</span></header><div class="whatsapp-conversation-list">${conversationList(data.conversations, selected?.id, dateBR)}</div></aside>
        <section class="whatsapp-thread" aria-label="Conversa selecionada">
          ${selected ? `<header><div class="whatsapp-contact"><span class="whatsapp-avatar">${text((selected.contact_name || "W").slice(0, 1).toUpperCase())}</span><div><strong>${text(selected.contact_name || selected.contact_wa_id)}</strong><small>${text(selected.contact_wa_id)} · ${text(selected.team)}</small></div></div><div class="whatsapp-window ${windowOpen ? "is-open" : "is-closed"}"><strong>${windowOpen ? "Contato recente" : "Contato antigo"}</strong><small>${windowOpen ? `recebido até ${text(dateBR(selected.customer_window_expires_at, true))}` : "confirme consentimento e contexto antes de responder"}</small></div></header>
          <div class="whatsapp-messages" id="whatsappMessages">${messageList(data.messages, dateBR)}</div>
          <footer class="whatsapp-composer">${allowed.has("reply_whatsapp") ? `<div class="whatsapp-quick-row">${quickReplyButtons(data.quickReplies)}</div><form id="whatsappMessageForm"><label for="whatsappMessageText" class="visually-hidden">Mensagem</label><textarea id="whatsappMessageText" name="text" maxlength="4000" ${data.integration.connected ? "" : "disabled"} placeholder="${data.integration.connected ? "Escreva uma resposta…" : "Conecte a instância da empresa para responder."}"></textarea><button class="primary" type="submit" ${data.integration.connected ? "" : "disabled"}>Enviar</button></form>` : '<p class="muted">Seu acesso permite consultar, mas não responder esta conversa.</p>'}</footer>` : '<div class="whatsapp-empty thread-empty"><strong>Selecione uma conversa</strong><p>O histórico e o contexto comercial aparecerão aqui.</p></div>'}
        </section>
        <aside class="whatsapp-context" aria-label="Contexto e distribuição">
          <section><p class="eyebrow">CONTEXTO CRM</p><h3>${text(selected?.crm_title || "Nenhuma conversa selecionada")}</h3>${selected?.crm_record_id ? `<a class="secondary" href="#" data-open-crm="${Number(selected.crm_record_id)}">Abrir oportunidade no CRM</a>` : ""}</section>
          ${selected ? `<section><p class="eyebrow">RESPONSÁVEL</p><strong>${text(selected.assigned_user_name || "Sem responsável")}</strong><small>${text(selected.team)}</small>${!selected.assigned_user_id && allowed.has("claim_whatsapp") ? '<button id="whatsappClaim" class="primary" type="button">Assumir conversa</button>' : ""}${allowed.has("assign_whatsapp") ? `<form id="whatsappAssignmentForm"><label><span>Equipe</span><select name="team"><option ${selected.team === "COMERCIAL" ? "selected" : ""}>COMERCIAL</option><option ${selected.team === "FINANCEIRO" ? "selected" : ""}>FINANCEIRO</option><option ${selected.team === "GESTAO" ? "selected" : ""}>GESTAO</option></select></label><label><span>Pessoa</span><select name="assignedUserId"><option value="">Sem responsável</option>${assignedOptions}</select></label><button class="secondary" type="submit">Distribuir</button></form>` : ""}</section>` : ""}
          <section><p class="eyebrow">SEU ACESSO</p><div class="whatsapp-access-list">${[...allowed].map((item) => `<span>${text(item.replaceAll("_", " "))}</span>`).join("") || '<span>Somente leitura</span>'}</div></section>
        </aside>
      </div>
      ${allowed.has("manage_whatsapp_templates") ? templateManager(data.quickReplies) : ""}
    </section>`;

    const integrationAction = async (path, method = "POST") => {
      try {
        const result = await api(path, { method, body: method === "DELETE" ? undefined : "{}" });
        if (result?.qrcode) qrCode = result.qrcode;
        toast("Integração WhatsApp atualizada.");
        await render(context, selected?.id);
      } catch (error) { toast(error.message); }
    };
    document.getElementById("whatsappCreateInstance")?.addEventListener("click", () => integrationAction("/api/whatsapp/instance"));
    document.getElementById("whatsappConnect")?.addEventListener("click", () => integrationAction("/api/whatsapp/instance/connect"));
    document.getElementById("whatsappRefreshStatus")?.addEventListener("click", () => integrationAction("/api/whatsapp/instance/status", "GET"));
    document.getElementById("whatsappDisconnect")?.addEventListener("click", () => integrationAction("/api/whatsapp/instance/disconnect"));
    document.getElementById("whatsappRetryWebhook")?.addEventListener("click", () => integrationAction("/api/whatsapp/instance/webhook"));
    document.getElementById("whatsappDeleteInstance")?.addEventListener("click", async () => {
      if (!global.confirm("Remover a instância desta empresa? A sessão será apagada também na uazapi.")) return;
      qrCode = "";
      await integrationAction("/api/whatsapp/instance", "DELETE");
    });

    document.querySelectorAll("[data-whatsapp-conversation]").forEach((button) => {
      button.onclick = () => render(context, Number(button.dataset.whatsappConversation)).catch((error) => toast(error.message));
    });
    document.querySelectorAll("[data-quick-reply]").forEach((button) => {
      button.onclick = () => {
        const composer = document.getElementById("whatsappMessageText");
        const body = button.dataset.quickBody.replaceAll("{{nome}}", selected?.contact_name || "cliente")
          .replaceAll("{{vendedor}}", state.user.name).replaceAll("{{referencia}}", "");
        composer.value = body; composer.focus();
      };
    });
    document.getElementById("whatsappMessageForm")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = event.currentTarget.querySelector("button[type=submit]");
      submit.disabled = true;
      try {
        const random = global.crypto?.randomUUID?.().replaceAll("-", "") || `${Date.now()}_${Math.random().toString(36).slice(2)}`;
        await api(`/api/whatsapp/conversations/${selected.id}/messages`, { method: "POST", body: JSON.stringify({ text: event.currentTarget.elements.text.value, clientRequestId: random }) });
        toast("Mensagem aceita pelo WhatsApp e registrada na conversa.");
        await render(context, selected.id);
      } catch (error) { toast(error.message); submit.disabled = false; }
    });
    document.getElementById("whatsappClaim")?.addEventListener("click", async () => {
      try { await api(`/api/whatsapp/conversations/${selected.id}/claim`, { method: "POST", body: "{}" }); toast("Conversa atribuída a você."); await render(context, selected.id); } catch (error) { toast(error.message); }
    });
    document.getElementById("whatsappAssignmentForm")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      try { await api(`/api/whatsapp/conversations/${selected.id}/assignment`, { method: "POST", body: JSON.stringify({ team: event.currentTarget.elements.team.value, assignedUserId: event.currentTarget.elements.assignedUserId.value || null }) }); toast("Distribuição atualizada e auditada."); await render(context, selected.id); } catch (error) { toast(error.message); }
    });
    document.getElementById("whatsappQuickReplyForm")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      try { await api("/api/whatsapp/quick-replies", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))) }); toast("Resposta rápida salva."); await render(context, selected?.id); } catch (error) { toast(error.message); }
    });
    document.querySelectorAll("[data-toggle-quick]").forEach((button) => { button.onclick = async () => {
      try { await api(`/api/whatsapp/quick-replies/${button.dataset.toggleQuick}`, { method: "PUT", body: JSON.stringify({ name: button.dataset.quickName, category: button.dataset.quickCategory, body: button.dataset.quickBody, active: button.dataset.quickActive !== "1" }) }); toast("Biblioteca atualizada."); await render(context, selected?.id); } catch (error) { toast(error.message); }
    }; });
    document.querySelector("[data-open-crm]")?.addEventListener("click", (event) => {
      event.preventDefault();
      document.querySelector('[data-nav="crm"]')?.click();
    });
    document.getElementById("whatsappMessages")?.lastElementChild?.scrollIntoView({ block: "end" });
    if (allowed.has("manage_whatsapp_integration") && data.integration.instance && !data.integration.connected) {
      const previousStatus = data.integration.instance.status;
      pollTimer = global.setInterval(async () => {
        if (state.screen !== "whatsapp") { global.clearInterval(pollTimer); pollTimer = null; return; }
        try {
          const refreshed = await api("/api/whatsapp/instance/status");
          if (refreshed.instance?.isConnected || refreshed.instance?.status !== previousStatus) {
            if (refreshed.instance?.isConnected) qrCode = "";
            await render(context, selected?.id);
          }
        } catch (_error) { /* o painel mantém o último estado; ação manual mostra detalhes */ }
      }, 15000);
    }
  }

  global.SIVSWhatsApp = Object.freeze({ render });
})(window);
