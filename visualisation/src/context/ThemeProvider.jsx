import { createContext, useContext, useEffect, useMemo, useState } from "react";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState("light");

  useEffect(() => {
    const stored = localStorage.getItem("ht_theme_mode") ?? "light";
    document.documentElement.setAttribute("data-theme", stored);
    if (stored !== "light") setThemeState(stored);
  }, []);

  const setTheme = (newTheme) => {
    if (typeof window !== "undefined") {
      document.documentElement.setAttribute("data-theme", newTheme);
      localStorage.setItem("ht_theme_mode", newTheme);
    }
    setThemeState(newTheme);
  };

  const value = useMemo(() => ({ theme, setTheme }), [theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
