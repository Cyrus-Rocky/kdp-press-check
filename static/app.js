(function () {
  var form = document.getElementById("upload-form");
  if (!form) return;

  var dropzone = document.getElementById("dropzone");
  var input = document.getElementById("file-input");
  var browseBtn = document.getElementById("browse-btn");
  var fileDisplay = document.getElementById("file-display");
  var fileNameEl = document.getElementById("file-name");
  var removeBtn = document.getElementById("file-remove");
  var submitBtn = document.getElementById("submit-btn");
  var statusEl = document.getElementById("form-status");

  var MAX_BYTES = 200 * 1024 * 1024;

  function announce(msg) {
    if (statusEl) statusEl.textContent = msg;
  }

  function formatSize(bytes) {
    var mb = bytes / (1024 * 1024);
    return mb >= 1 ? mb.toFixed(1) + " MB" : Math.round(bytes / 1024) + " KB";
  }

  var ALLOWED_EXTENSIONS = (form.dataset.accept || ".pdf,.docx,.txt,.rtf,.odt,.epub").split(",");

  function setFile(file) {
    if (!file) return;
    var name = file.name.toLowerCase();
    var isAllowed = ALLOWED_EXTENSIONS.some(function (ext) { return name.endsWith(ext); });
    if (!isAllowed) {
      if (name.endsWith(".doc")) {
        announce("Legacy .doc files aren't supported. Save it as .docx in Word, then upload that.");
      } else {
        announce("That file type isn't supported for this page. Check the accepted formats listed above.");
      }
      return;
    }
    if (file.size > MAX_BYTES) {
      announce("That file is larger than 200 MB. Choose a smaller PDF.");
      return;
    }
    fileNameEl.textContent = file.name + " · " + formatSize(file.size);
    fileDisplay.classList.add("show");
    submitBtn.disabled = false;
    announce(file.name + " ready to check.");
  }

  browseBtn.addEventListener("click", function () { input.click(); });

  input.addEventListener("change", function () {
    setFile(input.files && input.files[0]);
  });

  removeBtn.addEventListener("click", function () {
    input.value = "";
    fileDisplay.classList.remove("show");
    submitBtn.disabled = true;
    announce("File removed.");
  });

  ["dragenter", "dragover"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.remove("is-dragover");
    });
  });

  dropzone.addEventListener("drop", function (e) {
    var files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) {
      input.files = files;
      setFile(files[0]);
    }
  });

  form.addEventListener("submit", function () {
    if (!input.files || !input.files.length) return;
    submitBtn.disabled = true;
    submitBtn.classList.add("is-loading");
    dropzone.classList.add("is-scanning");
    announce("Checking manuscript against KDP print specifications. This can take a few seconds for long books.");
  });
})();
