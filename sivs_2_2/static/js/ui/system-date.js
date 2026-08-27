(function createSystemDate() {
  "use strict";

  const dayFormatter = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
  const timeFormatter = new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  function render() {
    const element = document.getElementById("systemDate");
    const dayElement = document.getElementById("globalDateDay");
    if (!element && !dayElement) return;
    const now = new Date();
    const label = dayFormatter.format(now);
    if (dayElement) dayElement.textContent = label.charAt(0).toUpperCase() + label.slice(1);
    if (!element) return;
    element.dateTime = now.toISOString();
    element.textContent = timeFormatter.format(now);
    /* Keep the full date available to assistive technology without adding visual weight. */
    element.setAttribute("aria-label", label);
  }

  function scheduleNextDay() {
    const now = new Date();
    const nextDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 1);
    window.setTimeout(() => {
      render();
      scheduleNextDay();
    }, nextDay.getTime() - now.getTime());
  }

  function scheduleNextSecond() {
    const now = new Date();
    const nextSecond = new Date(now.getTime() + 1000 - now.getMilliseconds());
    window.setTimeout(() => {
      render();
      scheduleNextSecond();
    }, Math.max(100, nextSecond.getTime() - now.getTime()));
  }

  document.addEventListener("DOMContentLoaded", () => {
    render();
    scheduleNextDay();
    scheduleNextSecond();
  });
})();
