import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";

test("English defaults, Turkish persistence, dynamic labels and non-mutating charts", () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "aptilume-i18n-"));
  const require = createRequire(import.meta.url);
  const preferences = new Map();
  globalThis.document = { documentElement: { lang: "" } };
  globalThis.localStorage = {
    getItem: (key) => preferences.get(key) ?? null,
    setItem: (key, value) => preferences.set(key, value),
  };
  try {
    const source = fs.readFileSync(
      new URL("../src/i18n.ts", import.meta.url),
      "utf8",
    );
    const compiled = ts
      .transpileModule(source, {
        compilerOptions: {
          module: ts.ModuleKind.CommonJS,
          target: ts.ScriptTarget.ES2022,
          esModuleInterop: true,
        },
      })
      .outputText.replace(
        'require("react")',
        `require(${JSON.stringify(require.resolve("react"))})`,
      );
    fs.mkdirSync(path.join(temporary, "locales"));
    fs.copyFileSync(
      new URL("../src/locales/en.json", import.meta.url),
      path.join(temporary, "locales/en.json"),
    );
    const target = path.join(temporary, "i18n.cjs");
    fs.writeFileSync(target, compiled);
    const i18n = createRequire(target)(target);
    assert.equal(i18n.getLocale(), "en");
    assert.equal(document.documentElement.lang, "en");
    assert.equal(i18n.t("Anketler"), "Surveys");
    assert.equal(
      i18n.t("24 gönderildi · 6 bekleniyor"),
      "24 submitted · 6 pending",
    );
    assert.equal(
      i18n.t("%32.6 ölçüm kapsamı · 47/144 gözlem"),
      "32.6% assessment coverage · 47/144 observations",
    );
    assert.equal(
      i18n.t("Data & Analytics, AI Literacy için gelişim planı"),
      "Development plan for Data & Analytics, AI Literacy",
    );
    assert.equal(i18n.formatLocale(), "en-US");
    const original = {
      series: [{ name: "Gönderildi" }],
      formatter: () => "24 gönderildi",
    };
    const chart = i18n.translateChart(original);
    assert.equal(chart.series[0].name, "Submitted");
    assert.equal(chart.formatter(), "24 submitted");
    assert.equal(original.series[0].name, "Gönderildi");
    i18n.setLocale("tr");
    assert.equal(i18n.t("Surveys"), "Anketler");
    assert.equal(i18n.t("Anketler"), "Anketler");
    assert.equal(
      i18n.t("24 submitted · 6 pending"),
      "24 gönderildi · 6 bekleniyor",
    );
    assert.equal(preferences.get("aptilume.language"), "tr");
    assert.equal(document.documentElement.lang, "tr");
    assert.equal(i18n.formatLocale(), "tr-TR");
    i18n.setLocale("invalid");
    assert.equal(i18n.getLocale(), "tr");
    const object = { authored: "original" };
    assert.equal(i18n.translateNode(object), object);
    assert.equal(i18n.t("x".repeat(3000)), "x".repeat(3000));
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
    delete globalThis.document;
    delete globalThis.localStorage;
  }
});
