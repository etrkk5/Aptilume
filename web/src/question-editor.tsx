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
    <Modal title="Soru seti · İK incelemesi" wide onClose={close}>
      <div className="modal-body question-set-editor">
        {error && (
          <div className="question-editor-error" role="alert">
            <AlertCircle size={18} />
            <div>
              {error}
              {data && (
                <button
                  className="text-btn"
                  type="button"
                  onClick={() => {
                    setDraft(null);
                    setRemove(null);
                    load();
                  }}
                >
                  Yerel taslağı bırak ve güncel seti yükle
                </button>
              )}
            </div>
          </div>
        )}
        {leave ? (
          <section className="question-editor-confirm">
            <h3>Kaydedilmemiş değişiklikler var</h3>
            <p>Kaydetmeden kapatırsanız bu sorudaki değişiklikler kaybolur.</p>
            <div className="modal-actions">
              <Button secondary onClick={() => setLeave(false)}>
                Düzenlemeye dön
              </Button>
              <Button onClick={onClose}>Kaydetmeden kapat</Button>
            </div>
          </section>
        ) : !data ? (
          <p role="status">Soru seti yükleniyor…</p>
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
              <ArrowLeft size={16} /> Sete dön
            </button>
            <h3>{draft.id ? "Soruyu düzenle" : "Yeni soru"}</h3>
            <p className="muted">
              Kaydettiğiniz içerik taslaktır. Çalışanlara İK onayı ve yayın
              sonrasında gösterilir. Tüm sorular zorunludur.
            </p>
            <fieldset disabled={saving} className="question-editor-fields">
              <div className="form-grid">
                <label>
                  Soru grubu
                  <select
                    aria-label="Soru grubu"
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
                    {data.groups.map((g: Any) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Yetkinlik
                  <select
                    aria-label="Soru yetkinliği"
                    value={draft.skill_id}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        skill_id: e.target.value,
                        ...defaults(data.skills[e.target.value], draft.type),
                      })
                    }
                  >
                    {data.groups
                      .find((g: Any) => g.id === draft.form_key)
                      .skill_ids.map((id: string) => (
                        <option key={id} value={id}>
                          {data.skills[id]?.name || id}
                        </option>
                      ))}
                  </select>
                </label>
                <label>
                  Soru türü
                  <select
                    aria-label="Soru türü"
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
                    {Object.entries(typeLabels).map(([id, label]: Any) => (
                      <option key={id} value={id}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                {draft.type === "open_text" && (
                  <label>
                    Kanıt türü
                    <select
                      aria-label="Kanıt türü"
                      value={draft.evidence_type}
                      onChange={(e) =>
                        setDraft({ ...draft, evidence_type: e.target.value })
                      }
                    >
                      <option value="scenario_reasoning">
                        Senaryoya verilen yanıt
                      </option>
                      <option value="self_reported_experience">
                        Beyan edilen uygulama deneyimi
                      </option>
                    </select>
                  </label>
                )}
              </div>
              <label>
                Soru metni
                <textarea
                  aria-label="Soru metni"
                  required
                  maxLength={8000}
                  rows={4}
                  value={draft.prompt}
                  onChange={(e) =>
                    setDraft({ ...draft, prompt: e.target.value })
                  }
                />
              </label>
              {draft.type !== "self_assessment" && (
                <label>
                  Değerlendirme referansı
                  <textarea
                    aria-label="Değerlendirme referansı"
                    maxLength={8000}
                    rows={3}
                    value={draft.reference}
                    onChange={(e) =>
                      setDraft({ ...draft, reference: e.target.value })
                    }
                  />
                  <small>
                    Yalnız değerlendirmede kullanılır; çalışana gösterilmez.
                  </small>
                </label>
              )}
              {draft.type !== "open_text" && (
                <section>
                  <h3>
                    {draft.type === "single_choice"
                      ? "Seçenekler ve doğru cevap"
                      : "Öz beyan seçenekleri"}
                  </h3>
                  <p className="muted">
                    {draft.type === "single_choice"
                      ? "En az iki seçenek girin ve bir doğru cevap seçin."
                      : "L1–L5 ve deneyimim yok eşlemesi korunur; görünen metinleri düzenleyebilirsiniz."}
                  </p>
                  {draft.options.map((o: Any, i: number) => (
                    <div className="question-option-editor" key={o.id}>
                      {draft.type === "single_choice" ? (
                        <label className="checkbox">
                          <input
                            type="radio"
                            name="correct-answer"
                            aria-label={`${i + 1}. seçenek doğru cevap`}
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
                          Doğru
                        </label>
                      ) : (
                        <span className="small-pill">
                          {o.id === "none" ? "Deneyim yok" : "L" + o.level}
                        </span>
                      )}
                      <label>
                        {i + 1}. seçenek
                        <textarea
                          aria-label={`${i + 1}. seçenek metni`}
                          required
                          rows={2}
                          maxLength={4000}
                          value={o.text}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              options: draft.options.map((x: Any, j: number) =>
                                i === j ? { ...x, text: e.target.value } : x,
                              ),
                            })
                          }
                        />
                      </label>
                      {draft.type === "single_choice" && (
                        <button
                          type="button"
                          className="icon-btn"
                          aria-label={`${i + 1}. seçeneği sil`}
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
                      )}
                    </div>
                  ))}
                  {draft.type === "single_choice" && (
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
                      Seçenek ekle
                    </Button>
                  )}
                </section>
              )}
              {draft.type === "open_text" && (
                <section>
                  <h3>Puanlama ölçütleri</h3>
                  <p className="muted">
                    L1, L2 ve L3 göstergeleri korunmalı. Her ölçüt için 0–4 puan
                    açıklamalarını tanımlayın. L4/L5 bu anketle doğrulanmaz.
                  </p>
                  {draft.rubric.map((r: Any, i: number) => (
                    <div className="question-rubric-editor" key={r.id}>
                      <div className="form-grid">
                        <label>
                          Ölçüt {i + 1} adı
                          <input
                            aria-label={`Ölçüt ${i + 1} adı`}
                            required
                            maxLength={200}
                            value={r.label}
                            onChange={(e) =>
                              setDraft({
                                ...draft,
                                rubric: draft.rubric.map((x: Any, j: number) =>
                                  i === j ? { ...x, label: e.target.value } : x,
                                ),
                              })
                            }
                          />
                        </label>
                        <label>
                          Ölçüt {i + 1} ağırlığı
                          <input
                            aria-label={`Ölçüt ${i + 1} ağırlığı`}
                            type="number"
                            required
                            min={1}
                            max={10}
                            value={r.weight}
                            onChange={(e) =>
                              setDraft({
                                ...draft,
                                rubric: draft.rubric.map((x: Any, j: number) =>
                                  i === j
                                    ? { ...x, weight: Number(e.target.value) }
                                    : x,
                                ),
                              })
                            }
                          />
                        </label>
                      </div>
                      <span className="small-pill">L{r.level} · 0–4 puan</span>
                      <label>
                        Ölçüt {i + 1} davranış tanımı
                        <textarea
                          aria-label={`Ölçüt ${i + 1} davranış tanımı`}
                          required
                          rows={3}
                          maxLength={4000}
                          value={r.descriptor}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              rubric: draft.rubric.map((x: Any, j: number) =>
                                i === j
                                  ? { ...x, descriptor: e.target.value }
                                  : x,
                              ),
                            })
                          }
                        />
                      </label>
                      <details>
                        <summary>0–4 puan açıklamalarını düzenle</summary>
                        <div className="question-anchor-grid">
                          {[0, 1, 2, 3, 4].map((score) => (
                            <label key={score}>
                              {score} puan
                              <textarea
                                aria-label={`Ölçüt ${i + 1}, ${score} puan açıklaması`}
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
                          ))}
                        </div>
                      </details>
                    </div>
                  ))}
                </section>
              )}
            </fieldset>
          </form>
        ) : (
          <>
            <div className="question-set-summary">
              <div>
                <h3>{data.name}</h3>
                <p className="muted">
                  Soru seti sürümü {data.revision} ·{" "}
                  {data.status === "ready"
                    ? "İK onaylı, henüz yayımlanmadı"
                    : data.can_edit
                      ? "İK incelemesinde"
                      : "Salt okunur"}
                </p>
              </div>
              <span className="small-pill">
                {data.questions.length} benzersiz soru
              </span>
            </div>
            <p className="muted">
              Ortak sorulardaki değişiklikler tüm rollere uygulanır. Her
              yetkinlik için en az bir açık uçlu ve tam bir öz beyan sorusu
              gerekir. Seviye önerisi için en az iki bağımsız yazılı kanıt
              gerekir.
            </p>
            {!data.can_edit && (
              <p className="notice">
                {data.status === "open" || data.status === "closed"
                  ? "Yayımlanmış anketin soru seti sabittir."
                  : "Düzenleme, onay ve yayın işlemleri İK tarafından yapılır."}
              </p>
            )}
            {issues.length > 0 && (
              <section className="question-editor-issues" role="status">
                <b>Yayın öncesi tamamlanacaklar</b>
                <ul>
                  {issues.map((issue: string, i: number) => (
                    <li key={i}>{issue}</li>
                  ))}
                </ul>
              </section>
            )}
            <div className="section-toolbar">
              <label>
                Soru grubu
                <select
                  aria-label="İncelenen soru grubu"
                  value={group}
                  onChange={(e) => {
                    setGroup(e.target.value);
                    setRemove(null);
                  }}
                >
                  {data.groups.map((g: Any) => (
                    <option key={g.id} value={g.id}>
                      {g.name} · {g.count} soru
                      {g.id !== "common"
                        ? ` · form toplamı ${g.participant_question_count}`
                        : ""}
                    </option>
                  ))}
                </select>
              </label>
              {data.can_edit && (
                <Button disabled={saving} onClick={() => newQuestion()}>
                  <Plus size={16} />
                  Soru ekle
                </Button>
              )}
            </div>
            <div className="question-review">
              {rows.map((q: Any, i: number) => (
                <article className="question-editor-card" key={q.id}>
                  <div className="question-card-heading">
                    <span className="eyebrow">
                      {i + 1} · {typeLabels[q.type]} ·{" "}
                      {data.skills[q.skill_id]?.name || q.skill_id}
                    </span>
                    {data.can_edit && (
                      <div className="catalog-buttons">
                        <button
                          className="icon-btn"
                          aria-label={`${i + 1}. soruyu kopyala`}
                          onClick={() => newQuestion(q)}
                        >
                          <Copy size={16} />
                        </button>
                        <button
                          className="icon-btn"
                          aria-label={`${i + 1}. soruyu düzenle`}
                          onClick={() => choose(q)}
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          className="icon-btn"
                          aria-label={`${i + 1}. soruyu sil`}
                          onClick={() => setRemove(q)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                  <h3>{q.prompt}</h3>
                  {q.options.length > 0 && (
                    <ul>
                      {q.options.map((o: Any) => (
                        <li key={o.id}>
                          {o.text}
                          {o.correct && <b> · Doğru cevap</b>}
                        </li>
                      ))}
                    </ul>
                  )}
                  {q.rubric.length > 0 && (
                    <details>
                      <summary>
                        Puanlama ölçütleri ve değerlendirme referansı
                      </summary>
                      {q.rubric.map((r: Any) => (
                        <p key={r.id}>
                          <b>
                            L{r.level} · {r.label} · Ağırlık {r.weight}
                          </b>
                          <br />
                          {r.descriptor}
                        </p>
                      ))}
                      <p>{q.reference}</p>
                    </details>
                  )}
                  {remove?.id === q.id && (
                    <div className="question-editor-confirm">
                      <p>
                        Bu soru taslaktan silinecek. Yetkinlik kapsamı eksilirse
                        set tamamlanana kadar yayın yapılamaz.
                      </p>
                      <div className="modal-actions">
                        <Button
                          secondary
                          disabled={saving}
                          onClick={() => setRemove(null)}
                        >
                          Vazgeç
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
                          Soruyu sil
                        </Button>
                      </div>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </>
        )}
      </div>
      {data?.can_edit && !draft && !leave && (
        <div className="question-publish-actions">
          {publish ? (
            <>
              <p>
                Güncel soru setini İK adına onaylayıp çalışanlara
                yayınlayacaksınız. Yayından sonra soru içeriği değiştirilemez.
              </p>
              <div className="modal-actions">
                <Button
                  secondary
                  disabled={saving}
                  onClick={() => setPublish(false)}
                >
                  Vazgeç
                </Button>
                <Button disabled={saving} onClick={() => approve(true)}>
                  <Send size={16} />
                  Onayla ve anketi yayınla
                </Button>
              </div>
            </>
          ) : (
            <>
              <span className="muted">
                Kayıtlar taslaktır. Onay ve yayın ayrı işlemlerdir.
              </span>
              <div className="catalog-buttons">
                <Button
                  secondary
                  disabled={saving || !!issues.length}
                  onClick={() => approve(false)}
                >
                  <Check size={16} />
                  Seti onayla
                </Button>
                <Button
                  disabled={saving || !!issues.length}
                  onClick={() => setPublish(true)}
                >
                  <Send size={16} />
                  Onayla ve yayınla
                </Button>
              </div>
            </>
          )}
        </div>
      )}
      {draft && !leave && (
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
            Değişiklikleri bırak
          </Button>
          <Button form="question-draft-form" type="submit" disabled={saving}>
            {saving ? "Kaydediliyor…" : "Soruyu kaydet"}
          </Button>
        </div>
      )}
    </Modal>
  );
}
