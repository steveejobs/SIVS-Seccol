(() => {
  "use strict";

  let context = null;
  const money = (cents) => new Intl.NumberFormat("pt-BR", {
    style: "currency", currency: "BRL",
  }).format(Number(cents || 0) / 100);
  const labels = {
    SHADOW: "Simulacao segura", SUPERVISED: "Supervisionado", AUTONOMOUS: "Autonomo",
    PREPARED: "Preparado", ARMED: "Armado", PAUSED: "Pausado", CLOSED: "Encerrado",
    RUNNING: "Em execucao", AWAITING_MANUAL: "Aguardando confirmacao",
    COMPLETED: "Concluido", FAILED: "Falhou", CANCELLED: "Cancelado", QUEUED: "Na fila",
  };

  function portalOptions(data, selected, escape) {
    return (data.portals || []).map((portal) => (
      `<option value="${escape(portal.key)}" ${portal.key === selected ? "selected" : ""}>${escape(portal.label)}${portal.live ? "" : " (consulta)"}</option>`
    )).join("");
  }

  function detailHTML(data, tenderId, helpers = {}) {
    const escape = helpers.escapeHTML || ((value) => String(value ?? ""));
    if (!data || data.valuesRestricted) return "";
    const policy = data.policy;
    if (!policy) {
      return `<section class="tender-detail-section portal-agent" aria-labelledby="portalAgentTitle-${tenderId}">
        <div class="panel-head"><div><p class="eyebrow gold">AGENTE DE PORTAL</p><h3 id="portalAgentTitle-${tenderId}">Operacao conectada ao edital</h3></div><span class="status">Aguardando proposta</span></div>
        <p class="muted">O agente e preparado automaticamente depois da aprovacao independente da proposta. Sem essa fotografia, nenhum valor pode ser autorizado.</p>
      </section>`;
    }
    const blockers = policy.blockers || [];
    const lastRun = (data.runs || [])[0];
    const activeRun = (data.runs || []).find((run) => (
      ["QUEUED", "RUNNING", "AWAITING_MANUAL"].includes(run.status)
    ));
    const receipts = data.receipts || [];
    const canEdit = Boolean(data.canConfigure);
    return `<section class="tender-detail-section portal-agent" aria-labelledby="portalAgentTitle-${tenderId}">
      <div class="panel-head"><div><p class="eyebrow gold">AGENTE DE PORTAL</p><h3 id="portalAgentTitle-${tenderId}">Disputa governada pela proposta v${escape(policy.proposal_version)}</h3><small class="muted">A IA observa e sugere; o sistema valida piso, passo, janela e duplicidade no servidor.</small></div><span class="status ${policy.status === "ARMED" ? "ativo" : "pendente"}">${escape(labels[policy.status] || policy.status)}</span></div>
      <div class="portal-agent-guardrails" aria-label="Limites financeiros do agente"><div><span>Valor aprovado</span><strong>${money(policy.approved_total_cents)}</strong></div><div><span>Piso absoluto</span><strong>${money(policy.floor_total_cents)}</strong></div><div><span>Margem de disputa</span><strong>${money(policy.approved_total_cents - policy.floor_total_cents)}</strong></div><div><span>Lances autorizados</span><strong>${escape(lastRun?.authorized_bid_count || 0)} / ${escape(policy.maximum_bid_count)}</strong></div></div>
      ${blockers.length ? `<div class="portal-agent-blockers" role="alert"><strong>Antes de operar</strong><ul>${blockers.map((item) => `<li>${escape(item)}</li>`).join("")}</ul></div>` : ""}
      <form class="portal-agent-policy" data-portal-agent-policy="${tenderId}">
        <label class="field"><span>Portal operacional</span><select name="portalKey" ${canEdit ? "" : "disabled"}>${portalOptions(data, policy.portal_key, escape)}</select></label>
        <label class="field portal-url"><span>URL oficial da sessao do fornecedor</span><input name="portalUrl" type="url" inputmode="url" value="${escape(policy.portal_url || "")}" placeholder="https://..." required ${canEdit ? "" : "disabled"}></label>
        <label class="field"><span>Modo</span><select name="mode" ${canEdit ? "" : "disabled"}><option value="SHADOW" ${policy.mode === "SHADOW" ? "selected" : ""}>Simulacao segura</option><option value="SUPERVISED" ${policy.mode === "SUPERVISED" ? "selected" : ""}>Supervisionado</option><option value="AUTONOMOUS" ${policy.mode === "AUTONOMOUS" ? "selected" : ""}>Autonomo</option></select></label>
        <label class="field"><span>Passo minimo (R$)</span><input name="minimumStep" type="number" min="0.01" step="0.01" value="${escape(policy.minimum_step_cents / 100)}" required ${canEdit ? "" : "disabled"}></label>
        <label class="field"><span>Reducao maxima por lance (R$)</span><input name="maximumReduction" type="number" min="0.01" step="0.01" value="${escape(policy.maximum_reduction_cents / 100)}" required ${canEdit ? "" : "disabled"}></label>
        <label class="field"><span>Maximo de lances</span><input name="maximumBidCount" type="number" min="1" max="1000" value="${escape(policy.maximum_bid_count)}" required ${canEdit ? "" : "disabled"}></label>
        <label class="field"><span>Inicio autorizado</span><input name="validFrom" type="datetime-local" value="${escape((policy.valid_from || "").slice(0, 16))}" ${canEdit ? "" : "disabled"}></label>
        <label class="field"><span>Fim autorizado</span><input name="validUntil" type="datetime-local" value="${escape((policy.valid_until || "").slice(0, 16))}" ${canEdit ? "" : "disabled"}></label>
        <label class="field portal-authorization"><span>Referencia da autorizacao escrita</span><input name="writtenAuthorizationReference" maxlength="500" value="${escape(policy.written_authorization_reference || "")}" placeholder="Ata, aprovacao ou documento interno" ${canEdit ? "" : "disabled"}></label>
        <label class="check-row portal-agent-permission"><input name="allowProposalSubmission" type="checkbox" ${policy.allow_proposal_submission ? "checked" : ""} ${canEdit ? "" : "disabled"}><span><strong>Autorizar protocolo da proposta</strong><small>Somente no modo autonomo homologado.</small></span></label>
        <label class="check-row portal-agent-permission"><input name="allowLiveBidding" type="checkbox" ${policy.allow_live_bidding ? "checked" : ""} ${canEdit ? "" : "disabled"}><span><strong>Autorizar lances externos</strong><small>O piso e a janela continuam inviolaveis.</small></span></label>
        <input name="expectedRevision" type="hidden" value="${escape(policy.revision)}">
        ${canEdit ? '<button class="secondary" type="submit">Salvar limites</button>' : ""}
      </form>
      <div class="portal-agent-actions" aria-label="Controles do agente">
        ${data.canArm && policy.status !== "ARMED" ? `<button class="primary" type="button" data-portal-agent-action="${tenderId}:arm">Armar politica</button>` : ""}
        ${data.canArm && policy.status === "ARMED" ? `<button class="secondary" type="button" data-portal-agent-action="${tenderId}:pause">Pausar</button>` : ""}
        ${data.canOperate && policy.status === "ARMED" && !activeRun ? `<button class="primary" type="button" data-portal-agent-action="${tenderId}:start">Iniciar agente</button>` : ""}
      </div>
      <section class="portal-agent-live" aria-labelledby="portalAgentLive-${tenderId}">
        <div><p class="eyebrow gold">ACOMPANHAMENTO AO VIVO</p><h4 id="portalAgentLive-${tenderId}">Tela do navegador da VPS</h4><p class="muted">Acompanhe a sessao sem usar Linux. A visualizacao e registrada e o controle do navegador permanece bloqueado para espectadores.</p></div>
        ${data.viewerAvailable ? `<button class="secondary" type="button" data-portal-agent-viewer="${tenderId}" aria-expanded="false">Assistir sessao ao vivo</button>` : '<p class="portal-agent-viewer-offline" role="status">A visualizacao protegida ainda sera configurada na VPS.</p>'}
        <div class="portal-agent-viewer-frame" data-portal-agent-viewer-frame="${tenderId}" hidden></div>
      </section>
      ${data.canOperate && activeRun ? `<form class="portal-agent-evaluate" data-portal-agent-evaluate="${tenderId}"><div><strong>Simular evento completo da disputa</strong><small>${policy.mode === "SHADOW" ? "Nenhum clique externo sera executado." : "O servidor ainda aplicara todos os limites."}</small></div><label class="field"><span>Melhor lance atual (R$)</span><input name="currentBest" type="number" min="0.01" step="0.01" required></label><label class="field"><span>Sugestao da IA (R$, opcional)</span><input name="suggestedBid" type="number" min="0.01" step="0.01"></label><button class="primary" type="submit">Avaliar proximo lance</button><output data-portal-agent-result role="status" aria-live="polite"></output></form>` : ""}
      <div class="portal-agent-timeline"><div class="panel-head"><h4>Trilha imutavel</h4><span class="status">${receipts.length}</span></div>${receipts.length ? `<ol>${receipts.map((receipt) => `<li><span class="portal-agent-dot" aria-hidden="true"></span><div><strong>${escape(receipt.event_type === "BID_AUTHORIZED" ? "Lance autorizado" : "Etapa simulada")}</strong><span>${escape(receipt.command_action || "Agente")} ${receipt.authorized_value_cents ? `- ${money(receipt.authorized_value_cents)}` : ""}</span><small>${escape(receipt.created_at)} - efeito externo: ${receipt.external_effect ? "sim" : "nao"}</small></div></li>`).join("")}</ol>` : '<p class="muted">A execucao ainda nao produziu eventos.</p>'}</div>
      <p class="portal-agent-safety"><strong>Regra inviolavel:</strong> CAPTCHA, MFA, divergencia de sessao, mudanca do edital ou valor abaixo do piso interrompem o fluxo e exigem intervencao.</p>
    </section>`;
  }

  function bindDetail(nextContext) {
    context = nextContext;
    document.querySelectorAll("[data-portal-agent-policy]").forEach((form) => {
      form.onsubmit = async (event) => {
        event.preventDefault();
        const tenderId = form.dataset.portalAgentPolicy;
        const values = Object.fromEntries(new FormData(form).entries());
        try {
          await context.api(`/api/tenders/results/${tenderId}/portal-agent-policy`, {
            method: "PUT", body: JSON.stringify(values),
          });
          context.toast("Politica do agente atualizada e auditada.");
          await context.reload();
        } catch (failure) { context.toast(failure.message); }
      };
    });
    document.querySelectorAll("[data-portal-agent-action]").forEach((button) => {
      button.onclick = async () => {
        const [tenderId, action] = button.dataset.portalAgentAction.split(":");
        button.disabled = true;
        try {
          await context.api(`/api/tenders/results/${tenderId}/portal-agent/${action}`, {
            method: "POST", body: "{}",
          });
          context.toast("Estado do agente atualizado.");
          await context.reload();
        } catch (failure) { context.toast(failure.message); button.disabled = false; }
      };
    });
    document.querySelectorAll("[data-portal-agent-evaluate]").forEach((form) => {
      form.onsubmit = async (event) => {
        event.preventDefault();
        const output = form.querySelector("[data-portal-agent-result]");
        const tenderId = form.dataset.portalAgentEvaluate;
        const values = Object.fromEntries(new FormData(form).entries());
        values.phase = "DISPUTE_OPEN";
        values.idempotencyKey = `ui-${tenderId}-${Date.now()}-${crypto.getRandomValues(new Uint32Array(1))[0]}`;
        output.textContent = "Validando limites...";
        try {
          const response = await context.api(`/api/tenders/results/${tenderId}/portal-agent/evaluate`, {
            method: "POST", body: JSON.stringify(values),
          });
          output.textContent = `Autorizado: ${new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(response.authorizedValue)} (${response.executionState}).`;
          context.toast("Lance avaliado pelo guardrail financeiro.");
          window.setTimeout(() => context.reload(), 700);
        } catch (failure) { output.textContent = failure.message; context.toast(failure.message); }
      };
    });
    document.querySelectorAll("[data-portal-agent-viewer]").forEach((button) => {
      button.onclick = async () => {
        const tenderId = button.dataset.portalAgentViewer;
        const frame = document.querySelector(`[data-portal-agent-viewer-frame="${tenderId}"]`);
        if (!frame) return;
        if (!frame.hidden) {
          frame.replaceChildren();
          frame.hidden = true;
          button.textContent = "Assistir sessao ao vivo";
          button.setAttribute("aria-expanded", "false");
          return;
        }
        button.disabled = true;
        try {
          const response = await context.api(`/api/tenders/results/${tenderId}/portal-agent/viewer`, {
            method: "POST", body: "{}",
          });
          const viewerUrl = new URL(response.viewerUrl);
          if (viewerUrl.protocol !== "https:") throw new Error("Visualizacao protegida indisponivel.");
          const iframe = document.createElement("iframe");
          iframe.src = viewerUrl.href;
          iframe.title = "Acompanhamento ao vivo do navegador do agente";
          iframe.loading = "eager";
          iframe.referrerPolicy = "no-referrer";
          iframe.setAttribute("allow", "fullscreen");
          frame.replaceChildren(iframe);
          frame.hidden = false;
          button.textContent = "Fechar acompanhamento";
          button.setAttribute("aria-expanded", "true");
          context.toast("Visualizacao ao vivo aberta e registrada.");
        } catch (failure) {
          context.toast(failure.message || "Nao foi possivel abrir a visualizacao.");
        } finally { button.disabled = false; }
      };
    });
  }

  window.SIVSTenderPortalAgent = { detailHTML, bindDetail };
})();
