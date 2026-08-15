(function createDialogComponent() {
  "use strict";

  const platform = window.SIVSPlatform;
  const ui = window.SIVSUI;
  const guards = new WeakMap();

  ui.setDialogGuard = function setDialogGuard(dialog, guard) {
    if (dialog && typeof guard === "function") guards.set(dialog, guard);
  };

  ui.closeDialog = function closeDialog(dialog) {
    if (!dialog?.open || dialog.classList.contains("is-dialog-closing")) return;
    if (guards.has(dialog) && guards.get(dialog)() === false) return;
    if (platform.reducedMotion.matches) return dialog.close();
    dialog.classList.add("is-dialog-closing");
    window.setTimeout(() => {
      dialog.classList.remove("is-dialog-closing");
      if (dialog.open) dialog.close();
    }, 130);
  };

  ui.setupDialogs = function setupDialogs() {
    document.querySelectorAll("dialog").forEach((dialog) => {
      dialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        ui.closeDialog(dialog);
      });
    });
  };
})();
