import { t, translateNode, formatLocale } from "./i18n";
import React, { useState, useEffect } from "react";
import { LogIn, LoaderCircle, ShieldCheck } from "lucide-react";
import { api, setCsrf } from "./client";
import { ThemeSwitch } from "./theme";
import { LanguageSwitch } from "./language-switch";
export function useIdentity() {
  const [user, setUser] = useState<any>(undefined);
  useEffect(() => {
    const load = () =>
      api("/auth/me")
        .then((u) => {
          setCsrf(u.csrf_token);
          setUser(u);
        })
        .catch(() => setUser(null));
    load();
    const restore = (event: PageTransitionEvent) => {
      if (event.persisted) {
        setUser(undefined);
        setCsrf("");
        load();
      }
    };
    window.addEventListener("pageshow", restore);
    const expired = () => {
      setCsrf("");
      setUser(null);
    };
    window.addEventListener("aptilume:unauthorized", expired);
    return () => {
      window.removeEventListener("aptilume:unauthorized", expired);
      window.removeEventListener("pageshow", restore);
    };
  }, []);
  return {
    user,
    setUser,
    signIn: async (username: string, password: string) => {
      const u = await api("/auth/login", "POST", { username, password });
      setCsrf(u.csrf_token);
      setUser(u);
    },
    signOut: async () => {
      try {
        await api("/auth/logout", "POST");
      } finally {
        setCsrf("");
        setUser(null);
      }
    },
  };
}
export function Login({ onLogin }: any) {
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <div className="login-page">
      <div className="login-theme">
        <LanguageSwitch />
        <ThemeSwitch />
      </div>
      <section className="login-intro">
        <img src="/brand/aptilume-mark.svg" alt={t("Aptilume")} />
        <div>
          <span>{t("AI SKILLS INTELLIGENCE")}</span>
          <h1>{t("Aptilume")}</h1>
          <p>
            {t(" Yetkinliklerinizi ke\u015Ffedin. ")}
            <br />
            {t(" Geli\u015Fiminizi birlikte planlay\u0131n. ")}
          </p>
        </div>
        <small>{t("Measure capability. Illuminate potential.")}</small>
      </section>
      <section className="login-form-wrap">
        <form
          className="login-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await onLogin(username, password);
            } catch (err: any) {
              setError(err.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="login-security">
            <ShieldCheck size={24} />
          </div>
          <h2>{t("Hesab\u0131n\u0131za giri\u015F yap\u0131n")}</h2>
          <p>
            {t(
              "Kullan\u0131c\u0131 ad\u0131n\u0131z ve parolan\u0131zla \u00E7al\u0131\u015Fma alan\u0131n\u0131za eri\u015Fin.",
            )}
          </p>
          <label htmlFor="login-user">
            {t(" Kullan\u0131c\u0131 ad\u0131 ")}
            <input
              id="login-user"
              required
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t("Kullan\u0131c\u0131 ad\u0131n\u0131z")}
            />
          </label>
          <label htmlFor="login-password">
            {t(" Parola ")}
            <input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {translateNode(
            error && (
              <div className="notice error" role="alert">
                {translateNode(error)}
              </div>
            ),
          )}
          <button className="btn primary" disabled={busy}>
            {translateNode(
              busy ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <LogIn size={17} />
              ),
            )}
            {translateNode(" ")}
            {t(" Giri\u015F yap ")}
          </button>
          <div className="login-help">
            {t(
              " Giri\u015F sorunu ya\u015F\u0131yorsan\u0131z kurumunuzun entegrasyon y\u00F6neticisine ba\u015Fvurun. ",
            )}
          </div>
        </form>
      </section>
    </div>
  );
}
