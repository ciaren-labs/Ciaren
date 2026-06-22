import { create } from "zustand";
import { persist } from "zustand/middleware";

interface TimezoneStore {
  timezone: string; // IANA timezone (e.g. "America/New_York") or "" for browser default
  setTimezone: (tz: string) => void;
}

export const useTimezoneStore = create<TimezoneStore>()(
  persist(
    (set) => ({
      timezone: "",
      setTimezone: (timezone) => set({ timezone }),
    }),
    { name: "ff-timezone" },
  ),
);

export const COMMON_TIMEZONES: { label: string; value: string }[] = [
  { label: "Browser default", value: "" },
  { label: "UTC", value: "UTC" },
  { label: "New York (ET)", value: "America/New_York" },
  { label: "Chicago (CT)", value: "America/Chicago" },
  { label: "Denver (MT)", value: "America/Denver" },
  { label: "Los Angeles (PT)", value: "America/Los_Angeles" },
  { label: "São Paulo (BRT)", value: "America/Sao_Paulo" },
  { label: "London (GMT/BST)", value: "Europe/London" },
  { label: "Paris / Berlin (CET)", value: "Europe/Paris" },
  { label: "Moscow (MSK)", value: "Europe/Moscow" },
  { label: "Dubai (GST)", value: "Asia/Dubai" },
  { label: "Kolkata (IST)", value: "Asia/Kolkata" },
  { label: "Singapore (SGT)", value: "Asia/Singapore" },
  { label: "Tokyo (JST)", value: "Asia/Tokyo" },
  { label: "Sydney (AEST)", value: "Australia/Sydney" },
];
