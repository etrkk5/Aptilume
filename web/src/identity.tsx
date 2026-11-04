import React, { useState, useEffect } from "react";
import { LogIn, LoaderCircle, ShieldCheck } from "lucide-react";
import { api, setCsrf } from "./client";
import { ThemeSwitch } from "./theme";
export function useIdentity() {
  const [user, setUser] = useState<any>(undefined);
  useEffect(() => {
    api("/auth/me")
      .then((u) => {
        setCsrf(u.csrf_token);
        setUser(u);
      })
      .catch(() => setUser(null));
    const expired = () => {
      setCsrf("");
      setUser(null);
    };
    window.addEventListener("aptilume:unauthorized", expired);
    return () => window.removeEventListener("aptilume:unauthorized", expired);
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
        <ThemeSwitch />
      </div>
      <section className="login-intro">
        <img src="/brand/yapi-kredi-logo.svg" alt="Yapı Kredi" />
        <div>
          <span>AI SKILLS INTELLIGENCE</span>
          <h1>Aptilume</h1>
          <p>
            Yetkinliklerinizi keşfedin.
            <br />
            Gelişiminizi birlikte planlayın.
          </p>
        </div>
        <small>Yapı Kredi · Kurum içi yetkinlik platformu</small>
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
          <h2>Hesabınıza giriş yapın</h2>
          <p>Kurumsal kullanıcı adınız ve parolanızla devam edin.</p>
          <label htmlFor="login-user">
            Kullanıcı adı
            <input
              id="login-user"
              required
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Kullanıcı adınız"
            />
          </label>
          <label htmlFor="login-password">
            Parola
            <input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <div className="notice error" role="alert">
              {error}
            </div>
          )}
          <button className="btn primary" disabled={busy}>
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <LogIn size={17} />
            )}{" "}
            Giriş yap
          </button>
          <div className="login-help">
            Giriş sorunu yaşıyorsanız kurumunuzun entegrasyon yöneticisine
            başvurun.
          </div>
        </form>
      </section>
    </div>
  );
}
