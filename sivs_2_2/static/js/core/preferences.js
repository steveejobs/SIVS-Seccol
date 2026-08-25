(function createPreferences(global) {
  "use strict";

  let scope = "anonymous";
  const storage = global.localStorage;
  const read = (name, fallback = []) => {
    try { return JSON.parse(storage.getItem(`sivs:${scope}:${name}`)) ?? fallback; }
    catch { return fallback; }
  };
  const write = (name, value) => {
    try { storage.setItem(`sivs:${scope}:${name}`, JSON.stringify(value)); }
    catch {}
  };

  global.SIVSPreferences = Object.freeze({
    configure(userId, companyId) { scope = `${userId || "user"}:${companyId || "company"}`; },
    favorites() { return read("favorites").filter((item) => typeof item === "string").slice(0, 8); },
    isFavorite(screen) { return this.favorites().includes(screen); },
    toggleFavorite(screen) {
      const favorites = this.favorites();
      const next = favorites.includes(screen)
        ? favorites.filter((item) => item !== screen)
        : [screen, ...favorites].slice(0, 8);
      write("favorites", next);
      return next.includes(screen);
    },
    remember(screen) {
      if (!screen || screen === "dashboard") return;
      write("recent-screens", [screen, ...read("recent-screens").filter((item) => item !== screen)].slice(0, 6));
    },
    recent() { return read("recent-screens").filter((item) => typeof item === "string").slice(0, 6); },
    openTabs() {
      return read("open-tabs").filter((item) => typeof item === "string" && item !== "dashboard").slice(0, 7);
    },
    openTab(screen) {
      if (!screen || screen === "dashboard") return this.openTabs();
      const current = this.openTabs();
      const next = current.includes(screen) ? current : [...current, screen].slice(-7);
      write("open-tabs", next);
      return next;
    },
    closeTab(screen) {
      const next = this.openTabs().filter((item) => item !== screen);
      write("open-tabs", next);
      return next;
    },
  });
})(window);
