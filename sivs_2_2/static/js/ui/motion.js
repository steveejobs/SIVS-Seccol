(function createMotionComponent() {
  "use strict";

  const platform = window.SIVSPlatform;
  const ui = window.SIVSUI;

  ui.announce = function announce(message) {
    const status = document.getElementById("pageStatus");
    if (!status) return;
    status.textContent = "";
    window.requestAnimationFrame(() => { status.textContent = message; });
  };

  ui.transitionOut = async function transitionOut(container) {
    if (!container) return;
    container.setAttribute("aria-busy", "true");
    container.classList.remove("is-view-entering");
    if (platform.reducedMotion.matches || !container.children.length) return;
    const hasWorkMotion = Boolean(container.querySelector(":scope > .work-center"));
    const hasControlMotion = Boolean(container.querySelector(":scope > .control-center"));
    container.classList.toggle("has-work-motion", hasWorkMotion);
    container.classList.toggle("has-control-motion", hasControlMotion);
    container.classList.add("is-view-leaving");
    await platform.wait(hasWorkMotion || hasControlMotion ? 610 : 125);
  };

  ui.transitionIn = function transitionIn(container) {
    if (!container) return;
    container.classList.remove("is-view-leaving");
    const hasControlMotion = Boolean(container.querySelector(":scope > .control-center"));
    container.classList.remove("has-work-motion");
    container.classList.toggle("has-control-motion", hasControlMotion);
    container.classList.add("is-view-entering");
    container.setAttribute("aria-busy", "false");
    const hasWorkMotion = Boolean(container.querySelector(":scope > .work-center"));
    window.setTimeout(
      () => container.classList.remove("is-view-entering"),
      platform.reducedMotion.matches ? 0 : hasWorkMotion || hasControlMotion ? 640 : 460,
    );
    ui.announce(document.getElementById("sectionTitle")?.textContent || "Conteúdo atualizado");
    ui.enhance?.(container);
  };
})();
