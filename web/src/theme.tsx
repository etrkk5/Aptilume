import React, { useState } from "react";
import { Moon, Sun } from "lucide-react";

type Theme = "light" | "dark";
function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem("aptilume-theme");
    if (stored === "light" || stored === "dark") return stored;
  } catch {}
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}
const initial = initialTheme();
document.documentElement.dataset.theme = initial;

export function ThemeSwitch() {
  const [theme, setTheme] = useState<Theme>(
    () => (document.documentElement.dataset.theme as Theme) || initial,
  );
  const next = theme === "dark" ? "light" : "dark";
  const label = next === "dark" ? "Koyu temaya geç" : "Açık temaya geç";
  return (
    <button
      type="button"
      className="icon-btn theme-toggle"
      aria-label={label}
      title={label}
      onClick={() => {
        document.documentElement.dataset.theme = next;
        setTheme(next);
        try {
          localStorage.setItem("aptilume-theme", next);
        } catch {}
      }}
    >
      {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
