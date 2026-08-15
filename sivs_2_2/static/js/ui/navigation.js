(function createNavigationComponent() {
  "use strict";

  const ui = window.SIVSUI;
  const compactNavigation = window.SIVSPlatform.compactNavigation;

  function elements() {
    return {
      button: document.getElementById("menuButton"),
      sidebar: document.getElementById("sidebar"),
      scrim: document.getElementById("sidebarScrim"),
    };
  }

  ui.setNavigation = function setNavigation(open) {
    const { button, sidebar, scrim } = elements();
    if (!button || !sidebar || !scrim) return;
    sidebar.classList.toggle("open", open);
    scrim.classList.toggle("is-visible", open);
    button.setAttribute("aria-expanded", String(open));
    scrim.setAttribute("aria-hidden", String(!open));
    sidebar.setAttribute("aria-hidden", String(compactNavigation.matches && !open));
    sidebar.inert = compactNavigation.matches && !open;
    document.body.classList.toggle("has-mobile-navigation", open);
  };

  ui.toggleNavigation = function toggleNavigation() {
    const { sidebar } = elements();
    ui.setNavigation(!sidebar?.classList.contains("open"));
  };

  ui.setupNavigation = function setupNavigation() {
    elements().scrim?.addEventListener("click", () => ui.setNavigation(false));
    compactNavigation.addEventListener("change", () => ui.setNavigation(false));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") ui.setNavigation(false);
    });
  };
})();
