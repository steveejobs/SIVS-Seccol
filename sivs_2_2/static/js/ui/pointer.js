(function createPointerComponent() {
  "use strict";

  const platform = window.SIVSPlatform;
  const ui = window.SIVSUI;
  const selector = [
    ".metric-card", ".module-card", ".portfolio-card", ".source-card",
    ".subject-card", ".kanban-card", ".norm-card",
  ].join(",");

  function setDepth(element, event) {
    const bounds = element.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width - .5) * 2;
    const y = ((event.clientY - bounds.top) / bounds.height - .5) * 2;
    element.style.setProperty("--pointer-x", `${(x * 1.2).toFixed(2)}deg`);
    element.style.setProperty("--pointer-y", `${(y * -1.2).toFixed(2)}deg`);
  }

  function resetDepth(element) {
    element.style.setProperty("--pointer-x", "0deg");
    element.style.setProperty("--pointer-y", "0deg");
  }

  ui.enhance = function enhance(root = document) {
    root.querySelectorAll(selector).forEach((element) => {
      if (element.dataset.sivsEnhanced === "true") return;
      element.dataset.sivsEnhanced = "true";
      element.classList.add("sivs-interactive");
      if (!platform.precisePointer.matches || platform.reducedMotion.matches) return;
      element.addEventListener("pointermove", (event) => setDepth(element, event), { passive: true });
      element.addEventListener("pointerleave", () => resetDepth(element), { passive: true });
    });
  };
})();
