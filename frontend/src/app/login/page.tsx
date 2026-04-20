"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, register, APIError } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (mode === "login") {
        const token = await login(email, password);
        localStorage.setItem("token", token);
        router.push("/");
      } else {
        await register(email, password, fullName || undefined);
        const token = await login(email, password);
        localStorage.setItem("token", token);
        router.push("/");
      }
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.message);
      } else {
        setError("Something went wrong. Try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <span className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm">P</span>
          <span className="font-semibold text-base tracking-tight">PropEdge Pro</span>
        </div>

        <div className="card p-6">
          {/* Tab toggle */}
          <div className="flex border border-border rounded-lg p-0.5 mb-6 bg-surface-overlay">
            {(["login", "register"] as const).map(m => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(null); }}
                className={cn(
                  "flex-1 py-1.5 text-sm font-medium rounded-md transition-all",
                  mode === m ? "bg-surface text-text-primary shadow-sm" : "text-text-secondary hover:text-text-primary",
                )}
              >
                {m === "login" ? "Sign In" : "Create Account"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  placeholder="Optional"
                  className="w-full bg-surface-overlay border border-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent placeholder-text-muted"
                />
              </div>
            )}
            <div>
              <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full bg-surface-overlay border border-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent placeholder-text-muted"
              />
            </div>
            <div>
              <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="w-full bg-surface-overlay border border-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent placeholder-text-muted"
              />
            </div>

            {error && (
              <p className="text-xs text-ev-negative bg-ev-negative-muted border border-ev-negative/20 rounded px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 bg-accent text-white rounded font-medium text-sm hover:bg-accent/80 transition-colors disabled:opacity-50"
            >
              {loading ? "…" : mode === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>
        </div>

        <p className="text-center text-2xs text-text-muted mt-4">
          Free accounts get 5 props/request.{" "}
          <a href="/pricing" className="text-accent hover:underline">See pricing →</a>
        </p>
      </div>
    </div>
  );
}
