import { t, translateNode, formatLocale } from "./i18n";
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
    : Number(x).toLocaleString(formatLocale(), { maximumFractionDigits: 1 });
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
    <Modal title={t("Hesap bilgilerim")} onClose={onClose}>
      <div className="modal-body">
        <dl className="report-info">
          <dt>{t("Ad")}</dt>
          <dd>{user.display_name}</dd>
          <dt>{t("Kullan\u0131c\u0131 ad\u0131")}</dt>
          <dd>{translateNode(user.username)}</dd>
          <dt>{t("E-posta")}</dt>
          <dd>{translateNode(user.email || "—")}</dd>
          <dt>{t("Yetki")}</dt>
          <dd>
            {translateNode(
              user.roles
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
                .join(", "),
            )}
          </dd>
        </dl>
        {translateNode(
          user.permissions.integrations && (
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
                {t(" \u00C7al\u0131\u015Fma alan\u0131 ad\u0131 ")}
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <Button secondary>
                {t("\u00C7al\u0131\u015Fma alan\u0131n\u0131 kaydet")}
              </Button>
            </form>
          ),
        )}
        {translateNode(
          user.can_change_password && (
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
              {translateNode(
                user.temporary_password && (
                  <div className="notice">
                    {t(
                      " \u0130lk kurulum hesab\u0131 kullan\u0131l\u0131yor. \u00DCretim kullan\u0131m\u0131ndan \u00F6nce g\u00FC\u00E7l\u00FC bir parola belirleyin. ",
                    )}
                  </div>
                ),
              )}
              <h3>{t("Parolam\u0131 de\u011Fi\u015Ftir")}</h3>
              <label>
                {t(" Mevcut parola ")}
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                />
              </label>
              <label>
                {t(" Yeni parola ")}
                <input
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={15}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <Button secondary>{t("Parolay\u0131 g\u00FCncelle")}</Button>
            </form>
          ),
        )}
      </div>
    </Modal>
  );
}
export function DirectorySettings({ action, busy }: any) {
  const [config, setConfig] = useState<any>(null),
    [open, setOpen] = useState(false),
    [result, setResult] = useState<any>(null),
    [review, setReview] = useState(false);
  const load = () =>
    api("/admin/directory").then((c) => setConfig({ ...c, password: "" }));
  useEffect(() => {
    load();
  }, []);
  if (!config)
    return (
      <div className="notice">
        <LoaderCircle className="spin" size={16} />
        {t(" Kurumsal dizin ayarlar\u0131 y\u00FCkleniyor. ")}
      </div>
    );
  const update = (key: string, value: any) =>
    setConfig({ ...config, [key]: value });
  return (
    <section className="panel directory-panel">
      <div className="panel-head">
        <div>
          <h2>{t("Kurumsal dizin \u00B7 \u0130ste\u011Fe ba\u011Fl\u0131")}</h2>
          <p>
            {t(
              "Active Directory ba\u011Flay\u0131c\u0131s\u0131. Yerel giri\u015F bu ba\u011Flant\u0131dan ba\u011F\u0131ms\u0131zd\u0131r.",
            )}
          </p>
        </div>
        <span className={`badge ${config.enabled ? "done" : ""}`}>
          <i />
          {translateNode(config.enabled ? "Etkin" : "Yapılandırma bekleniyor")}
        </span>
      </div>
      <div className="directory-summary">
        <div>
          <span>{t("Sunucu")}</span>
          <b>{translateNode(config.host || "Henüz girilmedi")}</b>
        </div>
        <div>
          <span>{t("Y\u00F6netici ili\u015Fkisi")}</span>
          <b>{translateNode(config.manager_attribute)}</b>
        </div>
        <div>
          <span>{t("Son e\u015Fitleme")}</span>
          <b>
            {translateNode(
              config.sync_status?.last_sync
                ? new Date(config.sync_status.last_sync * 1000).toLocaleString(
                    formatLocale(),
                  )
                : "Henüz yapılmadı",
            )}
          </b>
        </div>
        <div className="directory-actions">
          <Button
            secondary
            onClick={() => {
              if (config.pending_change)
                setConfig({
                  ...config,
                  ...config.pending_change.config,
                  password: "",
                });
              setOpen(true);
            }}
          >
            {t(" Ba\u011Flant\u0131y\u0131 d\u00FCzenle ")}
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
            {t(" Test et ")}
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
            {t(" E\u015Fitle ")}
          </Button>
        </div>
      </div>
      {translateNode(
        config.approval_required && (
          <div className="notice" style={{ margin: "0 26px 20px" }}>
            {t(
              " AD de\u011Fi\u015Fiklikleriniz aktif ba\u011Flant\u0131y\u0131 de\u011Fi\u015Ftirmeden \u0130K onay\u0131na g\u00F6nderilir. ",
            )}
          </div>
        ),
      )}
      {translateNode(
        config.pending_change && (
          <div className="directory-pending">
            <div>
              <b>{t("AD de\u011Fi\u015Fikli\u011Fi onay bekliyor")}</b>
              <p>
                {t(
                  "Aktif kimlik ve yetki politikas\u0131 hen\u00FCz de\u011Fi\u015Ftirilmedi.",
                )}
              </p>
            </div>
            <Button secondary onClick={() => setReview(true)}>
              {t(" \u00D6neriyi incele ")}
            </Button>
          </div>
        ),
      )}
      {translateNode(
        result && (
          <div className="directory-result" role="status">
            <CheckCircle2 size={16} />
            {translateNode(result.message)}
          </div>
        ),
      )}
      {translateNode(
        open && (
          <Modal
            title={t("Active Directory ba\u011Flant\u0131s\u0131")}
            onClose={() => {
              setOpen(false);
              load();
            }}
          >
            <form
              className="modal-body"
              onSubmit={async (e) => {
                e.preventDefault();
                const r = await action(() =>
                  api("/admin/directory", "PUT", config),
                );
                if (r) {
                  setResult({
                    status: "success",
                    message:
                      r.status === "pending_approval"
                        ? "Değişiklik İK onayına gönderildi. Aktif ayarlar korundu."
                        : "AD ayarları uygulandı.",
                  });
                  setOpen(false);
                  load();
                }
              }}
            >
              <div className="form-grid">
                <label>
                  {t(" AD sunucusu ")}
                  <input
                    value={config.host}
                    onChange={(e) => update("host", e.target.value)}
                    placeholder={t("ad.kurum.local")}
                  />
                </label>
                <label>
                  {t(" Port ")}
                  <input
                    type="number"
                    value={config.port}
                    min={1}
                    max={65535}
                    onChange={(e) => update("port", Number(e.target.value))}
                  />
                </label>
                <label>
                  {t(" \u015Eifreli ba\u011Flant\u0131 ")}
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
                    <option value="ldaps">{t("LDAPS")}</option>
                    <option value="starttls">{t("StartTLS")}</option>
                  </select>
                </label>
                <label>
                  {t(" Base DN ")}
                  <input
                    value={config.base_dn}
                    onChange={(e) => update("base_dn", e.target.value)}
                    placeholder={t("OU=Users,DC=kurum,DC=local")}
                  />
                </label>
              </div>
              <label>
                {t(" Servis hesab\u0131 DN ")}
                <input
                  value={config.bind_dn}
                  onChange={(e) => update("bind_dn", e.target.value)}
                  placeholder={t(
                    "CN=svc-aptilume,OU=Services,DC=kurum,DC=local",
                  )}
                />
              </label>
              <label>
                {t(" Servis hesab\u0131 parolas\u0131")}
                {translateNode(" ")}
                {translateNode(
                  config.has_secret && (
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
                  value={config.password}
                  onChange={(e) => update("password", e.target.value)}
                />
              </label>
              <label>
                {t(" Kurumsal CA dosyas\u0131 ")}
                <input
                  value={config.ca_file}
                  onChange={(e) => update("ca_file", e.target.value)}
                  placeholder={t("/etc/certs/kurum-ca.pem")}
                />
              </label>
              <div className="form-grid">
                {translateNode(
                  [
                    ["username_attribute", "Kullanıcı adı alanı"],
                    ["guid_attribute", "Kalıcı kimlik alanı"],
                    ["manager_attribute", "Yönetici alanı"],
                    ["department_attribute", "Ekip / departman alanı"],
                  ].map(([key, label]) => (
                    <label key={key}>
                      {translateNode(label)}
                      <input
                        value={config[key]}
                        onChange={(e) => update(key, e.target.value)}
                      />
                    </label>
                  )),
                )}
              </div>
              <h3>{t("Yetki gruplar\u0131")}</h3>
              <p className="muted">
                {t(
                  " Her sat\u0131ra bir grup DN yaz\u0131n. \u0130nsan kaynaklar\u0131 t\u00FCm kapsam\u0131, entegrasyon y\u00F6neticileri yaln\u0131zca ayarlar\u0131 g\u00F6r\u00FCr. Di\u011Fer y\u00F6neticilerin \u00E7al\u0131\u015Fan kapsam\u0131 AD manager ili\u015Fkisinden belirlenir. ",
                )}
              </p>
              {translateNode(
                [
                  ["hr", "İnsan kaynakları"],
                  ["admin", "Entegrasyon yöneticileri"],
                  ["manager", "Ekip yöneticileri"],
                ].map(([key, label]) => (
                  <label key={key}>
                    {translateNode(label)}
                    <textarea
                      rows={2}
                      value={(config.role_groups[key] || []).join("\n")}
                      onChange={(e) =>
                        update("role_groups", {
                          ...config.role_groups,
                          [key]: e.target.value.split("\n").filter(Boolean),
                        })
                      }
                      placeholder={t("CN=Grup,OU=Groups,DC=kurum,DC=local")}
                    />
                  </label>
                )),
              )}
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.nested_groups}
                  onChange={(e) => update("nested_groups", e.target.checked)}
                />
                {t(
                  " \u0130\u00E7 i\u00E7e AD gruplar\u0131n\u0131 \u00E7\u00F6z\u00FCmle ",
                )}
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.include_descendants}
                  onChange={(e) =>
                    update("include_descendants", e.target.checked)
                  }
                />
                {t(
                  " Y\u00F6neticilere alt y\u00F6netici ekiplerini de dahil et ",
                )}
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={config.enabled}
                  onChange={(e) => update("enabled", e.target.checked)}
                />
                {t(" Active Directory giri\u015Fini etkinle\u015Ftir ")}
              </label>
              <Button disabled={busy}>
                {translateNode(
                  config.approval_required
                    ? "İK onayına gönder"
                    : "Ayarları kaydet",
                )}
              </Button>
            </form>
          </Modal>
        ),
      )}
      {translateNode(
        review && config.pending_change && (
          <Modal
            title={t("AD de\u011Fi\u015Fikli\u011Fi incelemesi")}
            onClose={() => setReview(false)}
          >
            <div className="modal-body">
              <p className="muted">
                {t(
                  " De\u011Fi\u015Fiklik uyguland\u0131\u011F\u0131nda kurumsal oturumlar kapat\u0131l\u0131r. Grup, kal\u0131c\u0131 kimlik ve y\u00F6netici alanlar\u0131n\u0131 kontrol edin. ",
                )}
              </p>
              <dl className="report-info">
                {translateNode(
                  Object.entries(config.pending_change.config)
                    .filter(([key]) => key !== "has_secret")
                    .map(([key, value]) => (
                      <React.Fragment key={key}>
                        <dt>
                          {translateNode(
                            (
                              {
                                host: "Sunucu",
                                port: "Port",
                                base_dn: "Base DN",
                                bind_dn: "Servis hesabı",
                                role_groups: "Rol grupları",
                                manager_attribute: "Yönetici alanı",
                                guid_attribute: "Kalıcı kimlik",
                                enabled: "Etkin",
                                transport: "TLS türü",
                              } as any
                            )[key] || key,
                          )}
                        </dt>
                        <dd className="policy-value">
                          {translateNode(
                            typeof value === "object"
                              ? JSON.stringify(value, null, 2)
                              : String(value),
                          )}
                        </dd>
                      </React.Fragment>
                    )),
                )}
                <dt>{t("Gizli de\u011Fer")}</dt>
                <dd>
                  {translateNode(
                    config.pending_change.config.has_secret
                      ? "Şifreli olarak kayıtlı"
                      : "Girilmiyor",
                  )}
                </dd>
              </dl>
              {translateNode(
                config.can_approve ? (
                  <div className="modal-actions">
                    <Button
                      secondary
                      disabled={busy}
                      onClick={async () => {
                        if (
                          await action(
                            () =>
                              api(
                                "/admin/directory/changes/" +
                                  config.pending_change.id +
                                  "/reject",
                                "POST",
                              ),
                            "Öneri reddedildi.",
                          )
                        ) {
                          setReview(false);
                          load();
                        }
                      }}
                    >
                      {t(" Reddet ")}
                    </Button>
                    <Button
                      disabled={busy}
                      onClick={async () => {
                        if (
                          await action(
                            () =>
                              api(
                                "/admin/directory/changes/" +
                                  config.pending_change.id +
                                  "/approve",
                                "POST",
                              ),
                            "AD değişikliği uygulandı. Yeniden giriş yapın.",
                          )
                        ) {
                          setReview(false);
                          load();
                        }
                      }}
                    >
                      {t(" Onayla ve uygula ")}
                    </Button>
                  </div>
                ) : (
                  <div className="notice">
                    {t(
                      " Bu de\u011Fi\u015Fikli\u011Fi \u0130K yetkisine sahip bir kullan\u0131c\u0131 uygulayabilir. ",
                    )}
                  </div>
                ),
              )}
            </div>
          </Modal>
        ),
      )}
    </section>
  );
}
export function SecurityEvents() {
  const [events, setEvents] = useState<any[]>([]),
    [error, setError] = useState("");
  const load = () =>
    api("/admin/security-events?limit=50")
      .then(setEvents)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);
  return (
    <section className="panel security-events">
      <div className="panel-head">
        <div>
          <h2>{t("G\u00FCvenlik olaylar\u0131")}</h2>
          <p>
            {t(
              "Son 50 olay \u00B7 parola, anahtar ve yan\u0131t metni kaydedilmez",
            )}
          </p>
        </div>
        <Button secondary onClick={load}>
          <RefreshCw size={15} />
          {t(" Yenile ")}
        </Button>
      </div>
      {translateNode(
        error && <div className="notice error">{translateNode(error)}</div>,
      )}
      <table>
        <thead>
          <tr>
            <th>{t("Zaman")}</th>
            <th>{t("\u0130\u015Flem")}</th>
            <th>{t("Sonu\u00E7")}</th>
            <th>{t("\u0130stek kimli\u011Fi")}</th>
          </tr>
        </thead>
        <tbody>
          {translateNode(
            events.map((e) => (
              <tr key={e.id}>
                <td>
                  {translateNode(
                    new Date(e.created_at).toLocaleString(formatLocale()),
                  )}
                </td>
                <td>
                  {translateNode(e.event)}
                  <small className="cell-subtitle">
                    {translateNode(
                      e.detail.reason || e.detail.kind || e.actor_id,
                    )}
                  </small>
                </td>
                <td>
                  {translateNode(
                    (
                      {
                        success: "Başarılı",
                        denied: "Reddedildi",
                        error: "Hata",
                      } as any
                    )[e.outcome] || e.outcome,
                  )}
                </td>
                <td>
                  <small>
                    {translateNode(e.correlation_id || "Arka plan işlemi")}
                  </small>
                </td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </section>
  );
}
export function ActionEditor({ draft, boot, user, action, onClose }: any) {
  const [item, setItem] = useState({ ...draft }),
    [skills, setSkills] = useState<any[]>([]);
  useEffect(() => {
    api("/skills?include_archived=true&compact=true").then(setSkills);
  }, []);
  const update = (key: string, value: any) =>
    setItem({ ...item, [key]: value });
  return (
    <Modal
      title={t(item.id ? "Gelişim planını düzenle" : "Gelişim planı oluştur")}
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
          {t(" Plan ba\u015Fl\u0131\u011F\u0131 ")}
          <input
            required
            minLength={3}
            value={item.title}
            onChange={(e) => update("title", e.target.value)}
          />
        </label>
        <div className="form-grid">
          <label>
            {t(" Ekip ")}
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
              <option value="">
                {t("T\u00FCm kapsam / kat\u0131l\u0131mc\u0131 bazl\u0131")}
              </option>
              {translateNode(
                boot.teams.map((t: any) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                )),
              )}
            </select>
          </label>
          <label>
            {t(" Kat\u0131l\u0131mc\u0131 ")}
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
              <option value="">{t("Ekip i\u00E7in ortak plan")}</option>
              {translateNode(
                boot.participants
                  .filter(
                    (p: any) => !item.team_id || p.team_id === item.team_id,
                  )
                  .map((p: any) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  )),
              )}
            </select>
          </label>
          <label>
            {t(" Yetkinlik ")}
            <select
              value={item.skill_id || ""}
              onChange={(e) => update("skill_id", e.target.value)}
            >
              <option value="">{t("Genel geli\u015Fim")}</option>
              {translateNode(
                skills
                  .filter((s) => !s.archived || s.id === item.skill_id)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                      {translateNode(s.archived ? " (Arşivde)" : "")}
                    </option>
                  )),
              )}
            </select>
          </label>
          <label>
            {t(" Sorumlu ")}
            <input
              required
              minLength={2}
              value={item.owner_name}
              onChange={(e) => update("owner_name", e.target.value)}
            />
          </label>
          <label>
            {t(" Hedef tarih ")}
            <input
              type="date"
              value={item.due_date || ""}
              onChange={(e) => update("due_date", e.target.value)}
            />
          </label>
          <label>
            {t(" Durum ")}
            <select
              value={item.status}
              onChange={(e) => update("status", e.target.value)}
            >
              {translateNode(
                Object.entries(actionLabels).map(([key, label]) => (
                  <option key={key} value={key}>
                    {translateNode(String(label))}
                  </option>
                )),
              )}
            </select>
          </label>
        </div>
        <label>
          {t(" \u00C7al\u0131\u015Fma ve takip notlar\u0131 ")}
          <textarea
            rows={4}
            value={item.notes}
            onChange={(e) => update("notes", e.target.value)}
          />
        </label>
        <Button>
          {translateNode(item.id ? "Değişiklikleri kaydet" : "Planı oluştur")}
        </Button>
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
            aria-label={t("Plan durumu")}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">{t("T\u00FCm durumlar")}</option>
            {translateNode(
              Object.entries(actionLabels).map(([key, label]) => (
                <option key={key} value={key}>
                  {translateNode(String(label))}
                </option>
              )),
            )}
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
          {t(" Geli\u015Fim plan\u0131 olu\u015Ftur ")}
        </Button>
      </div>
      <section className="panel">
        <table>
          <thead>
            <tr>
              <th>{t("Plan")}</th>
              <th>{t("Kapsam")}</th>
              <th>{t("Sorumlu")}</th>
              <th>{t("Hedef tarih")}</th>
              <th>{t("Durum")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {translateNode(
              items
                .filter((x) => !status || x.status === status)
                .map((x) => (
                  <tr key={x.id}>
                    <td>
                      <b>{x.title}</b>
                    </td>
                    <td>
                      {translateNode(
                        boot.participants.find(
                          (p: any) => p.id === x.participant_id,
                        )?.name ||
                          boot.teams.find((t: any) => t.id === x.team_id)
                            ?.name ||
                          "Kurum geneli",
                      )}
                    </td>
                    <td>{translateNode(x.owner_name)}</td>
                    <td>
                      {translateNode(
                        x.due_date
                          ? new Date(
                              x.due_date + "T12:00:00",
                            ).toLocaleDateString(formatLocale())
                          : "—",
                      )}
                    </td>
                    <td>
                      <span
                        className={
                          "badge " + (x.status === "completed" ? "done" : "")
                        }
                      >
                        {translateNode(actionLabels[x.status])}
                      </span>
                    </td>
                    <td>
                      <button className="text-btn" onClick={() => onEdit(x)}>
                        {t(" D\u00FCzenle ")}
                        <ArrowRight size={13} />
                      </button>
                    </td>
                  </tr>
                )),
            )}
          </tbody>
        </table>
        {translateNode(
          !items.length && (
            <div className="empty">
              <h3>{t("Hen\u00FCz geli\u015Fim plan\u0131 yok")}</h3>
              <p>
                {t(
                  " Yetkinlik sonu\u00E7lar\u0131ndan veya bu ekrandan ilk aksiyonu olu\u015Fturabilirsiniz. ",
                )}
              </p>
            </div>
          ),
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
    <Modal
      title={t("\u00D6z beyan ve yaz\u0131l\u0131 de\u011Ferlendirme")}
      onClose={onClose}
    >
      <div className="modal-body">
        <div className="search">
          <Search size={16} />
          <input
            aria-label={t("Kar\u015F\u0131la\u015Ft\u0131rmada ara")}
            placeholder={t("\u00C7al\u0131\u015Fan veya yetkinlik ara\u2026")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <p className="muted">
          {t(
            " Yaz\u0131l\u0131 puan 0\u2013100 \u00F6l\u00E7e\u011Findedir. \u00D6z beyan ve seviye \u00F6nerisi ayr\u0131 g\u00F6stergelerdir. ",
          )}
        </p>
        <table>
          <thead>
            <tr>
              <th>{t("\u00C7al\u0131\u015Fan / yetkinlik")}</th>
              <th>{t("\u00D6z beyan")}</th>
              <th>{t("Yaz\u0131l\u0131 puan")}</th>
              <th>{t("Anket \u00F6nerisi")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {translateNode(
              rows.map((r: any) => (
                <tr key={r.assignment_id + r.skill_id}>
                  <td>
                    <b>{r.name}</b>
                    <small className="cell-subtitle">
                      {translateNode(r.skill_name)}
                    </small>
                  </td>
                  <td>
                    {translateNode(r.self_level ? "L" + r.self_level : "—")}
                  </td>
                  <td>{translateNode(fmt(r.written_score))}</td>
                  <td>
                    {translateNode(
                      r.suggested_level ? "L" + r.suggested_level : "Ölçülmedi",
                    )}
                  </td>
                  <td>
                    <button className="text-btn" onClick={() => onPerson(r)}>
                      {t(" Profili a\u00E7 ")}
                    </button>
                  </td>
                </tr>
              )),
            )}
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
            {translateNode(
              profile?.participant?.title || "Rol eşlemesi bekleniyor",
            )}
            {t(" \u00B7")}
            {translateNode(" ")}
            {translateNode(profile?.team?.name || "Ekip eşlemesi bekleniyor")}
          </p>
          <small>{translateNode(user.email)}</small>
        </div>
        <Button secondary onClick={onSurvey}>
          {t(" Anketlerime git ")}
          <ArrowRight size={15} />
        </Button>
      </section>
      {translateNode(
        results.map((r) => (
          <section className="panel profile-results" key={r.publication_id}>
            <div className="panel-head">
              <div>
                <h2>{translateNode(r.campaign_name)}</h2>
                <p>
                  {translateNode(
                    new Date(r.published_at).toLocaleDateString(formatLocale()),
                  )}
                  {t(" tarihli de\u011Ferlendirme ")}
                </p>
              </div>
              <button className="text-btn" onClick={() => setInfo(r)}>
                <Info size={14} />
                {t(" Rapor bilgileri ")}
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>{t("Yetkinlik")}</th>
                  <th>{t("Yaz\u0131l\u0131 puan")}</th>
                  <th>{t("\u00D6z beyan")}</th>
                  <th>{t("Anket \u00F6nerisi")}</th>
                  <th>{t("Hedef")}</th>
                </tr>
              </thead>
              <tbody>
                {translateNode(
                  r.rows.map((x: any) => (
                    <tr key={x.skill_id}>
                      <td>{translateNode(x.skill_name)}</td>
                      <td>{translateNode(fmt(x.written_score))}</td>
                      <td>
                        {translateNode(x.self_level ? "L" + x.self_level : "—")}
                      </td>
                      <td>
                        {translateNode(
                          x.suggested_level
                            ? "L" + x.suggested_level
                            : "Ölçülmedi",
                        )}
                      </td>
                      <td>
                        {t("L")}
                        {translateNode(x.target_level)}
                      </td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </section>
        )),
      )}
      {translateNode(
        !results.length && (
          <div className="empty">
            <h3>
              {t(
                "Hen\u00FCz yay\u0131mlanm\u0131\u015F de\u011Ferlendirmeniz yok",
              )}
            </h3>
            <p>
              {t(
                " Atanm\u0131\u015F anketlerinizi doldurduktan sonra sonu\u00E7lar bu ekranda yer alacak. ",
              )}
            </p>
          </div>
        ),
      )}
      {translateNode(
        plans.filter((p) => p.participant_id === user.participant_id).length >
          0 && (
          <section className="panel">
            <div className="panel-head">
              <h2>{t("Geli\u015Fim planlar\u0131m")}</h2>
            </div>
            {translateNode(
              plans
                .filter((p) => p.participant_id === user.participant_id)
                .map((p) => (
                  <div className="personal-plan" key={p.id}>
                    <b>{p.title}</b>
                    <span>{translateNode(actionLabels[p.status])}</span>
                    <p>{p.notes}</p>
                  </div>
                )),
            )}
          </section>
        ),
      )}
      {translateNode(
        info && (
          <Modal title={t("Rapor bilgileri")} onClose={() => setInfo(null)}>
            <div className="modal-body">
              <dl className="report-info">
                <dt>{t("Kaynak")}</dt>
                <dd>
                  {translateNode(
                    info.source === "simulation"
                      ? "Geliştirme simülasyonu"
                      : "LLM rubrik değerlendirmesi",
                  )}
                </dd>
                <dt>{t("S\u00FCr\u00FCm")}</dt>
                <dd>{translateNode(info.version)}</dd>
                <dt>{t("Yay\u0131n tarihi")}</dt>
                <dd>
                  {translateNode(
                    new Date(info.published_at).toLocaleString(formatLocale()),
                  )}
                </dd>
              </dl>
              <p className="muted">
                {t(
                  " Yaz\u0131l\u0131 puan, \u00F6z beyan ve seviye \u00F6nerisi ayr\u0131 g\u00F6stergelerdir. Bu form L4/L5 seviyesini do\u011Frulamaz. ",
                )}
              </p>
            </div>
          </Modal>
        ),
      )}
    </>
  );
}
