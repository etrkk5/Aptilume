import { t, translateNode, formatLocale } from "./i18n";
import React, { useEffect, useRef, useState } from "react";
import {
  Plus,
  Search,
  Pencil,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api } from "./client";
import { Button, Modal } from "./ui";
const roles: Record<string, string> = {
  admin: "Integration administrator",
  hr: "Human resources",
  manager: "Team manager",
  employee: "Employee",
};
export default function IdentityManagement({
  action,
  participants,
  user,
}: any) {
  const [data, setData] = useState<any>(null),
    [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0),
    [draft, setDraft] = useState<any>(null),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false);
  const sequence = useRef(0);
  async function load() {
    const seq = ++sequence.current;
    try {
      const value = await api(
        `/admin/users?q=${encodeURIComponent(query)}&offset=${offset}&limit=25`,
      );
      if (seq === sequence.current) {
        setData(value);
        setError("");
      }
    } catch (e: any) {
      if (seq === sequence.current) setError(e.message);
    }
  }
  useEffect(() => {
    const timer = setTimeout(load, 200);
    return () => {
      clearTimeout(timer);
      sequence.current++;
    };
  }, [query, offset]);
  function open(account?: any) {
    setDraft(
      account
        ? {
            ...account,
            role: account.roles[0],
            password: "",
            expected_version: data.version,
          }
        : {
            username: "",
            display_name: "",
            email: "",
            role: user.permissions.all_data ? "employee" : "admin",
            participant_id: null,
            manager_id: null,
            active: true,
            password: "",
            expected_version: data.version,
          },
    );
  }
  function update(key: string, value: any) {
    setDraft({ ...draft, [key]: value });
  }
  const business = draft && ["manager", "employee"].includes(draft.role);
  async function reloadDraft() {
    try {
      const fresh = await api(
        `/admin/users?q=${encodeURIComponent(draft.username)}&limit=100`,
      );
      setData(fresh);
      const account = fresh.items.find((item: any) => item.id === draft.id);
      if (draft.id && !account) {
        setDraft(null);
        return;
      }
      setDraft(
        account
          ? {
              ...account,
              role: account.roles[0],
              password: "",
              expected_version: fresh.version,
            }
          : { ...draft, password: "", expected_version: fresh.version },
      );
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <section className="panel identity-panel">
      <div className="panel-head">
        <div>
          <h2>{t("User accounts")}</h2>
          <p>{t("Local sign-in, roles and reporting relationships")}</p>
        </div>
        <Button
          disabled={!data?.local_management_enabled}
          onClick={() => open()}
        >
          <Plus size={16} />
          {t("Create account")}
        </Button>
      </div>
      <div className="identity-intro">
        <ShieldCheck size={19} />
        <p>
          {t(
            "Local accounts can sign in independently of a corporate directory. ",
          )}
          {translateNode(
            user.permissions.all_data
              ? "Link employee and manager accounts to HR profiles. Access follows the reporting relationship."
              : "HR manages business accounts and employee links. You can manage integration administrators here.",
          )}
        </p>
      </div>
      {translateNode(
        data && !data.local_management_enabled && (
          <div className="notice">
            {t("Presentation identities in this workspace are read-only.")}
          </div>
        ),
      )}
      <div className="identity-toolbar">
        <label className="identity-search">
          <Search size={17} />
          <input
            aria-label={t("Search users")}
            placeholder={t("Search name, username or email")}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <span>
          {translateNode(data?.total ?? "—")}
          {t(" accounts")}
        </span>
      </div>
      {translateNode(
        error && (
          <div className="notice error" role="alert">
            {translateNode(error)}
          </div>
        ),
      )}
      <div className="identity-table-wrap">
        <table className="identity-table">
          <thead>
            <tr>
              <th>{t("Account")}</th>
              <th>{t("Role")}</th>
              <th>{t("Sign-in source")}</th>
              <th>{t("Status")}</th>
              <th>
                <span className="sr-only">{t("Actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {translateNode(
              data?.items.map((account: any) => (
                <tr key={account.id}>
                  <td>
                    <b>{account.display_name}</b>
                    <small>{translateNode(account.username)}</small>
                  </td>
                  <td>
                    {translateNode(
                      account.roles
                        .map((r: string) => roles[r] || r)
                        .join(", "),
                    )}
                  </td>
                  <td>
                    {translateNode(
                      account.source === "local"
                        ? "Local account"
                        : account.source === "demo"
                          ? "Presentation account"
                          : "Corporate directory",
                    )}
                  </td>
                  <td>
                    <span className={`badge ${account.active ? "done" : ""}`}>
                      {translateNode(account.active ? "Active" : "Disabled")}
                    </span>
                  </td>
                  <td>
                    {translateNode(
                      account.source === "local" &&
                        data.local_management_enabled && (
                          <Button
                            secondary
                            onClick={() => open(account)}
                            aria-label={t(`Edit account ${account.username}`)}
                          >
                            <Pencil size={14} />
                            {t("Edit")}
                          </Button>
                        ),
                    )}
                  </td>
                </tr>
              )),
            )}
            {translateNode(
              data?.items.length === 0 && (
                <tr>
                  <td colSpan={5}>{t("No accounts match your search.")}</td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
      <div className="identity-pagination">
        <Button
          secondary
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 25))}
        >
          <ChevronLeft size={16} />
          {t("Previous")}
        </Button>
        <span>
          {translateNode(
            data?.total
              ? `${offset + 1}–${Math.min(offset + 25, data.total)}`
              : "0",
          )}
          {t(" / ")}
          {translateNode(data?.total ?? 0)}
        </span>
        <Button
          secondary
          disabled={!data || offset + 25 >= data.total}
          onClick={() => setOffset(offset + 25)}
        >
          {t("Next")}
          <ChevronRight size={16} />
        </Button>
      </div>
      {translateNode(
        draft && (
          <Modal
            title={t(draft.id ? "Edit account" : "Create local account")}
            onClose={() => setDraft(null)}
          >
            <form
              className="modal-body"
              onSubmit={async (e) => {
                e.preventDefault();
                if (saving || draft.expected_version !== data.version) return;
                setSaving(true);
                const payload: any = {
                  expected_version: draft.expected_version,
                  display_name: draft.display_name,
                  email: draft.email,
                  role: draft.role,
                  active: draft.active,
                  participant_id: business ? draft.participant_id : null,
                  manager_id: business ? draft.manager_id : null,
                  password: draft.password,
                };
                if (!draft.id) payload.username = draft.username;
                try {
                  const result = await action(
                    () =>
                      api(
                        `/admin/users${draft.id ? "/" + encodeURIComponent(draft.id) : ""}`,
                        draft.id ? "PUT" : "POST",
                        payload,
                      ),
                    draft.id
                      ? "Account updated. Previous sessions were closed."
                      : "Local account created.",
                  );
                  if (result) setDraft(null);
                  await load();
                } finally {
                  setSaving(false);
                }
              }}
            >
              {translateNode(
                draft.expected_version !== data.version && (
                  <div className="notice" role="alert">
                    {t(
                      "The account list changed. Load the current record and edit it again.",
                    )}
                    <Button secondary type="button" onClick={reloadDraft}>
                      {t("Load current record")}
                    </Button>
                  </div>
                ),
              )}
              <label>
                {t("Username")}
                <input
                  required
                  minLength={3}
                  maxLength={100}
                  pattern="[A-Za-z0-9][A-Za-z0-9_.@-]*"
                  autoComplete="off"
                  readOnly={!!draft.id}
                  value={draft.username}
                  onChange={(e) => update("username", e.target.value)}
                />
              </label>
              <label>
                {t("Full name")}
                <input
                  required
                  minLength={2}
                  maxLength={200}
                  value={draft.display_name}
                  onChange={(e) => update("display_name", e.target.value)}
                />
              </label>
              <label>
                {t("Email")}
                <input
                  type="email"
                  maxLength={254}
                  value={draft.email}
                  onChange={(e) => update("email", e.target.value)}
                />
              </label>
              <label>
                {t("Role")}
                <select
                  value={draft.role}
                  disabled={draft.id === user.id || draft.id === "local-admin"}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      role: e.target.value,
                      participant_id: null,
                      manager_id: null,
                    })
                  }
                >
                  {translateNode(
                    data.allowed_roles.map((r: string) => (
                      <option key={r} value={r}>
                        {translateNode(roles[r])}
                      </option>
                    )),
                  )}
                </select>
              </label>
              {translateNode(
                business && (
                  <>
                    <label>
                      {t("Employee profile")}
                      <select
                        required
                        value={draft.participant_id || ""}
                        onChange={(e) =>
                          update("participant_id", e.target.value || null)
                        }
                      >
                        <option value="">{t("Select a profile")}</option>
                        {translateNode(
                          participants.map((p: any) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                              {t(" \u00B7 ")}
                              {p.title}
                            </option>
                          )),
                        )}
                      </select>
                    </label>
                    <p className="muted">
                      {t(
                        "First create the employee profile in Teams and targets.",
                      )}
                    </p>
                    <label>
                      {t("Reporting manager")}
                      <select
                        value={draft.manager_id || ""}
                        onChange={(e) =>
                          update("manager_id", e.target.value || null)
                        }
                      >
                        <option value="">{t("No manager assigned")}</option>
                        {translateNode(
                          data.managers
                            .filter((m: any) => m.id !== draft.id)
                            .map((m: any) => (
                              <option key={m.id} value={m.id}>
                                {m.display_name}
                              </option>
                            )),
                        )}
                      </select>
                    </label>
                  </>
                ),
              )}
              <label>
                {translateNode(
                  draft.id
                    ? "New password (leave blank to keep it)"
                    : "Initial password",
                )}
                <input
                  type="password"
                  autoComplete="new-password"
                  required={!draft.id}
                  minLength={15}
                  maxLength={128}
                  value={draft.password}
                  onChange={(e) => update("password", e.target.value)}
                />
              </label>
              <p className="muted">
                {t(
                  "Choose a strong password of 15\u2013128 characters. Users can change their password from the account menu.",
                )}
              </p>
              {translateNode(
                draft.id && (
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      disabled={
                        draft.id === user.id || draft.id === "local-admin"
                      }
                      checked={draft.active}
                      onChange={(e) => update("active", e.target.value)}
                    />
                    {t("Account active")}
                  </label>
                ),
              )}
              <Button
                disabled={saving || draft.expected_version !== data.version}
              >
                {translateNode(saving ? "Saving…" : "Save account")}
              </Button>
            </form>
          </Modal>
        ),
      )}
    </section>
  );
}
