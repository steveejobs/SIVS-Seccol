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
  });
})(window);
