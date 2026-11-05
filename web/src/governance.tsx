import { t, translateNode, formatLocale } from "./i18n";
import React, { useEffect, useState, useRef } from "react";
import {
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  History,
  LoaderCircle,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { api } from "./client";
import { Button, Modal } from "./ui";
type Any = any;
export const qualityLabels: Any = {
  nonsensical: "Anlamlı içerik bulunamadı",
  off_topic: "Soruyla ilgisiz yanıt",
  insufficient_content: "Değerlendirme için yetersiz içerik",
  instruction_attempt: "Talimat yönlendirme içeren yanıt",
};
const when = (s: string) => new Date(s).toLocaleString(formatLocale());
export function PolicyEditor({ action }: Any) {
  const [data, setData] = useState<Any>(null),
    [draft, setDraft] = useState<Any>(null),
    [historical, setHistorical] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    try {
      const d = await api("/prompt-policies");
      setData(d);
      setDraft(d.active.instructions);
      setHistorical("");
      setError("");
    } catch (e: Any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    load();
  }, []);
  const changed =
    data && JSON.stringify(draft) !== JSON.stringify(data.active.instructions);
  if (!data)
    return (
      <div className="analytics-loading">
        {translateNode(
          error || (
            <>
              <LoaderCircle className="spin" />
              {t(" Politika y\u00FCkleniyor\u2026 ")}
            </>
          ),
        )}
      </div>
    );
  const fields = [
    [
      "questions",
      "Soru üretimi",
      "Ekip bağlamı, rol/kademe ve hedeflere göre soru ve rubrik üretimi.",
    ],
    [
      "grade",
      "Yanıt değerlendirme ve kalite kontrolü",
      "Dönem kapandıktan sonra kanıt, rubrik puanı ve yanıt kalitesi sınıflandırması.",
    ],
    [
      "insights",
      "Sonuç özeti ve gelişim önerileri",
      "Hesaplanan metriklerden üretilen dönem özeti.",
    ],
  ];
  return (
    <div className="governance-policy">
      <div className="notice">
        <ShieldCheck size={20} />
        <span>
          {t(
            " Bu talimatlar\u0131 yaln\u0131z \u0130K d\u00FCzenler. De\u011Fi\u015Fiklikler yeni i\u015Flere uygulan\u0131r; ba\u015Flam\u0131\u015F i\u015Fler, mevcut formlar ve ge\u00E7mi\u015F sonu\u00E7lar kendi s\u00FCr\u00FCm\u00FCn\u00FC korur. Veri eri\u015Fimi, zorunlu JSON \u015Femas\u0131 ve \u0130K inceleme kurallar\u0131 talimatlarla de\u011Fi\u015Ftirilemez. ",
          )}
        </span>
      </div>
      {translateNode(
        error && (
          <div className="notice error" role="alert">
            {translateNode(error)}
          </div>
        ),
      )}
      <section className="panel policy-toolbar">
        <div>
          <b>
            {t("Aktif politika \u00B7 v")}
            {translateNode(data.active.version)}
          </b>
          <small>
            {translateNode(when(data.active.created_at))}
            {t(" \u00B7")}
            {translateNode(" ")}
            {translateNode(
              data.active.created_by === "system"
                ? "Varsayılan kurum politikası"
                : "İK tarafından kaydedildi",
            )}
          </small>
        </div>
        <div className="policy-controls">
          <label>
            <History size={15} />
            <select
              aria-label={t("Ge\u00E7mi\u015F politika s\u00FCr\u00FCm\u00FC")}
              value={historical}
              onChange={async (e) => {
                const id = e.target.value;
                setHistorical(id);
                if (id) {
                  try {
                    const p = await api(`/prompt-policies/${id}`);
                    setDraft(p.instructions);
                  } catch (e: Any) {
                    setError(e.message);
                  }
                }
              }}
            >
              <option value="">
                {t(
                  "Ge\u00E7mi\u015F s\u00FCr\u00FCm\u00FC tasla\u011Fa al\u2026",
                )}
              </option>
              {translateNode(
                data.history.map((p: Any) => (
                  <option key={p.id} value={p.id}>
                    {t(" v")}
                    {translateNode(p.version)}
                    {t(" \u00B7 ")}
                    {translateNode(when(p.created_at))}
                  </option>
                )),
              )}
            </select>
          </label>
          <Button secondary onClick={() => setDraft({ ...data.defaults })}>
            <RotateCcw size={15} />
            {t(" Varsay\u0131lanlar\u0131 tasla\u011Fa al ")}
          </Button>
        </div>
      </section>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            const result = await action(
              () =>
                api("/prompt-policies", "POST", {
                  expected_version: data.active.version,
                  instructions: draft,
                }),
              "Yeni ölçüm politikası etkinleştirildi.",
            );
            if (result) await load();
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="policy-fields">
          {translateNode(
            fields.map(([key, title, description]) => (
              <section className="panel policy-field" key={key}>
                <div className="panel-head">
                  <div>
                    <h2>{translateNode(title)}</h2>
                    <p>{translateNode(description)}</p>
                  </div>
                  <FileText size={18} />
                </div>
                <label className="policy-instructions">
                  {t(" System instruction ")}
                  <textarea
                    aria-label={t(`${title} talimatı`)}
                    required
                    minLength={30}
                    maxLength={5000}
                    value={draft[key]}
                    onChange={(e) =>
                      setDraft({ ...draft, [key]: e.target.value })
                    }
                  />
                </label>
                <div className="policy-field-count">
                  {translateNode(
                    draft[key].length.toLocaleString(formatLocale()),
                  )}
                  {t(" / 5.000 karakter ")}
                </div>
              </section>
            )),
          )}
        </div>
        <div className="policy-save">
          <span>
            {translateNode(
              changed
                ? "Kaydedilmemiş talimat değişiklikleri var."
                : "Aktif sürümü görüntülüyorsunuz.",
            )}
          </span>
          <Button secondary type="button" onClick={load} disabled={busy}>
            {t(" Aktif s\u00FCr\u00FCm\u00FC y\u00FCkle ")}
          </Button>
          <Button disabled={!changed || busy}>
            {translateNode(
              busy ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <Check size={16} />
              ),
            )}
            {t(" Yeni s\u00FCr\u00FCm olarak kaydet ")}
          </Button>
        </div>
      </form>
    </div>
  );
}
export function QualityInbox({ boot, action }: Any) {
  const [data, setData] = useState<Any>(null),
    [status, setStatus] = useState("pending"),
    [team, setTeam] = useState(""),
    [campaign, setCampaign] = useState(""),
    [offset, setOffset] = useState(0),
    [detail, setDetail] = useState<Any>(null),
    [score, setScore] = useState(""),
    [reason, setReason] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const request = useRef(0);
  const query = new URLSearchParams({
    status,
    team_id: team,
    campaign_id: campaign,
    offset: String(offset),
  }).toString();
  const load = async () => {
    const sequence = ++request.current;
    try {
      const params = new URLSearchParams({
        status,
        limit: "25",
        offset: String(offset),
      });
      if (team) params.set("team_id", team);
      if (campaign) params.set("campaign_id", campaign);
      const result = await api(`/quality-cases?${params}`);
      if (sequence === request.current) {
        setData({ ...result, _query: query });
        setError("");
      }
    } catch (e: Any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => {
      clearInterval(timer);
      request.current++;
    };
  }, [status, team, campaign, offset]);
  if (!data || data._query !== query)
    return (
      <div className="analytics-loading">
        {translateNode(
          error || (
            <>
              <LoaderCircle className="spin" />
              {t(" \u0130K inceleme kuyru\u011Fu y\u00FCkleniyor\u2026 ")}
            </>
          ),
        )}
      </div>
    );
  return (
    <>
      <div className="notice">
        <ShieldCheck size={20} />
        <span>
          {t(
            " Etiketler yan\u0131t d\u00FCzeyinde \u00F6n inceleme i\u015Faretidir; ki\u015Fi hakk\u0131nda bir h\u00FCk\u00FCm de\u011Fildir. Kalite sorunu olan yan\u0131t otomatik puanlanmaz. \u0130K gerek\u00E7eli puan karar\u0131 verene kadar ilgili de\u011Ferlendirme yay\u0131mlanamaz. ",
          )}
        </span>
      </div>
      <div className="metrics-grid quality-summary">
        {translateNode(
          [
            ["İK incelemesi bekliyor", data.summary.pending],
            ["Karar verildi", data.summary.resolved],
            ["İncelenen yanıtların sahipleri", data.summary.people],
          ].map(([name, value]) => (
            <section className="metric-card" key={name}>
              <div className="metric-top">
                <span>{translateNode(name)}</span>
              </div>
              <strong>{translateNode(value)}</strong>
            </section>
          )),
        )}
      </div>
      <section className="panel quality-panel">
        <div className="quality-filters">
          <label>
            {t(" \u0130nceleme durumu ")}
            <select
              aria-label={t("Kalite inceleme durumu")}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setOffset(0);
              }}
            >
              <option value="pending">{t("\u0130nceleme bekliyor")}</option>
              <option value="resolved">{t("Karar verildi")}</option>
              <option value="all">{t("T\u00FCm\u00FC")}</option>
            </select>
          </label>
          <label>
            {t(" Ekip ")}
            <select
              aria-label={t("Kalite ekip filtresi")}
              value={team}
              onChange={(e) => {
                setTeam(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">{t("T\u00FCm ekipler")}</option>
              {translateNode(
                boot.teams.map((t: Any) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                )),
              )}
            </select>
          </label>
          <label>
            {t(" \u00D6l\u00E7\u00FCm d\u00F6nemi ")}
            <select
              aria-label={t("Kalite d\u00F6nem filtresi")}
              value={campaign}
              onChange={(e) => {
                setCampaign(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">{t("T\u00FCm d\u00F6nemler")}</option>
              {translateNode(
                boot.campaigns.map((c: Any) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                )),
              )}
            </select>
          </label>
          <Button secondary onClick={load}>
            {t(" Yenile ")}
          </Button>
        </div>
        {translateNode(
          error && (
            <div className="notice error" role="alert">
              {translateNode(error)}
            </div>
          ),
        )}
        <div className="analytics-table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("\u00C7al\u0131\u015Fan / ekip")}</th>
                <th>{t("Etiket")}</th>
                <th>{t("Soru / d\u00F6nem")}</th>
                <th>{t("Durum")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {translateNode(
                data.items.map((item: Any) => (
                  <tr key={item.id}>
                    <td>
                      <b>{item.name}</b>
                      <small className="analytics-cell-note">
                        {translateNode(item.team_name)}
                      </small>
                    </td>
                    <td>
                      {translateNode(
                        qualityLabels[item.category] || item.category,
                      )}
                      <small className="analytics-cell-note">
                        {translateNode(when(item.created_at))}
                      </small>
                    </td>
                    <td className="quality-question">
                      {translateNode(item.question)}
                      <small className="analytics-cell-note">
                        {translateNode(item.campaign_name)}
                      </small>
                    </td>
                    <td>
                      {translateNode(
                        item.review_status === "pending"
                          ? "İK incelemesi bekliyor"
                          : "Karar verildi",
                      )}
                    </td>
                    <td>
                      <button
                        className="text-btn"
                        onClick={async () => {
                          try {
                            setDetail(await api(`/quality-cases/${item.id}`));
                            setScore("");
                            setReason("");
                          } catch (e: Any) {
                            setError(e.message);
                          }
                        }}
                      >
                        {t(" \u0130ncele ")}
                        <ArrowUpRight size={15} />
                      </button>
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
        {translateNode(
          !data.items.length && (
            <div className="analytics-empty">
              {t(
                " Se\u00E7ili kapsamda yan\u0131t kalitesi inceleme kayd\u0131 yok. ",
              )}
            </div>
          ),
        )}
        <div className="analytics-pagination">
          <span>
            {translateNode(data.total)}
            {t(" kay\u0131t")}
          </span>
          <button
            className="icon-btn"
            aria-label={t("\u00D6nceki kalite sayfas\u0131")}
            disabled={!offset}
            onClick={() => setOffset((n) => Math.max(0, n - 25))}
          >
            <ChevronLeft size={16} />
          </button>
          <button
            className="icon-btn"
            aria-label={t("Sonraki kalite sayfas\u0131")}
            disabled={offset + 25 >= data.total}
            onClick={() => setOffset((n) => n + 25)}
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </section>
      {translateNode(
        detail && (
          <Modal
            title={t("\u0130K yan\u0131t kalitesi incelemesi")}
            onClose={() => setDetail(null)}
          >
            <div className="modal-body quality-review">
              <p className="muted">
                {detail.name}
                {t(" \u00B7 ")}
                {translateNode(detail.team_name)}
                {t(" \u00B7 ")}
                {translateNode(detail.campaign_name)}
              </p>
              <h3>{translateNode(detail.question)}</h3>
              <blockquote>{detail.answer}</blockquote>
              <div className="notice">
                <span>
                  <b>
                    {translateNode(
                      qualityLabels[detail.category] || detail.category,
                    )}
                  </b>
                  <br />
                  {detail.reason}
                </span>
              </div>
              <p className="muted">
                {t(" Kontrol t\u00FCr\u00FC:")}
                {translateNode(" ")}
                {translateNode(
                  detail.source === "rule"
                    ? "Temel içerik kuralı"
                    : detail.source === "mock"
                      ? "Demo model incelemesi"
                      : "LLM incelemesi",
                )}
                {translateNode(" ")}
                {t(" \u00B7 ")}
                {translateNode(detail.pass_no)}
                {t(". de\u011Ferlendirme ge\u00E7i\u015Fi ")}
              </p>
              {translateNode(
                detail.evidence_quotes?.length > 0 && (
                  <div>
                    <h3>
                      {t("Yan\u0131ttan i\u015Faretlenen al\u0131nt\u0131lar")}
                    </h3>
                    {translateNode(
                      detail.evidence_quotes.map((q: string, i: number) => (
                        <blockquote key={i}>{translateNode(q)}</blockquote>
                      )),
                    )}
                  </div>
                ),
              )}
              {translateNode(
                detail.self_review && (
                  <div className="notice">
                    {t(
                      " Kendi yan\u0131t\u0131n\u0131z i\u00E7in puan karar\u0131 veremezsiniz. Ba\u015Fka bir \u0130K yetkilisi incelemeli. ",
                    )}
                  </div>
                ),
              )}
              {translateNode(
                detail.decision && (
                  <section className="notice">
                    <span>
                      <b>
                        {t("\u0130K puan karar\u0131: ")}
                        {translateNode(detail.decision.score)}
                        {t(" / 100")}
                      </b>
                      <br />
                      {detail.decision.reason}
                      <br />
                      {translateNode(when(detail.decision.created_at))}
                    </span>
                  </section>
                ),
              )}
              {translateNode(
                detail.can_review ? (
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      setBusy(true);
                      try {
                        const result = await action(
                          () =>
                            api(
                              `/reviews/${detail.evaluation_id}/decision`,
                              "POST",
                              { score: Number(score), reason },
                            ),
                          "İK kalite incelemesi kaydedildi.",
                        );
                        if (result) {
                          setDetail(null);
                          await load();
                        }
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    <label>
                      {t(" \u0130K puan karar\u0131 (0\u2013100) ")}
                      <input
                        aria-label={t("\u0130K kalite puan\u0131")}
                        required
                        type="number"
                        min={0}
                        max={100}
                        step="0.1"
                        value={score}
                        onChange={(e) => setScore(e.target.value)}
                      />
                    </label>
                    <label>
                      {t(" Karar\u0131n gerek\u00E7esi ")}
                      <textarea
                        aria-label={t("\u0130K kalite karar gerek\u00E7esi")}
                        required
                        minLength={5}
                        maxLength={2000}
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                      />
                    </label>
                    <Button
                      disabled={
                        busy || score === "" || reason.trim().length < 5
                      }
                    >
                      {translateNode(
                        busy ? (
                          <LoaderCircle className="spin" size={16} />
                        ) : (
                          <Check size={16} />
                        ),
                      )}
                      {t(" \u0130K karar\u0131n\u0131 kaydet ")}
                    </Button>
                  </form>
                ) : (
                  <p className="muted">
                    {t(
                      " Bu kay\u0131t i\u00E7in yeni karar verilemiyor. Ge\u00E7mi\u015F kararlar de\u011Ferlendirme kayd\u0131nda saklan\u0131r. ",
                    )}
                  </p>
                ),
              )}
            </div>
          </Modal>
        ),
      )}
    </>
  );
}
