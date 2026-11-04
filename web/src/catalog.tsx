import React, { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  ChevronRight,
  Plus,
  Search,
  Pencil,
  Trash2,
  RotateCcw,
} from "lucide-react";
import { api } from "./client";
import { Button, Modal } from "./ui";

type Any = any;
const levelNames = ["Farkında", "Gelişen", "Yetkin", "İleri", "Lider"];
const newSkill = (code: number) => ({
  code,
  name: "",
  definition: "",
  owners: [],
  domain: "",
  family: "",
  owner_department: "",
  version: 1,
  levels: levelNames.map((label, i) => ({
    level: i + 1,
    label,
    description: "",
  })),
});

export function CatalogManager({ user, action }: Any) {
  const [data, setData] = useState<Any>(null),
    [q, setQ] = useState(""),
    [status, setStatus] = useState("active"),
    [offset, setOffset] = useState(0),
    [reload, setReload] = useState(0),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [detail, setDetail] = useState<Any>(null),
    [draft, setDraft] = useState<Any>(null),
    [removal, setRemoval] = useState<Any>(null),
    [saving, setSaving] = useState(false);
  const serial = useRef(0);
  const editable = user.roles.includes("hr");
  useEffect(() => {
    const request = ++serial.current;
    setLoading(true);
    const timer = window.setTimeout(() => {
      api(
        `/catalog/skills?${new URLSearchParams({ q, status, offset: String(offset), limit: "24" })}`,
      )
        .then((result) => {
          if (request !== serial.current) return;
          if (offset && offset >= result.total) {
            setOffset(0);
            return;
          }
          setData(result);
          setError("");
        })
        .catch((e) => {
          if (request === serial.current) setError(e.message);
        })
        .finally(() => {
          if (request === serial.current) setLoading(false);
        });
    }, 180);
    return () => {
      window.clearTimeout(timer);
      serial.current++;
    };
  }, [q, status, offset, reload]);
  async function change(task: () => Promise<Any>, message: string) {
    setSaving(true);
    try {
      const result = await action(task, message);
      if (result) {
        setDetail(null);
        setDraft(null);
        setRemoval(null);
        setReload((n) => n + 1);
      }
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <div className="section-toolbar catalog-toolbar">
        <div className="search">
          <Search size={17} />
          <input
            aria-label="Yetkinlik ara"
            maxLength={200}
            placeholder="Kod, yetkinlik veya tanım ara…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        <label className="catalog-filter">
          Katalog durumu
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="active">Aktif yetkinlikler</option>
            <option value="archived">Silinenler / arşiv</option>
            <option value="all">Tüm kayıtlar</option>
          </select>
        </label>
        {editable && (
          <Button
            disabled={!data || data.next_code > 9999}
            onClick={() => setDraft(newSkill(data.next_code))}
          >
            <Plus size={17} />
            Yetkinlik ekle
          </Button>
        )}
      </div>
      {data && (
        <p className="muted" aria-live="polite">
          {data.active_count} aktif yetkinlik · {data.active_count * 5} seviye
          tanımı · {data.archived_count} arşiv kaydı
        </p>
      )}
      {error && (
        <div className="catalog-error" role="alert">
          {error}{" "}
          <button className="text-btn" onClick={() => setReload((n) => n + 1)}>
            Yeniden dene
          </button>
        </div>
      )}
      {loading ? (
        <p className="muted" role="status">
          Katalog yükleniyor…
        </p>
      ) : (
        !error && (
          <>
            <div className="catalog-grid">
              {data?.items.map((s: Any) => (
                <button
                  className="panel skill-card"
                  key={s.id}
                  onClick={() => setDetail(s)}
                >
                  <div className="skill-top">
                    <span className="skill-code">
                      {String(s.code).padStart(2, "0")}
                    </span>
                    <span className="small-pill">
                      {s.archived
                        ? "Arşiv"
                        : s.common
                          ? "Ortak ölçüm"
                          : `v${s.version}`}
                    </span>
                    <ArrowUpRight size={17} />
                  </div>
                  <h3>{s.name}</h3>
                  <p>{s.definition}</p>
                  <div className="skill-footer">
                    <span>{s.levels.length} yetkinlik seviyesi</span>
                    <ChevronRight size={15} />
                  </div>
                </button>
              ))}
            </div>
            {!data?.items.length && (
              <div className="panel catalog-empty">
                Bu filtrelere uygun yetkinlik bulunamadı.
              </div>
            )}
            {!!data?.total && (
              <div className="section-toolbar catalog-pagination">
                <span className="muted">
                  {offset + 1}–{Math.min(offset + 24, data.total)} /{" "}
                  {data.total} kayıt
                </span>
                <div className="catalog-buttons">
                  <Button
                    secondary
                    disabled={!offset}
                    onClick={() => setOffset((n) => n - 24)}
                  >
                    Önceki
                  </Button>
                  <Button
                    secondary
                    disabled={offset + 24 >= data.total}
                    onClick={() => setOffset((n) => n + 24)}
                  >
                    Sonraki
                  </Button>
                </div>
              </div>
            )}
          </>
        )
      )}
      {detail && (
        <Modal title={detail.name} onClose={() => !saving && setDetail(null)}>
          <div className="modal-body">
            <p className="muted">
              Kod {detail.code} · Sürüm {detail.version}
              {detail.archived ? " · Arşivde" : ""}
            </p>
            <p>{detail.definition}</p>
            {(detail.domain ||
              detail.family ||
              detail.owner_department ||
              detail.owners.length > 0) && (
              <dl className="catalog-metadata">
                {[
                  ["Alan", detail.domain],
                  ["Aile", detail.family],
                  ["Sorumlu birim", detail.owner_department],
                  ["Skill Owner", detail.owners.join(", ")],
                ]
                  .filter(([, value]) => value)
                  .map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
              </dl>
            )}
            {detail.levels.map((x: Any) => (
              <div className="level-item" key={x.level}>
                <span>L{x.level}</span>
                <div>
                  <h3>{x.label}</h3>
                  <p>{x.description}</p>
                </div>
              </div>
            ))}
            {editable && (
              <>
                <p className="muted">
                  Değişiklikler yeni ölçümlerde kullanılır. Mevcut formların ve
                  sonuçların yetkinlik içeriği korunur.
                </p>
                {detail.common && (
                  <p className="muted">
                    Bu yetkinlik ortak soru setine bağlıdır. Düzenlenebilir;
                    silinemez.
                  </p>
                )}
                <div className="modal-actions">
                  {detail.archived ? (
                    <Button
                      disabled={saving}
                      onClick={() =>
                        change(
                          () =>
                            api(
                              `/skills/${detail.id}/restore?expected_version=${detail.version}`,
                              "POST",
                            ),
                          "Yetkinlik geri yüklendi.",
                        )
                      }
                    >
                      <RotateCcw size={16} />
                      Geri yükle
                    </Button>
                  ) : (
                    <>
                      <Button
                        secondary
                        disabled={saving || detail.common}
                        onClick={() => {
                          setRemoval(detail);
                          setDetail(null);
                        }}
                      >
                        <Trash2 size={16} />
                        Yetkinliği sil
                      </Button>
                      <Button
                        onClick={() => {
                          setDraft({
                            ...structuredClone(detail),
                            ownersText: detail.owners.join(", "),
                          });
                          setDetail(null);
                        }}
                      >
                        <Pencil size={16} />
                        Düzenle
                      </Button>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </Modal>
      )}
      {draft && (
        <Modal
          title={draft.id ? "Yetkinliği düzenle" : "Yeni yetkinlik"}
          onClose={() => !saving && setDraft(null)}
        >
          <form
            className="modal-body"
            onSubmit={(e) => {
              e.preventDefault();
              const payload = {
                code: Number(draft.code),
                name: draft.name,
                definition: draft.definition,
                levels: draft.levels,
                owners: (draft.ownersText || "")
                  .split(/[,\n]/)
                  .map((s: string) => s.trim())
                  .filter(Boolean),
                domain: draft.domain,
                family: draft.family,
                owner_department: draft.owner_department,
                expected_version: draft.version,
              };
              change(
                () =>
                  api(
                    draft.id ? `/skills/${draft.id}` : "/skills",
                    draft.id ? "PATCH" : "POST",
                    payload,
                  ),
                "Yetkinlik kaydedildi.",
              );
            }}
          >
            <p className="muted">
              Ad, tanım ve L1–L5 alanlarının tamamı zorunludur. Kod
              oluşturulduktan sonra değiştirilemez.
            </p>
            <fieldset disabled={saving} className="catalog-fieldset">
              <div className="form-grid">
                <label>
                  Yetkinlik kodu
                  <input
                    required
                    type="number"
                    min={1}
                    max={9999}
                    disabled={!!draft.id}
                    value={draft.code}
                    onChange={(e) =>
                      setDraft({ ...draft, code: Number(e.target.value) })
                    }
                  />
                </label>
                <label>
                  Yetkinlik adı
                  <input
                    required
                    minLength={2}
                    maxLength={200}
                    value={draft.name}
                    onChange={(e) =>
                      setDraft({ ...draft, name: e.target.value })
                    }
                  />
                </label>
              </div>
              <label>
                Yetkinlik tanımı
                <textarea
                  required
                  minLength={10}
                  maxLength={4000}
                  rows={3}
                  value={draft.definition}
                  onChange={(e) =>
                    setDraft({ ...draft, definition: e.target.value })
                  }
                />
              </label>
              <div className="form-grid">
                {[
                  ["domain", "Alan"],
                  ["family", "Yetkinlik ailesi"],
                  ["owner_department", "Sorumlu birim"],
                  ["ownersText", "Skill Owner (virgülle ayırın)"],
                ].map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <input
                      maxLength={key === "ownersText" ? 2000 : 200}
                      value={draft[key] || ""}
                      onChange={(e) =>
                        setDraft({ ...draft, [key]: e.target.value })
                      }
                    />
                  </label>
                ))}
              </div>
              <h3>Seviye tanımları</h3>
              {draft.levels.map((level: Any, i: number) => (
                <section className="catalog-level-editor" key={level.level}>
                  <span className="small-pill">L{level.level}</span>
                  <label>
                    L{level.level} seviye adı
                    <input
                      required
                      maxLength={100}
                      value={level.label}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          levels: draft.levels.map((x: Any, j: number) =>
                            i === j ? { ...x, label: e.target.value } : x,
                          ),
                        })
                      }
                    />
                  </label>
                  <label>
                    L{level.level} seviye tanımı
                    <textarea
                      required
                      maxLength={2000}
                      rows={3}
                      value={level.description}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          levels: draft.levels.map((x: Any, j: number) =>
                            i === j ? { ...x, description: e.target.value } : x,
                          ),
                        })
                      }
                    />
                  </label>
                </section>
              ))}
            </fieldset>
            <div className="modal-actions">
              <Button
                secondary
                type="button"
                disabled={saving}
                onClick={() => setDraft(null)}
              >
                Vazgeç
              </Button>
              <Button disabled={saving} type="submit">
                {saving ? "Kaydediliyor…" : "Yetkinliği kaydet"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
      {removal && (
        <Modal
          title="Yetkinliği sil"
          onClose={() => !saving && setRemoval(null)}
        >
          <div className="modal-body">
            <p>
              <b>{removal.name}</b> aktif katalogdan kaldırılıp arşive
              taşınacak. Geçmiş formlar ve sonuçlar korunur. Arşivden geri
              yükleyebilirsiniz.
            </p>
            <p className="muted">
              Yeni ölçümlerden önce bu yetkinliği kullanan ekip ve rol
              hedeflerini değiştirin veya yetkinliği geri yükleyin.
            </p>
            <div className="modal-actions">
              <Button
                secondary
                disabled={saving}
                onClick={() => setRemoval(null)}
              >
                Vazgeç
              </Button>
              <Button
                disabled={saving}
                onClick={() =>
                  change(
                    () =>
                      api(
                        `/skills/${removal.id}?expected_version=${removal.version}`,
                        "DELETE",
                      ),
                    "Yetkinlik silindi; arşivden geri yüklenebilir.",
                  )
                }
              >
                Sil ve arşive taşı
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
