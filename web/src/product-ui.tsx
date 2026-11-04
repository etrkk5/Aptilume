import React, { useState, useEffect } from "react";
import {
  Plus,
  ArrowRight,
  UserRound,
  Info,
  CheckCircle2,
  Network,
  RefreshCw,
  ShieldCheck,
  Search,
  LoaderCircle,
} from "lucide-react";
import { api } from "./client";
import { Button, Modal } from "./ui";
const fmt = (x: any) =>
  x == null
    ? "—"
    : Number(x).toLocaleString("tr-TR", { maximumFractionDigits: 1 });
const actionLabels: any = {
  planned: "Planlandı",
  in_progress: "Devam ediyor",
  completed: "Tamamlandı",
  archived: "Arşivlendi",
};

export function AccountPanel({
  user,
  workspace,
  action,
  onWorkspace,
  onClose,
  onPasswordChanged,
}: any) {
  const [name, setName] = useState(workspace?.name || ""),
    [current, setCurrent] = useState(""),
    [password, setPassword] = useState("");
  return (
    <Modal title="Hesap bilgilerim" onClose={onClose}>
      <div className="modal-body">
        <dl className="report-info">
          <dt>Ad</dt>
          <dd>{user.display_name}</dd>
          <dt>Kullanıcı adı</dt>
          <dd>{user.username}</dd>
          <dt>E-posta</dt>
          <dd>{user.email || "—"}</dd>
          <dt>Yetki</dt>
          <dd>
            {user.roles
              .map(
                (x: string) =>
                  (
                    ({
                      hr: "İnsan kaynakları",
                      manager: "Ekip yöneticisi",
                      admin: "Entegrasyon yöneticisi",
                      employee: "Çalışan",
                    }) as any
                  )[x],
              )
              .join(", ")}
          </dd>
        </dl>
        {user.permissions.integrations && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const result = await action(
                () => api("/settings/workspace", "PUT", { name }),
                "Çalışma alanı kaydedildi.",
              );
              if (result) onWorkspace(result);
            }}
          >
            <label>
              Çalışma alanı adı
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <Button secondary>Çalışma alanını kaydet</Button>
          </form>
        )}
        {user.id === "local-admin" && (
          <form
            className="password-section"
            onSubmit={async (e) => {
              e.preventDefault();
              const r = await action(
                () =>
                  api("/auth/password", "POST", {
                    current_password: current,
                    new_password: password,
                  }),
                "Parola değiştirildi. Yeniden giriş yapın.",
              );
              if (r) {
                onClose();
                onPasswordChanged();
              }
            }}
          >
            {user.temporary_password && (
              <div className="notice">
                İlk kurulum hesabı kullanılıyor. Üretim kullanımından önce güçlü
                bir parola belirleyin.
              </div>
            )}
            <h3>Yönetici parolası</h3>
            <label>
              Mevcut parola
              <input
                type="password"
                autoComplete="current-password"
                required
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </label>
            <label>
              Yeni parola
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={12}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <Button secondary>Parolayı güncelle</Button>
          </form>
        )}
      </div>
    </Modal>
  );
}

export function DirectorySettings({ action, busy }: any) {
  const [config, setConfig] = useState<any>(null),
    [open, setOpen] = useState(false),
    [result, setResult] = useState<any>(null);
  const load = () =>
    api("/admin/directory").then((c) => setConfig({ ...c, password: "" }));
  useEffect(() => {
    load();
  }, []);
  if (!config)
    return (
      <div className="notice">
        <LoaderCircle className="spin" size={16} />
        Active Directory ayarları yükleniyor.
      </div>
    );
  const update = (key: string, value: any) =>
    setConfig({ ...config, [key]: value });
  return (
    <section className="panel directory-panel">
      <div className="panel-head">
        <div>
          <h2>Active Directory</h2>
          <p>Kurumsal giriş, rol grupları ve yönetici ilişkisi</p>
        </div>
        <span className={`badge ${config.enabled ? "done" : ""}`}>
          <i />
          {config.enabled ? "Etkin" : "Yapılandırma bekleniyor"}
        </span>
      </div>
      <div className="directory-summary">
        <div>
          <span>Sunucu</span>
          <b>{config.host || "Henüz girilmedi"}</b>
        </div>
        <div>
          <span>Yönetici ilişkisi</span>
          <b>{config.manager_attribute}</b>
        </div>
        <div>
          <span>Son eşitleme</span>
          <b>
            {config.sync_status?.last_sync
              ? new Date(config.sync_status.last_sync * 1000).toLocaleString(
                  "tr-TR",
                )
              : "Henüz yapılmadı"}
          </b>
        </div>
        <div className="directory-actions">
          <Button secondary onClick={() => setOpen(true)}>
            Bağlantıyı düzenle
          </Button>
          <Button
            secondary
            disabled={busy || !config.host}
            onClick={async () => {
              const r = await action(() =>
                api("/admin/directory/test", "POST"),
              );
              if (r) setResult(r);
            }}
          >
            <Network size={15} />
            Test et
          </Button>
          <Button
            disabled={busy || !config.enabled}
            onClick={async () => {
              const r = await action(
                () => api("/admin/directory/sync", "POST"),
                "Dizin eşitlemesi tamamlandı.",
              );
              if (r) {
                setResult({
                  message: `${r.users} dizin kaydı eşitlendi.`,
                  status: "success",
                });
                load();
              }
            }}
          >
            <RefreshCw size={15} />
            Eşitle
          </Button>
        </div>
      </div>
      {result && (
        <div className="directory-result" role="status">
          <CheckCircle2 size={16} />
          {result.message}
        </div>
      )}
      {open && (
        <Modal
          title="Active Directory bağlantısı"
          onClose={() => {
            setOpen(false);
            load();
          }}
        >
          <form
            className="modal-body"
            onSubmit={async (e) => {
              e.preventDefault();
              const r = await action(
                () => api("/admin/directory", "PUT", config),
                "AD ayarları kaydedildi.",
              );
              if (r) {
                setOpen(false);
                load();
              }
            }}
          >
            <div className="form-grid">
              <label>
                AD sunucusu
                <input
                  value={config.host}
                  onChange={(e) => update("host", e.target.value)}
                  placeholder="ad.kurum.local"
                />
              </label>
              <label>
                Port
                <input
                  type="number"
                  value={config.port}
                  min={1}
                  max={65535}
                  onChange={(e) => update("port", Number(e.target.value))}
                />
              </label>
              <label>
                Şifreli bağlantı
                <select
                  value={config.transport}
                  onChange={(e) => {
                    setConfig({
                      ...config,
                      transport: e.target.value,
                      port: e.target.value === "ldaps" ? 636 : 389,
                    });
                  }}
                >
                  <option value="ldaps">LDAPS</option>
                  <option value="starttls">StartTLS</option>
                </select>
              </label>
              <label>
                Base DN
                <input
                  value={config.base_dn}
                  onChange={(e) => update("base_dn", e.target.value)}
                  placeholder="OU=Users,DC=kurum,DC=local"
                />
              </label>
            </div>
            <label>
              Servis hesabı DN
              <input
                value={config.bind_dn}
                onChange={(e) => update("bind_dn", e.target.value)}
                placeholder="CN=svc-aptilume,OU=Services,DC=kurum,DC=local"
              />
            </label>
            <label>
              Servis hesabı parolası{" "}
              {config.has_secret && (
                <small>· Kayıtlı; boş bırakırsanız korunur</small>
              )}
              <input
                type="password"
                autoComplete="new-password"
                value={config.password}
                onChange={(e) => update("password", e.target.value)}
              />
            </label>
            <label>
              Kurumsal CA dosyası
              <input
                value={config.ca_file}
                onChange={(e) => update("ca_file", e.target.value)}
                placeholder="/etc/certs/kurum-ca.pem"
              />
            </label>
            <div className="form-grid">
              {[
                ["username_attribute", "Kullanıcı adı alanı"],
                ["guid_attribute", "Kalıcı kimlik alanı"],
                ["manager_attribute", "Yönetici alanı"],
                ["department_attribute", "Ekip / departman alanı"],
              ].map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    value={config[key]}
                    onChange={(e) => update(key, e.target.value)}
                  />
                </label>
              ))}
            </div>
            <h3>Yetki grupları</h3>
            <p className="muted">
              Her satıra bir grup DN yazın. İnsan kaynakları tüm kapsamı,
              entegrasyon yöneticileri yalnızca ayarları görür. Diğer
              yöneticilerin çalışan kapsamı AD manager ilişkisinden belirlenir.
            </p>
            {[
              ["hr", "İnsan kaynakları"],
              ["admin", "Entegrasyon yöneticileri"],
              ["manager", "Ekip yöneticileri"],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <textarea
                  rows={2}
                  value={(config.role_groups[key] || []).join("\n")}
                  onChange={(e) =>
                    update("role_groups", {
                      ...config.role_groups,
                      [key]: e.target.value.split("\n").filter(Boolean),
                    })
                  }
                  placeholder="CN=Grup,OU=Groups,DC=kurum,DC=local"
                />
              </label>
            ))}
            <label className="checkbox">
              <input
                type="checkbox"
                checked={config.nested_groups}
                onChange={(e) => update("nested_groups", e.target.checked)}
              />
              İç içe AD gruplarını çözümle
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={config.include_descendants}
                onChange={(e) =>
                  update("include_descendants", e.target.checked)
                }
              />
              Yöneticilere alt yönetici ekiplerini de dahil et
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => update("enabled", e.target.checked)}
              />
              Active Directory girişini etkinleştir
            </label>
            <Button disabled={busy}>Ayarları kaydet</Button>
          </form>
        </Modal>
      )}
    </section>
  );
}

export function ActionEditor({ draft, boot, user, action, onClose }: any) {
  const [item, setItem] = useState({ ...draft }),
    [skills, setSkills] = useState<any[]>([]);
  useEffect(() => {
    api("/skills").then(setSkills);
  }, []);
  const update = (key: string, value: any) =>
    setItem({ ...item, [key]: value });
  return (
    <Modal
      title={item.id ? "Gelişim planını düzenle" : "Gelişim planı oluştur"}
      onClose={onClose}
    >
      <form
        className="modal-body"
        onSubmit={async (e) => {
          e.preventDefault();
          const payload = {
            ...item,
            publication_id: item.publication_id || null,
            team_id: item.team_id || null,
            participant_id: item.participant_id || null,
            skill_id: item.skill_id || null,
            due_date: item.due_date || null,
          };
          if (
            await action(
              () =>
                api(
                  item.id
                    ? "/development-actions/" + item.id
                    : "/development-actions",
                  item.id ? "PATCH" : "POST",
                  payload,
                ),
              "Gelişim planı kaydedildi.",
            )
          )
            onClose();
        }}
      >
        <label>
          Plan başlığı
          <input
            required
            minLength={3}
            value={item.title}
            onChange={(e) => update("title", e.target.value)}
          />
        </label>
        <div className="form-grid">
          <label>
            Ekip
            <select
              value={item.team_id || ""}
              onChange={(e) =>
                setItem({
                  ...item,
                  team_id: e.target.value,
                  participant_id: "",
                })
              }
            >
              <option value="">Tüm kapsam / katılımcı bazlı</option>
              {boot.teams.map((t: any) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Katılımcı
            <select
              value={item.participant_id || ""}
              onChange={(e) => {
                const p = boot.participants.find(
                  (x: any) => x.id === e.target.value,
                );
                setItem({
                  ...item,
                  participant_id: e.target.value,
                  team_id: p?.team_id || item.team_id,
                });
              }}
            >
              <option value="">Ekip için ortak plan</option>
              {boot.participants
                .filter((p: any) => !item.team_id || p.team_id === item.team_id)
                .map((p: any) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Yetkinlik
            <select
              value={item.skill_id || ""}
              onChange={(e) => update("skill_id", e.target.value)}
            >
              <option value="">Genel gelişim</option>
              {skills.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sorumlu
            <input
              required
              minLength={2}
              value={item.owner_name}
              onChange={(e) => update("owner_name", e.target.value)}
            />
          </label>
          <label>
            Hedef tarih
            <input
              type="date"
              value={item.due_date || ""}
              onChange={(e) => update("due_date", e.target.value)}
            />
          </label>
          <label>
            Durum
            <select
              value={item.status}
              onChange={(e) => update("status", e.target.value)}
            >
              {Object.entries(actionLabels).map(([key, label]) => (
                <option key={key} value={key}>
                  {String(label)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Çalışma ve takip notları
          <textarea
            rows={4}
            value={item.notes}
            onChange={(e) => update("notes", e.target.value)}
          />
        </label>
        <Button>{item.id ? "Değişiklikleri kaydet" : "Planı oluştur"}</Button>
      </form>
    </Modal>
  );
}

export function DevelopmentPlans({ boot, user, action, onEdit }: any) {
  const [items, setItems] = useState<any[]>([]),
    [status, setStatus] = useState("");
  const load = () => api("/development-actions").then(setItems);
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);
  return (
    <>
      <div className="section-toolbar">
        <div className="filter-field">
          <select
            aria-label="Plan durumu"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">Tüm durumlar</option>
            {Object.entries(actionLabels).map(([key, label]) => (
              <option key={key} value={key}>
                {String(label)}
              </option>
            ))}
          </select>
        </div>
        <Button
          onClick={() =>
            onEdit({
              title: "",
              owner_name: user.display_name,
              team_id: "",
              participant_id: "",
              skill_id: "",
              due_date: "",
              notes: "",
              status: "planned",
            })
          }
        >
          <Plus size={16} />
          Gelişim planı oluştur
        </Button>
      </div>
      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>Plan</th>
              <th>Kapsam</th>
              <th>Sorumlu</th>
              <th>Hedef tarih</th>
              <th>Durum</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items
              .filter((x) => !status || x.status === status)
              .map((x) => (
                <tr key={x.id}>
                  <td>
                    <b>{x.title}</b>
                  </td>
                  <td>
                    {boot.participants.find(
                      (p: any) => p.id === x.participant_id,
                    )?.name ||
                      boot.teams.find((t: any) => t.id === x.team_id)?.name ||
                      "Kurum geneli"}
                  </td>
                  <td>{x.owner_name}</td>
                  <td>
                    {x.due_date
                      ? new Date(x.due_date + "T12:00:00").toLocaleDateString(
                          "tr-TR",
                        )
                      : "—"}
                  </td>
                  <td>
                    <span
                      className={
                        "badge " + (x.status === "completed" ? "done" : "")
                      }
                    >
                      {actionLabels[x.status]}
                    </span>
                  </td>
                  <td>
                    <button className="text-btn" onClick={() => onEdit(x)}>
                      Düzenle
                      <ArrowRight size={13} />
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        {!items.length && (
          <div className="empty">
            <h3>Henüz gelişim planı yok</h3>
            <p>
              Yetkinlik sonuçlarından veya bu ekrandan ilk aksiyonu
              oluşturabilirsiniz.
            </p>
          </div>
        )}
      </section>
    </>
  );
}

export function Comparison({ report, onClose, onPerson }: any) {
  const [q, setQ] = useState("");
  const rows = report.rows.filter((x: any) =>
    (x.name + " " + x.skill_name)
      .toLocaleLowerCase("tr")
      .includes(q.toLocaleLowerCase("tr")),
  );
  return (
    <Modal title="Öz beyan ve yazılı değerlendirme" onClose={onClose}>
      <div className="modal-body">
        <div className="search">
          <Search size={16} />
          <input
            aria-label="Karşılaştırmada ara"
            placeholder="Çalışan veya yetkinlik ara…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <p className="muted">
          Yazılı puan 0–100 ölçeğindedir. Öz beyan ve seviye önerisi ayrı
          göstergelerdir.
        </p>
        <table>
          <thead>
            <tr>
              <th>Çalışan / yetkinlik</th>
              <th>Öz beyan</th>
              <th>Yazılı puan</th>
              <th>Anket önerisi</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any) => (
              <tr key={r.assignment_id + r.skill_id}>
                <td>
                  <b>{r.name}</b>
                  <small className="cell-subtitle">{r.skill_name}</small>
                </td>
                <td>{r.self_level ? "L" + r.self_level : "—"}</td>
                <td>{fmt(r.written_score)}</td>
                <td>
                  {r.suggested_level ? "L" + r.suggested_level : "Ölçülmedi"}
                </td>
                <td>
                  <button className="text-btn" onClick={() => onPerson(r)}>
                    Profili aç
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}

export function PersonalProfile({ user, onSurvey }: any) {
  const [profile, setProfile] = useState<any>(null),
    [results, setResults] = useState<any[]>([]),
    [plans, setPlans] = useState<any[]>([]),
    [info, setInfo] = useState<any>(null);
  useEffect(() => {
    api("/me/profile").then(setProfile);
    api("/me/results").then(setResults);
    api("/development-actions").then(setPlans);
  }, [user.id]);
  return (
    <>
      <section className="panel profile-card">
        <div className="profile-portrait">
          <UserRound size={30} />
        </div>
        <div>
          <h2>{user.display_name}</h2>
          <p>
            {profile?.participant?.title || "Rol eşlemesi bekleniyor"} ·{" "}
            {profile?.team?.name || "Ekip eşlemesi bekleniyor"}
          </p>
          <small>{user.email}</small>
        </div>
        <Button secondary onClick={onSurvey}>
          Anketlerime git
          <ArrowRight size={15} />
        </Button>
      </section>
      {results.map((r) => (
        <section className="panel profile-results" key={r.publication_id}>
          <div className="panel-head">
            <div>
              <h2>{r.campaign_name}</h2>
              <p>
                {new Date(r.published_at).toLocaleDateString("tr-TR")} tarihli
                değerlendirme
              </p>
            </div>
            <button className="text-btn" onClick={() => setInfo(r)}>
              <Info size={14} />
              Rapor bilgileri
            </button>
          </div>
          <table>
            <thead>
              <tr>
                <th>Yetkinlik</th>
                <th>Yazılı puan</th>
                <th>Öz beyan</th>
                <th>Anket önerisi</th>
                <th>Hedef</th>
              </tr>
            </thead>
            <tbody>
              {r.rows.map((x: any) => (
                <tr key={x.skill_id}>
                  <td>{x.skill_name}</td>
                  <td>{fmt(x.written_score)}</td>
                  <td>{x.self_level ? "L" + x.self_level : "—"}</td>
                  <td>
                    {x.suggested_level ? "L" + x.suggested_level : "Ölçülmedi"}
                  </td>
                  <td>L{x.target_level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {!results.length && (
        <div className="empty">
          <h3>Henüz yayımlanmış değerlendirmeniz yok</h3>
          <p>
            Atanmış anketlerinizi doldurduktan sonra sonuçlar bu ekranda yer
            alacak.
          </p>
        </div>
      )}
      {plans.filter((p) => p.participant_id === user.participant_id).length >
        0 && (
        <section className="panel">
          <div className="panel-head">
            <h2>Gelişim planlarım</h2>
          </div>
          {plans
            .filter((p) => p.participant_id === user.participant_id)
            .map((p) => (
              <div className="personal-plan" key={p.id}>
                <b>{p.title}</b>
                <span>{actionLabels[p.status]}</span>
                <p>{p.notes}</p>
              </div>
            ))}
        </section>
      )}
      {info && (
        <Modal title="Rapor bilgileri" onClose={() => setInfo(null)}>
          <div className="modal-body">
            <dl className="report-info">
              <dt>Kaynak</dt>
              <dd>
                {info.source === "simulation"
                  ? "Geliştirme simülasyonu"
                  : "LLM rubrik değerlendirmesi"}
              </dd>
              <dt>Sürüm</dt>
              <dd>{info.version}</dd>
              <dt>Yayın tarihi</dt>
              <dd>{new Date(info.published_at).toLocaleString("tr-TR")}</dd>
            </dl>
            <p className="muted">
              Yazılı puan, öz beyan ve seviye önerisi ayrı göstergelerdir. Bu
              form L4/L5 seviyesini doğrulamaz.
            </p>
          </div>
        </Modal>
      )}
    </>
  );
}
