import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import * as echarts from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Clock3,
  Database,
  FileText,
  FlaskConical,
  Layers3,
  LayoutDashboard,
  LoaderCircle,
  MoreHorizontal,
  Network,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
  Users,
  X,
  Zap,
  UserRound,
  LogOut,
  Info,
  ListChecks,
} from "lucide-react";
import "./style.css";
import { api } from "./client";
import { useIdentity, Login } from "./identity";
import { Button, Modal } from "./ui";
import { ThemeSwitch } from "./theme";
import {
  AccountPanel,
  DirectorySettings,
  ActionEditor,
  DevelopmentPlans,
  Comparison,
  PersonalProfile,
} from "./product-ui";
echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

type Any = any;
const API = "/api/v1";
const labels: Record<string, string> = {
  draft: "Taslak",
  preparing: "Hazırlanıyor",
  content_review: "İçerik incelemesi",
  ready: "Hazır",
  open: "Yanıt toplanıyor",
  closed: "Kapandı",
  queued: "Sırada",
  evaluating: "Değerlendiriliyor",
  validating: "Kontroller sürüyor",
  review_required: "İnceleme gerekli",
  ready_to_publish: "Yayına hazır",
  published: "Yayımlandı",
  failed: "Hata",
  cancelled: "İptal",
  submitted: "Gönderildi",
  not_started: "Başlamadı",
  done: "Tamamlandı",
  running: "Çalışıyor",
  complete: "Tamamlandı",
  incomplete: "Eksik",
  clear: "Kontrol edildi",
  resolved: "İncelendi",
};
const fmt = (v: Any, d = 0) =>
  v === null || v === undefined
    ? "—"
    : Number(v).toLocaleString("tr-TR", { maximumFractionDigits: d });
function Badge({
  status,
  children,
}: {
  status?: string;
  children?: React.ReactNode;
}) {
  return (
    <span className={`badge ${status || ""}`}>
      <i />
      {children || labels[status || ""] || status}
    </span>
  );
}
function Empty({ title, text, action }: Any) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Layers3 size={30} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
function Chart({ option, height = 260 }: Any) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!el.current) return;
    const c = echarts.init(el.current);
    c.setOption(option);
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      c.dispose();
    };
  }, [JSON.stringify(option)]);
  return <div ref={el} style={{ height, width: "100%" }} />;
}
const nav = [
  ["overview", "Genel görünüm", LayoutDashboard],
  ["campaigns", "Ölçüm dönemleri", ClipboardList],
  ["teams", "Ekipler ve hedefler", Users],
  ["catalog", "Yetkinlik kataloğu", BookOpen],
  ["survey", "Anketler", FileText],
  ["development", "Gelişim planları", ListChecks],
  ["profile", "Profilim", UserRound],
  ["jobs", "Değerlendirmeler", Activity],
  ["connections", "Bağlantı ayarları", Settings2],
] as const;

function App() {
  const { user, setUser, signIn, signOut } = useIdentity();
  const identityKey = useRef("");
  identityKey.current = user ? user.id + ":" + user.scope_revision : "";
  const reportRequest = useRef(0);
  const [view, setView] = useState("overview"),
    [boot, setBoot] = useState<Any>(null),
    [selected, setSelected] = useState(""),
    [report, setReport] = useState<Any>(null),
    [team, setTeam] = useState(""),
    [toast, setToast] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [detail, setDetail] = useState<Any>(null),
    [exportDetail, setExportDetail] = useState(false),
    [surveyCampaign, setSurveyCampaign] = useState("");
  const [accountMenu, setAccountMenu] = useState(false),
    [accountPanel, setAccountPanel] = useState(false),
    [workspaceSettings, setWorkspaceSettings] = useState<Any>(null),
    [reportInfo, setReportInfo] = useState(false),
    [comparison, setComparison] = useState(false),
    [actionDraft, setActionDraft] = useState<Any>(null);
  const availableNav = nav.filter(
    ([id]) =>
      user?.permissions.all_data ||
      (user?.permissions.manage_business && id !== "connections") ||
      (user?.permissions.integrations && id === "connections") ||
      (user?.permissions.business && ["profile", "survey"].includes(id)),
  );
  const notify = (s: string) => {
    setToast(s);
    setTimeout(() => setToast(""), 4500);
  };
  async function refresh() {
    const key = identityKey.current;
    try {
      const b = await api("/bootstrap");
      if (key !== identityKey.current) return;
      if (b.identity && b.identity.scope_revision !== user?.scope_revision) {
        setBoot(null);
        setReport(null);
        setDetail(null);
        setUser(b.identity);
        return;
      }
      setBoot(b);
      setSelected(
        (prev) =>
          (b.campaigns.some((c: Any) => c.id === prev) ? prev : "") ||
          b.campaigns.find((c: Any) => c.publication_id)?.id ||
          b.campaigns[0]?.id ||
          "",
      );
      if (b.degraded) {
        setView("connections");
        setError(b.message);
      } else setError("");
    } catch (e: Any) {
      setError(e.message);
    }
  }
  useEffect(() => {
    setBoot(null);
    setReport(null);
    setSelected("");
    setTeam("");
    setDetail(null);
    setAccountMenu(false);
    setAccountPanel(false);
    setActionDraft(null);
    setSurveyCampaign("");
    if (!user) return;
    setView(
      user.permissions.all_data || user.permissions.manage_business
        ? "overview"
        : user.permissions.integrations
          ? "connections"
          : "profile",
    );
    api("/settings/workspace")
      .then(setWorkspaceSettings)
      .catch(() => {});
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [user?.id, user?.scope_revision]);
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAccountMenu(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  const campaign = boot?.campaigns.find((c: Any) => c.id === selected);
  async function refreshReport() {
    const key = identityKey.current,
      request = ++reportRequest.current;
    if (campaign?.publication_id) {
      try {
        const result = await api(
          `/reports/${campaign.publication_id}${team ? "?team_id=" + team : ""}`,
        );
        if (key === identityKey.current && request === reportRequest.current)
          setReport(result);
      } catch (e: Any) {
        setError(e.message);
      }
    } else setReport(null);
  }
  useEffect(() => {
    refreshReport();
  }, [selected, campaign?.publication_id, team]);
  async function action(task: () => Promise<Any>, message?: string) {
    setBusy(true);
    try {
      const r = await task();
      if (message) notify(message);
      await refresh();
      await refreshReport();
      return r;
    } catch (e: Any) {
      notify(e.message);
      return null;
    } finally {
      setBusy(false);
    }
  }
  if (user === undefined)
    return (
      <div className="startup">
        <img
          className="startup-logo"
          src="/brand/yapi-kredi-logo.svg"
          alt="Yapı Kredi"
        />
        <LoaderCircle className="spin" />
      </div>
    );
  if (!user) return <Login onLogin={signIn} />;
  if (!boot)
    return (
      <div className="startup">
        <img
          className="startup-logo"
          src="/brand/yapi-kredi-logo.svg"
          alt="Yapı Kredi"
        />
        <h1>Aptilume</h1>
        <p>AI Skills Intelligence</p>
        {error ? <p>{error}</p> : <LoaderCircle className="spin" />}
      </div>
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="product-brand corporate-brand"
          onClick={() => setView(availableNav[0]?.[0] || "connections")}
          aria-label="Ana sayfa"
        >
          <img src="/brand/yapi-kredi-logo.svg" alt="Yapı Kredi" />
          <span>
            Aptilume<small>AI Skills Intelligence</small>
          </span>
        </button>
        <div className="workspace-label">ÇALIŞMA ALANI</div>
        <div className="workspace">
          <span className="workspace-dot" />
          {workspaceSettings?.name || "Yapı Kredi Teknoloji"}
        </div>
        <nav>
          {availableNav.map(([id, label, Icon], i) => (
            <React.Fragment key={id}>
              {id === "jobs" && <div className="nav-section">YÖNETİM</div>}
              <button
                className={view === id ? "nav-link active" : "nav-link"}
                onClick={() => {
                  setView(id);
                  if (id === "survey") setSurveyCampaign("");
                  setDetail(null);
                }}
              >
                <Icon size={19} />
                {label}
                {id === "catalog" && <span className="nav-count">42</span>}
              </button>
            </React.Fragment>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="user">
            <div className="avatar">
              <UserRound size={16} />
            </div>
            <div>
              {user.display_name}
              <small>
                {
                  (
                    {
                      admin: "Entegrasyon yöneticisi",
                      hr: "İnsan kaynakları",
                      manager: "Ekip yöneticisi",
                      employee: "Çalışan",
                    } as Any
                  )[user.roles[0]]
                }
              </small>
            </div>
            <button
              className="icon-btn account-toggle"
              aria-label="Yönetici menüsü"
              aria-expanded={accountMenu}
              onClick={() => setAccountMenu(!accountMenu)}
            >
              <MoreHorizontal size={18} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Çalışma alanı <ChevronRight size={14} />
            <b>{nav.find((x) => x[0] === view)?.[1]}</b>
          </div>
          <div className="topbar-right">
            <ThemeSwitch />
            <img src="/brand/yapi-kredi-logo.svg" alt="Yapı Kredi" />
            <button
              className="icon-btn"
              aria-label="Hesap menüsü"
              aria-expanded={accountMenu}
              onClick={() => setAccountMenu(!accountMenu)}
            >
              <UserRound size={18} />
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">AI YETKİNLİK HARİTASI</div>
              <h1>
                {
                  (
                    {
                      overview: "AI yetkinlik özeti",
                      campaigns: "Ölçüm dönemleri",
                      teams: "Ekipler ve rol hedefleri",
                      catalog: "Yetkinlik kataloğu",
                      survey: "Katılımcı anketleri",
                      jobs: "Toplu değerlendirmeler",
                      connections: "Entegrasyon yönetimi",
                      development: "Gelişim planları",
                      profile: "Yetkinlik profilim",
                    } as Any
                  )[view]
                }
              </h1>
              <p>
                {
                  (
                    {
                      overview:
                        "Ekiplerinizin AI yetkinliklerini keşfedin, gelişim alanlarını belirleyin.",
                      campaigns:
                        "Anketi hazırlayın, yanıtları toplayın ve dönem sonunda değerlendirin.",
                      teams:
                        "Ekip bağlamı ve rol hedefleri, kişiselleştirilmiş soruların temelini oluşturur.",
                      catalog:
                        "42 yetkinlik ve beş seviye ile kurum çapında tutarlı bir çerçeve.",
                      survey:
                        "Açık uçlu sorularla yaklaşımınızı, kontrollerinizi ve deneyiminizi paylaşın.",
                      jobs: "Anket kapanışından sonra çalışan toplu işleri ve incelemeleri takip edin.",
                      connections:
                        "Active Directory, LLM modelleri ve veritabanı bağlantılarını yönetin.",
                      development:
                        "Ölçüm sonuçlarını sorumlusu ve tarihi belirli gelişim aksiyonlarına dönüştürün.",
                      profile:
                        "Kendi değerlendirmelerinizi, hedeflerinizi ve gelişim planlarınızı takip edin.",
                    } as Any
                  )[view]
                }
              </p>
            </div>
            {view === "overview" && (
              <Button
                onClick={() =>
                  action(async () => {
                    const e = await api("/exports", "POST", {
                      publication_id: campaign.publication_id,
                      filters: { team_id: team || undefined },
                      detail: exportDetail,
                    });
                    notify(
                      "Excel hazırlanıyor. Değerlendirmeler ekranından indirebilirsiniz.",
                    );
                    return e;
                  })
                }
                disabled={!report || busy}
              >
                <ArrowDownToLine size={17} /> Excel’e aktar
              </Button>
            )}
          </div>
          {error && <div className="notice error">{error}</div>}
          {view === "overview" && (
            <>
              <div className="toolbar">
                <div className="filter-field">
                  <ClipboardList size={16} />
                  <select
                    aria-label="Ölçüm dönemi"
                    value={selected}
                    onChange={(e) => setSelected(e.target.value)}
                  >
                    {boot.campaigns.map((c: Any) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="filter-field">
                  <Users size={16} />
                  <select
                    aria-label="Ekip filtresi"
                    value={team}
                    onChange={(e) => setTeam(e.target.value)}
                  >
                    <option value="">Tüm ekipler</option>
                    {boot.teams.map((t: Any) => (
                      <option value={t.id} key={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
                <label className="export-toggle">
                  <input
                    type="checkbox"
                    checked={exportDetail}
                    onChange={(e) => setExportDetail(e.target.checked)}
                  />
                  Açık yanıtları dahil et
                </label>
                {report && (
                  <button
                    className="text-btn"
                    onClick={() => setReportInfo(true)}
                  >
                    <Info size={14} />
                    Rapor bilgileri
                  </button>
                )}
                <div className="toolbar-end">
                  <span className="live-dot" />
                  {report
                    ? "Yayımlanmış sonuç sürümü"
                    : "Henüz sonuç yayımlanmadı"}
                </div>
              </div>
              {report ? (
                <Dashboard
                  report={report}
                  onPerson={setDetail}
                  onAction={(title: string) =>
                    setActionDraft({
                      title,
                      publication_id: report.publication_id,
                      team_id: team,
                      participant_id: "",
                      skill_id: "",
                      owner_name: user.display_name,
                      due_date: "",
                      notes: "",
                      status: "planned",
                    })
                  }
                  onCompare={() => setComparison(true)}
                  onParticipation={() => {
                    setSurveyCampaign(selected);
                    setView("survey");
                  }}
                />
              ) : (
                <Empty
                  title="Bu dönemin sonuçları henüz hazır değil"
                  text="Yanıtlar toplandıktan ve kampanya kapandıktan sonra toplu değerlendirme başlatılır."
                  action={
                    <Button onClick={() => setView("campaigns")}>
                      Ölçüm dönemine git <ArrowRight size={16} />
                    </Button>
                  }
                />
              )}
            </>
          )}
          {view === "campaigns" && (
            <Campaigns
              boot={boot}
              action={action}
              busy={busy}
              setView={setView}
            />
          )}
          {view === "teams" && (
            <>
              <Teams boot={boot} action={action} user={user} />
              <RoleProfiles boot={boot} action={action} user={user} />
            </>
          )}
          {view === "catalog" && <Catalog />}
          {view === "survey" && (
            <Survey
              boot={boot}
              notify={notify}
              refresh={refresh}
              initialCampaign={surveyCampaign}
            />
          )}
          {view === "jobs" && <Jobs action={action} notify={notify} />}
          {view === "connections" && (
            <>
              <DirectorySettings action={action} busy={busy} />
              <Connections action={action} notify={notify} />
            </>
          )}
          {view === "development" && (
            <DevelopmentPlans
              boot={boot}
              user={user}
              action={action}
              onEdit={setActionDraft}
            />
          )}
          {view === "profile" && (
            <PersonalProfile user={user} onSurvey={() => setView("survey")} />
          )}
          <footer>
            <span>
              Aptilume <i /> AI Skills Intelligence
            </span>
            <span>Yapı Kredi · Kurum içi gelişim çalışma alanı</span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={19} />
          {toast}
        </div>
      )}
      {detail && (
        <Modal
          title={detail.name + " · Yetkinlik profili"}
          onClose={() => setDetail(null)}
        >
          <div className="modal-body">
            <p className="muted">
              {detail.team_name} · {detail.title}
            </p>
            <p className="muted">
              Yazılı yanıt puanı, öz beyan ve anket seviye önerisi birlikte
              gösterilir.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Yetkinlik</th>
                  <th>Yazılı puan</th>
                  <th>Öz beyan</th>
                  <th>Öneri</th>
                  <th>Hedef</th>
                </tr>
              </thead>
              <tbody>
                {report.rows
                  .filter(
                    (x: Any) => x.participant_id === detail.participant_id,
                  )
                  .map((r: Any) => (
                    <tr key={r.skill_id}>
                      <td>{r.skill_name}</td>
                      <td>{fmt(r.written_score, 1)}</td>
                      <td>{r.self_level ? "L" + r.self_level : "—"}</td>
                      <td>
                        {r.suggested_level
                          ? "L" + r.suggested_level
                          : "Ölçülmedi"}
                      </td>
                      <td>L{r.target_level}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Modal>
      )}
      {accountMenu && (
        <>
          <button
            className="menu-dismiss"
            aria-label="Hesap menüsünü kapat"
            onClick={() => setAccountMenu(false)}
          />
          <div className="user-menu" role="menu">
            <strong>{user.display_name}</strong>
            <small>{user.username}</small>
            <button
              role="menuitem"
              onClick={() => {
                setAccountMenu(false);
                setAccountPanel(true);
              }}
            >
              <UserRound size={16} />
              Hesap bilgilerim
            </button>
            {user.permissions.integrations && (
              <button
                role="menuitem"
                onClick={() => {
                  setAccountMenu(false);
                  setView("connections");
                }}
              >
                <Settings2 size={16} />
                Entegrasyon ayarları
              </button>
            )}
            <button
              role="menuitem"
              onClick={() => {
                setAccountMenu(false);
                signOut();
              }}
            >
              <LogOut size={16} />
              Çıkış yap
            </button>
          </div>
        </>
      )}
      {accountPanel && (
        <AccountPanel
          user={user}
          workspace={workspaceSettings}
          action={action}
          onWorkspace={setWorkspaceSettings}
          onClose={() => setAccountPanel(false)}
          onPasswordChanged={signOut}
        />
      )}
      {reportInfo && report && (
        <Modal title="Rapor bilgileri" onClose={() => setReportInfo(false)}>
          <div className="modal-body">
            <dl className="report-info">
              <dt>Ölçüm dönemi</dt>
              <dd>{report.campaign_name}</dd>
              <dt>Sonuç sürümü</dt>
              <dd>
                v{report.report_info?.version} · {report.publication_id}
              </dd>
              <dt>Yayın tarihi</dt>
              <dd>
                {report.report_info?.published_at
                  ? new Date(report.report_info.published_at).toLocaleString(
                      "tr-TR",
                    )
                  : "—"}
              </dd>
              <dt>Değerlendirme kaynağı</dt>
              <dd>
                {report.report_info?.source === "simulation"
                  ? "Test sağlayıcısı · örnek yanıtlar"
                  : "LLM değerlendirmesi"}
              </dd>
              <dt>Veri kapsamı</dt>
              <dd>
                {user.permissions.all_data
                  ? "Kurum geneli"
                  : user.permissions.manage_business
                    ? "Yönettiğiniz çalışanlar"
                    : "Kendi profiliniz"}
              </dd>
              <dt>Puanlama yöntemi</dt>
              <dd>
                Rubrik puanı, bilgi kontrolü ve öz beyan ayrı hesaplanır.
                Ölçülmeyen seviyeler için beceri açığı yazılmaz.
              </dd>
            </dl>
          </div>
        </Modal>
      )}
      {comparison && report && (
        <Comparison
          report={report}
          onClose={() => setComparison(false)}
          onPerson={(p: Any) => {
            setComparison(false);
            setDetail(p);
          }}
        />
      )}
      {actionDraft && (
        <ActionEditor
          draft={actionDraft}
          boot={boot}
          user={user}
          action={action}
          onClose={() => setActionDraft(null)}
        />
      )}
    </div>
  );
}

function Dashboard({
  report: r,
  onPerson,
  onAction,
  onCompare,
  onParticipation,
}: Any) {
  const people = Array.from(
    new Map(r.rows.map((x: Any) => [x.participant_id, x])).values(),
  ) as Any[];
  const teamNames = [
    ...new Set<string>(r.aggregates.map((x: Any) => x.team_name)),
  ];
  const core = [
    ...new Set<string>(
      r.aggregates
        .filter((x: Any) => x.section === "common")
        .map((x: Any) => x.skill_name),
    ),
  ];
  const bar = {
    grid: { left: 35, right: 20, top: 25, bottom: 35 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: teamNames.map((x) => x.replace(" & ", "\n& ")),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "#6b7b91", fontSize: 11, interval: 0 },
    },
    yAxis: {
      type: "value",
      max: 100,
      splitLine: { lineStyle: { color: "#edf1f6" } },
      axisLabel: { color: "#98a3b5" },
    },
    series: [
      {
        type: "bar",
        barWidth: 42,
        itemStyle: { color: "#0056a6", borderRadius: [5, 5, 0, 0] },
        data: teamNames.map((t) => {
          const v = r.aggregates.filter(
            (x: Any) =>
              x.team_name === t &&
              x.section === "common" &&
              x.written_score != null,
          );
          return v.length
            ? v.reduce((a: number, b: Any) => a + b.written_score, 0) / v.length
            : null;
        }),
      },
    ],
  };
  const tiles = [
    {
      label: "Davet edilen çalışan",
      value: fmt(r.assigned),
      sub: "Seçili ölçüm dönemi kapsamı",
      Icon: Users,
      color: "blue",
    },
    {
      label: "Anket katılımı",
      value: `%${fmt(r.completion_rate, 1)}`,
      sub: `${r.submitted} çalışan yanıtını gönderdi`,
      Icon: ClipboardList,
      color: "cyan",
    },
    {
      label: "Ortak bölüm puanı",
      value: fmt(r.common_score, 1),
      sub: `100 üzerinden · ${r.common_n} geçerli kişi`,
      Icon: BarChart3,
      color: "purple",
    },
    {
      label: "Yetkinlik kapsamı",
      value: fmt(new Set(r.rows.map((x: Any) => x.skill_id)).size),
      sub: "3 ortak + role özel yetkinlikler",
      Icon: Target,
      color: "amber",
    },
  ];
  return (
    <>
      <div className="metrics-grid">
        {tiles.map((t) => (
          <section className="metric-card" key={t.label}>
            <div className="metric-top">
              <span>{t.label}</span>
              <div className={`metric-icon ${t.color}`}>
                <t.Icon size={18} />
              </div>
            </div>
            <strong>{t.value}</strong>
            <small>{t.sub}</small>
          </section>
        ))}
      </div>
      <div className="insight-strip">
        <div className="sparkle-box">
          <Sparkles size={22} />
        </div>
        <div>
          <b>Veriyi gelişim fırsatına dönüştürün.</b>
          <p>
            {(!r.mock && r.insights?.summary) ||
              `${r.assigned} katılımcının ${r.submitted} tanesi yanıtlarını gönderdi. Yetkinlik haritasından ekip sonuçlarına, gelişim odaklarından aksiyon planlarına ulaşabilirsiniz.`}
          </p>
        </div>
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Ekiplerin ortak AI yetkinlikleri</h2>
              <p>Aynı sorular ve aynı rubrikle karşılaştırma</p>
            </div>
            <span className="small-pill">0–100</span>
          </div>
          <Chart option={bar} />
          <div className="chart-caption">
            <span className="legend-dot" /> Ortak yazılı bölüm{" "}
            <span className="muted">· En az 5 geçerli kişi</span>
          </div>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Katılım görünümü</h2>
              <p>Yanıt toplama kapsamı</p>
            </div>
            <button
              className="icon-btn"
              aria-label="Katılım ayrıntılarını aç"
              onClick={onParticipation}
            >
              <MoreHorizontal size={20} />
            </button>
          </div>
          <div className="participation">
            <div
              className="donut"
              style={{ "--pct": r.completion_rate + "%" } as Any}
            >
              <div>
                <strong>%{fmt(r.completion_rate)}</strong>
                <span>tamamlanma</span>
              </div>
            </div>
            <div className="participation-legend">
              <div>
                <i className="legend-dot" />
                Gönderildi<strong>{r.submitted}</strong>
              </div>
              <div>
                <i className="legend-dot grey" />
                Yanıt bekleniyor<strong>{r.assigned - r.submitted}</strong>
              </div>
            </div>
          </div>
          <div className="mini-note">
            <ShieldCheck size={16} /> Katılım, yetkinlik puanından ayrı izlenir.
          </div>
        </section>
      </div>
      <section className="panel heatmap-panel">
        <div className="panel-head">
          <div>
            <h2>Yetkinlik haritası</h2>
            <p>Ekiplerin ortak bölümdeki yazılı yanıt puanları</p>
          </div>
          <div className="heatmap-scale">
            <span>Düşük</span>
            {["#edf3fa", "#d0e4f6", "#94bfe3", "#4a91cc", "#0056a6"].map(
              (c) => (
                <i style={{ background: c }} key={c} />
              ),
            )}
            <span>Yüksek</span>
          </div>
        </div>
        <table className="heat-table">
          <thead>
            <tr>
              <th>Ekip</th>
              {core.map((c) => (
                <th key={c}>{c}</th>
              ))}
              <th>Geçerli kişi</th>
            </tr>
          </thead>
          <tbody>
            {teamNames.map((t) => (
              <tr key={t}>
                <td>
                  <div className="team-cell">
                    <span className="team-symbol">{t[0]}</span>
                    {t}
                  </div>
                </td>
                {core.map((c) => {
                  const a = r.aggregates.find(
                    (x: Any) => x.team_name === t && x.skill_name === c,
                  );
                  const v = a?.written_score;
                  return (
                    <td key={c}>
                      <div
                        className="heat-cell"
                        style={{
                          background:
                            v == null
                              ? "var(--soft)"
                              : `rgba(0,86,166,${0.08 + v / 160})`,
                          color: v > 60 ? "white" : "#004587",
                        }}
                      >
                        {fmt(v, 1)}
                      </div>
                    </td>
                  );
                })}
                <td className="muted">
                  {r.aggregates.find((x: Any) => x.team_name === t)?.n || 0}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <div className="dashboard-grid bottom-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Gelişim odakları</h2>
              <p>Rol hedeflerini uygulamalı çalışmalarla destekleyin</p>
            </div>
            <Target size={20} />
          </div>
          {r.insights?.actions?.map((x: string, i: number) => (
            <button
              className="action-item action-button"
              key={i}
              onClick={() => onAction(x)}
            >
              <span>0{i + 1}</span>
              <div>
                <b>{x}</b>
                <p>Skill Owner geri bildirimi ile ilerlemeyi izleyin.</p>
              </div>
              <ArrowUpRight size={18} />
            </button>
          ))}
          {!r.insights?.actions?.length && (
            <button
              className="action-item action-button"
              onClick={() => onAction("Yetkinlik gelişim planı")}
            >
              <span>01</span>
              <div>
                <b>Yetkinlik için gelişim planı oluşturun.</b>
                <p>Katılımcı, sorumlu ve hedef tarihi belirleyin.</p>
              </div>
              <ArrowUpRight size={18} />
            </button>
          )}
          <button className="action-item action-button" onClick={onCompare}>
            <span>02</span>
            <div>
              <b>Öz beyan ve yazılı yanıtları birlikte inceleyin.</b>
              <p>
                İki gösterge farklı bilgi sağlar; tek puanda birleştirilmez.
              </p>
            </div>
            <ArrowUpRight size={18} />
          </button>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Katılımcı profilleri</h2>
              <p>Çalışanların yetkinlik profillerini inceleyin</p>
            </div>
            <Users size={20} />
          </div>
          {people.slice(0, 4).map((p: Any, i: number) => (
            <button
              className="person-row"
              key={p.participant_id}
              onClick={() => onPerson(p)}
            >
              <span className={"person-avatar p" + i}>{p.name[0]}</span>
              <span>
                <b>{p.name}</b>
                <small>{p.team_name}</small>
              </span>
              <ChevronRight size={17} />
            </button>
          ))}
        </section>
      </div>
    </>
  );
}

function Campaigns({ boot, action, busy, setView }: Any) {
  const [modal, setModal] = useState(false),
    [name, setName] = useState(""),
    [qs, setQs] = useState<Any>(null);
  return (
    <>
      <div className="section-toolbar">
        <span className="muted">{boot.campaigns.length} ölçüm dönemi</span>
        <Button onClick={() => setModal(true)}>
          <Plus size={17} /> Yeni ölçüm dönemi
        </Button>
      </div>
      <div className="campaign-list">
        {boot.campaigns.map((c: Any) => (
          <section className="panel campaign-card" key={c.id}>
            <div className="campaign-icon">
              <ClipboardList size={26} />
            </div>
            <div className="campaign-main">
              <div className="campaign-title">
                <h2>{c.name}</h2>
                <Badge status={c.status} />
                {c.publication_id && <Badge status="published" />}
              </div>
              <p>Açık uçlu ağırlıklı · 22 soru · 6 yetkinlik / rol</p>
              <div className="campaign-meta">
                <span>
                  <Users size={15} />
                  {c.assigned} katılımcı
                </span>
                <span>
                  <CheckCircle2 size={15} />
                  {c.submitted} gönderim
                </span>
                <span>
                  <Clock3 size={15} />
                  {new Date(c.created_at).toLocaleDateString("tr-TR")}
                </span>
              </div>
            </div>
            <div
              className="campaign-actions"
              style={c.can_manage === false ? { display: "none" } : undefined}
            >
              {c.status === "draft" && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    action(
                      () =>
                        api(`/campaigns/${c.id}/generate-questions`, "POST"),
                      "Soru hazırlama işi sıraya alındı.",
                    )
                  }
                >
                  Soruları hazırla <Sparkles size={15} />
                </Button>
              )}
              {c.status === "content_review" && (
                <>
                  <Button
                    secondary
                    onClick={async () =>
                      setQs(await api(`/campaigns/${c.id}/questions`))
                    }
                  >
                    Soruları incele
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() =>
                      action(
                        () => api(`/campaigns/${c.id}/approve`, "POST"),
                        "Soru seti onaylandı.",
                      )
                    }
                  >
                    Seti onayla <Check size={15} />
                  </Button>
                </>
              )}
              {c.status === "ready" && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    action(
                      () => api(`/campaigns/${c.id}/open`, "POST"),
                      "Anket yanıt toplamaya açıldı.",
                    )
                  }
                >
                  Anketi aç <ArrowRight size={15} />
                </Button>
              )}
              {c.status === "open" && (
                <>
                  <Button secondary onClick={() => setView("survey")}>
                    Formlara git
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() =>
                      action(
                        () => api(`/campaigns/${c.id}/close`, "POST"),
                        "Kampanya kapandı. Toplu değerlendirme başlatılabilir.",
                      )
                    }
                  >
                    Dönemi kapat
                  </Button>
                </>
              )}
              {c.status === "closed" && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    action(
                      () => api(`/campaigns/${c.id}/evaluation-runs`, "POST"),
                      "Değerlendirme işi sıraya alındı.",
                    )
                  }
                >
                  Toplu değerlendir <Zap size={16} />
                </Button>
              )}
            </div>
          </section>
        ))}
      </div>
      <div className="notice">
        <Clock3 size={18} />
        <span>
          Değerlendirme, dönem kapandıktan sonra başlatılır. Form gönderimi
          sırasında LLM puanlaması yapılmaz.
        </span>
      </div>
      {modal && (
        <Modal title="Yeni ölçüm dönemi" onClose={() => setModal(false)}>
          <form
            className="modal-body"
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                await action(
                  () => api("/campaigns", "POST", { name }),
                  "Ölçüm dönemi oluşturuldu.",
                )
              ) {
                setModal(false);
                setName("");
              }
            }}
          >
            <label>
              Dönem adı
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Örn. AI Skills Baseline · Q1 2027"
              />
            </label>
            <p className="muted">
              Mevcut ekiplerin rol ve hedefleri bu döneme sabit bir kopya olarak
              alınır.
            </p>
            <Button disabled={busy}>Dönemi oluştur</Button>
          </form>
        </Modal>
      )}
      {qs && (
        <Modal title="Soru ve rubrik incelemesi" onClose={() => setQs(null)}>
          <div className="modal-body question-review">
            {qs.map((q: Any, i: number) => (
              <article key={q.id}>
                <span className="eyebrow">
                  {i + 1} · {q.type} · {q.skill_id}
                </span>
                <h3>{q.prompt}</h3>
                {q.rubric.map((r: Any) => (
                  <p key={r.id}>
                    <b>{r.label}</b> · {r.descriptor}
                  </p>
                ))}
                {q.options?.length > 0 &&
                  q.options.map((o: Any) => (
                    <p key={o.id}>
                      {o.text}
                      {o.correct && " ✓"}
                    </p>
                  ))}
              </article>
            ))}
          </div>
        </Modal>
      )}
    </>
  );
}

function Catalog() {
  const [skills, setSkills] = useState<Any[]>([]),
    [q, setQ] = useState(""),
    [detail, setDetail] = useState<Any>(null);
  useEffect(() => {
    api("/skills").then(setSkills);
  }, []);
  return (
    <>
      <div className="section-toolbar">
        <div className="search">
          <Search size={17} />
          <input
            aria-label="Yetkinlik ara"
            placeholder="Yetkinlik veya alan ara…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <span className="muted">42 yetkinlik · 210 seviye tanımı</span>
      </div>
      <div className="catalog-grid">
        {skills
          .filter((s) =>
            (s.name + " " + s.definition)
              .toLocaleLowerCase("tr")
              .includes(q.toLocaleLowerCase("tr")),
          )
          .map((s: Any) => (
            <button
              className="panel skill-card"
              key={s.id}
              onClick={() => setDetail(s)}
            >
              <div className="skill-top">
                <span className="skill-code">
                  {String(s.code).padStart(2, "0")}
                </span>
                <ArrowUpRight size={17} />
              </div>
              <h3>{s.name}</h3>
              <p>{s.definition}</p>
              <div className="skill-footer">
                <span>5 yetkinlik seviyesi</span>
                <ChevronRight size={15} />
              </div>
            </button>
          ))}
      </div>
      {detail && (
        <Modal title={detail.name} onClose={() => setDetail(null)}>
          <div className="modal-body">
            <p>{detail.definition}</p>
            {detail.levels.map((x: Any) => (
              <div className="level-item" key={x.level}>
                <span>L{x.level}</span>
                <div>
                  <h3>{x.label}</h3>
                  <p>{x.description}</p>
                </div>
              </div>
            ))}
          </div>
        </Modal>
      )}
    </>
  );
}

function Teams({ boot, action, user }: Any) {
  const [edit, setEdit] = useState<Any>(null),
    [skills, setSkills] = useState<Any[]>([]);
  useEffect(() => {
    api("/skills").then(setSkills);
  }, []);
  return (
    <>
      <div className="section-toolbar">
        <span className="muted">
          Ekip bağlamı ve hedefler yeni dönemlerde kullanılır.
        </span>
        {user.permissions.all_data && (
          <Button
            onClick={() =>
              setEdit({
                name: "",
                role: "",
                context: { purpose: "", tasks: [], tools: [], constraints: "" },
                targets: [],
              })
            }
          >
            <Plus size={17} /> Ekip ekle
          </Button>
        )}
      </div>
      <div className="team-grid">
        {boot.teams.map((t: Any) => (
          <section className="panel team-card" key={t.id}>
            <div className="team-card-top">
              <span className="team-symbol big">{t.name[0]}</span>
              <span className="small-pill">Bağlam v{t.version}</span>
            </div>
            <h2>{t.name}</h2>
            <p>{t.context.purpose}</p>
            <div className="team-role">
              <Users size={15} />
              {t.role}
            </div>
            <div className="targets">
              {t.targets.map((x: Any) => (
                <div key={x.skill_id}>
                  <span>
                    {skills.find((s) => s.id === x.skill_id)?.name ||
                      x.skill_id}
                  </span>
                  <b>L{x.target_level}</b>
                </div>
              ))}
            </div>
            {boot.editable_team_ids?.includes(t.id) ? (
              <Button
                secondary
                onClick={() => setEdit(JSON.parse(JSON.stringify(t)))}
              >
                Bağlam ve hedefleri düzenle <ArrowRight size={15} />
              </Button>
            ) : (
              <p className="muted">
                Ortak departman bağlamı İK tarafından yönetilir.
              </p>
            )}
          </section>
        ))}
      </div>
      {edit && (
        <Modal title="Ekip bağlamı ve hedefler" onClose={() => setEdit(null)}>
          <form
            className="modal-body"
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                await action(
                  () =>
                    api(
                      edit.id ? "/teams/" + edit.id : "/teams",
                      edit.id ? "PATCH" : "POST",
                      edit,
                    ),
                  "Ekip bağlamı kaydedildi.",
                )
              )
                setEdit(null);
            }}
          >
            <div className="form-grid">
              <label>
                Ekip adı
                <input
                  required
                  value={edit.name}
                  onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                />
              </label>
              <label>
                Rol / title
                <input
                  required
                  value={edit.role}
                  onChange={(e) => setEdit({ ...edit, role: e.target.value })}
                />
              </label>
            </div>
            <label>
              Ekip amacı ve iş senaryoları
              <textarea
                rows={4}
                value={edit.context.purpose}
                onChange={(e) =>
                  setEdit({
                    ...edit,
                    context: { ...edit.context, purpose: e.target.value },
                  })
                }
              />
            </label>
            <label>
              AI kullanım sınırları
              <textarea
                rows={2}
                value={edit.context.constraints}
                onChange={(e) =>
                  setEdit({
                    ...edit,
                    context: { ...edit.context, constraints: e.target.value },
                  })
                }
              />
            </label>
            <label>
              Yetkinlik ekle
              <select
                value=""
                onChange={(e) => {
                  if (
                    e.target.value &&
                    !edit.targets.some(
                      (x: Any) => x.skill_id === e.target.value,
                    )
                  )
                    setEdit({
                      ...edit,
                      targets: [
                        ...edit.targets,
                        {
                          skill_id: e.target.value,
                          target_level: 3,
                          criticality: 3,
                          applicable: true,
                        },
                      ],
                    });
                }}
              >
                <option value="">Yetkinlik seçin…</option>
                {skills.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="target-editor">
              {edit.targets.map((x: Any, i: number) => (
                <div key={x.skill_id}>
                  <span>
                    {skills.find((s) => s.id === x.skill_id)?.name ||
                      x.skill_id}
                  </span>
                  <label>
                    Hedef
                    <select
                      value={x.target_level}
                      onChange={(e) =>
                        setEdit({
                          ...edit,
                          targets: edit.targets.map((y: Any, j: number) =>
                            j === i
                              ? { ...y, target_level: Number(e.target.value) }
                              : y,
                          ),
                        })
                      }
                    >
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n} value={n}>
                          L{n}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Önem
                    <select
                      value={x.criticality}
                      onChange={(e) =>
                        setEdit({
                          ...edit,
                          targets: edit.targets.map((y: Any, j: number) =>
                            j === i
                              ? { ...y, criticality: Number(e.target.value) }
                              : y,
                          ),
                        })
                      }
                    >
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="Yetkinliği kaldır"
                    onClick={() =>
                      setEdit({
                        ...edit,
                        targets: edit.targets.filter(
                          (_: Any, j: number) => j !== i,
                        ),
                      })
                    }
                  >
                    <X size={15} />
                  </button>
                </div>
              ))}
            </div>
            <Button>Değişiklikleri kaydet</Button>
          </form>
        </Modal>
      )}
    </>
  );
}

function Survey({ boot, notify, refresh, initialCampaign }: Any) {
  const [cid, setCid] = useState(initialCampaign || ""),
    [list, setList] = useState<Any[]>([]),
    [aid, setAid] = useState("");
  const campaign = boot.campaigns.find(
    (c: Any) =>
      c.id ===
      (cid ||
        boot.campaigns.find((x: Any) => x.status === "open")?.id ||
        boot.campaigns[0]?.id),
  );
  useEffect(() => {
    if (campaign) api(`/campaigns/${campaign.id}/assignments`).then(setList);
  }, [campaign?.id, aid]);
  if (aid)
    return (
      <SurveyForm
        aid={aid}
        back={() => {
          setAid("");
          refresh();
        }}
        notify={notify}
      />
    );
  return (
    <>
      <div className="toolbar">
        <div className="filter-field">
          <ClipboardList size={16} />
          <select
            value={campaign?.id || ""}
            onChange={(e) => setCid(e.target.value)}
          >
            {boot.campaigns.map((c: Any) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <Badge status={campaign?.status} />
      </div>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Katılımcı formları</h2>
            <p>
              Erişim kapsamınızdaki katılımcıların atanmış formlarını
              görüntüleyin.
            </p>
          </div>
          <span className="small-pill">22 soru / form</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Katılımcı</th>
              <th>Ekip</th>
              <th>Rol</th>
              <th>Durum</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.map((a) => (
              <tr key={a.id}>
                <td>
                  <b>{a.name}</b>
                </td>
                <td>{a.team_name}</td>
                <td>{a.title}</td>
                <td>
                  <Badge status={a.status} />
                </td>
                <td>
                  <button className="text-btn" onClick={() => setAid(a.id)}>
                    {a.status === "submitted"
                      ? "Yanıtları görüntüle"
                      : "Formu aç"}{" "}
                    <ArrowRight size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
function SurveyForm({ aid, back, notify }: Any) {
  const [data, setData] = useState<Any>(null),
    [values, setValues] = useState<Record<string, Any>>({}),
    [saving, setSaving] = useState<Record<string, string>>({}),
    [page, setPage] = useState(0),
    [sending, setSending] = useState(false);
  const versions = useRef<Record<string, number>>({}),
    timers = useRef<Record<string, Any>>({}),
    queues = useRef<Record<string, Promise<Any>>>({}),
    current = useRef<Record<string, Any>>({}),
    dirty = useRef(new Set<string>());
  useEffect(() => {
    api(`/assignments/${aid}/form`).then((d) => {
      setData(d);
      const v: Any = {};
      d.questions.forEach((q: Any) => {
        v[q.id] = q.answer || { text: "", selected: [] };
        versions.current[q.id] = q.answer?.revision || 0;
      });
      current.current = v;
      setValues(v);
    });
  }, [aid]);
  async function save(qid: string) {
    clearTimeout(timers.current[qid]);
    if (!dirty.current.has(qid)) return;
    queues.current[qid] = (queues.current[qid] || Promise.resolve())
      .catch(() => {})
      .then(async () => {
        if (!dirty.current.has(qid)) return;
        const value = { ...current.current[qid] };
        setSaving((x) => ({ ...x, [qid]: "saving" }));
        try {
          const result = await api(
            `/assignments/${aid}/answers/${qid}`,
            "PUT",
            {
              text: value.text || "",
              selected: value.selected || [],
              revision: versions.current[qid],
            },
          );
          versions.current[qid] = result.revision;
          if (JSON.stringify(value) === JSON.stringify(current.current[qid]))
            dirty.current.delete(qid);
          setSaving((x) => ({ ...x, [qid]: "saved" }));
        } catch (e: Any) {
          setSaving((x) => ({ ...x, [qid]: "error" }));
          notify(e.message);
          throw e;
        }
      });
    return queues.current[qid];
  }
  function change(q: Any, value: Any) {
    const next = {
      ...current.current,
      [q.id]: {
        text: q.type === "open_text" ? value : "",
        selected: q.type !== "open_text" ? [value] : [],
      },
    };
    current.current = next;
    setValues(next);
    dirty.current.add(q.id);
    clearTimeout(timers.current[q.id]);
    timers.current[q.id] = setTimeout(() => save(q.id).catch(() => {}), 650);
  }
  async function send() {
    setSending(true);
    try {
      await Promise.all([...dirty.current].map(save));
      await api(`/assignments/${aid}/submit`, "POST");
      notify(
        "Yanıtlarınız gönderildi. Değerlendirme dönem kapanışından sonra yapılacak.",
      );
      setData({
        ...data,
        assignment: { ...data.assignment, status: "submitted" },
      });
    } catch (e: Any) {
      notify(e.message);
    } finally {
      setSending(false);
    }
  }
  if (!data)
    return (
      <Empty title="Form hazırlanıyor" text="Atanmış sorular yükleniyor." />
    );
  const locked =
    data.assignment.status === "submitted" ||
    data.campaign.status !== "open" ||
    data.can_answer === false;
  const answered = data.questions.filter(
    (q: Any) => values[q.id]?.text?.trim() || values[q.id]?.selected?.length,
  ).length;
  return (
    <>
      <button
        className="text-btn back"
        onClick={async () => {
          try {
            await Promise.all([...dirty.current].map(save));
            back();
          } catch {}
        }}
      >
        <ChevronLeft size={16} /> Katılımcılara dön
      </button>
      <div className="survey-layout">
        <aside className="panel survey-side">
          <div className="eyebrow">KATILIMCI FORMU</div>
          <h2>{data.assignment.profile_snapshot.name}</h2>
          <p>{data.assignment.profile_snapshot.title}</p>
          <div className="progress-track">
            <i
              style={{ width: (answered / data.questions.length) * 100 + "%" }}
            />
          </div>
          <b>
            {answered} / {data.questions.length} yanıtlandı
          </b>
          <div className="survey-side-note">
            <ShieldCheck size={20} />
            <p>
              Yanıtlarınız otomatik kaydedilir. Deneyiminiz olmayan sorularda
              bunu açıkça belirtebilirsiniz.
            </p>
          </div>
          <Badge status={locked ? "submitted" : "open"} />
        </aside>
        <div>
          <div className="survey-title">
            <span className="small-pill">{data.campaign.name}</span>
            <p>
              Yaklaşımınızı somut adımlar ve kontrollerle anlatın. Kısa, madde
              işaretli yanıtlar kabul edilir.
            </p>
          </div>
          {data.questions
            .slice(page * 5, page * 5 + 5)
            .map((q: Any, i: number) => (
              <section className="panel question-card" key={q.id}>
                <div className="question-number">
                  <span>{String(page * 5 + i + 1).padStart(2, "0")}</span>
                  <small>
                    {q.type === "open_text"
                      ? "AÇIK UÇLU"
                      : q.type === "self_assessment"
                        ? "ÖZ DEĞERLENDİRME"
                        : "BİLGİ KONTROLÜ"}
                  </small>
                  <span className="question-save">
                    {saving[q.id] === "saving" ? (
                      <>
                        <LoaderCircle className="spin" size={12} /> Kaydediliyor
                      </>
                    ) : saving[q.id] === "error" ? (
                      <button
                        className="text-btn"
                        onClick={() => save(q.id).catch(() => {})}
                      >
                        Tekrar kaydet
                      </button>
                    ) : saving[q.id] === "saved" ? (
                      <>
                        <Check size={12} /> Kaydedildi
                      </>
                    ) : (
                      ""
                    )}
                  </span>
                </div>
                <span className="skill-tag">{q.skill_name}</span>
                <h3>{q.prompt}</h3>
                {q.type === "open_text" ? (
                  <>
                    <textarea
                      aria-label={`Yanıt ${page * 5 + i + 1}`}
                      disabled={locked}
                      maxLength={8000}
                      rows={6}
                      value={values[q.id]?.text || ""}
                      onChange={(e) => change(q, e.target.value)}
                      onBlur={() => save(q.id).catch(() => {})}
                      placeholder="Yaklaşımınızı, uygulayacağınız kontrolleri ve deneyiminizi yazın…"
                    />
                    <small className="char-count">
                      {values[q.id]?.text?.length || 0} / 8.000
                    </small>
                  </>
                ) : (
                  <div className="options">
                    {q.options.map((o: Any) => (
                      <label
                        className={
                          values[q.id]?.selected?.includes(o.id)
                            ? "option checked"
                            : "option"
                        }
                        key={o.id}
                      >
                        <input
                          type="radio"
                          name={q.id}
                          disabled={locked}
                          checked={!!values[q.id]?.selected?.includes(o.id)}
                          onChange={() => change(q, o.id)}
                        />
                        <span>{o.text}</span>
                      </label>
                    ))}
                  </div>
                )}
              </section>
            ))}
          <div className="survey-pagination">
            <Button
              secondary
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft size={16} /> Önceki
            </Button>
            <span>
              {page + 1} / {Math.ceil(data.questions.length / 5)}
            </span>
            {(page + 1) * 5 < data.questions.length ? (
              <Button
                onClick={() => {
                  setPage(page + 1);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                Devam et <ChevronRight size={16} />
              </Button>
            ) : (
              <Button disabled={locked || sending} onClick={send}>
                {sending ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Check size={16} />
                )}{" "}
                Yanıtları gönder
              </Button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function Jobs({ action, notify }: Any) {
  const [runs, setRuns] = useState<Any[]>([]),
    [exports, setExports] = useState<Any[]>([]),
    [reviews, setReviews] = useState<Any>(null),
    [reason, setReason] = useState(""),
    [override, setOverride] = useState<Record<string, string>>({});
  async function load() {
    setRuns(await api("/evaluation-runs"));
    setExports(await api("/exports"));
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, []);
  return (
    <>
      <div className="notice">
        <FlaskConical size={18} />
        <span>
          Sonuçlar, puanlama ve gerekli incelemeler tamamlandıktan sonra
          yayımlanır.
        </span>
      </div>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Toplu değerlendirme işleri</h2>
            <p>Model ve girdi sürümü her koşuda sabitlenir.</p>
          </div>
          <Activity size={20} />
        </div>
        {!runs.length ? (
          <Empty
            title="Henüz değerlendirme yok"
            text="Bir kampanyayı kapatıp toplu değerlendirmeyi başlatın."
          />
        ) : (
          runs.map((r) => (
            <div className="run-row" key={r.id}>
              <div className="run-icon">
                <Zap size={22} />
              </div>
              <div className="run-info">
                <h3>{r.campaign_name}</h3>
                <small>
                  {r.id.slice(0, 8)} · {r.calls} puanlama çağrısı ·{" "}
                  {new Date(r.created_at).toLocaleString("tr-TR")}
                </small>
                <div className="progress-track">
                  <i style={{ width: r.progress + "%" }} />
                </div>
                <span>
                  {r.jobs.done}/{r.total} iş tamamlandı{" "}
                  {r.jobs.failed ? `· ${r.jobs.failed} hata` : ""}
                </span>
                {r.error && <p className="error-text">{r.error}</p>}
              </div>
              <Badge status={r.status} />
              <div className="run-actions">
                {r.reviews > 0 && (
                  <Button
                    secondary
                    onClick={async () =>
                      setReviews(await api(`/evaluation-runs/${r.id}/reviews`))
                    }
                  >
                    {r.reviews} inceleme
                  </Button>
                )}
                {r.can_manage && r.status === "ready_to_publish" && (
                  <Button
                    onClick={() =>
                      action(
                        () => api(`/evaluation-runs/${r.id}/publish`, "POST"),
                        "Sonuçlar yayımlandı.",
                      ).then(load)
                    }
                  >
                    Sonuçları yayımla
                  </Button>
                )}
                {r.can_manage && r.status === "failed" && (
                  <Button
                    onClick={() =>
                      action(
                        () =>
                          api(`/evaluation-runs/${r.id}/retry-failed`, "POST"),
                        "Başarısız işler yeniden sıraya alındı.",
                      ).then(load)
                    }
                  >
                    Başarısızları dene
                  </Button>
                )}
                {r.can_manage &&
                  ["queued", "evaluating", "validating"].includes(r.status) && (
                    <Button
                      secondary
                      onClick={() =>
                        action(
                          () => api(`/evaluation-runs/${r.id}/cancel`, "POST"),
                          "İş iptal edildi.",
                        ).then(load)
                      }
                    >
                      İptal et
                    </Button>
                  )}
              </div>
            </div>
          ))
        )}
      </section>
      <section className="panel export-panel">
        <div className="panel-head">
          <div>
            <h2>Excel çıktıları</h2>
            <p>Yayımlanmış sonuçlarla aynı veri sürümünü kullanır.</p>
          </div>
          <ArrowDownToLine size={20} />
        </div>
        {exports.length ? (
          <table>
            <thead>
              <tr>
                <th>Dosya</th>
                <th>İçerik</th>
                <th>Tarih</th>
                <th>Durum</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {exports.map((e) => (
                <tr key={e.id}>
                  <td>Aptilume-{e.id.slice(0, 8)}.xlsx</td>
                  <td>{e.detail ? "Detaylı değerlendirme" : "Toplu özet"}</td>
                  <td>{new Date(e.created_at).toLocaleString("tr-TR")}</td>
                  <td>
                    <Badge status={e.status === "ready" ? "done" : e.status} />
                  </td>
                  <td>
                    {e.status === "ready" && (
                      <a
                        className="text-btn"
                        href={`${API}/exports/${e.id}/download`}
                      >
                        <ArrowDownToLine size={15} /> İndir
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="inline-empty">
            Genel görünümden bir Excel çıktısı oluşturabilirsiniz.
          </div>
        )}
      </section>
      {reviews && (
        <Modal
          title="Değerlendirme incelemesi"
          onClose={() => setReviews(null)}
        >
          <div className="modal-body">
            {reviews.length ? (
              reviews.map((r: Any) => (
                <article className="review-item" key={r.id}>
                  <h3>{r.question}</h3>
                  <blockquote>{r.answer}</blockquote>
                  <p>
                    Model puanı: {fmt(r.score, 1)} · {r.flags.join(", ")}
                  </p>
                  {r.criteria.map((c: Any) => (
                    <p key={c.criterion_id}>
                      <b>
                        {c.criterion_id}: {c.points}/4
                      </b>{" "}
                      — {c.reason}
                    </p>
                  ))}
                  <label>
                    Düzeltilmiş soru puanı (isteğe bağlı, 0–100)
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={override[r.id] || ""}
                      onChange={(e) =>
                        setOverride({ ...override, [r.id]: e.target.value })
                      }
                      placeholder="Boş bırakırsanız model puanı korunur"
                    />
                  </label>
                  <label>
                    İnceleme gerekçesi
                    <input
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Kararınızın gerekçesini yazın"
                    />
                  </label>
                  <Button
                    disabled={reason.length < 5}
                    onClick={async () => {
                      if (
                        await action(
                          () =>
                            api(`/reviews/${r.id}/decision`, "POST", {
                              reason,
                              score: override[r.id]
                                ? Number(override[r.id])
                                : null,
                            }),
                          "İnceleme kaydedildi.",
                        )
                      ) {
                        setReviews(reviews.filter((x: Any) => x.id !== r.id));
                        setReason("");
                        load();
                      }
                    }}
                  >
                    Puanı onayla
                  </Button>
                </article>
              ))
            ) : (
              <Empty
                title="İncelemeler tamamlandı"
                text="Sonuç işinin tamamlanmasını bekleyebilirsiniz."
              />
            )}
          </div>
        </Modal>
      )}
    </>
  );
}

function Connections({ action, notify }: Any) {
  const [tab, setTab] = useState("llm"),
    [rows, setRows] = useState<Any[]>([]),
    [edit, setEdit] = useState<Any>(null),
    [test, setTest] = useState<Any>(null),
    [migration, setMigration] = useState<Any>(null);
  const load = () => api("/admin/connections/" + tab).then(setRows);
  useEffect(() => {
    load();
  }, [tab]);
  function newProfile() {
    setEdit({
      name: "",
      config:
        tab === "llm"
          ? {
              provider: "mock",
              model: "apt-mock-v1",
              endpoint: "mock://apt-lab",
              timeout: 90,
              concurrency: 3,
              scenario: "success",
            }
          : {
              engine: "postgresql",
              host: "",
              port: 5432,
              database: "",
              username: "",
              sslmode: "require",
              timeout: 10,
            },
      secret: "",
    });
  }
  const cfg = (k: string, v: Any) =>
    setEdit({ ...edit, config: { ...edit.config, [k]: v } });
  return (
    <>
      <div className="section-toolbar">
        <div className="tabs">
          <button
            className={tab === "llm" ? "active" : ""}
            onClick={() => setTab("llm")}
          >
            <Sparkles size={16} /> LLM bağlantıları
          </button>
          <button
            className={tab === "db" ? "active" : ""}
            onClick={() => setTab("db")}
          >
            <Database size={16} /> Veritabanları
          </button>
        </div>
        <Button onClick={newProfile}>
          <Plus size={17} /> Bağlantı ekle
        </Button>
      </div>
      <div className="connection-grid">
        {rows.map((p) => (
          <section className="panel connection-card" key={p.id}>
            <div className="connection-top">
              <div className="connection-symbol">
                {tab === "llm" ? (
                  <Sparkles size={22} />
                ) : (
                  <Database size={22} />
                )}
              </div>
              <span className="small-pill">v{p.version}</span>
            </div>
            <h2>{p.name}</h2>
            <p>{p.config.model || p.config.database || p.config.engine}</p>
            <code>{p.config.endpoint || p.config.host || p.config.path}</code>
            <div className="binding-tags">
              {p.active_for.map((x: string) => (
                <span key={x}>
                  {
                    (
                      {
                        generation: "Soru üretimi",
                        evaluation: "Puanlama",
                        insights: "İçgörüler",
                        application_db: "Aktif veri deposu",
                      } as Any
                    )[x]
                  }
                </span>
              ))}
            </div>
            <div className="connection-actions">
              <button
                className="text-btn"
                onClick={async () =>
                  setTest(
                    await api(`/admin/connections/${tab}/${p.id}/test`, "POST"),
                  )
                }
              >
                <Network size={15} /> Test et
              </button>
              <button
                className="text-btn"
                onClick={() => setEdit({ ...p, secret: "" })}
              >
                Düzenle
              </button>
              <button
                className="icon-btn danger"
                aria-label="Bağlantıyı sil"
                onClick={() =>
                  action(
                    () => api(`/admin/connections/${tab}/${p.id}`, "DELETE"),
                    "Bağlantı silindi.",
                  ).then(load)
                }
              >
                <Trash2 size={16} />
              </button>
            </div>
            {tab === "llm" ? (
              <div className="binding-controls">
                <span>Görev için seç:</span>
                {[
                  ["generation", "Sorular"],
                  ["evaluation", "Puanlama"],
                  ["insights", "İçgörü"],
                ].map(([purpose, label]) => (
                  <button
                    key={purpose}
                    disabled={p.active_for.includes(purpose)}
                    onClick={() =>
                      action(
                        () =>
                          api(`/admin/service-bindings/${purpose}`, "PUT", {
                            profile_id: p.id,
                          }),
                        label + " profili güncellendi.",
                      ).then(load)
                    }
                  >
                    {label}
                  </button>
                ))}
              </div>
            ) : (
              !p.active_for.length && (
                <button
                  className="text-btn migration-btn"
                  onClick={async () =>
                    setMigration({
                      ...(await api(
                        `/admin/db-connections/${p.id}/migration-preview`,
                        "POST",
                      )),
                      profile: p,
                    })
                  }
                >
                  DB geçişini önizle <ArrowRight size={14} />
                </button>
              )
            )}
          </section>
        ))}
      </div>
      <div className="notice">
        <ShieldCheck size={18} />
        <span>
          Gizli anahtarlar şifreli tutulur ve yeniden gösterilmez. Profil
          değişiklikleri geçmiş değerlendirmelerin sürümünü değiştirmez.
        </span>
      </div>
      {edit && (
        <Modal
          title={edit.id ? "Bağlantıyı düzenle" : "Yeni bağlantı"}
          onClose={() => setEdit(null)}
        >
          <form
            className="modal-body"
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                await action(
                  () =>
                    api(
                      `/admin/connections/${tab}${edit.id ? "/" + edit.id : ""}`,
                      edit.id ? "PATCH" : "POST",
                      edit,
                    ),
                  "Bağlantı kaydedildi.",
                )
              ) {
                setEdit(null);
                load();
              }
            }}
          >
            <label>
              Profil adı
              <input
                required
                value={edit.name}
                onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                placeholder="Örn. Kurum LLM · Puanlama"
              />
            </label>
            {tab === "llm" ? (
              <>
                <div className="form-grid">
                  <label>
                    Protokol
                    <select
                      value={edit.config.provider}
                      onChange={(e) => cfg("provider", e.target.value)}
                    >
                      <option value="mock">Mock · Development</option>
                      <option value="openai_responses">OpenAI Responses</option>
                      <option value="openai_compatible_chat">
                        OpenAI Compatible Chat
                      </option>
                    </select>
                  </label>
                  <label>
                    Model / deployment adı
                    <input
                      required
                      value={edit.config.model || ""}
                      onChange={(e) => cfg("model", e.target.value)}
                    />
                  </label>
                </div>
                <label>
                  Base URL
                  <input
                    value={edit.config.endpoint || ""}
                    onChange={(e) => cfg("endpoint", e.target.value)}
                    placeholder="https://llm.example/v1"
                  />
                </label>
                {edit.config.provider === "mock" && (
                  <label>
                    Mock test senaryosu
                    <select
                      value={edit.config.scenario || "success"}
                      onChange={(e) => cfg("scenario", e.target.value)}
                    >
                      {[
                        "success",
                        "timeout",
                        "rate_limit",
                        "unauthorized",
                        "server_error",
                        "invalid_json",
                        "unsupported_quote",
                      ].map((x) => (
                        <option key={x}>{x}</option>
                      ))}
                    </select>
                  </label>
                )}
                <div className="form-grid">
                  <label>
                    Timeout (saniye)
                    <input
                      type="number"
                      min="1"
                      max="300"
                      value={edit.config.timeout}
                      onChange={(e) => cfg("timeout", Number(e.target.value))}
                    />
                  </label>
                  <label>
                    Paralellik
                    <input
                      type="number"
                      min="1"
                      max="20"
                      value={edit.config.concurrency}
                      onChange={(e) =>
                        cfg("concurrency", Number(e.target.value))
                      }
                    />
                  </label>
                </div>
              </>
            ) : (
              <>
                <label>
                  Veritabanı motoru
                  <select
                    value={edit.config.engine}
                    onChange={(e) => cfg("engine", e.target.value)}
                  >
                    <option value="postgresql">PostgreSQL</option>
                    <option value="sqlite">SQLite</option>
                  </select>
                </label>
                {edit.config.engine === "sqlite" ? (
                  <label>
                    Dosya yolu
                    <input
                      required
                      value={edit.config.path || ""}
                      onChange={(e) => cfg("path", e.target.value)}
                      placeholder="DATA_DIR içindeki dosya"
                    />
                  </label>
                ) : (
                  <>
                    <div className="form-grid">
                      <label>
                        Host
                        <input
                          required
                          value={edit.config.host || ""}
                          onChange={(e) => cfg("host", e.target.value)}
                        />
                      </label>
                      <label>
                        Port
                        <input
                          type="number"
                          value={edit.config.port || 5432}
                          onChange={(e) => cfg("port", Number(e.target.value))}
                        />
                      </label>
                      <label>
                        Database
                        <input
                          required
                          value={edit.config.database || ""}
                          onChange={(e) => cfg("database", e.target.value)}
                        />
                      </label>
                      <label>
                        Kullanıcı
                        <input
                          value={edit.config.username || ""}
                          onChange={(e) => cfg("username", e.target.value)}
                        />
                      </label>
                    </div>
                    <label>
                      TLS modu
                      <select
                        value={edit.config.sslmode || "require"}
                        onChange={(e) => cfg("sslmode", e.target.value)}
                      >
                        <option>require</option>
                        <option>verify-full</option>
                        <option>prefer</option>
                      </select>
                    </label>
                  </>
                )}
              </>
            )}
            <label>
              {tab === "llm" ? "API anahtarı" : "Parola"}{" "}
              {edit.has_secret && (
                <small>· Kayıtlı; boş bırakırsanız korunur</small>
              )}
              <input
                type="password"
                autoComplete="new-password"
                value={edit.secret || ""}
                onChange={(e) => setEdit({ ...edit, secret: e.target.value })}
                placeholder="Gizli değer"
              />
            </label>
            {edit.has_secret && (
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={!!edit.clear_secret}
                  onChange={(e) =>
                    setEdit({ ...edit, clear_secret: e.target.checked })
                  }
                />
                Kayıtlı gizli değeri temizle
              </label>
            )}
            <div className="modal-actions">
              <Button secondary type="button" onClick={() => setEdit(null)}>
                Vazgeç
              </Button>
              <Button>Bağlantıyı kaydet</Button>
            </div>
          </form>
        </Modal>
      )}
      {test && (
        <Modal title="Bağlantı testi" onClose={() => setTest(null)}>
          <div className="modal-body">
            <Badge status={test.status === "success" ? "done" : "failed"} />
            <h3>{test.message}</h3>
            <p className="muted">
              Mod: {test.mode === "mock" ? "Simülasyon" : "Gerçek bağlantı"}{" "}
              {test.latency_ms != null && `· ${test.latency_ms} ms`}
            </p>
            <p>Bağlantı testi, LLM değerlendirme kalitesini doğrulamaz.</p>
          </div>
        </Modal>
      )}
      {migration && (
        <Modal title="Veritabanı geçişi" onClose={() => setMigration(null)}>
          <div className="modal-body">
            <h3>{migration.profile.name}</h3>
            <p>
              Mevcut veriler hedef DB’ye kopyalanır, kayıtlar doğrulanır ve
              aktif bağlantı değiştirilir. Hedef boş olmalıdır.
            </p>
            <p>
              Açık kampanya: <b>{migration.open_campaigns}</b>
            </p>
            <p className="muted">
              {Object.keys(migration.records).length} tablo doğrulanacak. Devam
              etmeden önce veri yedeğinizi alın.
            </p>
            <Button
              disabled={migration.open_campaigns > 0}
              onClick={async () => {
                if (
                  await action(
                    () =>
                      api(
                        `/admin/db-connections/${migration.profile.id}/activate`,
                        "POST",
                        { copy_existing: true },
                      ),
                    "DB geçişi tamamlandı.",
                  )
                ) {
                  setMigration(null);
                  load();
                }
              }}
            >
              Veriyi taşı ve etkinleştir
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function RoleProfiles({ boot, action, user }: Any) {
  const [role, setRole] = useState<Any>(null),
    [person, setPerson] = useState<Any>(null),
    [skills, setSkills] = useState<Any[]>([]);
  useEffect(() => {
    api("/skills").then(setSkills);
  }, []);
  const profiles = boot.role_profiles || [];
  const editableTeams = boot.teams.filter((t: Any) =>
    boot.editable_team_ids?.includes(t.id),
  );
  return (
    <>
      <div className="section-toolbar" style={{ marginTop: 30 }}>
        <div>
          <h2>Rol profilleri</h2>
          <span className="muted">
            Aynı ekipte farklı title ve hedefler için ayrı formlar hazırlayın.
          </span>
        </div>
        {!!editableTeams.length && (
          <Button
            secondary
            onClick={() =>
              setRole({
                team_id: editableTeams[0]?.id,
                title: "",
                job_band: "L3_L4",
                targets: editableTeams[0]?.targets || [],
              })
            }
          >
            <Plus size={16} /> Rol ekle
          </Button>
        )}
      </div>
      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>Rol / title</th>
              <th>Ekip</th>
              <th>Kademe</th>
              <th>Yetkinlik</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {profiles.map((r: Any) => (
              <tr key={r.id}>
                <td>
                  <b>{r.title}</b>
                </td>
                <td>{boot.teams.find((t: Any) => t.id === r.team_id)?.name}</td>
                <td>{r.job_band}</td>
                <td>
                  {r.targets.length} · v{r.version}
                </td>
                <td>
                  {boot.editable_team_ids?.includes(r.team_id) ? (
                    <button
                      className="text-btn"
                      onClick={() => setRole(JSON.parse(JSON.stringify(r)))}
                    >
                      Hedefleri düzenle
                    </button>
                  ) : (
                    <span className="muted">İK tarafından yönetilir</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <div className="section-toolbar" style={{ marginTop: 30 }}>
        <div>
          <h2>Katılımcılar ve rol eşlemeleri</h2>
          <span className="muted">
            Değişiklikler yeni ölçüm dönemlerinde geçerlidir.
          </span>
        </div>
        {user.permissions.all_data && (
          <Button
            secondary
            disabled={!profiles.length}
            onClick={() =>
              setPerson({
                name: "",
                title: "",
                role_profile_id: profiles[0]?.id,
                job_band: "L3_L4",
              })
            }
          >
            <Plus size={16} /> Katılımcı ekle
          </Button>
        )}
      </div>
      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>Katılımcı</th>
              <th>Title</th>
              <th>Rol profili</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {boot.participants.map((p: Any) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.title}</td>
                <td>
                  {profiles.find((r: Any) => r.id === p.role_profile_id)
                    ?.title || "Varsayılan"}
                </td>
                <td>
                  {user.permissions.all_data && (
                    <button
                      className="text-btn"
                      onClick={() => setPerson({ ...p })}
                    >
                      Düzenle
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {role && (
        <Modal title="Rol profili ve hedefler" onClose={() => setRole(null)}>
          <form
            className="modal-body"
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                await action(
                  () =>
                    api(
                      role.id ? `/role-profiles/${role.id}` : "/role-profiles",
                      role.id ? "PATCH" : "POST",
                      role,
                    ),
                  "Rol profili kaydedildi.",
                )
              )
                setRole(null);
            }}
          >
            <div className="form-grid">
              <label>
                Ekip
                <select
                  value={role.team_id}
                  disabled={!!role.id}
                  onChange={(e) =>
                    setRole({
                      ...role,
                      team_id: e.target.value,
                      targets:
                        boot.teams.find((t: Any) => t.id === e.target.value)
                          ?.targets || [],
                    })
                  }
                >
                  {editableTeams.map((t: Any) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Rol / title
                <input
                  required
                  value={role.title}
                  onChange={(e) => setRole({ ...role, title: e.target.value })}
                />
              </label>
              <label>
                İK kademesi
                <select
                  value={role.job_band}
                  onChange={(e) =>
                    setRole({ ...role, job_band: e.target.value })
                  }
                >
                  {["L1_L2", "L3_L4", "L5_L6"].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
            </div>
            <p className="muted">
              Bu başlangıç formu üç ortak ve üç rol yetkinliği kullanır. Rol
              yetkinliklerini değiştirmek için hedeflerden kaldırıp katalogdan
              ekleyin.
            </p>
            <label>
              Yetkinlik ekle
              <select
                value=""
                onChange={(e) => {
                  if (
                    e.target.value &&
                    !role.targets.some(
                      (x: Any) => x.skill_id === e.target.value,
                    )
                  )
                    setRole({
                      ...role,
                      targets: [
                        ...role.targets,
                        {
                          skill_id: e.target.value,
                          target_level: 3,
                          criticality: 3,
                          applicable: true,
                        },
                      ],
                    });
                }}
              >
                <option value="">Katalogdan seçin…</option>
                {skills.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="target-editor">
              {role.targets.map((x: Any, i: number) => (
                <div key={x.skill_id}>
                  <span>
                    {skills.find((s) => s.id === x.skill_id)?.name ||
                      x.skill_id}
                  </span>
                  <label>
                    Hedef
                    <select
                      value={x.target_level}
                      onChange={(e) =>
                        setRole({
                          ...role,
                          targets: role.targets.map((y: Any, j: number) =>
                            i === j
                              ? { ...y, target_level: Number(e.target.value) }
                              : y,
                          ),
                        })
                      }
                    >
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n} value={n}>
                          L{n}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Önem
                    <select
                      value={x.criticality}
                      onChange={(e) =>
                        setRole({
                          ...role,
                          targets: role.targets.map((y: Any, j: number) =>
                            i === j
                              ? { ...y, criticality: Number(e.target.value) }
                              : y,
                          ),
                        })
                      }
                    >
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="Yetkinliği kaldır"
                    onClick={() =>
                      setRole({
                        ...role,
                        targets: role.targets.filter(
                          (_: Any, j: number) => i !== j,
                        ),
                      })
                    }
                  >
                    <X size={15} />
                  </button>
                </div>
              ))}
            </div>
            <Button>Rolü kaydet</Button>
          </form>
        </Modal>
      )}
      {person && (
        <Modal title="Katılımcı rol eşlemesi" onClose={() => setPerson(null)}>
          <form
            className="modal-body"
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                await action(
                  () =>
                    api(
                      person.id
                        ? `/participants/${person.id}`
                        : "/participants",
                      person.id ? "PATCH" : "POST",
                      person,
                    ),
                  "Katılımcı kaydedildi.",
                )
              )
                setPerson(null);
            }}
          >
            <label>
              Ad
              <input
                required
                value={person.name}
                onChange={(e) => setPerson({ ...person, name: e.target.value })}
              />
            </label>
            <label>
              Title
              <input
                required
                value={person.title}
                onChange={(e) =>
                  setPerson({ ...person, title: e.target.value })
                }
              />
            </label>
            <label>
              Rol profili
              <select
                required
                value={person.role_profile_id || ""}
                onChange={(e) =>
                  setPerson({ ...person, role_profile_id: e.target.value })
                }
              >
                <option value="">Rol seçin…</option>
                {profiles.map((r: Any) => (
                  <option key={r.id} value={r.id}>
                    {boot.teams.find((t: Any) => t.id === r.team_id)?.name} ·{" "}
                    {r.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              İK kademesi
              <select
                value={person.job_band}
                onChange={(e) =>
                  setPerson({ ...person, job_band: e.target.value })
                }
              >
                {["L1_L2", "L3_L4", "L5_L6"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <Button>Katılımcıyı kaydet</Button>
          </form>
        </Modal>
      )}
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
