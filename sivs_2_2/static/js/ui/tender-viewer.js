(function createTenderViewer() {
  "use strict";

  let zoom = 100;
  let documentURL = "";

  function frameURL() {
    return `${documentURL}#zoom=${zoom}`;
  }

  function render() {
    const frame = document.getElementById("tenderViewerFrame");
    const value = document.getElementById("tenderViewerZoomValue");
    if (value) value.textContent = `${zoom}%`;
    if (frame) frame.src = frameURL();
  }

  function open(url, title) {
    const dialog = document.getElementById("tenderViewerDialog");
    if (!dialog || !url) return;
    documentURL = String(url).split("#")[0];
    zoom = 100;
    document.getElementById("tenderViewerTitle").textContent = title || "Documento oficial";
    const external = document.getElementById("tenderViewerExternal");
    const download = document.getElementById("tenderViewerDownload");
    external.href = documentURL;
    download.href = documentURL;
    render();
    if (!dialog.open) dialog.showModal();
  }

  function close() {
    const dialog = document.getElementById("tenderViewerDialog");
    if (!dialog?.open) return;
    dialog.close();
    document.getElementById("tenderViewerFrame").src = "about:blank";
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
  });

  window.SIVSTenderViewer = { open, close };
})();
