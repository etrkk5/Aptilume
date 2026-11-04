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
const when = (s: string) => new Date(s).toLocaleString("tr-TR");

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
        {error || (
          <>
            <LoaderCircle className="spin" />
            Politika yükleniyor…
          </>
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
          Bu talimatları yalnız İK düzenler. Değişiklikler yeni işlere
          uygulanır; başlamış işler, mevcut formlar ve geçmiş sonuçlar kendi
          sürümünü korur. Veri erişimi, zorunlu JSON şeması ve İK inceleme
          kuralları talimatlarla değiştirilemez.
        </span>
      </div>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      <section className="panel policy-toolbar">
        <div>
          <b>Aktif politika · v{data.active.version}</b>
          <small>
            {when(data.active.created_at)} ·{" "}
            {data.active.created_by === "system"
              ? "Varsayılan kurum politikası"
              : "İK tarafından kaydedildi"}
          </small>
        </div>
        <div className="policy-controls">
          <label>
            <History size={15} />
            <select
              aria-label="Geçmiş politika sürümü"
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
              <option value="">Geçmiş sürümü taslağa al…</option>
              {data.history.map((p: Any) => (
                <option key={p.id} value={p.id}>
                  v{p.version} · {when(p.created_at)}
                </option>
              ))}
            </select>
          </label>
          <Button secondary onClick={() => setDraft({ ...data.defaults })}>
            <RotateCcw size={15} />
            Varsayılanları taslağa al
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
          {fields.map(([key, title, description]) => (
            <section className="panel policy-field" key={key}>
              <div className="panel-head">
                <div>
                  <h2>{title}</h2>
                  <p>{description}</p>
                </div>
                <FileText size={18} />
              </div>
              <label className="policy-instructions">
                System instruction
                <textarea
                  aria-label={`${title} talimatı`}
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
                {draft[key].length.toLocaleString("tr-TR")} / 5.000 karakter
              </div>
            </section>
          ))}
        </div>
        <div className="policy-save">
          <span>
            {changed
              ? "Kaydedilmemiş talimat değişiklikleri var."
              : "Aktif sürümü görüntülüyorsunuz."}
          </span>
          <Button secondary type="button" onClick={load} disabled={busy}>
            Aktif sürümü yükle
          </Button>
          <Button disabled={!changed || busy}>
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Check size={16} />
            )}
            Yeni sürüm olarak kaydet
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
        {error || (
          <>
            <LoaderCircle className="spin" />
            İK inceleme kuyruğu yükleniyor…
          </>
        )}
      </div>
    );
  return (
    <>
      <div className="notice">
        <ShieldCheck size={20} />
        <span>
          Etiketler yanıt düzeyinde ön inceleme işaretidir; kişi hakkında bir
          hüküm değildir. Kalite sorunu olan yanıt otomatik puanlanmaz. İK
          gerekçeli puan kararı verene kadar ilgili değerlendirme yayımlanamaz.
        </span>
      </div>
      <div className="metrics-grid quality-summary">
        {[
          ["İK incelemesi bekliyor", data.summary.pending],
          ["Karar verildi", data.summary.resolved],
          ["İncelenen yanıtların sahipleri", data.summary.people],
        ].map(([name, value]) => (
          <section className="metric-card" key={name}>
            <div className="metric-top">
              <span>{name}</span>
            </div>
            <strong>{value}</strong>
          </section>
        ))}
      </div>
      <section className="panel quality-panel">
        <div className="quality-filters">
          <label>
            İnceleme durumu
            <select
              aria-label="Kalite inceleme durumu"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setOffset(0);
              }}
            >
              <option value="pending">İnceleme bekliyor</option>
              <option value="resolved">Karar verildi</option>
              <option value="all">Tümü</option>
            </select>
          </label>
          <label>
            Ekip
            <select
              aria-label="Kalite ekip filtresi"
              value={team}
              onChange={(e) => {
                setTeam(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">Tüm ekipler</option>
              {boot.teams.map((t: Any) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Ölçüm dönemi
            <select
              aria-label="Kalite dönem filtresi"
              value={campaign}
              onChange={(e) => {
                setCampaign(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">Tüm dönemler</option>
              {boot.campaigns.map((c: Any) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <Button secondary onClick={load}>
            Yenile
          </Button>
        </div>
        {error && (
          <div className="notice error" role="alert">
            {error}
          </div>
        )}
        <div className="analytics-table-scroll">
          <table>
            <thead>
              <tr>
                <th>Çalışan / ekip</th>
                <th>Etiket</th>
                <th>Soru / dönem</th>
                <th>Durum</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: Any) => (
                <tr key={item.id}>
                  <td>
                    <b>{item.name}</b>
                    <small className="analytics-cell-note">
                      {item.team_name}
                    </small>
                  </td>
                  <td>
                    {qualityLabels[item.category] || item.category}
                    <small className="analytics-cell-note">
                      {when(item.created_at)}
                    </small>
                  </td>
                  <td className="quality-question">
                    {item.question}
                    <small className="analytics-cell-note">
                      {item.campaign_name}
                    </small>
                  </td>
                  <td>
                    {item.review_status === "pending"
                      ? "İK incelemesi bekliyor"
                      : "Karar verildi"}
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
                      İncele
                      <ArrowUpRight size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!data.items.length && (
          <div className="analytics-empty">
            Seçili kapsamda yanıt kalitesi inceleme kaydı yok.
          </div>
        )}
        <div className="analytics-pagination">
          <span>{data.total} kayıt</span>
          <button
            className="icon-btn"
            aria-label="Önceki kalite sayfası"
            disabled={!offset}
            onClick={() => setOffset((n) => Math.max(0, n - 25))}
          >
            <ChevronLeft size={16} />
          </button>
          <button
            className="icon-btn"
            aria-label="Sonraki kalite sayfası"
            disabled={offset + 25 >= data.total}
            onClick={() => setOffset((n) => n + 25)}
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </section>
      {detail && (
        <Modal
          title="İK yanıt kalitesi incelemesi"
          onClose={() => setDetail(null)}
        >
          <div className="modal-body quality-review">
            <p className="muted">
              {detail.name} · {detail.team_name} · {detail.campaign_name}
            </p>
            <h3>{detail.question}</h3>
            <blockquote>{detail.answer}</blockquote>
            <div className="notice">
              <span>
                <b>{qualityLabels[detail.category] || detail.category}</b>
                <br />
                {detail.reason}
              </span>
            </div>
            <p className="muted">
              Kontrol türü:{" "}
              {detail.source === "rule"
                ? "Temel içerik kuralı"
                : detail.source === "mock"
                  ? "Demo model incelemesi"
                  : "LLM incelemesi"}{" "}
              · {detail.pass_no}. değerlendirme geçişi
            </p>
            {detail.evidence_quotes?.length > 0 && (
              <div>
                <h3>Yanıttan işaretlenen alıntılar</h3>
                {detail.evidence_quotes.map((q: string, i: number) => (
                  <blockquote key={i}>{q}</blockquote>
                ))}
              </div>
            )}
            {detail.self_review && (
              <div className="notice">
                Kendi yanıtınız için puan kararı veremezsiniz. Başka bir İK
                yetkilisi incelemeli.
              </div>
            )}
            {detail.decision && (
              <section className="notice">
                <span>
                  <b>İK puan kararı: {detail.decision.score} / 100</b>
                  <br />
                  {detail.decision.reason}
                  <br />
                  {when(detail.decision.created_at)}
                </span>
              </section>
            )}
            {detail.can_review ? (
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
                  İK puan kararı (0–100)
                  <input
                    aria-label="İK kalite puanı"
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
                  Kararın gerekçesi
                  <textarea
                    aria-label="İK kalite karar gerekçesi"
                    required
                    minLength={5}
                    maxLength={2000}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <Button
                  disabled={busy || score === "" || reason.trim().length < 5}
                >
                  {busy ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <Check size={16} />
                  )}
                  İK kararını kaydet
                </Button>
              </form>
            ) : (
              <p className="muted">
                Bu kayıt için yeni karar verilemiyor. Geçmiş kararlar
                değerlendirme kaydında saklanır.
              </p>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}
