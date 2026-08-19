(function () {
  // Handle both mobile and desktop theme toggles
  var btnMobile = document.getElementById("theme-toggle");
  var btnDesktop = document.getElementById("theme-toggle-desktop");
  var buttons = [btnMobile, btnDesktop].filter(Boolean);

  if (buttons.length === 0) return;

  var label = document.getElementById("theme-text");
  function syncAllButtons(theme) {
    var isDark = theme === "dark";
    buttons.forEach(function(btn) {
      btn.setAttribute("aria-pressed", isDark ? "true" : "false");
      btn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
    });
    if (label) label.textContent = isDark ? "Light mode" : "Dark mode";
  }

  syncAllButtons(document.documentElement.getAttribute("data-theme") || "light");

  buttons.forEach(function(btn) {
    btn.addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme") || "light";
      var next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      syncAllButtons(next);
      try {
        localStorage.setItem("kdp-theme", next);
      } catch (e) {}
    });
  });
})();
