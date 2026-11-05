import { t, translateNode, formatLocale } from "./i18n";
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
            aria-label={t("Yetkinlik ara")}
            maxLength={200}
            placeholder={t("Kod, yetkinlik veya tan\u0131m ara\u2026")}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        <label className="catalog-filter">
          {t(" Katalog durumu ")}
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="active">{t("Aktif yetkinlikler")}</option>
            <option value="archived">{t("Silinenler / ar\u015Fiv")}</option>
            <option value="all">{t("T\u00FCm kay\u0131tlar")}</option>
          </select>
        </label>
        {translateNode(
          editable && (
            <Button
              disabled={!data || data.next_code > 9999}
              onClick={() => setDraft(newSkill(data.next_code))}
            >
              <Plus size={17} />
              {t(" Yetkinlik ekle ")}
            </Button>
          ),
        )}
      </div>
      {translateNode(
        data && (
          <p className="muted" aria-live="polite">
            {translateNode(data.active_count)}
            {t(" aktif yetkinlik \u00B7 ")}
            {translateNode(data.active_count * 5)}
            {t(" seviye tan\u0131m\u0131 \u00B7 ")}
            {translateNode(data.archived_count)}
            {t(" ar\u015Fiv kayd\u0131 ")}
          </p>
        ),
      )}
      {translateNode(
        error && (
          <div className="catalog-error" role="alert">
            {translateNode(error)}
            {translateNode(" ")}
            <button
              className="text-btn"
              onClick={() => setReload((n) => n + 1)}
            >
              {t(" Yeniden dene ")}
            </button>
          </div>
        ),
      )}
      {translateNode(
        loading ? (
          <p className="muted" role="status">
            {t(" Katalog y\u00FCkleniyor\u2026 ")}
          </p>
        ) : (
          !error && (
            <>
              <div className="catalog-grid">
                {translateNode(
                  data?.items.map((s: Any) => (
                    <button
                      className="panel skill-card"
                      key={s.id}
                      onClick={() => setDetail(s)}
                    >
                      <div className="skill-top">
                        <span className="skill-code">
                          {translateNode(String(s.code).padStart(2, "0"))}
                        </span>
                        <span className="small-pill">
                          {translateNode(
                            s.archived
                              ? "Arşiv"
                              : s.common
                                ? "Ortak ölçüm"
                                : `v${s.version}`,
                          )}
                        </span>
                        <ArrowUpRight size={17} />
                      </div>
                      <h3>{s.name}</h3>
                      <p>{s.definition}</p>
                      <div className="skill-footer">
                        <span>
                          {translateNode(s.levels.length)}
                          {t(" yetkinlik seviyesi")}
                        </span>
                        <ChevronRight size={15} />
                      </div>
                    </button>
                  )),
                )}
              </div>
              {translateNode(
                !data?.items.length && (
                  <div className="panel catalog-empty">
                    {t(" Bu filtrelere uygun yetkinlik bulunamad\u0131. ")}
                  </div>
                ),
              )}
              {translateNode(
                !!data?.total && (
                  <div className="section-toolbar catalog-pagination">
                    <span className="muted">
                      {translateNode(offset + 1)}
                      {t("\u2013")}
                      {translateNode(Math.min(offset + 24, data.total))}
                      {t(" /")}
                      {translateNode(" ")}
                      {translateNode(data.total)}
                      {t(" kay\u0131t ")}
                    </span>
                    <div className="catalog-buttons">
                      <Button
                        secondary
                        disabled={!offset}
                        onClick={() => setOffset((n) => n - 24)}
                      >
                        {t(" \u00D6nceki ")}
                      </Button>
                      <Button
                        secondary
                        disabled={offset + 24 >= data.total}
                        onClick={() => setOffset((n) => n + 24)}
                      >
                        {t(" Sonraki ")}
                      </Button>
                    </div>
                  </div>
                ),
              )}
            </>
          )
        ),
      )}
      {translateNode(
        detail && (
          <Modal
            title={t(detail.name)}
            onClose={() => !saving && setDetail(null)}
          >
            <div className="modal-body">
              <p className="muted">
                {t(" Kod ")}
                {translateNode(detail.code)}
                {t(" \u00B7 S\u00FCr\u00FCm ")}
                {translateNode(detail.version)}
                {translateNode(detail.archived ? " · Arşivde" : "")}
              </p>
              <p>{detail.definition}</p>
              {translateNode(
                (detail.domain ||
                  detail.family ||
                  detail.owner_department ||
                  detail.owners.length > 0) && (
                  <dl className="catalog-metadata">
                    {translateNode(
                      [
                        ["Alan", detail.domain],
                        ["Aile", detail.family],
                        ["Sorumlu birim", detail.owner_department],
                        ["Skill Owner", detail.owners.join(", ")],
                      ]
                        .filter(([, value]) => value)
                        .map(([label, value]) => (
                          <div key={label}>
                            <dt>{translateNode(label)}</dt>
                            <dd>{translateNode(value)}</dd>
                          </div>
                        )),
                    )}
                  </dl>
                ),
              )}
              {translateNode(
                detail.levels.map((x: Any) => (
                  <div className="level-item" key={x.level}>
                    <span>
                      {t("L")}
                      {translateNode(x.level)}
                    </span>
                    <div>
                      <h3>{translateNode(x.label)}</h3>
                      <p>{x.description}</p>
                    </div>
                  </div>
                )),
              )}
              {translateNode(
                editable && (
                  <>
                    <p className="muted">
                      {t(
                        " De\u011Fi\u015Fiklikler yeni \u00F6l\u00E7\u00FCmlerde kullan\u0131l\u0131r. Mevcut formlar\u0131n ve sonu\u00E7lar\u0131n yetkinlik i\u00E7eri\u011Fi korunur. ",
                      )}
                    </p>
                    {translateNode(
                      detail.common && (
                        <p className="muted">
                          {t(
                            " Bu yetkinlik ortak soru setine ba\u011Fl\u0131d\u0131r. D\u00FCzenlenebilir; silinemez. ",
                          )}
                        </p>
                      ),
                    )}
                    <div className="modal-actions">
                      {translateNode(
                        detail.archived ? (
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
                            {t(" Geri y\u00FCkle ")}
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
                              {t(" Yetkinli\u011Fi sil ")}
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
                              {t(" D\u00FCzenle ")}
                            </Button>
                          </>
                        ),
                      )}
                    </div>
                  </>
                ),
              )}
            </div>
          </Modal>
        ),
      )}
      {translateNode(
        draft && (
          <Modal
            title={t(draft.id ? "Yetkinliği düzenle" : "Yeni yetkinlik")}
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
                {t(
                  " Ad, tan\u0131m ve L1\u2013L5 alanlar\u0131n\u0131n tamam\u0131 zorunludur. Kod olu\u015Fturulduktan sonra de\u011Fi\u015Ftirilemez. ",
                )}
              </p>
              <fieldset disabled={saving} className="catalog-fieldset">
                <div className="form-grid">
                  <label>
                    {t(" Yetkinlik kodu ")}
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
                    {t(" Yetkinlik ad\u0131 ")}
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
                  {t(" Yetkinlik tan\u0131m\u0131 ")}
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
                  {translateNode(
                    [
                      ["domain", "Alan"],
                      ["family", "Yetkinlik ailesi"],
                      ["owner_department", "Sorumlu birim"],
                      ["ownersText", "Skill Owner (virgülle ayırın)"],
                    ].map(([key, label]) => (
                      <label key={key}>
                        {translateNode(label)}
                        <input
                          maxLength={key === "ownersText" ? 2000 : 200}
                          value={draft[key] || ""}
                          onChange={(e) =>
                            setDraft({ ...draft, [key]: e.target.value })
                          }
                        />
                      </label>
                    )),
                  )}
                </div>
                <h3>{t("Seviye tan\u0131mlar\u0131")}</h3>
                {translateNode(
                  draft.levels.map((level: Any, i: number) => (
                    <section className="catalog-level-editor" key={level.level}>
                      <span className="small-pill">
                        {t("L")}
                        {translateNode(level.level)}
                      </span>
                      <label>
                        {t(" L")}
                        {translateNode(level.level)}
                        {t(" seviye ad\u0131 ")}
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
                        {t(" L")}
                        {translateNode(level.level)}
                        {t(" seviye tan\u0131m\u0131 ")}
                        <textarea
                          required
                          maxLength={2000}
                          rows={3}
                          value={level.description}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              levels: draft.levels.map((x: Any, j: number) =>
                                i === j
                                  ? { ...x, description: e.target.value }
                                  : x,
                              ),
                            })
                          }
                        />
                      </label>
                    </section>
                  )),
                )}
              </fieldset>
              <div className="modal-actions">
                <Button
                  secondary
                  type="button"
                  disabled={saving}
                  onClick={() => setDraft(null)}
                >
                  {t(" Vazge\u00E7 ")}
                </Button>
                <Button disabled={saving} type="submit">
                  {translateNode(
                    saving ? "Kaydediliyor…" : "Yetkinliği kaydet",
                  )}
                </Button>
              </div>
            </form>
          </Modal>
        ),
      )}
      {translateNode(
        removal && (
          <Modal
            title={t("Yetkinli\u011Fi sil")}
            onClose={() => !saving && setRemoval(null)}
          >
            <div className="modal-body">
              <p>
                <b>{removal.name}</b>
                {t(
                  " aktif katalogdan kald\u0131r\u0131l\u0131p ar\u015Five ta\u015F\u0131nacak. Ge\u00E7mi\u015F formlar ve sonu\u00E7lar korunur. Ar\u015Fivden geri y\u00FCkleyebilirsiniz. ",
                )}
              </p>
              <p className="muted">
                {t(
                  " Yeni \u00F6l\u00E7\u00FCmlerden \u00F6nce bu yetkinli\u011Fi kullanan ekip ve rol hedeflerini de\u011Fi\u015Ftirin veya yetkinli\u011Fi geri y\u00FCkleyin. ",
                )}
              </p>
              <div className="modal-actions">
                <Button
                  secondary
                  disabled={saving}
                  onClick={() => setRemoval(null)}
                >
                  {t(" Vazge\u00E7 ")}
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
                  {t(" Sil ve ar\u015Five ta\u015F\u0131 ")}
                </Button>
              </div>
            </div>
          </Modal>
        ),
      )}
    </>
  );
}
