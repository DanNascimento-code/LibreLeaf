(() => {
  const key = "libreleaf-theme";
  const root = document.documentElement;

  let savedTheme = null;
  try {
    savedTheme = localStorage.getItem(key);
  } catch (_error) {
    // Storage can be unavailable in privacy-restricted browsing contexts.
  }

  const applyTheme = (theme) => {
    const selected = theme === "light" ? "light" : "dark";
    root.dataset.theme = selected;
    root.style.colorScheme = selected;

    const button = document.querySelector(".theme-toggle");
    if (!button) return;
    const isLight = selected === "light";
    button.setAttribute("aria-pressed", String(isLight));
    button.querySelector(".theme-icon").textContent = isLight ? "☀" : "☾";
    button.querySelector(".theme-label").textContent = isLight ? "Light" : "Dark";
  };

  applyTheme(savedTheme);

  window.addEventListener("DOMContentLoaded", () => {
    applyTheme(root.dataset.theme);
    document.querySelector(".theme-toggle")?.addEventListener("click", () => {
      const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
      try {
        localStorage.setItem(key, nextTheme);
      } catch (_error) {
        // The selected theme still applies for the current page.
      }
    });
  });
})();
