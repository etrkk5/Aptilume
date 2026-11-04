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
    : Number(value).toLocaleString("tr-TR", { maximumFractionDigits: digits });
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
      aria-label="Rapor filtreleri"
      aria-busy={loading}
    >
      <div className="analytics-filter-heading">
        <div>
          <SlidersHorizontal size={17} />
          <b>Raporu keşfedin</b>
          <span>
            {activeCount
              ? `${activeCount} filtre etkin`
              : "Tüm erişim kapsamınız"}
          </span>
        </div>
        <button className="text-btn" disabled={!activeCount} onClick={onReset}>
          <RotateCcw size={14} /> Filtreleri temizle
        </button>
      </div>
      <div className="analytics-filter-grid">
        {fields.slice(0, 3).map(([key, label, all, entries]) => (
          <label key={key}>
            {label}
            <select
              aria-label={`${label} filtresi`}
              value={value[key]}
              onChange={(e) => update(key, e.target.value)}
            >
              <option value="">{all}</option>
              {entries.map(([id, name]: string[]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <details className="analytics-more-filters">
        <summary>Diğer filtreler · Kademe ve yanıt durumu</summary>
        <div className="analytics-filter-grid">
          {fields.slice(3).map(([key, label, all, entries]) => (
            <label key={key}>
              {label}
              <select
                aria-label={`${label} filtresi`}
                value={value[key]}
                onChange={(e) => update(key, e.target.value)}
              >
                <option value="">{all}</option>
                {entries.map(([id, name]: string[]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      </details>
      <div className="analytics-filter-note">
        <ShieldCheck size={14} />
        <span>
          Filtreler yalnızca yetkili olduğunuz kişilerde uygulanır. Excel aynı
          kapsamı kullanır.{team ? " Ekip kapsamı daraltıldı." : ""}
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
    instance.current?.setOption(option, { notMerge: true });
  }, [JSON.stringify(option)]);
  return (
    <div
      ref={ref}
      role="img"
      aria-label={label}
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
      <p>{text}</p>
      <span>{note}</span>
    </div>
  );
}
function ChartPanel({ title, subtitle, children, note, data }: Any) {
  return (
    <section className="panel analytics-chart-panel">
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </div>
      {children}
      <div className="analytics-chart-note">{note}</div>
      {data && (
        <details className="analytics-chart-data">
          <summary>Grafik verilerini göster</summary>
          <div className="analytics-table-scroll">
            <table>
              <tbody>
                {data.map((row: Any[], i: number) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
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
      `%${fmt(r.completion_rate)}`,
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
      r.target_met_rate == null ? "—" : `%${fmt(r.target_met_rate)}`,
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
        {tiles.map(([label, value, sub, Icon, color]: Any) => (
          <section className="metric-card" key={label}>
            <div className="metric-top">
              <span>{label}</span>
              <div className={`metric-icon ${color}`}>
                <Icon size={18} />
              </div>
            </div>
            <strong>{value}</strong>
            <small>{sub}</small>
          </section>
        ))}
      </div>
      <div className="analytics-scope-note">
        <Info size={16} />
        <p>
          <b>Nasıl okunmalı?</b> Ortak puan ve dağılım, seçili çalışanların üç
          ortak yetkinliğini temel alır. Yetkinlik ve bölüm filtreleri seviye,
          hedef farkı ve yetkinlik tablosunu daraltır. Farklı rol soru setleri
          tek bir başarı puanında birleştirilmez. Yetkinlik seçimi, yalnız o
          formun atandığı çalışanları kapsar. Hedef oranı seviye üretilebilen
          L1–L3 hedefleriyle sınırlıdır; kapsam oranının paydası yanıtı olan
          kişi-yetkinlik gözlemleridir.
        </p>
      </div>
      {!r.mock && r.insights?.summary && (
        <section className="panel analytics-insights">
          <h2>Değerlendirme özeti</h2>
          <p>{r.insights.summary}</p>
          {r.insights.actions?.map((text: string, i: number) => (
            <button key={i} className="text-btn" onClick={() => onAction(text)}>
              {text}
              <ArrowUpRight size={14} />
            </button>
          ))}
        </section>
      )}
      {!r.assigned && (
        <div className="notice">
          <Info size={18} />
          Bu filtrelerle eşleşen katılımcı yok. Filtreleri genişleterek tekrar
          deneyin.
        </div>
      )}
      <div className="analytics-charts">
        <ChartPanel
          title="Ekiplerin ortak AI puanı"
          subtitle="Aynı ortak sorular ve rubrikle karşılaştırma"
          note="0–100 · Her ekipte en az 5 geçerli kişi"
          data={teams.map((t: Any) => [
            t.team_name,
            fmt(t.common_score),
            `${t.common_n} geçerli kişi`,
          ])}
        >
          {teams.some((t: Any) => t.common_score != null) ? (
            <Chart
              option={common}
              label="Ekip bazında ortak yazılı yanıt puanı"
            />
          ) : (
            <NoChart />
          )}
        </ChartPanel>
        <ChartPanel
          title="Ekip bazında katılım"
          subtitle="Gönderildi, taslak ve başlamayan formlar"
          note={
            <button className="text-btn" onClick={onParticipation}>
              Ölçüm döneminin anketlerini aç <ArrowUpRight size={13} />
            </button>
          }
          data={teams.map((t: Any) => [
            t.team_name,
            `${t.submitted} gönderildi`,
            `${t.draft} taslak`,
            `${t.not_started} başlamadı`,
          ])}
        >
          {teams.length ? (
            <Chart
              option={participation}
              label="Ekiplerin anket gönderim ve taslak sayıları"
            />
          ) : (
            <NoChart text="Seçili kapsamda katılımcı bulunamadı." />
          )}
        </ChartPanel>
        <ChartPanel
          title="Ortak puan dağılımı"
          subtitle="Her çalışan dağılımda bir kez sayılır"
          note={`${r.common_n} geçerli kişi · Aralıklar puan bandını gösterir; yeterlilik seviyesi değildir.`}
          data={(r.score_distribution || []).map((d: Any) => [
            d.label,
            `${d.count} kişi`,
          ])}
        >
          {r.score_distribution?.length ? (
            <Chart
              option={distribution}
              label="Kişi bazında ortak yazılı puan dağılımı"
            />
          ) : (
            <NoChart />
          )}
        </ChartPanel>
        <ChartPanel
          title="Anket seviye önerileri"
          subtitle="Seçilen yetkinliklerde L1–L3 dağılımı"
          note={`${r.level_coverage} kişi-yetkinlik gözlemi · ${r.unmeasured_level_count} gözlemde seviye üretilemedi. L4/L5 bu anketle ölçülmez.`}
          data={
            Object.keys(r.levels || {}).length
              ? levelData.map((d) => [d.name, `${d.value} gözlem`])
              : undefined
          }
        >
          {Object.keys(r.levels || {}).length ? (
            <Chart
              option={levels}
              label="Kişi-yetkinlik bazında anket seviye önerileri"
            />
          ) : (
            <NoChart />
          )}
        </ChartPanel>
      </div>
      <section className="panel analytics-competencies">
        <div className="panel-head">
          <div>
            <h2>Yetkinlik karşılaştırması</h2>
            <p>
              Her satır bir ekip, yetkinlik ve karşılaştırılabilir soru
              grubudur.
            </p>
          </div>
          <span className="small-pill">
            {r.aggregates.length} karşılaştırma
          </span>
        </div>
        <div className="analytics-table-scroll">
          <table>
            <thead>
              <tr>
                <th>Ekip / soru grubu</th>
                <th>Yetkinlik</th>
                <th>Yazılı puan</th>
                <th>Geçerli kişi</th>
                <th>Hedef / fark</th>
                <th>Aksiyon</th>
              </tr>
            </thead>
            <tbody>
              {r.aggregates.map((a: Any) => (
                <tr key={`${a.team_id}:${a.skill_id}:${a.comparison_group}`}>
                  <td>
                    <b>{a.team_name}</b>
                    <small className="analytics-cell-note">
                      {a.section === "common"
                        ? "Ortak soru seti"
                        : a.role_title}
                    </small>
                    {a.section === "role" && (
                      <small className="analytics-group-id">
                        {groupLabel(a)}
                      </small>
                    )}
                  </td>
                  <td>
                    {a.skill_name}
                    <small className="analytics-cell-note">
                      {a.section === "common" ? "Ortak" : "Role özel"}
                    </small>
                  </td>
                  <td>
                    <div className="analytics-score">
                      <strong>{fmt(a.written_score)}</strong>
                      <div>
                        <span style={{ width: `${a.written_score || 0}%` }} />
                      </div>
                    </div>
                    {a.suppressed && (
                      <small className="analytics-cell-note">
                        5 kişiden az; gösterilmez
                      </small>
                    )}
                  </td>
                  <td>
                    {a.n}
                    <small className="analytics-cell-note">
                      {a.missing} eksik
                    </small>
                  </td>
                  <td>
                    {a.target_level ? `L${a.target_level}` : "—"}
                    <small className="analytics-cell-note">
                      {a.mean_gap == null
                        ? "Fark ölçülmedi"
                        : `${fmt(a.mean_gap, 2)} seviye farkı`}
                    </small>
                  </td>
                  <td>
                    <button
                      className="icon-btn"
                      aria-label={`${a.team_name}, ${a.skill_name} için gelişim planı`}
                      onClick={() =>
                        onAction(`${a.skill_name} gelişim planı`, a)
                      }
                    >
                      <ArrowUpRight size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!r.rows.length && (
          <div className="analytics-empty">
            Seçili filtreler için yayımlanmış yetkinlik sonucu bulunamadı.
          </div>
        )}
      </section>
      <div className="analytics-charts">
        <ChartPanel
          title="Öncelikli gelişim alanları"
          subtitle="Ölçülebilen hedeflere kalan ortalama seviye farkı"
          note="Yalnız L1–L3 hedefleri · En yüksek farkı olan 6 grup · Bir çalışan sıralaması değildir."
          data={gaps.map((a: Any) => [
            a.team_name,
            a.skill_name,
            groupLabel(a),
            fmt(a.mean_gap, 2),
          ])}
        >
          {gaps.length ? (
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
          )}
          <button
            className="analytics-compare-link text-btn"
            onClick={onCompare}
          >
            Öz beyan ve yazılı yanıtları karşılaştır <ArrowUpRight size={14} />
          </button>
        </ChartPanel>
        <section className="panel analytics-people">
          <div className="panel-head">
            <div>
              <h2>Katılımcı profilleri</h2>
              <p>Yayımlanmış sonucu olan {people.length} kişi</p>
            </div>
            <Users size={20} />
          </div>
          <div className="analytics-profile-tools">
            <label className="search">
              <Search size={15} />
              <input
                aria-label="Katılımcı profili ara"
                placeholder="Ad, unvan veya ekip ara"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <select
              aria-label="Profil sıralaması"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="name">Ada göre</option>
              <option value="team">Ekibe göre</option>
            </select>
          </div>
          {filteredPeople.slice(page * 8, page * 8 + 8).map((person: Any) => (
            <button
              className="person-row"
              key={person.participant_id}
              onClick={() => onPerson(person)}
            >
              <span className="person-avatar">{person.name[0]}</span>
              <span>
                <b>{person.name}</b>
                <small>
                  {person.title} · {person.team_name}
                </small>
              </span>
              <ChevronRight size={16} />
            </button>
          ))}
          {!filteredPeople.length && (
            <div className="analytics-empty">
              Aramanızla eşleşen profil yok.
            </div>
          )}
          <div className="analytics-pagination">
            <span>
              {filteredPeople.length} kişi · {Math.min(page + 1, count)} /{" "}
              {count}
            </span>
            <button
              className="icon-btn"
              aria-label="Önceki profil sayfası"
              disabled={!page}
              onClick={() => setPage((p) => p - 1)}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              className="icon-btn"
              aria-label="Sonraki profil sayfası"
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
