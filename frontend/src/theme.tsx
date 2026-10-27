import { AnimatePresence, motion } from "motion/react";
import { Moon, Sun } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

export type Theme = "dim" | "dark";

const KEY = "jobradar-theme";

function current(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "dim";
}

/** The page's theme, kept on <html data-theme> and remembered in this browser. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(current);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      // Private windows can refuse storage; the theme still applies for this visit.
    }
  }, [theme]);

  const toggle = useCallback(() => {
    // Fade the colours for a moment, then drop the class so normal hovers stay snappy.
    const root = document.documentElement;
    root.classList.add("theme-fade");
    window.setTimeout(() => root.classList.remove("theme-fade"), 400);
    setTheme((t) => (t === "dark" ? "dim" : "dark"));
  }, []);
  return [theme, toggle];
}

/** Sun in the dark theme (switch to dim), moon in the dim one (switch to dark). */
export function ThemeToggle() {
  const [theme, toggle] = useTheme();
  const next = theme === "dark" ? "dim" : "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to the ${next} theme`}
      title={`Switch to the ${next} theme`}
      className="theme-toggle relative size-9 justify-center overflow-hidden rounded-full p-0"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          className="grid place-items-center"
          initial={{ rotate: -90, scale: 0.4, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0.4, opacity: 0 }}
          transition={{ type: "spring", stiffness: 420, damping: 26 }}
        >
          {theme === "dark" ? <Sun size={17} strokeWidth={2} /> : <Moon size={17} strokeWidth={2} />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
