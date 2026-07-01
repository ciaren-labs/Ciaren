import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "light" | "dark";

function systemPrefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

interface ThemeStore {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

// Matches the inline script in index.html, which applies the same choice to
// <html> before first paint (reading the same "ciaren-theme" localStorage key) so
// there's no flash of the wrong theme while React boots.
export const useThemeStore = create<ThemeStore>()(
  persist(
    (set, get) => ({
      theme: systemPrefersDark() ? "dark" : "light",
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set({ theme: get().theme === "dark" ? "light" : "dark" }),
    }),
    { name: "ciaren-theme" },
  ),
);
