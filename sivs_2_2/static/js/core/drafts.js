(function createDraftStore(global) {
  "use strict";

  let scope = "anonymous";
  const storage = global.sessionStorage;
  const keyFor = (module, id = "new") => `sivs:draft:${scope}:${module}:${id || "new"}`;

  function capture(form, relationships = []) {
    const values = {};
    form.querySelectorAll("[name]").forEach((control) => {
      if (control.type === "hidden") return;
      if (control.type === "checkbox") values[control.name] = control.checked;
      else if (control.type !== "file") values[control.name] = control.value;
    });
    return { values, relationships, savedAt: new Date().toISOString() };
  }

  function restore(form, draft) {
    Object.entries(draft?.values || {}).forEach(([name, value]) => {
      const control = form.elements[name];
      if (!control) return;
      if (control.type === "checkbox") control.checked = Boolean(value);
      else control.value = value ?? "";
    });
    form.dispatchEvent(new Event("input", { bubbles: true }));
  }

  global.SIVSDrafts = Object.freeze({
    configure(userId, companyId) { scope = `${userId || "user"}:${companyId || "company"}`; },
    keyFor,
    capture,
    restore,
    load(module, id = "new") {
      try {
        const draft = JSON.parse(storage.getItem(keyFor(module, id)));
        if (!draft?.savedAt || Date.now() - Date.parse(draft.savedAt) > 7 * 86400000) {
          storage.removeItem(keyFor(module, id));
          return null;
        }
        return draft;
      } catch { return null; }
    },
    save(module, id, draft) {
      try { storage.setItem(keyFor(module, id), JSON.stringify(draft)); return true; }
      catch { return false; }
    },
    remove(module, id = "new") { storage.removeItem(keyFor(module, id)); },
  });
})(window);
