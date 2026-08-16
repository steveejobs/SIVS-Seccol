(function createSystemDate() {
  "use strict";

  const formatter = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  });

  function render() {
    const element = document.getElementById("systemDate");
    if (!element) return;
    const now = new Date();
    const label = formatter.format(now);
    element.dateTime = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0"),
    ].join("-");
    element.textContent = label.charAt(0).toUpperCase() + label.slice(1);
  }

  function scheduleNextDay() {
    const now = new Date();
    const nextDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 1);
    window.setTimeout(() => {
      render();
      scheduleNextDay();
    }, nextDay.getTime() - now.getTime());
  }

  document.addEventListener("DOMContentLoaded", () => {
    render();
    scheduleNextDay();
  });
})();
