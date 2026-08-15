(function initializeFormatters(global) {
  const core = global.SIVSCore ||= {};

  core.money = function money(value) {
    return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  };

  core.dateBR = function dateBR(value, withTime = false) {
    if (!value) return "—";
    const date = new Date(String(value).length === 10 ? `${value}T12:00:00` : value);
    if (Number.isNaN(date.valueOf())) return value;
    return withTime ? date.toLocaleString("pt-BR") : date.toLocaleDateString("pt-BR");
  };

  core.escapeHTML = function escapeHTML(value = "") {
    return String(value).replace(/[&<>'"]/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    }[char]));
  };

  core.safeExternalURL = function safeExternalURL(value) {
    try {
      const url = new URL(String(value || ""), global.location.origin);
      return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
    } catch {
      return "#";
    }
  };

  core.statusClass = function statusClass(value = "") {
    return String(value).toLowerCase().normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-");
  };
})(window);
