(function createTenderViewer() {
  "use strict";

  let zoom = 100;
  let documentURL = "";
  let objectURL = "";
  let requestController = null;

  function frameURL() {
    return objectURL ? `${objectURL}#zoom=${zoom}` : "about:blank";
  }

  function setStatus(message = "", error = false) {
    const status = document.getElementById("tenderViewerStatus");
    const frame = document.getElementById("tenderViewerFrame");
    if (!status || !frame) return;
    status.textContent = message;
    status.classList.toggle("hidden", !message);
    status.classList.toggle("error", Boolean(error));
    frame.classList.toggle("hidden", Boolean(message));
  }

  function releaseDocument() {
    requestController?.abort();
    requestController = null;
    if (objectURL) URL.revokeObjectURL(objectURL);
    objectURL = "";
  }

  function render() {
    const frame = document.getElementById("tenderViewerFrame");
    const value = document.getElementById("tenderViewerZoomValue");
    if (value) value.textContent = `${zoom}%`;
    if (frame && objectURL) frame.src = frameURL();
  }

  async function open(url, title) {
    const dialog = document.getElementById("tenderViewerDialog");
    if (!dialog || !url) return;
    releaseDocument();
    documentURL = String(url).split("#")[0];
    zoom = 100;
    document.getElementById("tenderViewerTitle").textContent = title || "Documento oficial";
    document.getElementById("tenderViewerExternal").href = documentURL;
    document.getElementById("tenderViewerDownload").href = documentURL;
    document.getElementById("tenderViewerZoomValue").textContent = "100%";
    setStatus("Carregando documento oficial…");
    if (!dialog.open) dialog.showModal();

    requestController = new AbortController();
    try {
      const response = await fetch(documentURL, {
        credentials: "same-origin",
        signal: requestController.signal,
        headers: { Accept: "application/pdf,image/*,text/plain,application/json,application/xml" },
      });
      if (!response.ok) {
        let message = `Não foi possível abrir o documento (HTTP ${response.status}).`;
        try { message = (await response.json()).message || message; } catch { /* resposta não JSON */ }
        throw new Error(message);
      }
      const blob = await response.blob();
      const type = String(blob.type || "").split(";", 1)[0].toLowerCase();
      const previewable = response.headers.get("X-SIVS-Previewable") === "1"
        || type === "application/pdf" || type.startsWith("image/")
        || type.startsWith("text/") || ["application/json", "application/xml"].includes(type);
      if (!previewable) {
        setStatus("Este formato não possui visualização segura no navegador. Use Baixar para abrir no aplicativo adequado.", true);
        return;
      }
      objectURL = URL.createObjectURL(blob);
      setStatus();
      render();
    } catch (failure) {
      if (failure.name !== "AbortError") {
        setStatus(failure.message || "Não foi possível carregar o documento.", true);
      }
    } finally {
      requestController = null;
    }
  }

  function close() {
    const dialog = document.getElementById("tenderViewerDialog");
    if (!dialog?.open) return;
    dialog.close();
    document.getElementById("tenderViewerFrame").src = "about:blank";
    releaseDocument();
    setStatus();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.getElementById("tenderViewerDialog");
    if (!dialog) return;
    dialog.querySelector("[data-viewer-close]").addEventListener("click", close);
    dialog.querySelector("[data-viewer-zoom-out]").addEventListener("click", () => {
      zoom = Math.max(50, zoom - 25); render();
    });
    dialog.querySelector("[data-viewer-zoom-in]").addEventListener("click", () => {
      zoom = Math.min(250, zoom + 25); render();
    });
    dialog.querySelector("[data-viewer-fit]").addEventListener("click", () => {
      zoom = 100; render();
    });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); close(); });
    dialog.addEventListener("close", releaseDocument);
  });

  window.SIVSTenderViewer = { open, close };
})();
