import { t, translateNode, formatLocale } from "./i18n";
import React, { useEffect, useState } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  ArrowLeft,
  Check,
  Send,
  Copy,
  AlertCircle,
} from "lucide-react";
import { api } from "./client";
import { Button, Modal } from "./ui";
type Any = any;
const typeLabels: Any = {
  open_text: "Açık uçlu",
  single_choice: "Tek seçim",
  self_assessment: "Öz beyan",
};
const anchors: Any = {
  "0": "Gösterge yok veya yanlış",
  "1": "Kavramı anıyor, uygulama belirsiz",
  "2": "Kısmen uygulanabilir, önemli eksik var",
  "3": "Doğru ve uygulanabilir açıklıyor",
  "4": "Sınırları ve doğrulamayı somutlaştırıyor",
};
function defaults(skill: Any, type: string) {
  return {
    rubric:
      type === "open_text"
        ? [1, 2, 3].map((level) => ({
            id: `c${level}`,
            label: `L${level} davranış göstergesi`,
            level,
            indicator_id: `${skill.id}:L${level}`,
            weight: 1,
            max_points: 4,
            descriptor:
              skill.levels.find((l: Any) => l.level === level)?.description ||
              "",
            anchors: { ...anchors },
          }))
        : [],
    options:
      type === "self_assessment"
        ? [
            ...skill.levels.map((l: Any) => ({
              id: String(l.level),
              text: `L${l.level} · ${l.label} — ${l.description}`,
              level: l.level,
              correct: false,
            })),
            {
              id: "none",
              text: "Henüz deneyimim yok",
              level: null,
              correct: false,
            },
          ]
        : type === "single_choice"
          ? ["a", "b", "c", "d"].map((id, i) => ({
              id,
              text: "",
              correct: i === 0,
              level: null,
            }))
          : [],
    reference: type === "open_text" ? skill.definition : "",
    evidence_type: "scenario_reasoning",
  };
}
export function QuestionSetEditor({ campaignId, action, onClose }: Any) {
  const [data, setData] = useState<Any>(null),
    [group, setGroup] = useState("common"),
    [draft, setDraft] = useState<Any>(null),
    [base, setBase] = useState(""),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false),
    [remove, setRemove] = useState<Any>(null),
    [leave, setLeave] = useState(false),
    [publish, setPublish] = useState(false);
  const dirty = !!draft && JSON.stringify(draft) !== base;
  async function load() {
    try {
      const value = await api(`/campaigns/${campaignId}/question-set`);
      setData(value);
      setError("");
      return value;
    } catch (e: Any) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
  }, [campaignId]);
  const close = () => {
    if (saving) return;
    if (dirty) {
      setLeave(true);
      return;
    }
    onClose();
  };
  const choose = (q: Any) => {
    const value = structuredClone(q);
    value.expected_version = data.version;
    setDraft(value);
    setBase(JSON.stringify(value));
    setError("");
  };
  const newQuestion = (copy?: Any) => {
    const skill =
      data.skills[data.groups.find((g: Any) => g.id === group).skill_ids[0]];
    const value = copy
      ? { ...structuredClone(copy), id: undefined }
      : {
          form_key: group,
          skill_id: skill.id,
          type: "open_text",
          prompt: "",
          section: group === "common" ? "common" : "role",
          ...defaults(skill, "open_text"),
        };
    value.expected_version = data.version;
    setDraft(value);
    setBase("");
    setError("");
  };
  async function mutate(task: () => Promise<Any>, message: string) {
    setSaving(true);
    setError("");
    try {
      return await action(async () => {
        try {
          return await task();
        } catch (e: Any) {
          setError(e.message);
          throw e;
        }
      }, message);
    } finally {
      setSaving(false);
    }
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    const {
      form_key,
      skill_id,
      type,
      prompt,
      rubric,
      options,
      reference,
      evidence_type,
      expected_version,
    } = draft;
    const value = {
      form_key,
      skill_id,
      type,
      prompt,
      rubric,
      options,
      reference,
      evidence_type,
      expected_version,
    };
    const result = await mutate(
      () =>
        api(
          `/campaigns/${campaignId}/questions${draft.id ? "/" + draft.id : ""}`,
          draft.id ? "PATCH" : "POST",
          value,
        ),
      "Soru taslağı kaydedildi. Yayın için İK onayı gerekiyor.",
    );
    if (result) {
      setData(result);
      setDraft(null);
      setRemove(null);
    }
  }
  async function approve(open: boolean) {
    const result = await mutate(
      async () => {
        const approved = await api(`/campaigns/${campaignId}/approve`, "POST", {
          expected_version: data.version,
        });
        if (open)
          return api(`/campaigns/${campaignId}/open`, "POST", {
            expected_version: approved.row_version,
          });
        return approved;
      },
      open
        ? "İK onaylı soru seti yayımlandı; anket yanıt toplamaya açıldı."
        : "Soru seti İK tarafından onaylandı.",
    );
    if (result) {
      setPublish(false);
      if (open) onClose();
      else await load();
    } else setPublish(false);
  }
  const issues = data?.issues || [];
  const rows = data?.questions.filter((q: Any) => q.form_key === group) || [];
  return (
    <Modal
      title={t("Soru seti \u00B7 \u0130K incelemesi")}
      wide
      onClose={close}
    >
      <div className="modal-body question-set-editor">
        {translateNode(
          error && (
            <div className="question-editor-error" role="alert">
              <AlertCircle size={18} />
              <div>
                {translateNode(error)}
                {translateNode(
                  data && (
                    <button
                      className="text-btn"
                      type="button"
                      onClick={() => {
                        setDraft(null);
                        setRemove(null);
                        load();
                      }}
                    >
                      {t(
                        " Yerel tasla\u011F\u0131 b\u0131rak ve g\u00FCncel seti y\u00FCkle ",
                      )}
                    </button>
                  ),
                )}
              </div>
            </div>
          ),
        )}
        {translateNode(
          leave ? (
            <section className="question-editor-confirm">
              <h3>{t("Kaydedilmemi\u015F de\u011Fi\u015Fiklikler var")}</h3>
              <p>
                {t(
                  "Kaydetmeden kapat\u0131rsan\u0131z bu sorudaki de\u011Fi\u015Fiklikler kaybolur.",
                )}
              </p>
              <div className="modal-actions">
                <Button secondary onClick={() => setLeave(false)}>
                  {t(" D\u00FCzenlemeye d\u00F6n ")}
                </Button>
                <Button onClick={onClose}>{t("Kaydetmeden kapat")}</Button>
              </div>
            </section>
          ) : !data ? (
            <p role="status">{t("Soru seti y\u00FCkleniyor\u2026")}</p>
          ) : draft ? (
            <form id="question-draft-form" onSubmit={save}>
              <button
                className="text-btn"
                type="button"
                disabled={saving}
                onClick={() => {
                  if (dirty) setLeave(true);
                  else setDraft(null);
                }}
              >
                <ArrowLeft size={16} />
                {t(" Sete d\u00F6n ")}
              </button>
              <h3>
                {translateNode(draft.id ? "Soruyu düzenle" : "Yeni soru")}
              </h3>
              <p className="muted">
                {t(
                  " Kaydetti\u011Finiz i\u00E7erik taslakt\u0131r. \u00C7al\u0131\u015Fanlara \u0130K onay\u0131 ve yay\u0131n sonras\u0131nda g\u00F6sterilir. T\u00FCm sorular zorunludur. ",
                )}
              </p>
              <fieldset disabled={saving} className="question-editor-fields">
                <div className="form-grid">
                  <label>
                    {t(" Soru grubu ")}
                    <select
                      aria-label={t("Soru grubu")}
                      value={draft.form_key}
                      onChange={(e) => {
                        const g = data.groups.find(
                          (g: Any) => g.id === e.target.value,
                        );
                        const skill = data.skills[g.skill_ids[0]];
                        setDraft({
                          ...draft,
                          form_key: g.id,
                          skill_id: skill.id,
                          ...defaults(skill, draft.type),
                        });
                      }}
                    >
                      {translateNode(
                        data.groups.map((g: Any) => (
                          <option key={g.id} value={g.id}>
                            {g.id === "common" ? t(g.name) : g.name}
                          </option>
                        )),
                      )}
                    </select>
                  </label>
                  <label>
                    {t(" Yetkinlik ")}
                    <select
                      aria-label={t("Soru yetkinli\u011Fi")}
                      value={draft.skill_id}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          skill_id: e.target.value,
                          ...defaults(data.skills[e.target.value], draft.type),
                        })
                      }
                    >
                      {translateNode(
                        data.groups
                          .find((g: Any) => g.id === draft.form_key)
                          .skill_ids.map((id: string) => (
                            <option key={id} value={id}>
                              {translateNode(data.skills[id]?.name || id)}
                            </option>
                          )),
                      )}
                    </select>
                  </label>
                  <label>
                    {t(" Soru t\u00FCr\u00FC ")}
                    <select
                      aria-label={t("Soru t\u00FCr\u00FC")}
                      value={draft.type}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          type: e.target.value,
                          ...defaults(
                            data.skills[draft.skill_id],
                            e.target.value,
                          ),
                        })
                      }
                    >
                      {translateNode(
                        Object.entries(typeLabels).map(([id, label]: Any) => (
                          <option key={id} value={id}>
                            {translateNode(label)}
                          </option>
                        )),
                      )}
                    </select>
                  </label>
                  {translateNode(
                    draft.type === "open_text" && (
                      <label>
                        {t(" Kan\u0131t t\u00FCr\u00FC ")}
                        <select
                          aria-label={t("Kan\u0131t t\u00FCr\u00FC")}
                          value={draft.evidence_type}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              evidence_type: e.target.value,
                            })
                          }
                        >
                          <option value="scenario_reasoning">
                            {t(" Senaryoya verilen yan\u0131t ")}
                          </option>
                          <option value="self_reported_experience">
                            {t(" Beyan edilen uygulama deneyimi ")}
                          </option>
                        </select>
                      </label>
                    ),
                  )}
                </div>
                <label>
                  {t(" Soru metni ")}
                  <textarea
                    aria-label={t("Soru metni")}
                    required
                    maxLength={8000}
                    rows={4}
                    value={draft.prompt}
                    onChange={(e) =>
                      setDraft({ ...draft, prompt: e.target.value })
                    }
                  />
                </label>
                {translateNode(
                  draft.type !== "self_assessment" && (
                    <label>
                      {t(" De\u011Ferlendirme referans\u0131 ")}
                      <textarea
                        aria-label={t("De\u011Ferlendirme referans\u0131")}
                        maxLength={8000}
                        rows={3}
                        value={draft.reference}
                        onChange={(e) =>
                          setDraft({ ...draft, reference: e.target.value })
                        }
                      />
                      <small>
                        {t(
                          " Yaln\u0131z de\u011Ferlendirmede kullan\u0131l\u0131r; \u00E7al\u0131\u015Fana g\u00F6sterilmez. ",
                        )}
                      </small>
                    </label>
                  ),
                )}
                {translateNode(
                  draft.type !== "open_text" && (
                    <section>
                      <h3>
                        {translateNode(
                          draft.type === "single_choice"
                            ? "Seçenekler ve doğru cevap"
                            : "Öz beyan seçenekleri",
                        )}
                      </h3>
                      <p className="muted">
                        {translateNode(
                          draft.type === "single_choice"
                            ? "En az iki seçenek girin ve bir doğru cevap seçin."
                            : "L1–L5 ve deneyimim yok eşlemesi korunur; görünen metinleri düzenleyebilirsiniz.",
                        )}
                      </p>
                      {translateNode(
                        draft.options.map((o: Any, i: number) => (
                          <div className="question-option-editor" key={o.id}>
                            {translateNode(
                              draft.type === "single_choice" ? (
                                <label className="checkbox">
                                  <input
                                    type="radio"
                                    name="correct-answer"
                                    aria-label={t(
                                      `${i + 1}. seçenek doğru cevap`,
                                    )}
                                    checked={o.correct}
                                    onChange={() =>
                                      setDraft({
                                        ...draft,
                                        options: draft.options.map(
                                          (x: Any, j: number) => ({
                                            ...x,
                                            correct: i === j,
                                          }),
                                        ),
                                      })
                                    }
                                  />
                                  {t(" Do\u011Fru ")}
                                </label>
                              ) : (
                                <span className="small-pill">
                                  {translateNode(
                                    o.id === "none"
                                      ? "Deneyim yok"
                                      : "L" + o.level,
                                  )}
                                </span>
                              ),
                            )}
                            <label>
                              {translateNode(i + 1)}
                              {t(". se\u00E7enek ")}
                              <textarea
                                aria-label={t(`${i + 1}. seçenek metni`)}
                                required
                                rows={2}
                                maxLength={4000}
                                value={o.text}
                                onChange={(e) =>
                                  setDraft({
                                    ...draft,
                                    options: draft.options.map(
                                      (x: Any, j: number) =>
                                        i === j
                                          ? { ...x, text: e.target.value }
                                          : x,
                                    ),
                                  })
                                }
                              />
                            </label>
                            {translateNode(
                              draft.type === "single_choice" && (
                                <button
                                  type="button"
                                  className="icon-btn"
                                  aria-label={t(`${i + 1}. seçeneği sil`)}
                                  disabled={draft.options.length <= 2}
                                  onClick={() =>
                                    setDraft({
                                      ...draft,
                                      options: draft.options.filter(
                                        (_: Any, j: number) => j !== i,
                                      ),
                                    })
                                  }
                                >
                                  <Trash2 size={16} />
                                </button>
                              ),
                            )}
                          </div>
                        )),
                      )}
                      {translateNode(
                        draft.type === "single_choice" && (
                          <Button
                            type="button"
                            secondary
                            disabled={draft.options.length >= 6}
                            onClick={() =>
                              setDraft({
                                ...draft,
                                options: [
                                  ...draft.options,
                                  {
                                    id: `o${crypto.randomUUID().slice(0, 8)}`,
                                    text: "",
                                    correct: false,
                                    level: null,
                                  },
                                ],
                              })
                            }
                          >
                            <Plus size={16} />
                            {t(" Se\u00E7enek ekle ")}
                          </Button>
                        ),
                      )}
                    </section>
                  ),
                )}
                {translateNode(
                  draft.type === "open_text" && (
                    <section>
                      <h3>{t("Puanlama \u00F6l\u00E7\u00FCtleri")}</h3>
                      <p className="muted">
                        {t(
                          " L1, L2 ve L3 g\u00F6stergeleri korunmal\u0131. Her \u00F6l\u00E7\u00FCt i\u00E7in 0\u20134 puan a\u00E7\u0131klamalar\u0131n\u0131 tan\u0131mlay\u0131n. L4/L5 bu anketle do\u011Frulanmaz. ",
                        )}
                      </p>
                      {translateNode(
                        draft.rubric.map((r: Any, i: number) => (
                          <div className="question-rubric-editor" key={r.id}>
                            <div className="form-grid">
                              <label>
                                {t(" \u00D6l\u00E7\u00FCt ")}
                                {translateNode(i + 1)}
                                {t(" ad\u0131 ")}
                                <input
                                  aria-label={t(`Ölçüt ${i + 1} adı`)}
                                  required
                                  maxLength={200}
                                  value={r.label}
                                  onChange={(e) =>
                                    setDraft({
                                      ...draft,
                                      rubric: draft.rubric.map(
                                        (x: Any, j: number) =>
                                          i === j
                                            ? { ...x, label: e.target.value }
                                            : x,
                                      ),
                                    })
                                  }
                                />
                              </label>
                              <label>
                                {t(" \u00D6l\u00E7\u00FCt ")}
                                {translateNode(i + 1)}
                                {t(" a\u011F\u0131rl\u0131\u011F\u0131 ")}
                                <input
                                  aria-label={t(`Ölçüt ${i + 1} ağırlığı`)}
                                  type="number"
                                  required
                                  min={1}
                                  max={10}
                                  value={r.weight}
                                  onChange={(e) =>
                                    setDraft({
                                      ...draft,
                                      rubric: draft.rubric.map(
                                        (x: Any, j: number) =>
                                          i === j
                                            ? {
                                                ...x,
                                                weight: Number(e.target.value),
                                              }
                                            : x,
                                      ),
                                    })
                                  }
                                />
                              </label>
                            </div>
                            <span className="small-pill">
                              {t("L")}
                              {translateNode(r.level)}
                              {t(" \u00B7 0\u20134 puan")}
                            </span>
                            <label>
                              {t(" \u00D6l\u00E7\u00FCt ")}
                              {translateNode(i + 1)}
                              {t(" davran\u0131\u015F tan\u0131m\u0131 ")}
                              <textarea
                                aria-label={t(`Ölçüt ${i + 1} davranış tanımı`)}
                                required
                                rows={3}
                                maxLength={4000}
                                value={r.descriptor}
                                onChange={(e) =>
                                  setDraft({
                                    ...draft,
                                    rubric: draft.rubric.map(
                                      (x: Any, j: number) =>
                                        i === j
                                          ? { ...x, descriptor: e.target.value }
                                          : x,
                                    ),
                                  })
                                }
                              />
                            </label>
                            <details>
                              <summary>
                                {t(
                                  "0\u20134 puan a\u00E7\u0131klamalar\u0131n\u0131 d\u00FCzenle",
                                )}
                              </summary>
                              <div className="question-anchor-grid">
                                {translateNode(
                                  [0, 1, 2, 3, 4].map((score) => (
                                    <label key={score}>
                                      {translateNode(score)}
                                      {t(" puan ")}
                                      <textarea
                                        aria-label={t(
                                          `Ölçüt ${i + 1}, ${score} puan açıklaması`,
                                        )}
                                        required
                                        maxLength={1000}
                                        rows={2}
                                        value={r.anchors[String(score)] || ""}
                                        onChange={(e) =>
                                          setDraft({
                                            ...draft,
                                            rubric: draft.rubric.map(
                                              (x: Any, j: number) =>
                                                i === j
                                                  ? {
                                                      ...x,
                                                      anchors: {
                                                        ...x.anchors,
                                                        [score]: e.target.value,
                                                      },
                                                    }
                                                  : x,
                                            ),
                                          })
                                        }
                                      />
                                    </label>
                                  )),
                                )}
                              </div>
                            </details>
                          </div>
                        )),
                      )}
                    </section>
                  ),
                )}
              </fieldset>
            </form>
          ) : (
            <>
              <div className="question-set-summary">
                <div>
                  <h3>{data.name}</h3>
                  <p className="muted">
                    {t(" Soru seti s\u00FCr\u00FCm\u00FC ")}
                    {translateNode(data.revision)}
                    {t(" \u00B7")}
                    {translateNode(" ")}
                    {translateNode(
                      data.status === "ready"
                        ? "İK onaylı, henüz yayımlanmadı"
                        : data.can_edit
                          ? "İK incelemesinde"
                          : "Salt okunur",
                    )}
                  </p>
                </div>
                <span className="small-pill">
                  {translateNode(data.questions.length)}
                  {t(" benzersiz soru ")}
                </span>
              </div>
              <p className="muted">
                {t(
                  " Ortak sorulardaki de\u011Fi\u015Fiklikler t\u00FCm rollere uygulan\u0131r. Her yetkinlik i\u00E7in en az bir a\u00E7\u0131k u\u00E7lu ve tam bir \u00F6z beyan sorusu gerekir. Seviye \u00F6nerisi i\u00E7in en az iki ba\u011F\u0131ms\u0131z yaz\u0131l\u0131 kan\u0131t gerekir. ",
                )}
              </p>
              {translateNode(
                !data.can_edit && (
                  <p className="notice">
                    {translateNode(
                      data.status === "open" || data.status === "closed"
                        ? "Yayımlanmış anketin soru seti sabittir."
                        : "Düzenleme, onay ve yayın işlemleri İK tarafından yapılır.",
                    )}
                  </p>
                ),
              )}
              {translateNode(
                issues.length > 0 && (
                  <section className="question-editor-issues" role="status">
                    <b>{t("Yay\u0131n \u00F6ncesi tamamlanacaklar")}</b>
                    <ul>
                      {translateNode(
                        issues.map((issue: string, i: number) => (
                          <li key={i}>{translateNode(issue)}</li>
                        )),
                      )}
                    </ul>
                  </section>
                ),
              )}
              <div className="section-toolbar">
                <label>
                  {t(" Soru grubu ")}
                  <select
                    aria-label={t("\u0130ncelenen soru grubu")}
                    value={group}
                    onChange={(e) => {
                      setGroup(e.target.value);
                      setRemove(null);
                    }}
                  >
                    {translateNode(
                      data.groups.map((g: Any) => (
                        <option key={g.id} value={g.id}>
                          {g.id === "common" ? t(g.name) : g.name}
                          {t(" \u00B7 ")}
                          {translateNode(g.count)}
                          {t(" soru ")}
                          {translateNode(
                            g.id !== "common"
                              ? ` · form toplamı ${g.participant_question_count}`
                              : "",
                          )}
                        </option>
                      )),
                    )}
                  </select>
                </label>
                {translateNode(
                  data.can_edit && (
                    <Button disabled={saving} onClick={() => newQuestion()}>
                      <Plus size={16} />
                      {t(" Soru ekle ")}
                    </Button>
                  ),
                )}
              </div>
              <div className="question-review">
                {translateNode(
                  rows.map((q: Any, i: number) => (
                    <article className="question-editor-card" key={q.id}>
                      <div className="question-card-heading">
                        <span className="eyebrow">
                          {translateNode(i + 1)}
                          {t(" \u00B7 ")}
                          {translateNode(typeLabels[q.type])}
                          {t(" \u00B7")}
                          {translateNode(" ")}
                          {translateNode(
                            data.skills[q.skill_id]?.name || q.skill_id,
                          )}
                        </span>
                        {translateNode(
                          data.can_edit && (
                            <div className="catalog-buttons">
                              <button
                                className="icon-btn"
                                aria-label={t(`${i + 1}. soruyu kopyala`)}
                                onClick={() => newQuestion(q)}
                              >
                                <Copy size={16} />
                              </button>
                              <button
                                className="icon-btn"
                                aria-label={t(`${i + 1}. soruyu düzenle`)}
                                onClick={() => choose(q)}
                              >
                                <Pencil size={16} />
                              </button>
                              <button
                                className="icon-btn"
                                aria-label={t(`${i + 1}. soruyu sil`)}
                                onClick={() => setRemove(q)}
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>
                          ),
                        )}
                      </div>
                      <h3>{q.prompt}</h3>
                      {translateNode(
                        q.options.length > 0 && (
                          <ul>
                            {translateNode(
                              q.options.map((o: Any) => (
                                <li key={o.id}>
                                  {o.text}
                                  {translateNode(
                                    o.correct && (
                                      <b>{t(" \u00B7 Do\u011Fru cevap")}</b>
                                    ),
                                  )}
                                </li>
                              )),
                            )}
                          </ul>
                        ),
                      )}
                      {translateNode(
                        q.rubric.length > 0 && (
                          <details>
                            <summary>
                              {t(
                                " Puanlama \u00F6l\u00E7\u00FCtleri ve de\u011Ferlendirme referans\u0131 ",
                              )}
                            </summary>
                            {translateNode(
                              q.rubric.map((r: Any) => (
                                <p key={r.id}>
                                  <b>
                                    {t(" L")}
                                    {translateNode(r.level)}
                                    {t(" \u00B7 ")}
                                    {translateNode(r.label)}
                                    {t(" \u00B7 A\u011F\u0131rl\u0131k ")}
                                    {translateNode(r.weight)}
                                  </b>
                                  <br />
                                  {translateNode(r.descriptor)}
                                </p>
                              )),
                            )}
                            <p>{q.reference}</p>
                          </details>
                        ),
                      )}
                      {translateNode(
                        remove?.id === q.id && (
                          <div className="question-editor-confirm">
                            <p>
                              {t(
                                " Bu soru taslaktan silinecek. Yetkinlik kapsam\u0131 eksilirse set tamamlanana kadar yay\u0131n yap\u0131lamaz. ",
                              )}
                            </p>
                            <div className="modal-actions">
                              <Button
                                secondary
                                disabled={saving}
                                onClick={() => setRemove(null)}
                              >
                                {t(" Vazge\u00E7 ")}
                              </Button>
                              <Button
                                disabled={saving}
                                onClick={async () => {
                                  const result = await mutate(
                                    () =>
                                      api(
                                        `/campaigns/${campaignId}/questions/${q.id}?expected_version=${data.version}`,
                                        "DELETE",
                                      ),
                                    "Soru taslaktan silindi.",
                                  );
                                  if (result) {
                                    setData(result);
                                    setRemove(null);
                                  }
                                }}
                              >
                                {t(" Soruyu sil ")}
                              </Button>
                            </div>
                          </div>
                        ),
                      )}
                    </article>
                  )),
                )}
              </div>
            </>
          ),
        )}
      </div>
      {translateNode(
        data?.can_edit && !draft && !leave && (
          <div className="question-publish-actions">
            {translateNode(
              publish ? (
                <>
                  <p>
                    {t(
                      " G\u00FCncel soru setini \u0130K ad\u0131na onaylay\u0131p \u00E7al\u0131\u015Fanlara yay\u0131nlayacaks\u0131n\u0131z. Yay\u0131ndan sonra soru i\u00E7eri\u011Fi de\u011Fi\u015Ftirilemez. ",
                    )}
                  </p>
                  <div className="modal-actions">
                    <Button
                      secondary
                      disabled={saving}
                      onClick={() => setPublish(false)}
                    >
                      {t(" Vazge\u00E7 ")}
                    </Button>
                    <Button disabled={saving} onClick={() => approve(true)}>
                      <Send size={16} />
                      {t(" Onayla ve anketi yay\u0131nla ")}
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <span className="muted">
                    {t(
                      " Kay\u0131tlar taslakt\u0131r. Onay ve yay\u0131n ayr\u0131 i\u015Flemlerdir. ",
                    )}
                  </span>
                  <div className="catalog-buttons">
                    <Button
                      secondary
                      disabled={saving || !!issues.length}
                      onClick={() => approve(false)}
                    >
                      <Check size={16} />
                      {t(" Seti onayla ")}
                    </Button>
                    <Button
                      disabled={saving || !!issues.length}
                      onClick={() => setPublish(true)}
                    >
                      <Send size={16} />
                      {t(" Onayla ve yay\u0131nla ")}
                    </Button>
                  </div>
                </>
              ),
            )}
          </div>
        ),
      )}
      {translateNode(
        draft && !leave && (
          <div className="question-publish-actions">
            <Button
              type="button"
              secondary
              disabled={saving}
              onClick={() => {
                setDraft(null);
                setError("");
              }}
            >
              {t(" De\u011Fi\u015Fiklikleri b\u0131rak ")}
            </Button>
            <Button form="question-draft-form" type="submit" disabled={saving}>
              {translateNode(saving ? "Kaydediliyor…" : "Soruyu kaydet")}
            </Button>
          </div>
        ),
      )}
    </Modal>
  );
}
