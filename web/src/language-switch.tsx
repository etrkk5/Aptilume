import React from "react";
import { getLocale, setLocale, useLocale, t } from "./i18n";

export function LanguageSwitch() {
  const locale = useLocale();
  return (
    <select
      className="language-switch"
      aria-label={t("Dil")}
      title={t("English / Türkçe")}
      value={locale}
      onChange={(event) => setLocale(event.target.value as "en" | "tr")}
    >
      <option value="en">EN</option>
      <option value="tr">TR</option>
    </select>
  );
}
