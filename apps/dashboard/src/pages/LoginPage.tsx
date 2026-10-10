import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Button, Field, inputClass } from "../components/layout";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-16">
      <div className="w-full max-w-sm animate-rise">
        <div className="mb-6 flex items-center gap-2">
          <svg viewBox="0 0 32 32" className="h-8 w-8 text-signal" aria-hidden>
            <rect x="8" y="19" width="4" height="6" rx="1" fill="currentColor" />
            <rect x="14" y="14" width="4" height="11" rx="1" fill="currentColor" opacity="0.7" />
            <rect x="20" y="8" width="4" height="17" rx="1" fill="currentColor" opacity="0.4" />
          </svg>
          <div>
            <p className="font-display text-xl font-semibold tracking-tight">NetQuota</p>
            <p className="text-xs text-muted">Household usage & quota console</p>
          </div>
        </div>

        <form
          onSubmit={submit}
          className="space-y-4 rounded-card border border-line bg-surface p-5 shadow-meter"
        >
          <Field label="Administrator">
            <input
              value={username}
              autoComplete="username"
              onChange={(e) => setUsername(e.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
          </Field>
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" disabled={busy || !password} className="w-full">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-faint">
          Self-hosted. The dashboard never sees device or router credentials.
        </p>
      </div>
    </div>
  );
}