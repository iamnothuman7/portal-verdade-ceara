document.addEventListener("DOMContentLoaded", () => {
  const button = document.querySelector("[data-menu]");
  const sidebar = document.querySelector("#sidebar");
  if (!button || !sidebar) return;
  button.addEventListener("click", () => sidebar.classList.toggle("open"));
  document.addEventListener("click", (event) => {
    if (window.innerWidth <= 900 && sidebar.classList.contains("open") && !sidebar.contains(event.target) && event.target !== button) sidebar.classList.remove("open");
  });
});
