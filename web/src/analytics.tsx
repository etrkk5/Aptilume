import {
  t,
  translateNode,
  formatLocale,
  useLocale,
  translateChart,
  getLocale,
} from "./i18n";
import React, { useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { BarChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import {
  Users,
  ClipboardList,
  BarChart3,
  Target,
  ShieldCheck,
  SlidersHorizontal,
  RotateCcw,
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowUpRight,
  Info,
  ListChecks,
} from "lucide-react";
echarts.use([
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
]);
type Any = any;
export const emptyReportFilters = {
  title: "",
  skill_id: "",
  section: "",
  job_band: "",
  response_status: "",
};
export type ReportFilters = typeof emptyReportFilters;
const fmt = (value: Any, digits = 1) =>
  value == null
    ? "—"
    : Number(value).toLocaleString(formatLocale(), {
        maximumFractionDigits: digits,
      });
const states: Any = {
  not_started: "Başlamadı",
  draft: "Taslak",
  submitted: "Gönderildi",
};
export function AnalyticsFilters({
  value,
  options,
  team,
  onChange,
  onReset,
  activeCount,
  loading,
}: Any) {
  const update = (key: string, selected: string) => {
    const next = { ...value, [key]: selected };
    if (
      key === "section" &&
      selected &&
      options.skills?.find((s: Any) => s.id === value.skill_id)?.section !==
        selected
    )
      next.skill_id = "";
    onChange(next);
  };
  const fields: Any[] = [
    [
      "title",
      "Unvan / rol",
      "Tüm unvanlar",
      (options.titles || []).map((t: string) => [t, t]),
    ],
    [
      "skill_id",
      "Yetkinlik",
      "Tüm yetkinlikler",
      (options.skills || [])
        .filter((s: Any) => !value.section || s.section === value.section)
        .map((s: Any) => [s.id, s.name]),
    ],
    [
      "section",
      "Ölçüm bölümü",
      "Ortak + role özel",
      [
        ["common", "Ortak yetkinlikler"],
        ["role", "Role özel yetkinlikler"],
      ],
    ],
    [
      "job_band",
      "Kademe",
      "Tüm kademeler",
      (options.job_bands || []).map((b: string) => [b, b]),
    ],
    [
      "response_status",
      "Yanıt durumu",
      "Tüm yanıt durumları",
      Object.entries(states),
    ],
  ];
  return (
    <section
      className="analytics-filters"
      aria-label={t("Rapor filtreleri")}
      aria-busy={loading}
    >
      <div className="analytics-filter-heading">
        <div>
          <SlidersHorizontal size={17} />
          <b>{t("Raporu ke\u015Ffedin")}</b>
          <span>
            {translateNode(
              activeCount
                ? `${activeCount} filtre etkin`
                : "Tüm erişim kapsamınız",
            )}
          </span>
        </div>
        <button className="text-btn" disabled={!activeCount} onClick={onReset}>
          <RotateCcw size={14} />
          {t(" Filtreleri temizle ")}
        </button>
      </div>
      <div className="analytics-filter-grid">
        {translateNode(
          fields.slice(0, 3).map(([key, label, all, entries]) => (
            <label key={key}>
              {translateNode(label)}
              <select
                aria-label={t(`${label} filtresi`)}
                value={value[key]}
                onChange={(e) => update(key, e.target.value)}
              >
                <option value="">{translateNode(all)}</option>
                {translateNode(
                  entries.map(([id, name]: string[]) => (
                    <option key={id} value={id}>
                      {translateNode(name)}
                    </option>
                  )),
                )}
              </select>
            </label>
          )),
        )}
      </div>
      <details className="analytics-more-filters">
        <summary>
          {t("Di\u011Fer filtreler \u00B7 Kademe ve yan\u0131t durumu")}
        </summary>
        <div className="analytics-filter-grid">
          {translateNode(
            fields.slice(3).map(([key, label, all, entries]) => (
              <label key={key}>
                {translateNode(label)}
                <select
                  aria-label={t(`${label} filtresi`)}
                  value={value[key]}
                  onChange={(e) => update(key, e.target.value)}
                >
                  <option value="">{translateNode(all)}</option>
                  {translateNode(
                    entries.map(([id, name]: string[]) => (
                      <option key={id} value={id}>
                        {translateNode(name)}
                      </option>
                    )),
                  )}
                </select>
              </label>
            )),
          )}
        </div>
      </details>
      <div className="analytics-filter-note">
        <ShieldCheck size={14} />
        <span>
          {t(
            " Filtreler yaln\u0131zca yetkili oldu\u011Funuz ki\u015Filerde uygulan\u0131r. Excel ayn\u0131 kapsam\u0131 kullan\u0131r.",
          )}
          {translateNode(team ? " Ekip kapsamı daraltıldı." : "")}
        </span>
      </div>
    </section>
  );
}
function useChartColors() {
  const read = () => document.documentElement.dataset.theme === "dark";
  const [dark, setDark] = useState(read);
  useEffect(() => {
    const observer = new MutationObserver(() => setDark(read()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => observer.disconnect();
  }, []);
  return {
    text: dark ? "#b8cbe0" : "#687e98",
    line: dark ? "#2a3c52" : "#e9eff6",
    surface: dark ? "#162537" : "#ffffff",
    blue: dark ? "#68b1f5" : "#0056a6",
    cyan: dark ? "#53c7dc" : "#05a4c6",
    purple: dark ? "#b8a1ec" : "#7a66bb",
    pale: dark ? "#405670" : "#d9e4ef",
  };
}
function Chart({ option, label, height = 260 }: Any) {
  const language = useLocale();
  const ref = useRef<HTMLDivElement>(null),
    instance = useRef<Any>(null);
  useEffect(() => {
    if (!ref.current) return;
    instance.current = echarts.init(ref.current);
    const observer = new ResizeObserver(() => instance.current?.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      instance.current?.dispose();
    };
  }, []);
  useEffect(() => {
    instance.current?.setOption(translateChart(option), { notMerge: true });
  }, [JSON.stringify(option), language]);
  return (
    <div
      ref={ref}
      role="img"
      aria-label={t(label)}
      style={{ width: "100%", height }}
    />
  );
}
function NoChart({
  text = "En az 5 farklı kişinin geçerli sonucu gerekli.",
  note = "Eksik veya bastırılmış değerler sıfır puan değildir.",
}: Any) {
  return (
    <div className="analytics-no-chart">
      <ShieldCheck size={24} />
      <p>{translateNode(text)}</p>
      <span>{translateNode(note)}</span>
    </div>
  );
}
function ChartPanel({ title, subtitle, children, note, data }: Any) {
  return (
    <section className="panel analytics-chart-panel">
      <div className="panel-head">
        <div>
          <h2>{translateNode(title)}</h2>
          <p>{translateNode(subtitle)}</p>
        </div>
      </div>
      {translateNode(children)}
      <div className="analytics-chart-note">{translateNode(note)}</div>
      {translateNode(
        data && (
          <details className="analytics-chart-data">
            <summary>{t("Grafik verilerini g\u00F6ster")}</summary>
            <div className="analytics-table-scroll">
              <table>
                <tbody>
                  {translateNode(
                    data.map((row: Any[], i: number) => (
                      <tr key={i}>
                        {translateNode(
                          row.map((cell, j) => (
                            <td key={j}>{translateNode(cell)}</td>
                          )),
                        )}
                      </tr>
                    )),
                  )}
                </tbody>
              </table>
            </div>
          </details>
        ),
      )}
    </section>
  );
}
export function Dashboard({
  report: r,
  onPerson,
  onAction,
  onCompare,
  onParticipation,
}: Any) {
  const colors = useChartColors();
  const [search, setSearch] = useState(""),
    [page, setPage] = useState(0),
    [sort, setSort] = useState("name");
  const teams = r.team_summary || [];
  const chartBase = {
    backgroundColor: "transparent",
    color: [colors.blue, colors.cyan, colors.purple, colors.pale],
    textStyle: { fontFamily: "Inter, sans-serif", color: colors.text },
    tooltip: {
      trigger: "axis",
      renderMode: "richText",
      backgroundColor: colors.surface,
      borderColor: colors.line,
      textStyle: { color: colors.text },
    },
    legend: {
      bottom: 0,
      textStyle: { color: colors.text },
      itemWidth: 12,
      itemHeight: 8,
    },
  };
  const axis = {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: colors.text, fontSize: 10 },
    splitLine: { lineStyle: { color: colors.line } },
  };
  const teamLabel = (t: Any) => t.team_name.replace(" & ", "\n& ");
  const common = {
    ...chartBase,
    grid: { left: 42, right: 20, top: 20, bottom: 64 },
    xAxis: {
      ...axis,
      type: "category",
      data: teams.map(teamLabel),
      axisLabel: { ...axis.axisLabel, interval: 0 },
    },
    yAxis: { ...axis, type: "value", min: 0, max: 100 },
    series: [
      {
        name: "Ortak yazılı puan",
        type: "bar",
        barMaxWidth: 48,
        itemStyle: { borderRadius: [5, 5, 0, 0] },
        data: teams.map((t: Any) => t.common_score),
      },
    ],
  };
  const participation = {
    ...chartBase,
    grid: { left: 20, right: 24, top: 20, bottom: 44, containLabel: true },
    xAxis: { ...axis, type: "value", minInterval: 1 },
    yAxis: {
      ...axis,
      type: "category",
      data: teams.map((t: Any) => t.team_name),
      axisLabel: { ...axis.axisLabel, width: 120, overflow: "truncate" },
    },
    series: [
      ["Gönderildi", "submitted"],
      ["Taslak", "draft"],
      ["Başlamadı", "not_started"],
    ].map(([name, key], i) => ({
      name,
      type: "bar",
      stack: "people",
      barMaxWidth: 28,
      itemStyle: { color: [colors.blue, colors.cyan, colors.pale][i] },
      data: teams.map((t: Any) => t[key]),
    })),
  };
  const distribution = {
    ...chartBase,
    grid: { left: 44, right: 20, top: 20, bottom: 40 },
    legend: { show: false },
    xAxis: {
      ...axis,
      type: "category",
      name: "Puan",
      data: (r.score_distribution || []).map((d: Any) => d.label),
    },
    yAxis: { ...axis, type: "value", name: "Kişi", minInterval: 1 },
    series: [
      {
        type: "bar",
        barMaxWidth: 60,
        data: (r.score_distribution || []).map((d: Any) => d.count),
        itemStyle: { color: colors.cyan, borderRadius: [5, 5, 0, 0] },
      },
    ],
  };
  const levelData = [1, 2, 3].map((level) => ({
    name: `L${level}`,
    value: r.levels?.[String(level)] || 0,
  }));
  const levels = {
    ...chartBase,
    tooltip: { ...chartBase.tooltip, trigger: "item" },
    series: [
      {
        type: "pie",
        radius: ["44%", "68%"],
        center: ["50%", "44%"],
        label: { color: colors.text, formatter: "{b}: {c}" },
        avoidLabelOverlap: true,
        data: levelData,
      },
    ],
  };
  const gaps = [...r.aggregates]
    .filter((a: Any) => !a.suppressed && a.mean_gap != null && a.mean_gap > 0)
    .sort((a: Any, b: Any) => b.mean_gap - a.mean_gap)
    .slice(0, 6);
  const roleSets = [
    ...new Set(
      r.aggregates
        .filter((a: Any) => a.section === "role")
        .map((a: Any) => a.comparison_group),
    ),
  ];
  const groupLabel = (a: Any) =>
    a.section === "common"
      ? "Ortak soru seti"
      : `Rol soru seti ${roleSets.indexOf(a.comparison_group) + 1}`;
  const gapsChart = {
    ...chartBase,
    legend: { show: false },
    grid: { left: 18, right: 35, top: 12, bottom: 35, containLabel: true },
    xAxis: { ...axis, type: "value", min: 0, max: 3, name: "Seviye farkı" },
    yAxis: {
      ...axis,
      type: "category",
      inverse: true,
      data: gaps.map(
        (a: Any) =>
          `${a.skill_name}\n${a.team_name} · ${a.section === "role" ? a.role_title : "Ortak"}`,
      ),
      axisLabel: { ...axis.axisLabel, width: 170, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 18,
        data: gaps.map((a: Any) => a.mean_gap),
        itemStyle: { color: colors.purple, borderRadius: [0, 4, 4, 0] },
      },
    ],
  };
  const people = Array.from(
    new Map(r.rows.map((row: Any) => [row.participant_id, row])).values(),
  ) as Any[];
  const filteredPeople = people
    .filter((p) =>
      `${p.name} ${p.title} ${p.team_name}`
        .toLocaleLowerCase("tr")
        .includes(search.toLocaleLowerCase("tr")),
    )
    .sort(
      (a, b) =>
        (sort === "team" ? a.team_name.localeCompare(b.team_name, "tr") : 0) ||
        a.name.localeCompare(b.name, "tr"),
    );
  useEffect(
    () => setPage(0),
    [search, sort, r.publication_id, JSON.stringify(r.filters)],
  );
  const count = Math.max(1, Math.ceil(filteredPeople.length / 8));
  const tiles = [
    [
      "Davet edilen çalışan",
      fmt(r.assigned, 0),
      "Seçili çalışan kapsamı",
      Users,
      "blue",
    ],
    [
      "Anket katılımı",
      getLocale() === "en"
        ? `${fmt(r.completion_rate)}%`
        : `%${fmt(r.completion_rate)}`,
      `${r.submitted} gönderildi · ${r.assigned - r.submitted} bekleniyor`,
      ClipboardList,
      "cyan",
    ],
    [
      "Ortak bölüm puanı",
      fmt(r.common_score),
      `${r.common_n} geçerli kişi · 100 üzerinden`,
      BarChart3,
      "purple",
    ],
    [
      "Ortak puan medyanı",
      fmt(r.common_median),
      "Üç ortak yetkinlik · kişi bazında",
      BarChart3,
      "blue",
    ],
    [
      "Ölçülen hedeflere ulaşma",
      r.target_met_rate == null
        ? "—"
        : getLocale() === "en"
          ? `${fmt(r.target_met_rate)}%`
          : `%${fmt(r.target_met_rate)}`,
      r.target_eligible_n
        ? `${r.target_coverage_rate == null ? "Kapsam bastırıldı" : `%${fmt(r.target_coverage_rate)} ölçüm kapsamı`} · ${r.target_comparison_n}/${r.target_eligible_n} gözlem`
        : "Ölçülebilir L1–L3 hedefi yok",
      Target,
      "amber",
    ],
    [
      "Seçili yetkinlikler",
      fmt(new Set(r.rows.map((row: Any) => row.skill_id)).size, 0),
      `${r.complete_people} kişide geçerli yazılı sonuç`,
      ListChecks,
      "cyan",
    ],
  ];
  return (
    <div className="analytics-dashboard">
      <div className="metrics-grid analytics-metrics">
        {translateNode(
          tiles.map(([label, value, sub, Icon, color]: Any) => (
            <section className="metric-card" key={label}>
              <div className="metric-top">
                <span>{translateNode(label)}</span>
                <div className={`metric-icon ${color}`}>
                  <Icon size={18} />
                </div>
              </div>
              <strong>{translateNode(value)}</strong>
              <small>{translateNode(sub)}</small>
            </section>
          )),
        )}
      </div>
      <div className="analytics-scope-note">
        <Info size={16} />
        <p>
          <b>{t("Nas\u0131l okunmal\u0131?")}</b>
          {t(
            " Ortak puan ve da\u011F\u0131l\u0131m, se\u00E7ili \u00E7al\u0131\u015Fanlar\u0131n \u00FC\u00E7 ortak yetkinli\u011Fini temel al\u0131r. Yetkinlik ve b\u00F6l\u00FCm filtreleri seviye, hedef fark\u0131 ve yetkinlik tablosunu daralt\u0131r. Farkl\u0131 rol soru setleri tek bir ba\u015Far\u0131 puan\u0131nda birle\u015Ftirilmez. Yetkinlik se\u00E7imi, yaln\u0131z o formun atand\u0131\u011F\u0131 \u00E7al\u0131\u015Fanlar\u0131 kapsar. Hedef oran\u0131 seviye \u00FCretilebilen L1\u2013L3 hedefleriyle s\u0131n\u0131rl\u0131d\u0131r; kapsam oran\u0131n\u0131n paydas\u0131 yan\u0131t\u0131 olan ki\u015Fi-yetkinlik g\u00F6zlemleridir. ",
          )}
        </p>
      </div>
      {translateNode(
        !r.mock && r.insights?.summary && (
          <section className="panel analytics-insights">
            <h2>{t("De\u011Ferlendirme \u00F6zeti")}</h2>
            <p>{r.insights.summary}</p>
            {translateNode(
              r.insights.actions?.map((text: string, i: number) => (
                <button
                  key={i}
                  className="text-btn"
                  onClick={() => onAction(text)}
                >
                  {translateNode(text)}
                  <ArrowUpRight size={14} />
                </button>
              )),
            )}
          </section>
        ),
      )}
      {translateNode(
        !r.assigned && (
          <div className="notice">
            <Info size={18} />
            {t(
              " Bu filtrelerle e\u015Fle\u015Fen kat\u0131l\u0131mc\u0131 yok. Filtreleri geni\u015Fleterek tekrar deneyin. ",
            )}
          </div>
        ),
      )}
      <div className="analytics-charts">
        <ChartPanel
          title={t("Ekiplerin ortak AI puan\u0131")}
          subtitle="Aynı ortak sorular ve rubrikle karşılaştırma"
          note="0–100 · Her ekipte en az 5 geçerli kişi"
          data={teams.map((t: Any) => [
            t.team_name,
            fmt(t.common_score),
            `${t.common_n} geçerli kişi`,
          ])}
        >
          {translateNode(
            teams.some((t: Any) => t.common_score != null) ? (
              <Chart
                option={common}
                label="Ekip bazında ortak yazılı yanıt puanı"
              />
            ) : (
              <NoChart />
            ),
          )}
        </ChartPanel>
        <ChartPanel
          title={t("Ekip baz\u0131nda kat\u0131l\u0131m")}
          subtitle="Gönderildi, taslak ve başlamayan formlar"
          note={
            <button className="text-btn" onClick={onParticipation}>
              {t(" \u00D6l\u00E7\u00FCm d\u00F6neminin anketlerini a\u00E7 ")}
              <ArrowUpRight size={13} />
            </button>
          }
          data={teams.map((t: Any) => [
            t.team_name,
            `${t.submitted} gönderildi`,
            `${t.draft} taslak`,
            `${t.not_started} başlamadı`,
          ])}
        >
          {translateNode(
            teams.length ? (
              <Chart
                option={participation}
                label="Ekiplerin anket gönderim ve taslak sayıları"
              />
            ) : (
              <NoChart text="Seçili kapsamda katılımcı bulunamadı." />
            ),
          )}
        </ChartPanel>
        <ChartPanel
          title={t("Ortak puan da\u011F\u0131l\u0131m\u0131")}
          subtitle="Her çalışan dağılımda bir kez sayılır"
          note={`${r.common_n} geçerli kişi · Aralıklar puan bandını gösterir; yeterlilik seviyesi değildir.`}
          data={(r.score_distribution || []).map((d: Any) => [
            d.label,
            `${d.count} kişi`,
          ])}
        >
          {translateNode(
            r.score_distribution?.length ? (
              <Chart
                option={distribution}
                label="Kişi bazında ortak yazılı puan dağılımı"
              />
            ) : (
              <NoChart />
            ),
          )}
        </ChartPanel>
        <ChartPanel
          title={t("Anket seviye \u00F6nerileri")}
          subtitle="Seçilen yetkinliklerde L1–L3 dağılımı"
          note={`${r.level_coverage} kişi-yetkinlik gözlemi · ${r.unmeasured_level_count} gözlemde seviye üretilemedi. L4/L5 bu anketle ölçülmez.`}
          data={
            Object.keys(r.levels || {}).length
              ? levelData.map((d) => [d.name, `${d.value} gözlem`])
              : undefined
          }
        >
          {translateNode(
            Object.keys(r.levels || {}).length ? (
              <Chart
                option={levels}
                label="Kişi-yetkinlik bazında anket seviye önerileri"
              />
            ) : (
              <NoChart />
            ),
          )}
        </ChartPanel>
      </div>
      <section className="panel analytics-competencies">
        <div className="panel-head">
          <div>
            <h2>{t("Yetkinlik kar\u015F\u0131la\u015Ft\u0131rmas\u0131")}</h2>
            <p>
              {t(
                " Her sat\u0131r bir ekip, yetkinlik ve kar\u015F\u0131la\u015Ft\u0131r\u0131labilir soru grubudur. ",
              )}
            </p>
          </div>
          <span className="small-pill">
            {translateNode(r.aggregates.length)}
            {t(" kar\u015F\u0131la\u015Ft\u0131rma ")}
          </span>
        </div>
        <div className="analytics-table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("Ekip / soru grubu")}</th>
                <th>{t("Yetkinlik")}</th>
                <th>{t("Yaz\u0131l\u0131 puan")}</th>
                <th>{t("Ge\u00E7erli ki\u015Fi")}</th>
                <th>{t("Hedef / fark")}</th>
                <th>{t("Aksiyon")}</th>
              </tr>
            </thead>
            <tbody>
              {translateNode(
                r.aggregates.map((a: Any) => (
                  <tr key={`${a.team_id}:${a.skill_id}:${a.comparison_group}`}>
                    <td>
                      <b>{translateNode(a.team_name)}</b>
                      <small className="analytics-cell-note">
                        {translateNode(
                          a.section === "common"
                            ? "Ortak soru seti"
                            : a.role_title,
                        )}
                      </small>
                      {translateNode(
                        a.section === "role" && (
                          <small className="analytics-group-id">
                            {translateNode(groupLabel(a))}
                          </small>
                        ),
                      )}
                    </td>
                    <td>
                      {translateNode(a.skill_name)}
                      <small className="analytics-cell-note">
                        {translateNode(
                          a.section === "common" ? "Ortak" : "Role özel",
                        )}
                      </small>
                    </td>
                    <td>
                      <div className="analytics-score">
                        <strong>{translateNode(fmt(a.written_score))}</strong>
                        <div>
                          <span style={{ width: `${a.written_score || 0}%` }} />
                        </div>
                      </div>
                      {translateNode(
                        a.suppressed && (
                          <small className="analytics-cell-note">
                            {t(" 5 ki\u015Fiden az; g\u00F6sterilmez ")}
                          </small>
                        ),
                      )}
                    </td>
                    <td>
                      {translateNode(a.n)}
                      <small className="analytics-cell-note">
                        {translateNode(a.missing)}
                        {t(" eksik ")}
                      </small>
                    </td>
                    <td>
                      {translateNode(
                        a.target_level ? `L${a.target_level}` : "—",
                      )}
                      <small className="analytics-cell-note">
                        {translateNode(
                          a.mean_gap == null
                            ? "Fark ölçülmedi"
                            : `${fmt(a.mean_gap, 2)} seviye farkı`,
                        )}
                      </small>
                    </td>
                    <td>
                      <button
                        className="icon-btn"
                        aria-label={t(
                          `${a.team_name}, ${a.skill_name} için gelişim planı`,
                        )}
                        onClick={() =>
                          onAction(`${a.skill_name} gelişim planı`, a)
                        }
                      >
                        <ArrowUpRight size={17} />
                      </button>
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
        {translateNode(
          !r.rows.length && (
            <div className="analytics-empty">
              {t(
                " Se\u00E7ili filtreler i\u00E7in yay\u0131mlanm\u0131\u015F yetkinlik sonucu bulunamad\u0131. ",
              )}
            </div>
          ),
        )}
      </section>
      <div className="analytics-charts">
        <ChartPanel
          title={t("\u00D6ncelikli geli\u015Fim alanlar\u0131")}
          subtitle="Ölçülebilen hedeflere kalan ortalama seviye farkı"
          note="Yalnız L1–L3 hedefleri · En yüksek farkı olan 6 grup · Bir çalışan sıralaması değildir."
          data={gaps.map((a: Any) => [
            a.team_name,
            a.skill_name,
            groupLabel(a),
            fmt(a.mean_gap, 2),
          ])}
        >
          {translateNode(
            gaps.length ? (
              <Chart
                option={gapsChart}
                height={Math.max(240, gaps.length * 57)}
                label="Ekip ve yetkinlik bazında ortalama hedef farkları"
              />
            ) : (
              <NoChart
                text={
                  r.aggregates.some((a: Any) => a.mean_gap != null)
                    ? "Ölçülebilen hedeflerde seviye farkı yok."
                    : "Seçili kapsamda gösterilebilir hedef farkı bulunamadı."
                }
                note={`${r.target_comparison_n} / ${r.target_eligible_n} hedef gözleminde seviye ölçülebildi. Ölçülemeyenler için hedefe ulaşıldığı söylenemez.`}
              />
            ),
          )}
          <button
            className="analytics-compare-link text-btn"
            onClick={onCompare}
          >
            {t(
              " \u00D6z beyan ve yaz\u0131l\u0131 yan\u0131tlar\u0131 kar\u015F\u0131la\u015Ft\u0131r ",
            )}
            <ArrowUpRight size={14} />
          </button>
        </ChartPanel>
        <section className="panel analytics-people">
          <div className="panel-head">
            <div>
              <h2>{t("Kat\u0131l\u0131mc\u0131 profilleri")}</h2>
              <p>
                {t("Yay\u0131mlanm\u0131\u015F sonucu olan ")}
                {translateNode(people.length)}
                {t(" ki\u015Fi")}
              </p>
            </div>
            <Users size={20} />
          </div>
          <div className="analytics-profile-tools">
            <label className="search">
              <Search size={15} />
              <input
                aria-label={t("Kat\u0131l\u0131mc\u0131 profili ara")}
                placeholder={t("Ad, unvan veya ekip ara")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <select
              aria-label={t("Profil s\u0131ralamas\u0131")}
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="name">{t("Ada g\u00F6re")}</option>
              <option value="team">{t("Ekibe g\u00F6re")}</option>
            </select>
          </div>
          {translateNode(
            filteredPeople.slice(page * 8, page * 8 + 8).map((person: Any) => (
              <button
                className="person-row"
                key={person.participant_id}
                onClick={() => onPerson(person)}
              >
                <span className="person-avatar">
                  {translateNode(person.name[0])}
                </span>
                <span>
                  <b>{person.name}</b>
                  <small>
                    {person.title}
                    {t(" \u00B7 ")}
                    {translateNode(person.team_name)}
                  </small>
                </span>
                <ChevronRight size={16} />
              </button>
            )),
          )}
          {translateNode(
            !filteredPeople.length && (
              <div className="analytics-empty">
                {t(" Araman\u0131zla e\u015Fle\u015Fen profil yok. ")}
              </div>
            ),
          )}
          <div className="analytics-pagination">
            <span>
              {translateNode(filteredPeople.length)}
              {t(" ki\u015Fi \u00B7 ")}
              {translateNode(Math.min(page + 1, count))}
              {t(" /")}
              {translateNode(" ")}
              {translateNode(count)}
            </span>
            <button
              className="icon-btn"
              aria-label={t("\u00D6nceki profil sayfas\u0131")}
              disabled={!page}
              onClick={() => setPage((p) => p - 1)}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              className="icon-btn"
              aria-label={t("Sonraki profil sayfas\u0131")}
              disabled={page + 1 >= count}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
