"use client";

const STORAGE_KEY = "docs-base-theme";

function applyTheme(theme: "light" | "dark") {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
}

export function ThemeToggle() {
  return (
    <button
      type="button"
      className="border-border hover:bg-muted rounded-md border px-3 py-2 text-sm"
      onClick={(event) => {
        const nextTheme = document.documentElement.classList.contains("dark")
          ? "light"
          : "dark";
        applyTheme(nextTheme);
        window.localStorage.setItem(STORAGE_KEY, nextTheme);
        event.currentTarget.textContent =
          nextTheme === "dark" ? "Light" : "Dark";
      }}
    >
      Toggle theme
    </button>
  );
}
