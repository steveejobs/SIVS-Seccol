(function createPlatformCapabilities() {
  "use strict";

  window.SIVSPlatform = Object.freeze({
    precisePointer: window.matchMedia("(hover: hover) and (pointer: fine)"),
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)"),
    compactNavigation: window.matchMedia("(max-width: 900px)"),
    wait: (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds)),
  });
  window.SIVSUI = window.SIVSUI || {};
})();
