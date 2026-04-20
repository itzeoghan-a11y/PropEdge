"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { getMe, updateMe, swrKeys, APIError } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  return (
    <Suspense>
      <SettingsContent />
    </Suspense>
  );
}

function SettingsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const upgraded = searchParams.get("upgraded") === "1";

  const { data: user, mutate } = useSWR(swrKeys.me(), getMe);

  const [alertMinEv, setAlertMinEv] = useState(0.05);
  const [alertMinConf, setAlertMinConf] = useState(60);
  const [alertSteam, setAlertSteam] = useState(true);
  const [discordWebhook, setDiscordWebhook] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setAlertMinEv(user.alert_min_ev ?? 0.05);
      setAlertMinConf(user.alert_min_confidence ?? 60);
      setAlertSteam(user.alert_steam ?? true);
      setDiscordWebhook(user.discord_webhook ?? "");
    }
  }, [user]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateMe({
        alert_min_ev: alertMinEv,
        alert_min_confidence: alertMinConf,
        alert_steam: alertSteam,
        discord_webhook: discordWebhook || undefined,
      });
      await mutate();
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err instanceof APIError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("token");
    router.push("/login");
  }

  const tierColor = user?.tier === "elite" ? "text-elite" : user?.tier === "pro" ? "text-accent" : "text-text-secondary";

  return (
    <div className="max-w-2xl mx-auto px-6 py-6 space-y-6">
      <header>
        <h1 className="text-base font-semibold">Settings</h1>
        <p className="text-xs text-text-muted mt-0.5">Account preferences · Alert thresholds · Notification channels</p>
      </header>

      {upgraded && (
        <div className="bg-ev-positive/10 border border-ev-positive/30 rounded-lg px-4 py-3 text-sm text-ev-positive">
          Subscription activated! Your account has been upgraded.
        </div>
      )}

      {/* Account info */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Account</h2>
          {user && (
            <span className={cn("badge text-xs capitalize font-semibold border", tierColor,
              user.tier === "elite" ? "bg-elite/10 border-elite/30" :
              user.tier === "pro" ? "bg-accent/10 border-accent/30" :
              "bg-surface-overlay border-border"
            )}>
              {user.tier} tier
            </span>
          )}
        </div>
        <div className="p-4 space-y-2">
          {user && (
            <>
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-muted">Email</span>
                <span className="text-text-primary font-mono">{user.email}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-muted">Subscription</span>
                <span className={cn("text-sm capitalize", user.subscription_status === "active" ? "text-ev-positive" : "text-text-muted")}>
                  {user.subscription_status}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-muted">Prop limit</span>
                <span className="text-text-secondary">{user.daily_prop_limit ?? "Unlimited"} per request</span>
              </div>
            </>
          )}
          {user?.tier === "free" && (
            <div className="pt-2">
              <a
                href="/pricing"
                className="inline-flex items-center gap-1.5 text-xs text-accent hover:underline font-medium"
              >
                Upgrade for unlimited access →
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Alert preferences */}
      <form onSubmit={handleSave} className="space-y-4">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Alert Preferences</h2>
          </div>
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Min EV for alerts</label>
                <select
                  value={alertMinEv}
                  onChange={e => setAlertMinEv(parseFloat(e.target.value))}
                  className="w-full bg-surface-overlay border border-border rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
                >
                  <option value={0.03}>3%</option>
                  <option value={0.05}>5%</option>
                  <option value={0.08}>8%</option>
                  <option value={0.10}>10%</option>
                </select>
              </div>
              <div>
                <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Min Confidence for alerts</label>
                <select
                  value={alertMinConf}
                  onChange={e => setAlertMinConf(parseFloat(e.target.value))}
                  className="w-full bg-surface-overlay border border-border rounded px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-accent"
                >
                  <option value={50}>50</option>
                  <option value={60}>60</option>
                  <option value={70}>70</option>
                  <option value={80}>80</option>
                </select>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="steam-alerts"
                checked={alertSteam}
                onChange={e => setAlertSteam(e.target.checked)}
                className="w-4 h-4 rounded border-border accent-accent"
              />
              <label htmlFor="steam-alerts" className="text-sm text-text-secondary">
                Include steam move alerts
              </label>
            </div>
          </div>
        </div>

        {/* Notification channels */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Notifications</h2>
            <span className="text-2xs text-text-muted">Pro+ only</span>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <label className="text-2xs text-text-muted uppercase tracking-wide block mb-1">Discord Webhook URL</label>
              <input
                type="url"
                value={discordWebhook}
                onChange={e => setDiscordWebhook(e.target.value)}
                placeholder="https://discord.com/api/webhooks/..."
                className="w-full bg-surface-overlay border border-border rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent placeholder-text-muted font-mono"
              />
              <p className="text-2xs text-text-muted mt-1">
                Paste your Discord channel webhook. PropEdge will post +EV alerts directly to your channel.
              </p>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-accent text-white rounded text-sm font-medium hover:bg-accent/80 transition-colors disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
          {saved && <span className="text-xs text-ev-positive">Saved!</span>}
          {error && <span className="text-xs text-ev-negative">{error}</span>}
          <div className="flex-1" />
          <button
            type="button"
            onClick={handleLogout}
            className="px-4 py-2 bg-surface-overlay border border-border text-text-secondary rounded text-sm hover:border-ev-negative/40 hover:text-ev-negative transition-colors"
          >
            Sign Out
          </button>
        </div>
      </form>
    </div>
  );
}
