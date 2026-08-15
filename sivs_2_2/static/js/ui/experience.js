(function startSIVSExperience() {
  "use strict";

  const ui = window.SIVSUI;
  ui.setupNavigation();
  ui.setupDialogs();
  ui.enhance(document);

  const content = document.getElementById("content");
  if (content) {
    let enhancementFrame = 0;
    const observer = new MutationObserver(() => {
      window.cancelAnimationFrame(enhancementFrame);
      enhancementFrame = window.requestAnimationFrame(() => ui.enhance(content));
    });
    observer.observe(content, { childList: true, subtree: true });
  }

  window.SIVSUI = Object.freeze(ui);
})();
