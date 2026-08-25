(function createWorkspaceTabs(global) {
  "use strict";

  const ui = global.SIVSUI = global.SIVSUI || {};
  let config = null;
  let activeScreen = "dashboard";

  const unique = (items) => items.filter((item, index) => items.indexOf(item) === index);

  function availableTabs() {
    if (!config) return [];
    return unique(["dashboard", ...config.preferences.openTabs(), activeScreen])
      .filter((screen) => config.canAccess(screen));
  }

  function focusRelative(button, direction) {
    const buttons = [...config.container.querySelectorAll("[data-workspace-tab]")];
    const index = buttons.indexOf(button);
    if (index < 0 || !buttons.length) return;
    const target = direction === "home" ? buttons[0]
      : direction === "end" ? buttons.at(-1)
        : buttons[(index + direction + buttons.length) % buttons.length];
    target?.focus();
  }

  function render() {
    if (!config?.container) return;
    const tabs = availableTabs();
    config.container.innerHTML = tabs.map((screen) => {
      const active = screen === activeScreen;
      const label = config.label(screen);
      return `<span class="workspace-tab-shell ${active ? "active" : ""}">
        <button type="button" class="workspace-tab" data-workspace-tab="${config.escape(screen)}" ${active ? 'aria-current="page"' : ""} title="Abrir ${config.escape(label)}">
          <span class="workspace-tab-icon" aria-hidden="true">${config.escape(config.icon(screen))}</span><span>${config.escape(label)}</span>
        </button>
        ${screen === "dashboard" ? "" : `<button type="button" class="workspace-tab-close" data-workspace-tab-close="${config.escape(screen)}" aria-label="Fechar aba ${config.escape(label)}">×</button>`}
      </span>`;
    }).join("");
    config.container.hidden = tabs.length < 2;
    config.container.querySelectorAll("[data-workspace-tab]").forEach((button) => {
      button.addEventListener("click", () => config.navigate(button.dataset.workspaceTab));
      button.addEventListener("keydown", (event) => {
        const directions = { ArrowLeft: -1, ArrowRight: 1, Home: "home", End: "end" };
        if (!(event.key in directions)) return;
        event.preventDefault();
        focusRelative(button, directions[event.key]);
      });
    });
    config.container.querySelectorAll("[data-workspace-tab-close]").forEach((button) => {
      button.addEventListener("click", async () => {
        const screen = button.dataset.workspaceTabClose;
        const before = availableTabs();
        const closedIndex = before.indexOf(screen);
        config.preferences.closeTab(screen);
        if (screen === activeScreen) {
          const remaining = availableTabs().filter((item) => item !== screen);
          const target = remaining[Math.min(Math.max(closedIndex - 1, 0), remaining.length - 1)] || "dashboard";
          await config.navigate(target);
        } else {
          render();
        }
      });
    });
    const activeShell = config.container.querySelector('[aria-current="page"]')?.closest(
      ".workspace-tab-shell",
    );
    global.requestAnimationFrame(() => activeShell?.scrollIntoView({
      block: "nearest", inline: "nearest", behavior: "auto",
    }));
  }

  ui.workspaceTabs = Object.freeze({
    configure(options) {
      config = options;
      render();
    },
    activate(screen) {
      activeScreen = screen || "dashboard";
      config?.preferences.openTab(activeScreen);
      render();
    },
    render,
  });
})(window);
