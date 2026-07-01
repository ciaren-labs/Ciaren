import { useState } from "react";

export function useLayoutPreference(
  page: string,
  defaultLayout: "cards" | "table" = "cards",
): ["cards" | "table", (l: "cards" | "table") => void] {
  const key = `ciaren-layout-${page}`;
  const [layout, setLayoutState] = useState<"cards" | "table">(() => {
    try {
      return (localStorage.getItem(key) as "cards" | "table") ?? defaultLayout;
    } catch {
      return defaultLayout;
    }
  });
  const setLayout = (l: "cards" | "table") => {
    try {
      localStorage.setItem(key, l);
    } catch {
      // ignore quota errors
    }
    setLayoutState(l);
  };
  return [layout, setLayout];
}
