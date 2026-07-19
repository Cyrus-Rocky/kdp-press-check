(function () {
  var shell = document.getElementById("app-shell");
  var collapseBtn = document.getElementById("sidebar-toggle");
  var openBtn = document.getElementById("sidebar-open");
  var backdrop = document.getElementById("sidebar-backdrop");
  if (!shell) return;

  // ── Desktop collapse/expand (persisted) ──
  try {
    if (localStorage.getItem("kdp-sidebar") === "collapsed") {
      shell.classList.add("is-collapsed");
    }
  } catch (e) {}

  if (collapseBtn) {
    collapseBtn.addEventListener("click", function () {
      var collapsed = shell.classList.toggle("is-collapsed");
      collapseBtn.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
      try { localStorage.setItem("kdp-sidebar", collapsed ? "collapsed" : "expanded"); } catch (e) {}
    });
  }

  // ── Mobile drawer ──
  function openDrawer() { shell.classList.add("is-open"); }
  function closeDrawer() { shell.classList.remove("is-open"); }
  if (openBtn) openBtn.addEventListener("click", openDrawer);
  if (backdrop) backdrop.addEventListener("click", closeDrawer);
  // close the drawer after tapping a link on mobile
  shell.querySelectorAll(".side-link").forEach(function (a) {
    a.addEventListener("click", function () {
      if (window.matchMedia("(max-width: 860px)").matches && a.tagName === "A") closeDrawer();
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeDrawer();
  });
})();
