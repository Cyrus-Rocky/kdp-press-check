(function () {
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;

  function syncButton(theme) {
    var isDark = theme === "dark";
    btn.setAttribute("aria-pressed", isDark ? "true" : "false");
    btn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
  }

  syncButton(document.documentElement.getAttribute("data-theme") || "light");

  btn.addEventListener("click", function () {
    var current = document.documentElement.getAttribute("data-theme") || "light";
    var next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    syncButton(next);
    try {
      localStorage.setItem("kdp-theme", next);
    } catch (e) {}
  });
})();
