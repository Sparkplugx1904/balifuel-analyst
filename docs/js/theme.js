// BaliFuel Analyst — Theme Management Module (Dark & Light Mode)
(function () {
  function applyTheme(theme) {
    const isLight = theme === "light";
    const icon = document.getElementById("themeIcon");
    const label = document.getElementById("themeLabel");

    if (isLight) {
      document.documentElement.setAttribute("data-theme", "light");
      if (icon) icon.textContent = "\u2600";
      if (label) label.textContent = "LIGHT";
    } else {
      document.documentElement.removeAttribute("data-theme");
      if (icon) icon.textContent = "\u263E";
      if (label) label.textContent = "DARK";
    }

    try {
      localStorage.setItem("balifuel_theme", theme);
    } catch (e) {}

    // Dispatch custom event for Plotly charts and other modules
    window.dispatchEvent(new CustomEvent("themechange", { detail: { theme: theme, isLight: isLight } }));
  }

  function initTheme() {
    let saved = "dark";
    try {
      saved = localStorage.getItem("balifuel_theme") || "dark";
    } catch (e) {}

    applyTheme(saved);

    const btn = document.getElementById("themeToggleBtn");
    if (btn) {
      btn.addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        applyTheme(cur === "light" ? "dark" : "light");
      });
    }
  }

  window.BaliTheme = {
    apply: applyTheme,
    init: initTheme,
    isLight: () => document.documentElement.getAttribute("data-theme") === "light"
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTheme);
  } else {
    initTheme();
  }
})();
