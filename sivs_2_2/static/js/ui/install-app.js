(function createInstallAppExperience() {
  "use strict";

  let deferredPrompt = null;
  const standaloneQuery = window.matchMedia("(display-mode: standalone)");
  const compactQuery = window.matchMedia("(max-width: 900px)");

  function isStandalone() {
    return standaloneQuery.matches || window.navigator.standalone === true;
  }

  function isAppleMobile() {
    return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
  }

  function installButtons() {
    return [...document.querySelectorAll("[data-install-app]")];
  }

  function updateButtons() {
    const visible = !isStandalone() && (Boolean(deferredPrompt) || compactQuery.matches);
    installButtons().forEach((button) => {
      button.hidden = !visible;
      button.setAttribute("aria-hidden", String(!visible));
    });
  }

  function showInstructions() {
    const dialog = document.getElementById("installDialog");
    const steps = document.getElementById("installSteps");
    const confirm = document.getElementById("installConfirmButton");
    if (!dialog || !steps || !confirm) return;

    if (isAppleMobile()) {
      steps.innerHTML = "<strong>No iPhone ou iPad</strong><ol><li>Abra esta página no Safari.</li><li>Toque em Compartilhar.</li><li>Escolha Adicionar à Tela de Início.</li><li>Confirme em Adicionar.</li></ol>";
      confirm.hidden = true;
    } else if (deferredPrompt) {
      steps.innerHTML = "<strong>Instale como aplicativo</strong><p>O Sistema Seccol abrirá em uma janela própria e criará um ícone na tela inicial.</p>";
      confirm.hidden = false;
      confirm.textContent = "Instalar agora";
    } else {
      steps.innerHTML = "<strong>Adicionar à tela inicial</strong><ol><li>Abra o menu do navegador.</li><li>Escolha Instalar aplicativo ou Adicionar à tela inicial.</li><li>Confirme a instalação.</li></ol><p class=\"muted\">Em redes externas, a instalação exige HTTPS.</p>";
      confirm.hidden = true;
    }
    if (!dialog.open) dialog.showModal();
  }

  async function requestInstall() {
    if (!deferredPrompt) return showInstructions();
    const prompt = deferredPrompt;
    deferredPrompt = null;
    await prompt.prompt();
    const choice = await prompt.userChoice;
    if (choice.outcome !== "accepted") updateButtons();
    const dialog = document.getElementById("installDialog");
    if (dialog?.open) window.SIVSUI?.closeDialog?.(dialog);
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    updateButtons();
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    updateButtons();
  });

  document.addEventListener("DOMContentLoaded", () => {
    installButtons().forEach((button) => button.addEventListener("click", showInstructions));
    document.getElementById("installConfirmButton")?.addEventListener("click", requestInstall);
    updateButtons();
  });

  compactQuery.addEventListener?.("change", updateButtons);
  standaloneQuery.addEventListener?.("change", updateButtons);
})();
