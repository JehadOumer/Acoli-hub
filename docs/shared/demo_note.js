/* Shared Demo note control for static GitHub Pages tools. */
(function () {
  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function closeNote() {
    var el = document.getElementById("demoNoteModal");
    if (el) el.classList.remove("open");
  }

  function openNote() {
    var el = document.getElementById("demoNoteModal");
    if (el) el.classList.add("open");
  }

  ready(function () {
    var controls = document.querySelector(".tool-bar .controls");
    if (!controls || document.getElementById("demoNoteBtn")) return;

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn quiet demo-note-btn";
    btn.id = "demoNoteBtn";
    btn.textContent = "Demo note";
    controls.insertBefore(btn, controls.firstChild);

    var backdrop = document.createElement("div");
    backdrop.className = "demo-note-backdrop";
    backdrop.id = "demoNoteModal";
    backdrop.setAttribute("role", "presentation");
    backdrop.innerHTML =
      '<div class="demo-note-modal" role="dialog" aria-modal="true" aria-labelledby="demoNoteTitle">' +
      '<p class="dn-kicker">GitHub Pages</p>' +
      '<h2 id="demoNoteTitle">Demo note</h2>' +
      "<p>This is a static snapshot of a working Lab Hub web app. It runs from baked files with no live server.</p>" +
      "<p>Only a small, testable subset of the data is included here. Totals and coverage shown in the interface (corpora, language pairs, languages, and similar figures) describe the full collections available to the live apps, not the size of this demo sample.</p>" +
      '<div class="dn-actions"><button type="button" class="btn primary" id="demoNoteClose">Close</button></div>' +
      "</div>";
    document.body.appendChild(backdrop);

    btn.addEventListener("click", openNote);
    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop) closeNote();
    });
    document.getElementById("demoNoteClose").addEventListener("click", closeNote);
    window.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && backdrop.classList.contains("open")) closeNote();
    });
  });
})();
