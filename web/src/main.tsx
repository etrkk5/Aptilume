import { t, translateNode, formatLocale, useLocale, getLocale } from "./i18n";
import React, { lazy, Suspense, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
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
import { LanguageSwitch } from "./language-switch";
import { CatalogManager } from "./catalog";
import { PolicyEditor, QualityInbox, qualityLabels } from "./governance";
import {
  AccountPanel,
  DirectorySettings,
  ActionEditor,
  DevelopmentPlans,
  Comparison,
  PersonalProfile,
  SecurityEvents,
} from "./product-ui";
import {
  AnalyticsFilters,
  Dashboard,
  emptyReportFilters,
  type ReportFilters,
} from "./analytics";
const IdentityManagement = lazy(() => import("./identity-management"));
const QuestionSetEditor = lazy(() =>
  import("./question-editor").then((m) => ({ default: m.QuestionSetEditor })),
);
function campaignCount(c: any) {
  const counts = Object.values(c.question_counts || {}).map(Number);
  if (!counts.length)
    return ["draft", "preparing", "content_review"].includes(c.status)
      ? "AI başlangıç seti · 22 soru / rol · İK incelemesi"
      : "22 soru / rol · Yayımlanmış set";
  const min = Math.min(...counts),
    max = Math.max(...counts);
  return `${min === max ? min : `${min}–${max}`} soru / rol · İK onaylı set`;
}
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
    : Number(v).toLocaleString(formatLocale(), { maximumFractionDigits: d });
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
      {translateNode(children || labels[status || ""] || status)}
    </span>
  );
}
function Empty({ title, text, action }: Any) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Layers3 size={30} />
      </div>
      <h3>{translateNode(title)}</h3>
      <p>{translateNode(text)}</p>
      {translateNode(action)}
    </div>
  );
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
  ["quality", "Yanıt kalitesi", ShieldCheck],
  ["policy", "Ölçüm politikası", BookOpen],
  ["users", "Kimlik ve erişim", ShieldCheck],
  ["connections", "Bağlantı ayarları", Settings2],
] as const;
function App() {
  useLocale();
  const { user, setUser, signIn, signOut } = useIdentity();
  const identityKey = useRef("");
  identityKey.current = user ? user.id + ":" + user.scope_revision : "";
  const reportRequest = useRef(0);
  const [view, setView] = useState("overview"),
    [boot, setBoot] = useState<Any>(null),
    [selected, setSelected] = useState(""),
    [reportResult, setReport] = useState<Any>(null),
    [team, setTeam] = useState(""),
    [toast, setToast] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState<ReportFilters>({
    ...emptyReportFilters,
  });
  const [reportOptions, setReportOptions] = useState<Any>(null);
  const [reportBusy, setReportBusy] = useState(false);
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
      (user?.permissions.manage_business &&
        !["connections", "quality", "policy", "users"].includes(id)) ||
      (user?.permissions.integrations &&
        ["connections", "users"].includes(id)) ||
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
      setBoot({ ...b, _viewerKey: key });
      setSelected(
        (prev) =>
          (b.campaigns.some((c: Any) => c.id === prev) ? prev : "") ||
          b.campaigns.find((c: Any) => c.publication_id)?.id ||
          b.campaigns[0]?.id ||
          "",
      );
      if (b.degraded) {
        setReport(null);
        setDetail(null);
        setView(user.permissions.integrations ? "connections" : "profile");
        setError(
          user.permissions.integrations
            ? b.message
            : "Veri deposu şu anda kullanılamıyor. İK veya entegrasyon yöneticisine başvurun.",
        );
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
    setFilters({ ...emptyReportFilters });
    setReportOptions(null);
    setReportBusy(false);
    reportRequest.current++;
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
  const appliedFilters = Object.fromEntries(
    Object.entries({ team_id: team, ...filters }).filter(([, value]) => value),
  );
  const reportQuery = new URLSearchParams(appliedFilters).toString();
  const requestKey = `${campaign?.publication_id || ""}?${reportQuery}`;
  const report = reportResult?._requestKey === requestKey ? reportResult : null;
  async function refreshReport() {
    const key = identityKey.current,
      request = ++reportRequest.current;
    if (!campaign?.publication_id) {
      setReport(null);
      setReportBusy(false);
      return;
    }
    setReportBusy(true);
    try {
      const result = await api(
        `/reports/${campaign.publication_id}${reportQuery ? "?" + reportQuery : ""}`,
      );
      if (key === identityKey.current && request === reportRequest.current) {
        setReport({ ...result, _requestKey: requestKey });
        setReportOptions({
          ...result.filter_options,
          publication_id: campaign.publication_id,
        });
        setError("");
      }
    } catch (e: Any) {
      if (key === identityKey.current && request === reportRequest.current) {
        setError(e.message);
        setReport(null);
      }
    } finally {
      if (key === identityKey.current && request === reportRequest.current)
        setReportBusy(false);
    }
  }
  useEffect(() => {
    refreshReport();
  }, [requestKey]);
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
          src="/brand/aptilume-mark.svg"
          alt={t("Aptilume")}
        />
        <LoaderCircle className="spin" />
      </div>
    );
  if (!user) return <Login onLogin={signIn} />;
  if (!boot || boot._viewerKey !== identityKey.current)
    return (
      <div className="startup">
        <img
          className="startup-logo"
          src="/brand/aptilume-mark.svg"
          alt={t("Aptilume")}
        />
        <h1>{t("Aptilume")}</h1>
        <p>{t("AI Skills Intelligence")}</p>
        {translateNode(
          error ? (
            <p>{translateNode(error)}</p>
          ) : (
            <LoaderCircle className="spin" />
          ),
        )}
      </div>
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="product-brand corporate-brand"
          onClick={() => setView(availableNav[0]?.[0] || "connections")}
          aria-label={t("Ana sayfa")}
        >
          <img src="/brand/aptilume-mark.svg" alt={t("Aptilume")} />
          <span>
            {t(" Aptilume")}
            <small>{t("AI Skills Intelligence")}</small>
          </span>
        </button>
        <div className="workspace-label">{t("\u00C7ALI\u015EMA ALANI")}</div>
        <div className="workspace">
          <span className="workspace-dot" />
          {translateNode(workspaceSettings?.name || "Aptilume Workspace")}
        </div>
        <nav>
          {translateNode(
            availableNav.map(([id, label, Icon], i) => (
              <React.Fragment key={id}>
                {translateNode(
                  id === "jobs" && (
                    <div className="nav-section">{t("Y\u00D6NET\u0130M")}</div>
                  ),
                )}
                <button
                  className={view === id ? "nav-link active" : "nav-link"}
                  onClick={() => {
                    setView(id);
                    if (id === "survey") setSurveyCampaign("");
                    setDetail(null);
                  }}
                >
                  <Icon size={19} />
                  {translateNode(label)}
                  {translateNode(
                    id === "catalog" && (
                      <span className="nav-count">
                        {translateNode(boot.skills_count)}
                      </span>
                    ),
                  )}
                  {translateNode(
                    id === "quality" && boot.quality_pending > 0 && (
                      <span className="nav-count">
                        {translateNode(boot.quality_pending)}
                      </span>
                    ),
                  )}
                </button>
              </React.Fragment>
            )),
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="user">
            <div className="avatar">
              <UserRound size={16} />
            </div>
            <div>
              {user.display_name}
              <small>
                {translateNode(
                  (
                    {
                      admin: "Entegrasyon yöneticisi",
                      hr: "İnsan kaynakları",
                      manager: "Ekip yöneticisi",
                      employee: "Çalışan",
                    } as Any
                  )[user.roles[0]],
                )}
              </small>
            </div>
            <button
              className="icon-btn account-toggle"
              aria-label={t("Y\u00F6netici men\u00FCs\u00FC")}
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
            {t(" \u00C7al\u0131\u015Fma alan\u0131 ")}
            <ChevronRight size={14} />
            <b>{translateNode(nav.find((x) => x[0] === view)?.[1])}</b>
          </div>
          <div className="topbar-right">
            <LanguageSwitch />
            <ThemeSwitch />
            <button
              className="icon-btn"
              aria-label={t("Hesap men\u00FCs\u00FC")}
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
              <div className="eyebrow">
                {t("AI YETK\u0130NL\u0130K HAR\u0130TASI")}
              </div>
              <h1>
                {translateNode(
                  (
                    {
                      overview: "AI yetkinlik özeti",
                      campaigns: "Ölçüm dönemleri",
                      teams: "Ekipler ve rol hedefleri",
                      catalog: "Yetkinlik kataloğu",
                      survey: "Katılımcı anketleri",
                      jobs: "Toplu değerlendirmeler",
                      quality: "Yanıt kalitesi incelemeleri",
                      policy: "Ölçüm politikası ve talimatlar",
                      connections: "Entegrasyon yönetimi",
                      users: "Kimlik ve erişim yönetimi",
                      development: "Gelişim planları",
                      profile: "Yetkinlik profilim",
                    } as Any
                  )[view],
                )}
              </h1>
              <p>
                {translateNode(
                  (
                    {
                      overview:
                        "Ekiplerinizin AI yetkinliklerini keşfedin, gelişim alanlarını belirleyin.",
                      campaigns:
                        "Anketi hazırlayın, yanıtları toplayın ve dönem sonunda değerlendirin.",
                      teams:
                        "Ekip bağlamı ve rol hedefleri, kişiselleştirilmiş soruların temelini oluşturur.",
                      catalog:
                        "Yetkinlikleri ve beş seviye tanımını kurumun ihtiyaçlarına göre yönetin.",
                      survey:
                        "Açık uçlu sorularla yaklaşımınızı, kontrollerinizi ve deneyiminizi paylaşın.",
                      jobs: "Anket kapanışından sonra çalışan toplu işleri ve incelemeleri takip edin.",
                      connections:
                        "Kimlik sağlayıcılarını, LLM modellerini ve veritabanı bağlantılarını yönetin.",
                      users:
                        "Yerel hesapları, rolleri ve raporlama ilişkilerini yönetin.",
                      development:
                        "Ölçüm sonuçlarını sorumlusu ve tarihi belirli gelişim aksiyonlarına dönüştürün.",
                      quality:
                        "Dönem sonrası işaretlenen yanıtları inceleyin ve gerekçeli İK kararınızı kaydedin.",
                      policy:
                        "Soru üretimi ve değerlendirme talimatlarını sürümleyerek yönetin.",
                      profile:
                        "Kendi değerlendirmelerinizi, hedeflerinizi ve gelişim planlarınızı takip edin.",
                    } as Any
                  )[view],
                )}
              </p>
            </div>
            {translateNode(
              view === "overview" && (
                <Button
                  onClick={() =>
                    action(async () => {
                      const e = await api("/exports", "POST", {
                        publication_id: campaign.publication_id,
                        filters: appliedFilters,
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
                  <ArrowDownToLine size={17} />
                  {t(" Excel\u2019e aktar ")}
                </Button>
              ),
            )}
          </div>
          {translateNode(
            error && <div className="notice error">{translateNode(error)}</div>,
          )}
          {translateNode(
            view === "overview" && (
              <>
                <div className="toolbar">
                  <div className="filter-field">
                    <ClipboardList size={16} />
                    <select
                      aria-label={t("\u00D6l\u00E7\u00FCm d\u00F6nemi")}
                      value={selected}
                      onChange={(e) => {
                        setSelected(e.target.value);
                        setTeam("");
                        setFilters({ ...emptyReportFilters });
                        setReportOptions(null);
                        setDetail(null);
                      }}
                    >
                      {translateNode(
                        boot.campaigns.map((c: Any) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        )),
                      )}
                    </select>
                  </div>
                  <div className="filter-field">
                    <Users size={16} />
                    <select
                      aria-label={t("Ekip filtresi")}
                      value={team}
                      onChange={(e) => {
                        setTeam(e.target.value);
                        setDetail(null);
                      }}
                    >
                      <option value="">{t("T\u00FCm ekipler")}</option>
                      {translateNode(
                        boot.teams.map((t: Any) => (
                          <option value={t.id} key={t.id}>
                            {t.name}
                          </option>
                        )),
                      )}
                    </select>
                  </div>
                  <label className="export-toggle">
                    <input
                      type="checkbox"
                      checked={exportDetail}
                      onChange={(e) => setExportDetail(e.target.checked)}
                    />
                    {t(" A\u00E7\u0131k yan\u0131tlar\u0131 dahil et ")}
                  </label>
                  {translateNode(
                    report && (
                      <button
                        className="text-btn"
                        onClick={() => setReportInfo(true)}
                      >
                        <Info size={14} />
                        {t(" Rapor bilgileri ")}
                      </button>
                    ),
                  )}
                  <div className="toolbar-end">
                    <span className="live-dot" />
                    {translateNode(
                      reportBusy
                        ? "Rapor güncelleniyor…"
                        : report
                          ? "Yayımlanmış sonuç sürümü"
                          : "Henüz sonuç yayımlanmadı",
                    )}
                  </div>
                </div>
                {translateNode(
                  campaign?.publication_id && (
                    <AnalyticsFilters
                      value={filters}
                      options={
                        reportOptions?.publication_id ===
                        campaign.publication_id
                          ? reportOptions
                          : {}
                      }
                      team={team}
                      activeCount={Object.keys(appliedFilters).length}
                      loading={reportBusy}
                      onChange={(next: ReportFilters) => {
                        setFilters(next);
                        setDetail(null);
                      }}
                      onReset={() => {
                        setFilters({ ...emptyReportFilters });
                        setTeam("");
                        setDetail(null);
                      }}
                    />
                  ),
                )}
                {translateNode(
                  reportBusy ? (
                    <div className="analytics-loading" role="status">
                      <LoaderCircle className="spin" size={22} />
                      {t(
                        " Rapor filtrelere g\u00F6re haz\u0131rlan\u0131yor\u2026 ",
                      )}
                    </div>
                  ) : report ? (
                    <Dashboard
                      report={report}
                      onPerson={setDetail}
                      onAction={(title: string, context?: Any) =>
                        setActionDraft({
                          title,
                          publication_id: report.publication_id,
                          team_id: context?.team_id || team,
                          participant_id: "",
                          skill_id: context?.skill_id || "",
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
                      title={t(
                        "Bu d\u00F6nemin sonu\u00E7lar\u0131 hen\u00FCz haz\u0131r de\u011Fil",
                      )}
                      text="Yanıtlar toplandıktan ve kampanya kapandıktan sonra toplu değerlendirme başlatılır."
                      action={
                        <Button onClick={() => setView("campaigns")}>
                          {t(" \u00D6l\u00E7\u00FCm d\u00F6nemine git ")}
                          <ArrowRight size={16} />
                        </Button>
                      }
                    />
                  ),
                )}
              </>
            ),
          )}
          {translateNode(
            view === "campaigns" && (
              <Campaigns
                user={user}
                boot={boot}
                action={action}
                busy={busy}
                setView={setView}
              />
            ),
          )}
          {translateNode(
            view === "teams" && (
              <>
                <Teams boot={boot} action={action} user={user} />
                <RoleProfiles boot={boot} action={action} user={user} />
              </>
            ),
          )}
          {translateNode(
            view === "catalog" && (
              <CatalogManager user={user} action={action} />
            ),
          )}
          {translateNode(
            view === "survey" && (
              <Survey
                boot={boot}
                notify={notify}
                refresh={refresh}
                initialCampaign={surveyCampaign}
              />
            ),
          )}
          {translateNode(
            view === "jobs" && <Jobs action={action} notify={notify} />,
          )}
          {translateNode(
            view === "quality" && user.permissions.all_data && (
              <QualityInbox boot={boot} action={action} />
            ),
          )}
          {translateNode(
            view === "policy" && user.permissions.all_data && (
              <PolicyEditor action={action} />
            ),
          )}
          {translateNode(
            view === "users" && user.permissions.integrations && (
              <Suspense fallback={<p>{t("Hesaplar y\u00FCkleniyor.")}</p>}>
                <IdentityManagement
                  action={action}
                  participants={boot.participants || []}
                  user={user}
                />
              </Suspense>
            ),
          )}
          {translateNode(
            view === "connections" && (
              <>
                <DirectorySettings action={action} busy={busy} />
                <Connections
                  action={action}
                  notify={notify}
                  user={user}
                  security={boot.security}
                />
                {translateNode(user.permissions.all_data && <SecurityEvents />)}
              </>
            ),
          )}
          {translateNode(
            view === "development" && (
              <DevelopmentPlans
                boot={boot}
                user={user}
                action={action}
                onEdit={setActionDraft}
              />
            ),
          )}
          {translateNode(
            view === "profile" && !boot.degraded && (
              <PersonalProfile user={user} onSurvey={() => setView("survey")} />
            ),
          )}
          <footer>
            <span>
              {t(" Aptilume ")}
              <i />
              {t(" AI Skills Intelligence ")}
            </span>
            <span>{t("Aptilume \u00B7 AI Skills Intelligence")}</span>
          </footer>
        </main>
      </div>
      {translateNode(
        toast && (
          <div className="toast" role="status">
            <CheckCircle2 size={19} />
            {translateNode(toast)}
          </div>
        ),
      )}
      {translateNode(
        detail && report && (
          <Modal
            title={t(detail.name + " · Yetkinlik profili")}
            onClose={() => setDetail(null)}
          >
            <div className="modal-body">
              <p className="muted">
                {translateNode(detail.team_name)}
                {t(" \u00B7 ")}
                {detail.title}
              </p>
              <p className="muted">
                {t(
                  " Yaz\u0131l\u0131 yan\u0131t puan\u0131, \u00F6z beyan ve anket seviye \u00F6nerisi birlikte g\u00F6sterilir. ",
                )}
              </p>
              <table>
                <thead>
                  <tr>
                    <th>{t("Yetkinlik")}</th>
                    <th>{t("Yaz\u0131l\u0131 puan")}</th>
                    <th>{t("\u00D6z beyan")}</th>
                    <th>{t("\u00D6neri")}</th>
                    <th>{t("Hedef")}</th>
                  </tr>
                </thead>
                <tbody>
                  {translateNode(
                    report.rows
                      .filter(
                        (x: Any) => x.participant_id === detail.participant_id,
                      )
                      .map((r: Any) => (
                        <tr key={r.skill_id}>
                          <td>{translateNode(r.skill_name)}</td>
                          <td>{translateNode(fmt(r.written_score, 1))}</td>
                          <td>
                            {translateNode(
                              r.self_level ? "L" + r.self_level : "—",
                            )}
                          </td>
                          <td>
                            {translateNode(
                              r.suggested_level
                                ? "L" + r.suggested_level
                                : "Ölçülmedi",
                            )}
                          </td>
                          <td>
                            {t("L")}
                            {translateNode(r.target_level)}
                          </td>
                        </tr>
                      )),
                  )}
                </tbody>
              </table>
            </div>
          </Modal>
        ),
      )}
      {translateNode(
        accountMenu && (
          <>
            <button
              className="menu-dismiss"
              aria-label={t("Hesap men\u00FCs\u00FCn\u00FC kapat")}
              onClick={() => setAccountMenu(false)}
            />
            <div className="user-menu" role="menu">
              <strong>{user.display_name}</strong>
              <small>{translateNode(user.username)}</small>
              <button
                role="menuitem"
                onClick={() => {
                  setAccountMenu(false);
                  setAccountPanel(true);
                }}
              >
                <UserRound size={16} />
                {t(" Hesap bilgilerim ")}
              </button>
              {translateNode(
                user.permissions.integrations && (
                  <button
                    role="menuitem"
                    onClick={() => {
                      setAccountMenu(false);
                      setView("connections");
                    }}
                  >
                    <Settings2 size={16} />
                    {t(" Entegrasyon ayarlar\u0131 ")}
                  </button>
                ),
              )}
              <button
                role="menuitem"
                onClick={() => {
                  setAccountMenu(false);
                  signOut();
                }}
              >
                <LogOut size={16} />
                {t(" \u00C7\u0131k\u0131\u015F yap ")}
              </button>
            </div>
          </>
        ),
      )}
      {translateNode(
        accountPanel && (
          <AccountPanel
            user={user}
            workspace={workspaceSettings}
            action={action}
            onWorkspace={setWorkspaceSettings}
            onClose={() => setAccountPanel(false)}
            onPasswordChanged={signOut}
          />
        ),
      )}
      {translateNode(
        reportInfo && report && (
          <Modal
            title={t("Rapor bilgileri")}
            onClose={() => setReportInfo(false)}
          >
            <div className="modal-body">
              <dl className="report-info">
                <dt>{t("\u00D6l\u00E7\u00FCm d\u00F6nemi")}</dt>
                <dd>{translateNode(report.campaign_name)}</dd>
                <dt>{t("Sonu\u00E7 s\u00FCr\u00FCm\u00FC")}</dt>
                <dd>
                  {t(" v")}
                  {translateNode(report.report_info?.version)}
                  {t(" \u00B7 ")}
                  {translateNode(report.publication_id)}
                </dd>
                <dt>{t("Yay\u0131n tarihi")}</dt>
                <dd>
                  {translateNode(
                    report.report_info?.published_at
                      ? new Date(
                          report.report_info.published_at,
                        ).toLocaleString(formatLocale())
                      : "—",
                  )}
                </dd>
                <dt>{t("De\u011Ferlendirme kayna\u011F\u0131")}</dt>
                <dd>
                  {translateNode(
                    report.report_info?.source === "simulation"
                      ? "Test sağlayıcısı · örnek yanıtlar"
                      : "LLM değerlendirmesi",
                  )}
                </dd>
                <dt>{t("Veri kapsam\u0131")}</dt>
                <dd>
                  {translateNode(
                    user.permissions.all_data
                      ? "Kurum geneli"
                      : user.permissions.manage_business
                        ? "Yönettiğiniz çalışanlar"
                        : "Kendi profiliniz",
                  )}
                </dd>
                <dt>{t("Soru \u00FCretimi talimat s\u00FCr\u00FCm\u00FC")}</dt>
                <dd>
                  {translateNode(
                    report.prompt_policy?.generation_version
                      ? `v${report.prompt_policy.generation_version}`
                      : "Eski sürümde kaydedilmemiş",
                  )}
                </dd>
                <dt>{t("De\u011Ferlendirme talimat s\u00FCr\u00FCm\u00FC")}</dt>
                <dd>
                  {translateNode(
                    report.prompt_policy?.evaluation_version
                      ? `v${report.prompt_policy.evaluation_version}`
                      : "Eski sürümde kaydedilmemiş",
                  )}
                </dd>
                <dt>{t("Puanlama y\u00F6ntemi")}</dt>
                <dd>
                  {t(
                    " Rubrik puan\u0131, bilgi kontrol\u00FC ve \u00F6z beyan ayr\u0131 hesaplan\u0131r. \u00D6l\u00E7\u00FClmeyen seviyeler i\u00E7in beceri a\u00E7\u0131\u011F\u0131 yaz\u0131lmaz. ",
                  )}
                </dd>
              </dl>
            </div>
          </Modal>
        ),
      )}
      {translateNode(
        comparison && report && (
          <Comparison
            report={report}
            onClose={() => setComparison(false)}
            onPerson={(p: Any) => {
              setComparison(false);
              setDetail(p);
            }}
          />
        ),
      )}
      {translateNode(
        actionDraft && (
          <ActionEditor
            draft={actionDraft}
            boot={boot}
            user={user}
            action={action}
            onClose={() => setActionDraft(null)}
          />
        ),
      )}
    </div>
  );
}
function Campaigns({ boot, action, busy, setView, user }: Any) {
  const [modal, setModal] = useState(false),
    [name, setName] = useState(""),
    [qs, setQs] = useState<Any>(null),
    [campaignTeams, setCampaignTeams] = useState<string[]>([]);
  return (
    <>
      <div className="section-toolbar">
        <span className="muted">
          {translateNode(boot.campaigns.length)}
          {t(" \u00F6l\u00E7\u00FCm d\u00F6nemi")}
        </span>
        <Button
          onClick={() => {
            setCampaignTeams(boot.teams.map((t: Any) => t.id));
            setModal(true);
          }}
        >
          <Plus size={17} />
          {t(" Yeni \u00F6l\u00E7\u00FCm d\u00F6nemi ")}
        </Button>
      </div>
      <div className="campaign-list">
        {translateNode(
          boot.campaigns.map((c: Any) => (
            <section className="panel campaign-card" key={c.id}>
              <div className="campaign-icon">
                <ClipboardList size={26} />
              </div>
              <div className="campaign-main">
                <div className="campaign-title">
                  <h2>{c.name}</h2>
                  <Badge status={c.status} />
                  {translateNode(
                    c.publication_id && <Badge status="published" />,
                  )}
                </div>
                <p>{translateNode(campaignCount(c))}</p>
                <div className="campaign-meta">
                  <span>
                    <Users size={15} />
                    {translateNode(c.assigned)}
                    {t(" kat\u0131l\u0131mc\u0131 ")}
                  </span>
                  <span>
                    <CheckCircle2 size={15} />
                    {translateNode(c.submitted)}
                    {t(" g\u00F6nderim ")}
                  </span>
                  <span>
                    <Clock3 size={15} />
                    {translateNode(
                      new Date(c.created_at).toLocaleDateString(formatLocale()),
                    )}
                  </span>
                </div>
              </div>
              <div
                className="campaign-actions"
                style={c.can_manage === false ? { display: "none" } : undefined}
              >
                {translateNode(
                  c.status === "draft" && (
                    <Button
                      disabled={busy}
                      onClick={() =>
                        action(
                          () =>
                            api(
                              `/campaigns/${c.id}/generate-questions`,
                              "POST",
                            ),
                          "Soru hazırlama işi sıraya alındı.",
                        )
                      }
                    >
                      {t(" Sorular\u0131 haz\u0131rla ")}
                      <Sparkles size={15} />
                    </Button>
                  ),
                )}
                {translateNode(
                  ["content_review", "ready"].includes(c.status) && (
                    <Button secondary onClick={() => setQs(c.id)}>
                      {translateNode(
                        user.permissions.all_data
                          ? "Soruları düzenle ve yayınla"
                          : "Soruları incele",
                      )}
                    </Button>
                  ),
                )}
                {translateNode(
                  c.status === "open" && (
                    <>
                      <Button secondary onClick={() => setView("survey")}>
                        {t(" Formlara git ")}
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
                        {t(" D\u00F6nemi kapat ")}
                      </Button>
                    </>
                  ),
                )}
                {translateNode(
                  c.status === "closed" && (
                    <Button
                      disabled={busy}
                      onClick={() =>
                        action(
                          () =>
                            api(`/campaigns/${c.id}/evaluation-runs`, "POST"),
                          "Değerlendirme işi sıraya alındı.",
                        )
                      }
                    >
                      {t(" Toplu de\u011Ferlendir ")}
                      <Zap size={16} />
                    </Button>
                  ),
                )}
              </div>
            </section>
          )),
        )}
      </div>
      <div className="notice">
        <Clock3 size={18} />
        <span>
          {t(
            " De\u011Ferlendirme, d\u00F6nem kapand\u0131ktan sonra ba\u015Flat\u0131l\u0131r. Form g\u00F6nderimi s\u0131ras\u0131nda LLM puanlamas\u0131 yap\u0131lmaz. ",
          )}
        </span>
      </div>
      {translateNode(
        modal && (
          <Modal
            title={t("Yeni \u00F6l\u00E7\u00FCm d\u00F6nemi")}
            onClose={() => setModal(false)}
          >
            <form
              className="modal-body"
              onSubmit={async (e) => {
                e.preventDefault();
                if (
                  await action(
                    () =>
                      api("/campaigns", "POST", {
                        name,
                        team_ids: campaignTeams,
                        language: getLocale(),
                      }),
                    "Ölçüm dönemi oluşturuldu.",
                  )
                ) {
                  setModal(false);
                  setName("");
                }
              }}
            >
              <label>
                {t(" D\u00F6nem ad\u0131 ")}
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("\u00D6rn. AI Skills Baseline \u00B7 Q1 2027")}
                />
              </label>
              <fieldset className="campaign-team-picker">
                <p>
                  {t("Anket dili")}: {getLocale().toUpperCase()} ·{" "}
                  {t("Yeni ölçümler seçili dilde oluşturulur.")}
                </p>
                <legend>{t("Hedef ekipler")}</legend>
                <label className="campaign-all-teams">
                  <input
                    type="checkbox"
                    aria-label={t("T\u00FCm ekipler")}
                    checked={
                      boot.teams.length > 0 &&
                      campaignTeams.length === boot.teams.length
                    }
                    ref={(node) => {
                      if (node)
                        node.indeterminate =
                          campaignTeams.length > 0 &&
                          campaignTeams.length < boot.teams.length;
                    }}
                    onChange={(e) =>
                      setCampaignTeams(
                        e.target.checked
                          ? boot.teams.map((t: Any) => t.id)
                          : [],
                      )
                    }
                  />
                  <b>{t("T\u00FCm ekipler")}</b>
                  <small>
                    {translateNode(campaignTeams.length)}
                    {t(" / ")}
                    {translateNode(boot.teams.length)}
                    {t(" ekip se\u00E7ildi ")}
                  </small>
                </label>
                {translateNode(
                  boot.teams.map((t: Any) => (
                    <label key={t.id}>
                      <input
                        type="checkbox"
                        checked={campaignTeams.includes(t.id)}
                        onChange={(e) =>
                          setCampaignTeams((ids) =>
                            e.target.checked
                              ? [...ids, t.id]
                              : ids.filter((id) => id !== t.id),
                          )
                        }
                      />
                      {t.name}
                    </label>
                  )),
                )}
              </fieldset>
              <div className="notice">
                <Sparkles size={18} />
                <span>
                  {t(
                    " Se\u00E7ilen ekiplerin ba\u011Flam\u0131, rol profilleri ve hedefleri d\u00F6neme sabitlenir. Sorular bu ba\u011Flamla \u00FCretilir; her \u00E7al\u0131\u015Fan atanm\u0131\u015F rol formunu al\u0131r. Ortak sorular kar\u015F\u0131la\u015Ft\u0131r\u0131labilir kal\u0131r. ",
                  )}
                </span>
              </div>
              <Button disabled={busy || !campaignTeams.length}>
                {t(" D\u00F6nemi olu\u015Ftur ")}
              </Button>
            </form>
          </Modal>
        ),
      )}
      {translateNode(
        qs && (
          <Suspense
            fallback={
              <p role="status">
                {t("Soru edit\u00F6r\u00FC y\u00FCkleniyor\u2026")}
              </p>
            }
          >
            <QuestionSetEditor
              campaignId={qs}
              action={action}
              onClose={() => setQs(null)}
            />
          </Suspense>
        ),
      )}
    </>
  );
}
function Teams({ boot, action, user }: Any) {
  const [edit, setEdit] = useState<Any>(null),
    [skills, setSkills] = useState<Any[]>([]);
  useEffect(() => {
    api("/skills?include_archived=true&compact=true").then(setSkills);
  }, []);
  return (
    <>
      <div className="section-toolbar">
        <span className="muted">
          {t(
            " Ekip ba\u011Flam\u0131 ve hedefler yeni d\u00F6nemlerde kullan\u0131l\u0131r. ",
          )}
        </span>
        {translateNode(
          user.permissions.all_data && (
            <Button
              onClick={() =>
                setEdit({
                  name: "",
                  role: "",
                  context: {
                    purpose: "",
                    tasks: [],
                    tools: [],
                    constraints: "",
                  },
                  targets: [],
                })
              }
            >
              <Plus size={17} />
              {t(" Ekip ekle ")}
            </Button>
          ),
        )}
      </div>
      <div className="team-grid">
        {translateNode(
          boot.teams.map((t: Any) => (
            <section className="panel team-card" key={t.id}>
              <div className="team-card-top">
                <span className="team-symbol big">
                  {translateNode(t.name[0])}
                </span>
                <span className="small-pill">
                  {t("Ba\u011Flam v")}
                  {translateNode(t.version)}
                </span>
              </div>
              <h2>{t.name}</h2>
              <p>{translateNode(t.context.purpose)}</p>
              <div className="team-role">
                <Users size={15} />
                {translateNode(t.role)}
              </div>
              <div className="targets">
                {translateNode(
                  t.targets.map((x: Any) => (
                    <div key={x.skill_id}>
                      <span>
                        {translateNode(
                          skills.find((s) => s.id === x.skill_id)?.name ||
                            x.skill_id,
                        )}
                        {translateNode(
                          skills.find((s) => s.id === x.skill_id)?.archived &&
                            " (Arşivde)",
                        )}
                      </span>
                      <b>
                        {t("L")}
                        {translateNode(x.target_level)}
                      </b>
                    </div>
                  )),
                )}
              </div>
              {translateNode(
                boot.editable_team_ids?.includes(t.id) ? (
                  <Button
                    secondary
                    onClick={() => setEdit(JSON.parse(JSON.stringify(t)))}
                  >
                    {t(" Ba\u011Flam ve hedefleri d\u00FCzenle ")}
                    <ArrowRight size={15} />
                  </Button>
                ) : (
                  <p className="muted">
                    {t(
                      " Ortak departman ba\u011Flam\u0131 \u0130K taraf\u0131ndan y\u00F6netilir. ",
                    )}
                  </p>
                ),
              )}
            </section>
          )),
        )}
      </div>
      {translateNode(
        edit && (
          <Modal
            title={t("Ekip ba\u011Flam\u0131 ve hedefler")}
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
                  {t(" Ekip ad\u0131 ")}
                  <input
                    required
                    value={edit.name}
                    onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                  />
                </label>
                <label>
                  {t(" Rol / title ")}
                  <input
                    required
                    value={edit.role}
                    onChange={(e) => setEdit({ ...edit, role: e.target.value })}
                  />
                </label>
              </div>
              <label>
                {t(" Ekip amac\u0131 ve i\u015F senaryolar\u0131 ")}
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
                {t(" AI kullan\u0131m s\u0131n\u0131rlar\u0131 ")}
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
                {t(" Yetkinlik ekle ")}
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
                  <option value="">{t("Yetkinlik se\u00E7in\u2026")}</option>
                  {translateNode(
                    skills
                      .filter((s) => !s.archived)
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      )),
                  )}
                </select>
              </label>
              <div className="target-editor">
                {translateNode(
                  edit.targets.map((x: Any, i: number) => (
                    <div key={x.skill_id}>
                      <span>
                        {translateNode(
                          skills.find((s) => s.id === x.skill_id)?.name ||
                            x.skill_id,
                        )}
                        {translateNode(
                          skills.find((s) => s.id === x.skill_id)?.archived &&
                            " (Arşivde)",
                        )}
                      </span>
                      <label>
                        {t(" Hedef ")}
                        <select
                          value={x.target_level}
                          onChange={(e) =>
                            setEdit({
                              ...edit,
                              targets: edit.targets.map((y: Any, j: number) =>
                                j === i
                                  ? {
                                      ...y,
                                      target_level: Number(e.target.value),
                                    }
                                  : y,
                              ),
                            })
                          }
                        >
                          {translateNode(
                            [1, 2, 3, 4, 5].map((n) => (
                              <option key={n} value={n}>
                                {t(" L")}
                                {translateNode(n)}
                              </option>
                            )),
                          )}
                        </select>
                      </label>
                      <label>
                        {t(" \u00D6nem ")}
                        <select
                          value={x.criticality}
                          onChange={(e) =>
                            setEdit({
                              ...edit,
                              targets: edit.targets.map((y: Any, j: number) =>
                                j === i
                                  ? {
                                      ...y,
                                      criticality: Number(e.target.value),
                                    }
                                  : y,
                              ),
                            })
                          }
                        >
                          {translateNode(
                            [1, 2, 3, 4, 5].map((n) => (
                              <option key={n}>{translateNode(n)}</option>
                            )),
                          )}
                        </select>
                      </label>
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={t("Yetkinli\u011Fi kald\u0131r")}
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
                  )),
                )}
              </div>
              <Button>{t("De\u011Fi\u015Fiklikleri kaydet")}</Button>
            </form>
          </Modal>
        ),
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
            {translateNode(
              boot.campaigns.map((c: Any) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              )),
            )}
          </select>
        </div>
        <Badge status={campaign?.status} />
      </div>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>{t("Kat\u0131l\u0131mc\u0131 formlar\u0131")}</h2>
            <p>
              {t(
                " Eri\u015Fim kapsam\u0131n\u0131zdaki kat\u0131l\u0131mc\u0131lar\u0131n atanm\u0131\u015F formlar\u0131n\u0131 g\u00F6r\u00FCnt\u00FCleyin. ",
              )}
            </p>
          </div>
          <span className="small-pill">{t("Her soru zorunlu")}</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>{t("Kat\u0131l\u0131mc\u0131")}</th>
              <th>{t("Ekip")}</th>
              <th>{t("Rol")}</th>
              <th>{t("Durum")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {translateNode(
              list.map((a) => (
                <tr key={a.id}>
                  <td>
                    <b>{a.name}</b>
                  </td>
                  <td>{translateNode(a.team_name)}</td>
                  <td>{a.title}</td>
                  <td>
                    <Badge status={a.status} />
                  </td>
                  <td>
                    <button className="text-btn" onClick={() => setAid(a.id)}>
                      {translateNode(
                        a.status === "submitted"
                          ? "Yanıtları görüntüle"
                          : "Formu aç",
                      )}
                      {translateNode(" ")}
                      <ArrowRight size={14} />
                    </button>
                  </td>
                </tr>
              )),
            )}
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
    [sending, setSending] = useState(false),
    [showMissing, setShowMissing] = useState(false);
  const isAnswered = (q: Any) =>
    q.type === "open_text"
      ? !!(current.current[q.id]?.text || "")
          .replace(/[\u200B-\u200D\uFEFF]/g, "")
          .trim()
      : current.current[q.id]?.selected?.length === 1;
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
    const missing = data.questions.findIndex((q: Any) => !isAnswered(q));
    if (missing >= 0) {
      setShowMissing(true);
      setPage(Math.floor(missing / 5));
      notify("Tüm sorular zorunludur. Eksik yanıtları tamamlayın.");
      return;
    }
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
      <Empty
        title={t("Form haz\u0131rlan\u0131yor")}
        text="Atanmış sorular yükleniyor."
      />
    );
  const locked =
    data.assignment.status === "submitted" ||
    data.campaign.status !== "open" ||
    data.can_answer === false;
  const answered = data.questions.filter(isAnswered).length;
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
        <ChevronLeft size={16} />
        {t(" Kat\u0131l\u0131mc\u0131lara d\u00F6n ")}
      </button>
      <div className="survey-layout">
        <aside className="panel survey-side">
          <div className="eyebrow">{t("KATILIMCI FORMU")}</div>
          <h2>{data.assignment.profile_snapshot.name}</h2>
          <p>{data.assignment.profile_snapshot.title}</p>
          <div className="progress-track">
            <i
              style={{ width: (answered / data.questions.length) * 100 + "%" }}
            />
          </div>
          <b>
            {translateNode(answered)}
            {t(" / ")}
            {translateNode(data.questions.length)}
            {t(" yan\u0131tland\u0131 ")}
          </b>
          <div className="survey-side-note">
            <ShieldCheck size={20} />
            <p>
              {t(
                " T\u00FCm sorular zorunludur. Yan\u0131tlar\u0131n\u0131z otomatik kaydedilir. Deneyiminiz olmayan sorularda bunu a\u00E7\u0131k\u00E7a belirtebilirsiniz. ",
              )}
            </p>
          </div>
          <Badge status={locked ? "submitted" : "open"} />
        </aside>
        <div>
          <div className="survey-title">
            <span className="small-pill">{data.campaign.name}</span>
            <p>
              {t(
                " Yakla\u015F\u0131m\u0131n\u0131z\u0131 somut ad\u0131mlar ve kontrollerle anlat\u0131n. K\u0131sa, madde i\u015Faretli yan\u0131tlar kabul edilir. ",
              )}
            </p>
          </div>
          {translateNode(
            data.questions
              .slice(page * 5, page * 5 + 5)
              .map((q: Any, i: number) => (
                <section
                  id={`survey-question-${q.id}`}
                  className={`panel question-card ${showMissing && !isAnswered(q) && !locked ? "question-missing" : ""}`}
                  key={q.id}
                >
                  <div className="question-number">
                    <span>
                      {translateNode(String(page * 5 + i + 1).padStart(2, "0"))}
                    </span>
                    <small>
                      {translateNode(
                        q.type === "open_text"
                          ? "AÇIK UÇLU"
                          : q.type === "self_assessment"
                            ? "ÖZ DEĞERLENDİRME"
                            : "BİLGİ KONTROLÜ",
                      )}
                    </small>
                    <span className="question-save">
                      {translateNode(
                        saving[q.id] === "saving" ? (
                          <>
                            <LoaderCircle className="spin" size={12} />
                            {t(" Kaydediliyor ")}
                          </>
                        ) : saving[q.id] === "error" ? (
                          <button
                            className="text-btn"
                            onClick={() => save(q.id).catch(() => {})}
                          >
                            {t(" Tekrar kaydet ")}
                          </button>
                        ) : saving[q.id] === "saved" ? (
                          <>
                            <Check size={12} />
                            {t(" Kaydedildi ")}
                          </>
                        ) : (
                          ""
                        ),
                      )}
                    </span>
                  </div>
                  <span className="skill-tag">
                    {translateNode(q.skill_name)}
                  </span>
                  <span className="question-required">{t("Zorunlu")}</span>
                  <h3>{q.prompt}</h3>
                  {translateNode(
                    showMissing && !isAnswered(q) && !locked && (
                      <p
                        className="question-error"
                        id={`missing-${q.id}`}
                        role="alert"
                      >
                        {t(
                          " Bu soruyu yan\u0131tlay\u0131n. Deneyiminiz yoksa a\u00E7\u0131k\u00E7a belirtebilirsiniz. ",
                        )}
                      </p>
                    ),
                  )}
                  {translateNode(
                    q.type === "open_text" ? (
                      <>
                        <textarea
                          aria-label={t(`Yanıt ${page * 5 + i + 1}`)}
                          disabled={locked || sending}
                          required
                          aria-required="true"
                          aria-invalid={
                            showMissing && !isAnswered(q) && !locked
                          }
                          aria-describedby={
                            showMissing && !isAnswered(q)
                              ? `missing-${q.id}`
                              : undefined
                          }
                          maxLength={8000}
                          rows={6}
                          value={values[q.id]?.text || ""}
                          onChange={(e) => change(q, e.target.value)}
                          onBlur={() => save(q.id).catch(() => {})}
                          placeholder={t(
                            "Yakla\u015F\u0131m\u0131n\u0131z\u0131, uygulayaca\u011F\u0131n\u0131z kontrolleri ve deneyiminizi yaz\u0131n\u2026",
                          )}
                        />
                        <small className="char-count">
                          {translateNode(values[q.id]?.text?.length || 0)}
                          {t(" / 8.000 ")}
                        </small>
                      </>
                    ) : (
                      <div className="options">
                        {translateNode(
                          q.options.map((o: Any) => (
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
                                disabled={locked || sending}
                                required
                                aria-required="true"
                                checked={
                                  !!values[q.id]?.selected?.includes(o.id)
                                }
                                onChange={() => change(q, o.id)}
                              />
                              <span>{o.text}</span>
                            </label>
                          )),
                        )}
                      </div>
                    ),
                  )}
                </section>
              )),
          )}
          <div className="survey-pagination">
            <Button
              secondary
              disabled={page === 0 || sending}
              onClick={() => {
                setShowMissing(false);
                setPage(page - 1);
              }}
            >
              <ChevronLeft size={16} />
              {t(" \u00D6nceki ")}
            </Button>
            <span>
              {translateNode(page + 1)}
              {t(" / ")}
              {translateNode(Math.ceil(data.questions.length / 5))}
            </span>
            {translateNode(
              (page + 1) * 5 < data.questions.length ? (
                <Button
                  onClick={() => {
                    if (
                      !locked &&
                      data.questions
                        .slice(page * 5, page * 5 + 5)
                        .some((q: Any) => !isAnswered(q))
                    ) {
                      setShowMissing(true);
                      notify("Bu sayfadaki zorunlu soruları tamamlayın.");
                      return;
                    }
                    setShowMissing(false);
                    setPage(page + 1);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  {t(" Devam et ")}
                  <ChevronRight size={16} />
                </Button>
              ) : (
                <Button disabled={locked || sending} onClick={send}>
                  {translateNode(
                    sending ? (
                      <LoaderCircle size={16} className="spin" />
                    ) : (
                      <Check size={16} />
                    ),
                  )}
                  {translateNode(" ")}
                  {t(" Yan\u0131tlar\u0131 g\u00F6nder ")}
                </Button>
              ),
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
          {t(
            " Sonu\u00E7lar, puanlama ve gerekli incelemeler tamamland\u0131ktan sonra yay\u0131mlan\u0131r. ",
          )}
        </span>
      </div>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>{t("Toplu de\u011Ferlendirme i\u015Fleri")}</h2>
            <p>
              {t(
                "Model ve girdi s\u00FCr\u00FCm\u00FC her ko\u015Fuda sabitlenir.",
              )}
            </p>
          </div>
          <Activity size={20} />
        </div>
        {translateNode(
          !runs.length ? (
            <Empty
              title={t("Hen\u00FCz de\u011Ferlendirme yok")}
              text="Bir kampanyayı kapatıp toplu değerlendirmeyi başlatın."
            />
          ) : (
            runs.map((r) => (
              <div className="run-row" key={r.id}>
                <div className="run-icon">
                  <Zap size={22} />
                </div>
                <div className="run-info">
                  <h3>{translateNode(r.campaign_name)}</h3>
                  <small>
                    {translateNode(r.id.slice(0, 8))}
                    {t(" \u00B7 ")}
                    {translateNode(r.calls)}
                    {t(" puanlama \u00E7a\u011Fr\u0131s\u0131 \u00B7")}
                    {translateNode(" ")}
                    {translateNode(
                      new Date(r.created_at).toLocaleString(formatLocale()),
                    )}
                  </small>
                  <div className="progress-track">
                    <i style={{ width: r.progress + "%" }} />
                  </div>
                  <span>
                    {translateNode(r.jobs.done)}
                    {t("/")}
                    {translateNode(r.total)}
                    {t(" i\u015F tamamland\u0131")}
                    {translateNode(" ")}
                    {translateNode(
                      r.jobs.failed ? `· ${r.jobs.failed} hata` : "",
                    )}
                  </span>
                  {translateNode(
                    r.error && (
                      <p className="error-text">{translateNode(r.error)}</p>
                    ),
                  )}
                </div>
                <Badge status={r.status} />
                <div className="run-actions">
                  {translateNode(
                    r.reviews > 0 && (
                      <Button
                        secondary
                        onClick={async () =>
                          setReviews(
                            await api(`/evaluation-runs/${r.id}/reviews`),
                          )
                        }
                      >
                        {translateNode(r.reviews)}
                        {t(" inceleme ")}
                      </Button>
                    ),
                  )}
                  {translateNode(
                    r.can_manage && r.status === "ready_to_publish" && (
                      <Button
                        onClick={() =>
                          action(
                            () =>
                              api(`/evaluation-runs/${r.id}/publish`, "POST"),
                            "Sonuçlar yayımlandı.",
                          ).then(load)
                        }
                      >
                        {t(" Sonu\u00E7lar\u0131 yay\u0131mla ")}
                      </Button>
                    ),
                  )}
                  {translateNode(
                    r.can_manage && r.status === "failed" && (
                      <Button
                        onClick={() =>
                          action(
                            () =>
                              api(
                                `/evaluation-runs/${r.id}/retry-failed`,
                                "POST",
                              ),
                            "Başarısız işler yeniden sıraya alındı.",
                          ).then(load)
                        }
                      >
                        {t(" Ba\u015Far\u0131s\u0131zlar\u0131 dene ")}
                      </Button>
                    ),
                  )}
                  {translateNode(
                    r.can_manage &&
                      ["queued", "evaluating", "validating"].includes(
                        r.status,
                      ) && (
                        <Button
                          secondary
                          onClick={() =>
                            action(
                              () =>
                                api(`/evaluation-runs/${r.id}/cancel`, "POST"),
                              "İş iptal edildi.",
                            ).then(load)
                          }
                        >
                          {t(" \u0130ptal et ")}
                        </Button>
                      ),
                  )}
                </div>
              </div>
            ))
          ),
        )}
      </section>
      <section className="panel export-panel">
        <div className="panel-head">
          <div>
            <h2>{t("Excel \u00E7\u0131kt\u0131lar\u0131")}</h2>
            <p>
              {t(
                "Yay\u0131mlanm\u0131\u015F sonu\u00E7larla ayn\u0131 veri s\u00FCr\u00FCm\u00FCn\u00FC kullan\u0131r.",
              )}
            </p>
          </div>
          <ArrowDownToLine size={20} />
        </div>
        {translateNode(
          exports.length ? (
            <table>
              <thead>
                <tr>
                  <th>{t("Dosya")}</th>
                  <th>{t("\u0130\u00E7erik")}</th>
                  <th>{t("Tarih")}</th>
                  <th>{t("Durum")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {translateNode(
                  exports.map((e) => (
                    <tr key={e.id}>
                      <td>
                        {t("Aptilume-")}
                        {translateNode(e.id.slice(0, 8))}
                        {t(".xlsx")}
                      </td>
                      <td>
                        {translateNode(
                          e.detail ? "Detaylı değerlendirme" : "Toplu özet",
                        )}
                      </td>
                      <td>
                        {translateNode(
                          new Date(e.created_at).toLocaleString(formatLocale()),
                        )}
                      </td>
                      <td>
                        <Badge
                          status={e.status === "ready" ? "done" : e.status}
                        />
                      </td>
                      <td>
                        {translateNode(
                          e.status === "ready" && (
                            <a
                              className="text-btn"
                              href={`${API}/exports/${e.id}/download`}
                            >
                              <ArrowDownToLine size={15} />
                              {t(" \u0130ndir ")}
                            </a>
                          ),
                        )}
                      </td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          ) : (
            <div className="inline-empty">
              {t(
                " Genel g\u00F6r\u00FCn\u00FCmden bir Excel \u00E7\u0131kt\u0131s\u0131 olu\u015Fturabilirsiniz. ",
              )}
            </div>
          ),
        )}
      </section>
      {translateNode(
        reviews && (
          <Modal
            title={t("De\u011Ferlendirme incelemesi")}
            onClose={() => setReviews(null)}
          >
            <div className="modal-body">
              {translateNode(
                reviews.length ? (
                  reviews.map((r: Any) => (
                    <article className="review-item" key={r.id}>
                      <h3>{translateNode(r.question)}</h3>
                      <blockquote>{r.answer}</blockquote>
                      <p>
                        {t(" Model puan\u0131: ")}
                        {translateNode(fmt(r.score, 1))}
                        {t(" \u00B7 ")}
                        {translateNode(r.flags.join(", "))}
                      </p>
                      {translateNode(
                        r.criteria.map((c: Any) => (
                          <p key={c.criterion_id}>
                            <b>
                              {translateNode(c.criterion_id)}
                              {t(": ")}
                              {translateNode(c.points)}
                              {t("/4 ")}
                            </b>
                            {translateNode(" ")}
                            {t(" \u2014 ")}
                            {c.reason}
                          </p>
                        )),
                      )}
                      {translateNode(
                        r.quality && (
                          <div className="notice">
                            <span>
                              <b>
                                {translateNode(
                                  qualityLabels[r.quality.category] ||
                                    r.quality.category,
                                )}
                              </b>
                              <br />
                              {r.quality.reason}
                              <br />
                              {t(
                                " Bu yan\u0131t i\u00E7in \u0130K taraf\u0131ndan a\u00E7\u0131k puan karar\u0131 verilmelidir. ",
                              )}
                            </span>
                          </div>
                        ),
                      )}
                      <label>
                        {translateNode(
                          r.quality
                            ? "İK puan kararı (zorunlu, 0–100)"
                            : "Düzeltilmiş soru puanı (isteğe bağlı, 0–100)",
                        )}
                        <input
                          type="number"
                          min="0"
                          max="100"
                          value={override[r.id] || ""}
                          onChange={(e) =>
                            setOverride({ ...override, [r.id]: e.target.value })
                          }
                          placeholder={t(
                            r.quality
                              ? "İK puan kararını girin"
                              : "Boş bırakırsanız model puanı korunur",
                          )}
                        />
                      </label>
                      <label>
                        {t(" \u0130nceleme gerek\u00E7esi ")}
                        <input
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          placeholder={t(
                            "Karar\u0131n\u0131z\u0131n gerek\u00E7esini yaz\u0131n",
                          )}
                        />
                      </label>
                      {translateNode(
                        r.can_review === false && (
                          <div className="notice">
                            {translateNode(
                              r.quality
                                ? "Bu kalite kaydı için yetkili başka bir İK kullanıcısı inceleme yapmalı."
                                : "Kendi yanıtınızı onaylayamazsınız. Başka bir yetkili incelemeli.",
                            )}
                          </div>
                        ),
                      )}
                      <Button
                        disabled={
                          reason.length < 5 ||
                          r.can_review === false ||
                          (r.quality && !override[r.id])
                        }
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
                            setReviews(
                              reviews.filter((x: Any) => x.id !== r.id),
                            );
                            setReason("");
                            load();
                          }
                        }}
                      >
                        {t(" Puan\u0131 onayla ")}
                      </Button>
                    </article>
                  ))
                ) : (
                  <Empty
                    title={t("\u0130ncelemeler tamamland\u0131")}
                    text="Sonuç işinin tamamlanmasını bekleyebilirsiniz."
                  />
                ),
              )}
            </div>
          </Modal>
        ),
      )}
    </>
  );
}
function Connections({ action, notify, user, security }: Any) {
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
              sslmode: "verify-full",
              sslrootcert: "",
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
            <Sparkles size={16} />
            {t(" LLM ba\u011Flant\u0131lar\u0131 ")}
          </button>
          <button
            className={tab === "db" ? "active" : ""}
            onClick={() => setTab("db")}
          >
            <Database size={16} />
            {t(" Veritabanlar\u0131 ")}
          </button>
        </div>
        <Button onClick={newProfile}>
          <Plus size={17} />
          {t(" Ba\u011Flant\u0131 ekle ")}
        </Button>
      </div>
      <div className="connection-grid">
        {translateNode(
          rows.map((p) => (
            <section className="panel connection-card" key={p.id}>
              <div className="connection-top">
                <div className="connection-symbol">
                  {translateNode(
                    tab === "llm" ? (
                      <Sparkles size={22} />
                    ) : (
                      <Database size={22} />
                    ),
                  )}
                </div>
                <span className="small-pill">
                  {t("v")}
                  {translateNode(p.version)}
                </span>
              </div>
              <h2>{p.name}</h2>
              <p>
                {translateNode(
                  p.config.model || p.config.database || p.config.engine,
                )}
              </p>
              <code>
                {translateNode(
                  p.config.endpoint || p.config.host || p.config.path,
                )}
              </code>
              <div className="binding-tags">
                {translateNode(
                  p.active_for.map((x: string) => (
                    <span key={x}>
                      {translateNode(
                        (
                          {
                            generation: "Soru üretimi",
                            evaluation: "Puanlama",
                            insights: "İçgörüler",
                            application_db: "Aktif veri deposu",
                          } as Any
                        )[x],
                      )}
                    </span>
                  )),
                )}
              </div>
              <div className="connection-actions">
                <button
                  className="text-btn"
                  onClick={async () =>
                    setTest(
                      await api(
                        `/admin/connections/${tab}/${p.id}/test`,
                        "POST",
                      ),
                    )
                  }
                >
                  <Network size={15} />
                  {t(" Test et ")}
                </button>
                <button
                  className="text-btn"
                  onClick={() => setEdit({ ...p, secret: "" })}
                >
                  {t(" D\u00FCzenle ")}
                </button>
                <button
                  className="icon-btn danger"
                  aria-label={t("Ba\u011Flant\u0131y\u0131 sil")}
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
              {translateNode(
                tab === "llm" && user.permissions.all_data ? (
                  <div className="binding-controls">
                    <span>{t("G\u00F6rev i\u00E7in se\u00E7:")}</span>
                    {translateNode(
                      [
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
                                api(
                                  `/admin/service-bindings/${purpose}`,
                                  "PUT",
                                  {
                                    profile_id: p.id,
                                  },
                                ),
                              label + " profili güncellendi.",
                            ).then(load)
                          }
                        >
                          {translateNode(label)}
                        </button>
                      )),
                    )}
                  </div>
                ) : tab === "db" &&
                  user.permissions.all_data &&
                  !security?.offline_database_migration ? (
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
                      {t(" DB ge\u00E7i\u015Fini \u00F6nizle ")}
                      <ArrowRight size={14} />
                    </button>
                  )
                ) : (
                  <p className="muted">
                    {translateNode(
                      tab === "llm"
                        ? "Veri aktaracak görevleri İK etkinleştirir."
                        : "Üretimde DB değişimi, API ve worker durdurularak işletim ekibi tarafından yapılır.",
                    )}
                    {translateNode(
                      tab === "db" && (
                        <small className="cell-subtitle">
                          {t(" Profil kimli\u011Fi: ")}
                          {translateNode(p.id)}
                        </small>
                      ),
                    )}
                  </p>
                ),
              )}
            </section>
          )),
        )}
      </div>
      <div className="notice">
        <ShieldCheck size={18} />
        <span>
          {t(
            " Gizli anahtarlar \u015Fifreli tutulur ve yeniden g\u00F6sterilmez. Profil de\u011Fi\u015Fiklikleri ge\u00E7mi\u015F de\u011Ferlendirmelerin s\u00FCr\u00FCm\u00FCn\u00FC de\u011Fi\u015Ftirmez. ",
          )}
        </span>
      </div>
      {translateNode(
        edit && (
          <Modal
            title={t(edit.id ? "Bağlantıyı düzenle" : "Yeni bağlantı")}
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
                {t(" Profil ad\u0131 ")}
                <input
                  required
                  value={edit.name}
                  onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                  placeholder={t("\u00D6rn. Kurum LLM \u00B7 Puanlama")}
                />
              </label>
              {translateNode(
                tab === "llm" ? (
                  <>
                    <div className="form-grid">
                      <label>
                        {t(" Protokol ")}
                        <select
                          value={edit.config.provider}
                          onChange={(e) => cfg("provider", e.target.value)}
                        >
                          <option value="mock">
                            {t("Mock \u00B7 Development")}
                          </option>
                          <option value="openai_responses">
                            {t("OpenAI Responses")}
                          </option>
                          <option value="openai_compatible_chat">
                            {t(" OpenAI Compatible Chat ")}
                          </option>
                        </select>
                      </label>
                      <label>
                        {t(" Model / deployment ad\u0131 ")}
                        <input
                          required
                          value={edit.config.model || ""}
                          onChange={(e) => cfg("model", e.target.value)}
                        />
                      </label>
                    </div>
                    <label>
                      {t(" Base URL ")}
                      <input
                        value={edit.config.endpoint || ""}
                        onChange={(e) => cfg("endpoint", e.target.value)}
                        placeholder={t("https://llm.example/v1")}
                      />
                    </label>
                    {translateNode(
                      edit.config.provider === "mock" && (
                        <label>
                          {t(" Mock test senaryosu ")}
                          <select
                            value={edit.config.scenario || "success"}
                            onChange={(e) => cfg("scenario", e.target.value)}
                          >
                            {translateNode(
                              [
                                "success",
                                "timeout",
                                "rate_limit",
                                "unauthorized",
                                "server_error",
                                "invalid_json",
                                "unsupported_quote",
                              ].map((x) => (
                                <option key={x}>{translateNode(x)}</option>
                              )),
                            )}
                          </select>
                        </label>
                      ),
                    )}
                    <div className="form-grid">
                      <label>
                        {t(" Timeout (saniye) ")}
                        <input
                          type="number"
                          min="1"
                          max="300"
                          value={edit.config.timeout}
                          onChange={(e) =>
                            cfg("timeout", Number(e.target.value))
                          }
                        />
                      </label>
                      <label>
                        {t(" Paralellik ")}
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
                      {t(" Veritaban\u0131 motoru ")}
                      <select
                        value={edit.config.engine}
                        onChange={(e) => cfg("engine", e.target.value)}
                      >
                        <option value="postgresql">{t("PostgreSQL")}</option>
                        <option value="sqlite">{t("SQLite")}</option>
                      </select>
                    </label>
                    {translateNode(
                      edit.config.engine === "sqlite" ? (
                        <label>
                          {t(" Dosya yolu ")}
                          <input
                            required
                            value={edit.config.path || ""}
                            onChange={(e) => cfg("path", e.target.value)}
                            placeholder={t("DATA_DIR i\u00E7indeki dosya")}
                          />
                        </label>
                      ) : (
                        <>
                          <div className="form-grid">
                            <label>
                              {t(" Host ")}
                              <input
                                required
                                value={edit.config.host || ""}
                                onChange={(e) => cfg("host", e.target.value)}
                              />
                            </label>
                            <label>
                              {t(" Port ")}
                              <input
                                type="number"
                                value={edit.config.port || 5432}
                                onChange={(e) =>
                                  cfg("port", Number(e.target.value))
                                }
                              />
                            </label>
                            <label>
                              {t(" Database ")}
                              <input
                                required
                                value={edit.config.database || ""}
                                onChange={(e) =>
                                  cfg("database", e.target.value)
                                }
                              />
                            </label>
                            <label>
                              {t(" Kullan\u0131c\u0131 ")}
                              <input
                                value={edit.config.username || ""}
                                onChange={(e) =>
                                  cfg("username", e.target.value)
                                }
                              />
                            </label>
                          </div>
                          <label>
                            {t(" TLS modu ")}
                            <select
                              value={edit.config.sslmode || "require"}
                              onChange={(e) => cfg("sslmode", e.target.value)}
                            >
                              <option>{t("require")}</option>
                              <option>{t("verify-full")}</option>
                              <option>{t("prefer")}</option>
                            </select>
                          </label>
                          <label>
                            {t(" Kurumsal DB CA dosyas\u0131 ")}
                            <input
                              value={edit.config.sslrootcert || ""}
                              onChange={(e) =>
                                cfg("sslrootcert", e.target.value)
                              }
                              placeholder={t("/etc/certs/kurum-ca.pem")}
                            />
                          </label>
                        </>
                      ),
                    )}
                  </>
                ),
              )}
              <label>
                {translateNode(tab === "llm" ? "API anahtarı" : "Parola")}
                {translateNode(" ")}
                {translateNode(
                  edit.has_secret && (
                    <small>
                      {t(
                        "\u00B7 Kay\u0131tl\u0131; bo\u015F b\u0131rak\u0131rsan\u0131z korunur",
                      )}
                    </small>
                  ),
                )}
                <input
                  type="password"
                  autoComplete="new-password"
                  value={edit.secret || ""}
                  onChange={(e) => setEdit({ ...edit, secret: e.target.value })}
                  placeholder={t("Gizli de\u011Fer")}
                />
              </label>
              <p className="muted">
                {t(
                  " Sunucu veya hesap de\u011Fi\u015Fti\u011Finde gizli de\u011Feri yeniden girin. \u00DCretimde DB i\u00E7in verify-full sertifika do\u011Frulamas\u0131 zorunludur. ",
                )}
              </p>
              {translateNode(
                edit.has_secret && (
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={!!edit.clear_secret}
                      onChange={(e) =>
                        setEdit({ ...edit, clear_secret: e.target.checked })
                      }
                    />
                    {t(" Kay\u0131tl\u0131 gizli de\u011Feri temizle ")}
                  </label>
                ),
              )}
              <div className="modal-actions">
                <Button secondary type="button" onClick={() => setEdit(null)}>
                  {t(" Vazge\u00E7 ")}
                </Button>
                <Button>{t("Ba\u011Flant\u0131y\u0131 kaydet")}</Button>
              </div>
            </form>
          </Modal>
        ),
      )}
      {translateNode(
        test && (
          <Modal
            title={t("Ba\u011Flant\u0131 testi")}
            onClose={() => setTest(null)}
          >
            <div className="modal-body">
              <Badge status={test.status === "success" ? "done" : "failed"} />
              <h3>{translateNode(test.message)}</h3>
              <p className="muted">
                {t(" Mod: ")}
                {translateNode(
                  test.mode === "mock" ? "Simülasyon" : "Gerçek bağlantı",
                )}
                {translateNode(" ")}
                {translateNode(
                  test.latency_ms != null && `· ${test.latency_ms} ms`,
                )}
              </p>
              <p>
                {t(
                  "Ba\u011Flant\u0131 testi, LLM de\u011Ferlendirme kalitesini do\u011Frulamaz.",
                )}
              </p>
            </div>
          </Modal>
        ),
      )}
      {translateNode(
        migration && (
          <Modal
            title={t("Veritaban\u0131 ge\u00E7i\u015Fi")}
            onClose={() => setMigration(null)}
          >
            <div className="modal-body">
              <h3>{migration.profile.name}</h3>
              <p>
                {t(
                  " Mevcut veriler hedef DB\u2019ye kopyalan\u0131r, kay\u0131tlar do\u011Frulan\u0131r ve aktif ba\u011Flant\u0131 de\u011Fi\u015Ftirilir. Hedef bo\u015F olmal\u0131d\u0131r. ",
                )}
              </p>
              <p>
                {t(" A\u00E7\u0131k kampanya: ")}
                <b>{translateNode(migration.open_campaigns)}</b>
              </p>
              <p className="muted">
                {translateNode(Object.keys(migration.records).length)}
                {t(
                  " tablo do\u011Frulanacak. Devam etmeden \u00F6nce veri yede\u011Finizi al\u0131n. ",
                )}
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
                {t(" Veriyi ta\u015F\u0131 ve etkinle\u015Ftir ")}
              </Button>
            </div>
          </Modal>
        ),
      )}
    </>
  );
}
function RoleProfiles({ boot, action, user }: Any) {
  const [role, setRole] = useState<Any>(null),
    [person, setPerson] = useState<Any>(null),
    [skills, setSkills] = useState<Any[]>([]);
  useEffect(() => {
    api("/skills?include_archived=true&compact=true").then(setSkills);
  }, []);
  const profiles = boot.role_profiles || [];
  const editableTeams = boot.teams.filter((t: Any) =>
    boot.editable_team_ids?.includes(t.id),
  );
  return (
    <>
      <div className="section-toolbar" style={{ marginTop: 30 }}>
        <div>
          <h2>{t("Rol profilleri")}</h2>
          <span className="muted">
            {t(
              " Ayn\u0131 ekipte farkl\u0131 title ve hedefler i\u00E7in ayr\u0131 formlar haz\u0131rlay\u0131n. ",
            )}
          </span>
        </div>
        {translateNode(
          !!editableTeams.length && (
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
              <Plus size={16} />
              {t(" Rol ekle ")}
            </Button>
          ),
        )}
      </div>
      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>{t("Rol / title")}</th>
              <th>{t("Ekip")}</th>
              <th>{t("Kademe")}</th>
              <th>{t("Yetkinlik")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {translateNode(
              profiles.map((r: Any) => (
                <tr key={r.id}>
                  <td>
                    <b>{r.title}</b>
                  </td>
                  <td>
                    {boot.teams.find((t: Any) => t.id === r.team_id)?.name}
                  </td>
                  <td>{translateNode(r.job_band)}</td>
                  <td>
                    {translateNode(r.targets.length)}
                    {t(" \u00B7 v")}
                    {translateNode(r.version)}
                  </td>
                  <td>
                    {translateNode(
                      boot.editable_team_ids?.includes(r.team_id) ? (
                        <button
                          className="text-btn"
                          onClick={() => setRole(JSON.parse(JSON.stringify(r)))}
                        >
                          {t(" Hedefleri d\u00FCzenle ")}
                        </button>
                      ) : (
                        <span className="muted">
                          {t("\u0130K taraf\u0131ndan y\u00F6netilir")}
                        </span>
                      ),
                    )}
                  </td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </section>
      <div className="section-toolbar" style={{ marginTop: 30 }}>
        <div>
          <h2>{t("Kat\u0131l\u0131mc\u0131lar ve rol e\u015Flemeleri")}</h2>
          <span className="muted">
            {t(
              " De\u011Fi\u015Fiklikler yeni \u00F6l\u00E7\u00FCm d\u00F6nemlerinde ge\u00E7erlidir. ",
            )}
          </span>
        </div>
        {translateNode(
          user.permissions.all_data && (
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
              <Plus size={16} />
              {t(" Kat\u0131l\u0131mc\u0131 ekle ")}
            </Button>
          ),
        )}
      </div>
      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>{t("Kat\u0131l\u0131mc\u0131")}</th>
              <th>{t("Title")}</th>
              <th>{t("Rol profili")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {translateNode(
              boot.participants.map((p: Any) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{p.title}</td>
                  <td>
                    {translateNode(
                      profiles.find((r: Any) => r.id === p.role_profile_id)
                        ?.title || "Varsayılan",
                    )}
                  </td>
                  <td>
                    {translateNode(
                      user.permissions.all_data && (
                        <button
                          className="text-btn"
                          onClick={() => setPerson({ ...p })}
                        >
                          {t(" D\u00FCzenle ")}
                        </button>
                      ),
                    )}
                  </td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </section>
      {translateNode(
        role && (
          <Modal
            title={t("Rol profili ve hedefler")}
            onClose={() => setRole(null)}
          >
            <form
              className="modal-body"
              onSubmit={async (e) => {
                e.preventDefault();
                if (
                  await action(
                    () =>
                      api(
                        role.id
                          ? `/role-profiles/${role.id}`
                          : "/role-profiles",
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
                  {t(" Ekip ")}
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
                    {translateNode(
                      editableTeams.map((t: Any) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      )),
                    )}
                  </select>
                </label>
                <label>
                  {t(" Rol / title ")}
                  <input
                    required
                    value={role.title}
                    onChange={(e) =>
                      setRole({ ...role, title: e.target.value })
                    }
                  />
                </label>
                <label>
                  {t(" \u0130K kademesi ")}
                  <select
                    value={role.job_band}
                    onChange={(e) =>
                      setRole({ ...role, job_band: e.target.value })
                    }
                  >
                    {translateNode(
                      ["L1_L2", "L3_L4", "L5_L6"].map((x) => (
                        <option key={x}>{translateNode(x)}</option>
                      )),
                    )}
                  </select>
                </label>
              </div>
              <p className="muted">
                {t(
                  " Bu ba\u015Flang\u0131\u00E7 formu \u00FC\u00E7 ortak ve \u00FC\u00E7 rol yetkinli\u011Fi kullan\u0131r. Rol yetkinliklerini de\u011Fi\u015Ftirmek i\u00E7in hedeflerden kald\u0131r\u0131p katalogdan ekleyin. ",
                )}
              </p>
              <label>
                {t(" Yetkinlik ekle ")}
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
                  <option value="">{t("Katalogdan se\u00E7in\u2026")}</option>
                  {translateNode(
                    skills
                      .filter((s) => !s.archived)
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      )),
                  )}
                </select>
              </label>
              <div className="target-editor">
                {translateNode(
                  role.targets.map((x: Any, i: number) => (
                    <div key={x.skill_id}>
                      <span>
                        {translateNode(
                          skills.find((s) => s.id === x.skill_id)?.name ||
                            x.skill_id,
                        )}
                        {translateNode(
                          skills.find((s) => s.id === x.skill_id)?.archived &&
                            " (Arşivde)",
                        )}
                      </span>
                      <label>
                        {t(" Hedef ")}
                        <select
                          value={x.target_level}
                          onChange={(e) =>
                            setRole({
                              ...role,
                              targets: role.targets.map((y: Any, j: number) =>
                                i === j
                                  ? {
                                      ...y,
                                      target_level: Number(e.target.value),
                                    }
                                  : y,
                              ),
                            })
                          }
                        >
                          {translateNode(
                            [1, 2, 3, 4, 5].map((n) => (
                              <option key={n} value={n}>
                                {t(" L")}
                                {translateNode(n)}
                              </option>
                            )),
                          )}
                        </select>
                      </label>
                      <label>
                        {t(" \u00D6nem ")}
                        <select
                          value={x.criticality}
                          onChange={(e) =>
                            setRole({
                              ...role,
                              targets: role.targets.map((y: Any, j: number) =>
                                i === j
                                  ? {
                                      ...y,
                                      criticality: Number(e.target.value),
                                    }
                                  : y,
                              ),
                            })
                          }
                        >
                          {translateNode(
                            [1, 2, 3, 4, 5].map((n) => (
                              <option key={n}>{translateNode(n)}</option>
                            )),
                          )}
                        </select>
                      </label>
                      <button
                        type="button"
                        className="icon-btn"
                        aria-label={t("Yetkinli\u011Fi kald\u0131r")}
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
                  )),
                )}
              </div>
              <Button>{t("Rol\u00FC kaydet")}</Button>
            </form>
          </Modal>
        ),
      )}
      {translateNode(
        person && (
          <Modal
            title={t("Kat\u0131l\u0131mc\u0131 rol e\u015Flemesi")}
            onClose={() => setPerson(null)}
          >
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
                {t(" Ad ")}
                <input
                  required
                  value={person.name}
                  onChange={(e) =>
                    setPerson({ ...person, name: e.target.value })
                  }
                />
              </label>
              <label>
                {t(" Title ")}
                <input
                  required
                  value={person.title}
                  onChange={(e) =>
                    setPerson({ ...person, title: e.target.value })
                  }
                />
              </label>
              <label>
                {t(" Rol profili ")}
                <select
                  required
                  value={person.role_profile_id || ""}
                  onChange={(e) =>
                    setPerson({ ...person, role_profile_id: e.target.value })
                  }
                >
                  <option value="">{t("Rol se\u00E7in\u2026")}</option>
                  {translateNode(
                    profiles.map((r: Any) => (
                      <option key={r.id} value={r.id}>
                        {boot.teams.find((t: Any) => t.id === r.team_id)?.name}
                        {t(" \u00B7")}
                        {translateNode(" ")}
                        {r.title}
                      </option>
                    )),
                  )}
                </select>
              </label>
              <label>
                {t(" \u0130K kademesi ")}
                <select
                  value={person.job_band}
                  onChange={(e) =>
                    setPerson({ ...person, job_band: e.target.value })
                  }
                >
                  {translateNode(
                    ["L1_L2", "L3_L4", "L5_L6"].map((x) => (
                      <option key={x}>{translateNode(x)}</option>
                    )),
                  )}
                </select>
              </label>
              <Button>{t("Kat\u0131l\u0131mc\u0131y\u0131 kaydet")}</Button>
            </form>
          </Modal>
        ),
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
