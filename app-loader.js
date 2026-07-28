(() => {
  "use strict";

  function loadScript(src, onload) {
    const script = document.createElement("script");
    script.src = src;
    script.onload = onload;
    script.onerror = () => console.error(`Impossibile caricare ${src}`);
    document.head.appendChild(script);
  }

  function startScheduler() {
    loadScript("csv-compat.js?v=20260728-1", () => {
      loadScript("app.js?v=20260728-1", () => {
        document.dispatchEvent(new Event("scheduler:compat-ready"));
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startScheduler, { once: true });
  } else {
    startScheduler();
  }
})();
