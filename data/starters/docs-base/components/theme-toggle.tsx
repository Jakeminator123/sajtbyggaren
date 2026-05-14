"use client";

import { useState } from "react";

const STORAGE_KEY = "docs-base-theme";

type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
}

function readDOMTheme(): Theme {
  // The inline boot script in layout.tsx sets the `dark` class on
  // <html> before React hydrates, so reading the class on the client
  // returns the user's actual saved/system theme. On the server
  // `document` is undefined so we fall back to the neutral default.
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function ThemeToggle() {
  // Lazy-initialise from the DOM so the first client render already
  // reflects the boot script's theme without calling setState inside
  // a useEffect (which would trip react-hooks/set-state-in-effect).
  // Server-render returns "light" (neutral SSR default); the button
  // sets suppressHydrationWarning so the intentional client/server
  // label difference does not log a hydration warning.
  const [theme, setTheme] = useState<Theme>(readDOMTheme);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage may be blocked (private mode, quota). The inline
      // boot script falls back to prefers-color-scheme on the next
      // page load so the toggle still works for the current session.
    }
  }

  const isDark = theme === "dark";
  return (
    <button
      type="button"
      className="border-border hover:bg-muted rounded-md border px-3 py-2 text-sm"
      onClick={toggle}
      aria-pressed={isDark}
      aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
      suppressHydrationWarning
    >
      <span suppressHydrationWarning>
        {isDark ? "Light mode" : "Dark mode"}
      </span>
    </button>
  );
}
