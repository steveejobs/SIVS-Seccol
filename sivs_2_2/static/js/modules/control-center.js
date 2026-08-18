(function initializeControlCenter(global) {
  "use strict";

  const seenClientErrors = new Map();
  let refreshTimer = 0;

  function text(value) {
    return global.SIVSCore.escapeHTML(String(value ?? ""));
  }

  function bytes(value) {
    const amount = Number(value || 0);
    if (amount < 1024) return `${amount} B`;
    if (amount < 1024 ** 2) return `${(amount / 1024).toFixed(1)} KB`;
    if (amount < 1024 ** 3) return `${(amount / 1024 ** 2).toFixed(1)} MB`;
    return `${(amount / 1024 ** 3).toFixed(1)} GB`;
  }

  function duration(totalSeconds) {
    const seconds = Math.max(0, Number(totalSeconds || 0));
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return days ? `${days}d ${hours}h` : hours ? `${hours}h ${minutes}min` : `${minutes}min`;
  }

  function clientName(userAgent) {
    const value = String(userAgent || "");
    const browser = value.includes("Edg/") ? "Edge" : value.includes("Chrome/") ? "Chrome"
      : value.includes("Firefox/") ? "Firefox" : value.includes("Safari/") ? "Safari" : "Navegador";
    const device = /Android|iPhone|iPad|Mobile/i.test(value) ? "mobile" : "computador";
    return `${browser} · ${device}`;
  }

  function statusBadge(ok, yes, no) {
    return `<span class="control-state ${ok ? "is-ok" : "is-warning"}"><i aria-hidden="true"></i>${text(ok ? yes : no)}</span>`;
  }

  function sessionRows(items, dateBR) {
    if (!items.length) return '<div class="empty">Nenhuma sessão válida nesta empresa.</div>';
    const people = new Map();
    items.forEach((item) => {
      const key = String(item.userId);
      if (!people.has(key)) people.set(key, { user: item, sessions: [] });
      people.get(key).sessions.push(item);
    });
    return `<div class="control-people">${[...people.values()].map(({ user, sessions }) => {
      const online = sessions.some((item) => item.activeNow);
      const sessionLabel = `${sessions.length} ${sessions.length === 1 ? "sessão" : "sessões"}`;
      return `<article class="control-person">
        <header><div class="title-cell"><strong>${text(user.name)}</strong><small>${text(user.email)} · ${text(user.role)}</small></div><div class="control-person-state">${statusBadge(online, online ? "Online" : "Inativo", "Inativo")}<span class="status">${text(sessionLabel)}</span></div></header>
        <div class="table-wrap borderless"><table class="data-table control-table"><thead><tr><th>Estado da sessão</th><th>Última atividade</th><th>Origem</th><th>Ação</th></tr></thead><tbody>${sessions.map((item) => `<tr>
          <td>${statusBadge(item.activeNow, item.current ? "Você · online" : "Online", "Inativa")}</td>
          <td><time datetime="${text(item.lastActivityAt || "")}">${text(dateBR(item.lastActivityAt, true))}</time><small class="control-subline">Expira ${text(dateBR(item.expiresAt, true))}</small></td>
          <td><strong>${text(item.ipAddress)}</strong><small class="control-subline">${text(clientName(item.userAgent))}</small></td>
          <td>${item.current ? '<span class="muted">Sessão atual</span>' : `<button class="secondary" type="button" data-end-session="${text(item.id)}">Encerrar</button>`}</td>
        </tr>`).join("")}</tbody></table></div>
      </article>`;
    }).join("")}</div>`;
  }

  function eventRows(items, dateBR) {
    const open = items.filter((item) => !item.resolved_at);
    if (!items.length) return '<div class="empty">Nenhum erro técnico registrado nesta empresa.</div>';
    return `<div class="control-event-list">${items.slice(0, 30).map((item) => `<article class="control-event ${item.resolved_at ? "is-resolved" : ""}">
      <span class="control-severity severity-${text(item.severity)}">${text(item.severity)}</span>
      <div><strong>${text(item.message)}</strong><small>${text(item.category)} · ${text(item.event_type)} · ${text(dateBR(item.created_at, true))}</small>${item.request_id ? `<code>Ref. ${text(item.request_id)}</code>` : ""}</div>
      ${item.resolved_at ? '<span class="control-resolved">Resolvido</span>' : `<button class="secondary" type="button" data-resolve-event="${Number(item.id)}">Marcar resolvido</button>`}
    </article>`).join("")}</div><p class="muted control-list-note">${open.length} evento(s) ainda aberto(s).</p>`;
  }

  function changeRows(items, dateBR) {
    if (!items.length) return '<div class="empty">Nenhuma alteração auditada nesta empresa.</div>';
    return `<div class="control-change-list">${items.slice(0, 40).map((item) => `<article>
      <span class="control-action">${text(item.action)}</span>
      <div><strong>${text(item.user_name || "Sistema")}</strong><small>${text(item.entity_type)}${item.entity_id ? ` #${text(item.entity_id)}` : ""}</small></div>
      <time datetime="${text(item.created_at)}">${text(dateBR(item.created_at, true))}</time>
    </article>`).join("")}</div>`;
  }

  function requestRows(requests) {
    if (!requests.slowest?.length) return '<div class="empty">As métricas começam a aparecer após as primeiras requisições.</div>';
    return `<div class="table-wrap borderless"><table class="data-table control-table"><thead><tr><th>Rota</th><th>Status</th><th>Tempo</th></tr></thead><tbody>${requests.slowest.map((item) => `<tr><td><code>${text(item.method)} ${text(item.path)}</code></td><td>${Number(item.status)}</td><td>${Number(item.durationMs).toFixed(0)} ms</td></tr>`).join("")}</tbody></table></div>`;
  }

  async function render(context, quiet = false) {
    const { api, state, setHeader, dateBR, toast } = context;
    if (!quiet) setHeader("OPERAÇÃO E SEGURANÇA", "Centro de Controle");
    const data = await api("/api/control-center");
    if (state.screen !== "control_center") return;
    const { summary, health, requests, jobs } = data;
    const storageOk = !health.persistentStorageRequired || health.persistentStorageVerified;
    document.getElementById("content").innerHTML = `<section class="control-center" aria-labelledby="controlCenterTitle">
      <header class="control-hero"><div><p class="eyebrow gold">VISÃO OPERACIONAL EM TEMPO REAL</p><h2 id="controlCenterTitle">Tudo o que acontece no Sistema Seccol</h2><p>Sessões, alterações, falhas, desempenho, continuidade e integrações da empresa ativa em um único lugar.</p></div><div class="control-refresh"><span>Atualizado ${text(dateBR(data.generatedAt, true))}</span><button id="refreshControlCenter" class="secondary" type="button">↻ Atualizar</button></div></header>
      <div class="control-metrics" aria-label="Resumo operacional">
        <article><span class="metric-icon is-online">●</span><div><strong>${summary.activeUsers}</strong><span>Pessoas online</span><small>${summary.activeSessions} sessão(ões) nos últimos 5 min</small></div></article>
        <article><span class="metric-icon">♙</span><div><strong>${summary.usersEnabled}/${summary.usersTotal}</strong><span>Usuários habilitados</span><small>${summary.validSessions} sessão(ões) válidas</small></div></article>
        <article><span class="metric-icon ${summary.openErrors ? "is-error" : "is-ok"}">!</span><div><strong>${summary.openErrors}</strong><span>Erros abertos</span><small>${requests.serverErrors} erro(s) HTTP em 15 min</small></div></article>
        <article><span class="metric-icon">↯</span><div><strong>${Number(requests.p95Ms).toFixed(0)} ms</strong><span>Resposta p95</span><small>${requests.last15Minutes} requisições em 15 min</small></div></article>
      </div>
      <section class="control-health panel"><div class="panel-head"><div><h3>Saúde e continuidade</h3><small class="muted">Estado do processo atual e do armazenamento.</small></div>${statusBadge(storageOk && health.schedulerRunning, "Operação saudável", "Atenção necessária")}</div><div class="control-health-grid panel-body">
        <div><span>Aplicação</span><strong>v${text(health.version)}</strong><small>Ativa há ${text(duration(health.uptimeSeconds))}</small></div>
        <div><span>Banco SQLite</span><strong>${text(bytes(health.databaseBytes))}</strong><small>WAL ${text(bytes(health.walBytes))}</small></div>
        <div><span>Armazenamento</span><strong>${text(bytes(health.diskFreeBytes))} livres</strong><small>de ${text(bytes(health.diskTotalBytes))}</small></div>
        <div><span>Volume persistente</span><strong>${storageOk ? "Verificado" : "Não verificado"}</strong><small>${health.persistentStorageRequired ? "Obrigatório em produção" : "Validação não exigida neste ambiente"}</small></div>
        <div><span>Último backup</span><strong>${health.lastBackupAt ? text(dateBR(health.lastBackupAt, true)) : "Não registrado"}</strong><small>Backup integral auditado</small></div>
        <div><span>Agendador</span><strong>${health.schedulerRunning ? "Executando" : "Parado"}</strong><small>${Number(jobs.running || 0)} job(s) em execução</small></div>
        <div><span>OpenRouter</span><strong>${health.aiConfigured ? "Configurado" : "Desativado"}</strong><small>Assistência por IA</small></div>
        <div><span>Consulta CNPJ</span><strong>${health.cnpjLookupConfigured ? "Configurada" : "Desativada"}</strong><small>Credencial nunca exibida</small></div>
      </div></section>
      <section class="panel control-sessions"><div class="panel-head"><div><h3>Pessoas e sessões</h3><small class="muted">Cada pessoa aparece uma vez; dispositivos e acessos ficam agrupados abaixo dela.</small></div><div class="control-session-summary"><span class="status">${new Set(data.sessions.map((item) => item.userId)).size} pessoa(s)</span><span class="status">${data.sessions.length} sessão(ões)</span></div></div><div class="panel-body">${sessionRows(data.sessions, dateBR)}</div></section>
      <div class="control-columns"><section class="panel"><div class="panel-head"><div><h3>Erros e alertas</h3><small class="muted">Falhas persistidas do servidor e do navegador.</small></div><label class="control-filter"><span>Exibir</span><select id="controlEventFilter"><option value="open">Abertos</option><option value="all">Todos</option><option value="error">Erros</option><option value="warning">Alertas</option><option value="resolved">Resolvidos</option></select></label></div><div id="controlEventResults" class="panel-body">${eventRows(data.events.filter((item) => !item.resolved_at), dateBR)}</div></section>
      <section class="panel"><div class="panel-head"><div><h3>Últimas alterações</h3><small class="muted">Quem fez, o que fez e quando fez.</small></div><label class="control-filter"><span>Pesquisar</span><input id="controlChangeSearch" type="search" placeholder="Pessoa, ação ou registro" autocomplete="off"></label></div><div id="controlChangeResults" class="panel-body">${changeRows(data.changes, dateBR)}</div></section></div>
      <section class="panel"><div class="panel-head"><div><h3>Desempenho das requisições</h3><small class="muted">Janela móvel dos últimos 15 minutos; reinicia com o servidor.</small></div><div class="control-request-summary"><span>${requests.averageMs} ms média</span><span>${requests.clientErrors} respostas 4xx</span><span>${requests.sinceStart} desde o início</span></div></div><div class="panel-body">${requestRows(requests)}</div></section>
    </section>`;

    document.getElementById("refreshControlCenter").onclick = () => render(context, true).catch((error) => toast(error.message));
    document.querySelectorAll("[data-end-session]").forEach((button) => { button.onclick = async () => {
      if (!global.confirm("Encerrar esta sessão agora? O usuário precisará entrar novamente.")) return;
      try {
        await api(`/api/control-center/sessions/${button.dataset.endSession}`, { method: "DELETE", body: "{}" });
        toast("Sessão encerrada e ação registrada na auditoria.");
        await render(context, true);
      } catch (error) { toast(error.message); }
    }; });
    const bindEventActions = () => document.querySelectorAll("[data-resolve-event]").forEach((button) => { button.onclick = async () => {
      try {
        await api(`/api/control-center/events/${button.dataset.resolveEvent}/resolve`, { method: "POST", body: "{}" });
        toast("Evento marcado como resolvido.");
        await render(context, true);
      } catch (error) { toast(error.message); }
    }; });
    bindEventActions();

    document.getElementById("controlEventFilter").onchange = (event) => {
      const mode = event.target.value;
      const filtered = data.events.filter((item) => mode === "all"
        || (mode === "open" && !item.resolved_at)
        || (mode === "resolved" && item.resolved_at)
        || (mode === "error" && item.severity === "error")
        || (mode === "warning" && item.severity === "warning"));
      document.getElementById("controlEventResults").innerHTML = eventRows(filtered, dateBR);
      bindEventActions();
    };
    document.getElementById("controlChangeSearch").oninput = (event) => {
      const query = event.target.value.trim().toLocaleLowerCase("pt-BR");
      const filtered = !query ? data.changes : data.changes.filter((item) => [
        item.user_name || "Sistema", item.action, item.entity_type, item.entity_id,
      ].some((value) => String(value || "").toLocaleLowerCase("pt-BR").includes(query)));
      document.getElementById("controlChangeResults").innerHTML = changeRows(filtered, dateBR);
    };

    global.clearTimeout(refreshTimer);
    refreshTimer = global.setTimeout(() => {
      if (state.screen === "control_center" && document.visibilityState === "visible") {
        render(context, true).catch(() => {});
      }
    }, 30000);
  }

  function reportClientError(payload) {
    const state = global.SIVSState;
    if (!state?.user || !state.csrf) return;
    const fingerprint = `${payload.message}|${payload.source}|${payload.line}`;
    const now = Date.now();
    if (now - (seenClientErrors.get(fingerprint) || 0) < 60000) return;
    seenClientErrors.set(fingerprint, now);
    global.fetch("/api/telemetry/client-error", {
      method: "POST", credentials: "same-origin", keepalive: true,
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrf },
      body: JSON.stringify({ ...payload, page: global.location.pathname + global.location.search }),
    }).catch(() => {});
  }

  global.addEventListener("error", (event) => reportClientError({
    message: event.message || "Erro JavaScript sem mensagem", source: event.filename || "",
    line: event.lineno || 0, column: event.colno || 0, stack: event.error?.stack || "",
  }));
  global.addEventListener("unhandledrejection", (event) => reportClientError({
    message: event.reason?.message || String(event.reason || "Promise rejeitada"),
    source: "unhandledrejection", line: 0, column: 0, stack: event.reason?.stack || "",
  }));

  global.SIVSControlCenter = Object.freeze({ render });
})(window);
