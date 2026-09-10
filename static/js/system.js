document.addEventListener("DOMContentLoaded", () => {
  const button = document.querySelector("[data-menu]");
  const sidebar = document.querySelector("#sidebar");
  if (button && sidebar) {
    button.addEventListener("click", () => sidebar.classList.toggle("open"));
    document.addEventListener("click", (event) => {
      if (window.innerWidth <= 900 && sidebar.classList.contains("open") && !sidebar.contains(event.target) && event.target !== button) sidebar.classList.remove("open");
    });
  }

  document.querySelectorAll("[data-copy]").forEach((copyButton) => {
    copyButton.addEventListener("click", async () => {
      const source = document.querySelector(copyButton.dataset.copy);
      if (!source) return;
      const value = source.textContent.trim();
      try {
        await navigator.clipboard.writeText(value);
      } catch {
        const temporary = document.createElement("textarea");
        temporary.value = value;
        temporary.style.position = "fixed";
        temporary.style.opacity = "0";
        document.body.appendChild(temporary);
        temporary.select();
        document.execCommand("copy");
        temporary.remove();
      }
      const original = copyButton.textContent;
      copyButton.textContent = "Link copiado";
      window.setTimeout(() => { copyButton.textContent = original; }, 1800);
    });
  });

  document.querySelectorAll(".toast").forEach((toast) => {
    window.setTimeout(() => toast.classList.add("toast-hidden"), 5000);
  });
});
