(function createCommandPalette(global) {
  "use strict";

  const ui = global.SIVSUI;
  const escapeHTML = global.SIVSCore.escapeHTML;
  const preferences = global.SIVSPreferences;
  let config;
  let timer;
  let request;
  let activeIndex = 0;
  let currentItems = [];
  let lastRecords = [];
  let listenersReady = false;

  const elements = () => ({
    dialog: document.getElementById("commandDialog"),
    input: document.getElementById("commandInput"),
    results: document.getElementById("commandResults"),
  });

  function screenItems(query = "") {
    const normalized = query.trim().toLocaleLowerCase("pt-BR");
    const screens = config.screens().filter((item) => config.canAccess(item.key));
    const orderedKeys = normalized
      ? []
      : [...preferences.favorites(), ...preferences.recent()].filter((key, index, values) => values.indexOf(key) === index);
    const ordered = orderedKeys.map((key) => screens.find((item) => item.key === key)).filter(Boolean);
    const remaining = screens.filter((item) => !orderedKeys.includes(item.key));
    return [...ordered, ...remaining].filter((item) => !normalized || `${item.label} ${item.group}`.toLocaleLowerCase("pt-BR").includes(normalized));
  }

  function render(records = [], loading = false) {
    if (!loading) lastRecords = records;
    const { input, results } = elements();
    const query = input.value.trim();
    const screens = screenItems(query).slice(0, query ? 8 : 10);
    currentItems = [
      ...screens.map((item) => ({ type: "screen", ...item })),
      ...records.map((item) => ({ type: "record", ...item })),
    ];
    activeIndex = Math.min(activeIndex, Math.max(0, currentItems.length - 1));
    const screenHTML = screens.map((item, index) => `<div class="command-row"><button class="command-result ${index === activeIndex ? "active" : ""}" data-command-index="${index}"><span class="command-result-icon">${escapeHTML(config.icon(item.key))}</span><span><strong>${escapeHTML(item.label)}</strong><small>${escapeHTML(item.group)}</small></span></button><button type="button" class="command-favorite ${preferences.isFavorite(item.key) ? "selected" : ""}" data-command-favorite="${escapeHTML(item.key)}" aria-label="${preferences.isFavorite(item.key) ? "Remover dos favoritos" : "Adicionar aos favoritos"}">★</button></div>`).join("");
    const recordOffset = screens.length;
    const recordHTML = records.map((item, index) => `<button class="command-result ${recordOffset + index === activeIndex ? "active" : ""}" data-command-index="${recordOffset + index}"><span class="command-result-icon">${escapeHTML(config.icon(item.module))}</span><span><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(config.label(item.module))} · ${escapeHTML(item.status)}</small></span><time>${item.dueDate ? escapeHTML(item.dueDate.split("-").reverse().join("/")) : "Abrir"}</time></button>`).join("");
    results.innerHTML = `${screens.length ? `<div class="command-group-label">Áreas e atalhos</div>${screenHTML}` : ""}${query.length >= 2 ? `<div class="command-group-label">Registros encontrados</div>${loading ? '<div class="command-feedback">Pesquisando com suas permissões…</div>' : recordHTML || '<div class="command-feedback">Nenhum registro corresponde à busca.</div>'}` : !screens.length ? '<div class="command-feedback">Digite ao menos dois caracteres para pesquisar registros.</div>' : ""}`;
    bindResults();
  }

  function bindResults() {
    elements().results.querySelectorAll("[data-command-index]").forEach((button) => {
      button.onclick = (event) => {
        activate(Number(button.dataset.commandIndex));
      };
    });
    elements().results.querySelectorAll("[data-command-favorite]").forEach((button) => {
      const toggle = (event) => {
        event.preventDefault(); event.stopPropagation();
        preferences.toggleFavorite(button.dataset.commandFavorite);
        render(lastRecords);
        config.onPreferencesChanged?.();
      };
      button.onclick = toggle;
    });
  }

  function activate(index) {
    const item = currentItems[index];
    if (!item) return;
    const dialog = elements().dialog;
    ui.closeDialog(dialog);
    const follow = () => {
      if (item.type === "record") config.openRecord(item.id);
      else config.navigate(item.key);
    };
    if (dialog.open) window.setTimeout(follow, 140);
    else follow();
  }

  async function search() {
    const query = elements().input.value.trim();
    activeIndex = 0;
    request?.abort();
    if (query.length < 2) return render();
    const controller = new AbortController();
    request = controller;
    render([], true);
    try {
      const records = await config.search(query, controller.signal);
      if (request !== controller || elements().input.value.trim() !== query) return;
      render(records);
    } catch (failure) {
      if (failure.name !== "AbortError") elements().results.innerHTML = '<div class="command-feedback error">Não foi possível pesquisar agora.</div>';
    }
  }

  function open() {
    const { dialog, input } = elements();
    request?.abort();
    request = null;
    clearTimeout(timer);
    if (!dialog.open) dialog.showModal();
    input.value = "";
    render();
    requestAnimationFrame(() => input.focus());
    ui.announce?.("Busca global aberta");
  }

  ui.commandPalette = {
    configure(nextConfig) {
      config = nextConfig;
      if (listenersReady) return;
      listenersReady = true;
      const { input } = elements();
      elements().dialog.addEventListener("close", () => { request?.abort(); request = null; });
      document.getElementById("commandButton").onclick = open;
      input.oninput = () => { clearTimeout(timer); timer = setTimeout(search, 220); };
      input.onkeydown = (event) => {
        if (event.key === "ArrowDown") { event.preventDefault(); activeIndex = Math.min(activeIndex + 1, currentItems.length - 1); render(lastRecords); }
        if (event.key === "ArrowUp") { event.preventDefault(); activeIndex = Math.max(activeIndex - 1, 0); render(lastRecords); }
        if (event.key === "Enter") { event.preventDefault(); activate(activeIndex); }
      };
      document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
          event.preventDefault(); open();
        }
      });
    },
    open,
  };
})(window);
