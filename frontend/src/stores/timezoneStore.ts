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
    { name: "ciaren-timezone" },
  ),
);

export const COMMON_TIMEZONES: { label: string; value: string }[] = [
  { label: "Browser default", value: "" },
  // UTC
  { label: "UTC+00:00 — UTC / GMT", value: "UTC" },
  // Americas
  { label: "UTC-12:00 — International Date Line West", value: "Etc/GMT+12" },
  { label: "UTC-11:00 — American Samoa (SST)", value: "Pacific/Pago_Pago" },
  { label: "UTC-10:00 — Hawaii (HST)", value: "Pacific/Honolulu" },
  { label: "UTC-09:00 — Alaska (AKST)", value: "America/Anchorage" },
  { label: "UTC-08:00 — Pacific US/Canada (PST)", value: "America/Los_Angeles" },
  { label: "UTC-07:00 — Mountain US/Canada (MST)", value: "America/Denver" },
  { label: "UTC-06:00 — Central US/Canada (CST)", value: "America/Chicago" },
  { label: "UTC-06:00 — Mexico City (CST)", value: "America/Mexico_City" },
  { label: "UTC-05:00 — Eastern US/Canada (EST)", value: "America/New_York" },
  { label: "UTC-05:00 — Lima / Bogotá / Quito (PET/COT/ECT)", value: "America/Lima" },
  { label: "UTC-04:00 — Caracas / Santiago / La Paz", value: "America/Caracas" },
  { label: "UTC-04:00 — Atlantic Canada (AST)", value: "America/Halifax" },
  { label: "UTC-03:00 — São Paulo / Brasília (BRT)", value: "America/Sao_Paulo" },
  { label: "UTC-03:00 — Buenos Aires (ART)", value: "America/Argentina/Buenos_Aires" },
  { label: "UTC-03:30 — Newfoundland (NST)", value: "America/St_Johns" },
  { label: "UTC-02:00 — South Georgia", value: "Atlantic/South_Georgia" },
  { label: "UTC-01:00 — Azores (AZOT)", value: "Atlantic/Azores" },
  // Europe / Africa
  { label: "UTC+00:00 — London (GMT/BST)", value: "Europe/London" },
  { label: "UTC+00:00 — Lisbon (WET/WEST)", value: "Europe/Lisbon" },
  { label: "UTC+00:00 — Accra / Dakar (GMT)", value: "Africa/Accra" },
  { label: "UTC+01:00 — Paris / Berlin / Rome (CET)", value: "Europe/Paris" },
  { label: "UTC+01:00 — Lagos / Casablanca (WAT)", value: "Africa/Lagos" },
  { label: "UTC+02:00 — Cairo (EET)", value: "Africa/Cairo" },
  { label: "UTC+02:00 — Athens / Helsinki (EET)", value: "Europe/Athens" },
  { label: "UTC+02:00 — Johannesburg / Harare (CAT)", value: "Africa/Johannesburg" },
  { label: "UTC+03:00 — Moscow (MSK)", value: "Europe/Moscow" },
  { label: "UTC+03:00 — Nairobi / Addis Ababa (EAT)", value: "Africa/Nairobi" },
  { label: "UTC+03:00 — Riyadh / Kuwait / Baghdad (AST)", value: "Asia/Riyadh" },
  { label: "UTC+03:30 — Tehran (IRST)", value: "Asia/Tehran" },
  // Asia
  { label: "UTC+04:00 — Dubai / Abu Dhabi (GST)", value: "Asia/Dubai" },
  { label: "UTC+04:00 — Baku / Tbilisi / Yerevan", value: "Asia/Baku" },
  { label: "UTC+04:30 — Kabul (AFT)", value: "Asia/Kabul" },
  { label: "UTC+05:00 — Karachi (PKT)", value: "Asia/Karachi" },
  { label: "UTC+05:00 — Tashkent / Yekaterinburg", value: "Asia/Tashkent" },
  { label: "UTC+05:30 — Mumbai / Kolkata / Chennai (IST)", value: "Asia/Kolkata" },
  { label: "UTC+05:45 — Kathmandu (NPT)", value: "Asia/Kathmandu" },
  { label: "UTC+06:00 — Dhaka (BST)", value: "Asia/Dhaka" },
  { label: "UTC+06:00 — Almaty / Novosibirsk", value: "Asia/Almaty" },
  { label: "UTC+06:30 — Yangon (MMT)", value: "Asia/Yangon" },
  { label: "UTC+07:00 — Bangkok / Jakarta / Hanoi (ICT/WIB)", value: "Asia/Bangkok" },
  { label: "UTC+08:00 — Beijing / Shanghai / Hong Kong (CST)", value: "Asia/Shanghai" },
  { label: "UTC+08:00 — Singapore (SGT)", value: "Asia/Singapore" },
  { label: "UTC+08:00 — Kuala Lumpur (MYT)", value: "Asia/Kuala_Lumpur" },
  { label: "UTC+08:00 — Taipei (CST)", value: "Asia/Taipei" },
  { label: "UTC+08:00 — Perth (AWST)", value: "Australia/Perth" },
  { label: "UTC+09:00 — Tokyo (JST)", value: "Asia/Tokyo" },
  { label: "UTC+09:00 — Seoul (KST)", value: "Asia/Seoul" },
  { label: "UTC+09:30 — Adelaide (ACST/ACDT)", value: "Australia/Adelaide" },
  { label: "UTC+09:30 — Darwin (ACST)", value: "Australia/Darwin" },
  { label: "UTC+10:00 — Sydney / Melbourne / Canberra (AEST)", value: "Australia/Sydney" },
  { label: "UTC+10:00 — Brisbane (AEST)", value: "Australia/Brisbane" },
  { label: "UTC+10:00 — Vladivostok", value: "Asia/Vladivostok" },
  { label: "UTC+11:00 — Magadan / Sakhalin", value: "Asia/Magadan" },
  { label: "UTC+11:00 — Noumea (NCT)", value: "Pacific/Noumea" },
  { label: "UTC+12:00 — Auckland / Wellington (NZST)", value: "Pacific/Auckland" },
  { label: "UTC+12:00 — Fiji (FJT)", value: "Pacific/Fiji" },
  { label: "UTC+13:00 — Nuku'alofa / Samoa (TOT/WST)", value: "Pacific/Tongatapu" },
  { label: "UTC+14:00 — Kiritimati (LINT)", value: "Pacific/Kiritimati" },
];
