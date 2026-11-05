import { useSyncExternalStore } from "react";
import english from "./locales/en.json";

export type Locale = "en" | "tr";
const storageKey = "aptilume.language";
let locale: Locale = "en";
try {
  if (localStorage.getItem(storageKey) === "tr") locale = "tr";
} catch {
  /* Storage can be unavailable in private sessions. */
}
document.documentElement.lang = locale;
const listeners = new Set<() => void>();
const entries = Object.entries(english);
const en = new Map(entries);
const tr = new Map(entries.map(([key, value]) => [value, key]));
const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const patterns = new Map<Locale, RegExp>();
const templates = new Map<
  Locale,
  Array<{ pattern: RegExp; output: string; indexes: number[] }>
>();
for (const language of ["en", "tr"] as const) {
  const source = language === "en" ? en : tr;
  const keys = [...source.keys()]
    .filter((key) => key.length > 2)
    .sort((a, b) => b.length - a.length);
  patterns.set(
    language,
    new RegExp(
      `(?<![\\p{L}\\p{N}_])(?:${keys.map(escape).join("|")})(?![\\p{L}\\p{N}_])`,
      "gu",
    ),
  );
  templates.set(
    language,
    [...source.entries()]
      .filter(([key]) => /\{\d+\}/.test(key))
      .sort(
        ([a], [b]) =>
          b.replace(/\{\d+\}/g, "").length - a.replace(/\{\d+\}/g, "").length,
      )
      .map(([key, output]) => {
        const indexes: number[] = [];
        const pattern = key
          .split(/(\{\d+\})/g)
          .map((part) => {
            if (/^\{\d+\}$/.test(part)) {
              indexes.push(Number(part.slice(1, -1)));
              return "([\\s\\S]*?)";
            }
            return escape(part);
          })
          .join("");
        return {
          pattern: new RegExp("^" + pattern + "$", "u"),
          output,
          indexes,
        };
      }),
  );
}

export function getLocale(): Locale {
  return locale;
}
export function formatLocale(): string {
  return locale === "tr" ? "tr-TR" : "en-US";
}
export function setLocale(value: Locale) {
  if (value !== "en" && value !== "tr") return;
  locale = value;
  document.documentElement.lang = value;
  try {
    localStorage.setItem(storageKey, value);
  } catch {
    /* Preference remains in memory. */
  }
  listeners.forEach((listener) => listener());
}
export function useLocale(): Locale {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getLocale,
    () => "en",
  );
}

/** Translate interface text. Stored names, authored questions and responses stay untouched. */
export function t(value: string): string;
export function t<T>(value: T): T;
export function t(value: any): any {
  if (typeof value !== "string") return value;
  const key = value.trim();
  if (!key || key.length > 2048) return value;
  const table = locale === "en" ? en : tr;
  if (locale === "tr" && en.has(key)) return value;
  const exact = table.get(key);
  if (exact) return value.replace(key, exact);
  for (const template of templates.get(locale)!) {
    const match = key.match(template.pattern);
    if (!match) continue;
    const args = new Map(
      template.indexes.map((index, position) => [
        index,
        t(match[position + 1]),
      ]),
    );
    return value.replace(
      key,
      template.output.replace(
        /\{(\d+)\}/g,
        (_, index) => args.get(Number(index)) || "",
      ),
    );
  }
  return value.replace(
    patterns.get(locale)!,
    (part) => table.get(part) || part,
  );
}

/** Render-time translation keeps module-level status maps responsive to language changes. */
export function translateNode(value: any): any {
  if (typeof value === "string") return t(value);
  if (Array.isArray(value)) return value.map(translateNode);
  return value;
}

export function translateChart(value: any): any {
  if (typeof value === "string") return t(value);
  if (typeof value === "function")
    return (...args: any[]) => translateChart(value(...args));
  if (Array.isArray(value)) return value.map(translateChart);
  if (
    value &&
    typeof value === "object" &&
    Object.getPrototypeOf(value) === Object.prototype
  )
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, translateChart(item)]),
    );
  return value;
}
