"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { getCheckoutUrl, APIError } from "@/lib/api";
import { cn } from "@/lib/utils";

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Try PropEdge with limited access.",
    tier: null,
    features: [
      "5 props per request",
      "Dashboard access",
      "Basic EV filtering",
      "25 bet history rows",
    ],
    excluded: [
      "Steam alerts",
      "Line shopping details",
      "Unlimited props",
      "Backtesting",
    ],
    cta: "Get Started Free",
    href: "/login",
    highlight: false,
  },
  {
    name: "Pro",
    price: "$49",
    period: "per month",
    description: "Full access to the EV engine and line shopping.",
    tier: "pro" as const,
    features: [
      "Unlimited props",
      "Steam alerts (real-time)",
      "Line shopping across all books",
      "Full bet history + P&L",
      "Backtesting",
      "Discord webhook alerts",
      "Best available line flag",
    ],
    excluded: [],
    cta: "Start Pro",
    href: null,
    highlight: true,
  },
  {
    name: "Elite",
    price: "$99",
    period: "per month",
    description: "Everything in Pro, plus sharp money tools.",
    tier: "elite" as const,
    features: [
      "Everything in Pro",
      "Steam + reverse line movement",
      "ML model output (when enabled)",
      "Priority alerts",
      "SMS alerts via Twilio",
      "Higher alert frequency",
    ],
    excluded: [],
    cta: "Start Elite",
    href: null,
    highlight: false,
  },
];

export default function PricingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubscribe(tier: "pro" | "elite") {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    setLoading(tier);
    setError(null);
    try {
      const { checkout_url } = await getCheckoutUrl(tier);
      window.location.href = checkout_url;
    } catch (err) {
      if (err instanceof APIError && err.status === 503) {
        setError("Payments are not yet configured. Contact support.");
      } else {
        setError("Failed to start checkout. Try again.");
      }
      setLoading(null);
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-12 space-y-10">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">Simple, transparent pricing</h1>
        <p className="text-text-secondary mt-2">
          PropEdge surfaces +EV player props automatically. Choose the tier that fits your volume.
        </p>
      </div>

      {error && (
        <div className="text-center">
          <p className="text-sm text-ev-negative bg-ev-negative-muted border border-ev-negative/20 rounded px-4 py-2 inline-block">
            {error}
          </p>
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {PLANS.map(plan => (
          <div
            key={plan.name}
            className={cn(
              "card p-6 flex flex-col gap-4 relative",
              plan.highlight && "border-accent/40 shadow-lg shadow-accent/5",
            )}
          >
            {plan.highlight && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="badge bg-accent text-white border-0 text-xs px-3 py-0.5">Most Popular</span>
              </div>
            )}

            <div>
              <h2 className="font-semibold text-base">{plan.name}</h2>
              <div className="mt-1 flex items-baseline gap-1">
                <span className={cn("text-3xl font-bold font-mono", plan.highlight ? "text-accent" : "text-text-primary")}>
                  {plan.price}
                </span>
                <span className="text-text-muted text-sm">/{plan.period}</span>
              </div>
              <p className="text-text-secondary text-xs mt-2">{plan.description}</p>
            </div>

            <div className="space-y-2 flex-1">
              {plan.features.map(f => (
                <div key={f} className="flex items-center gap-2 text-xs text-text-primary">
                  <svg className="w-3.5 h-3.5 text-ev-positive flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  {f}
                </div>
              ))}
              {plan.excluded.map(f => (
                <div key={f} className="flex items-center gap-2 text-xs text-text-muted">
                  <svg className="w-3.5 h-3.5 text-text-muted flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                  {f}
                </div>
              ))}
            </div>

            {plan.href ? (
              <a
                href={plan.href}
                className={cn(
                  "block text-center py-2 rounded font-medium text-sm transition-colors",
                  "bg-surface-overlay text-text-primary border border-border hover:border-accent/40 hover:text-accent",
                )}
              >
                {plan.cta}
              </a>
            ) : (
              <button
                onClick={() => plan.tier && handleSubscribe(plan.tier)}
                disabled={loading === plan.tier}
                className={cn(
                  "w-full py-2 rounded font-medium text-sm transition-colors",
                  plan.highlight
                    ? "bg-accent text-white hover:bg-accent/80"
                    : "bg-surface-overlay text-text-primary border border-border hover:border-accent/40 hover:text-accent",
                  "disabled:opacity-50",
                )}
              >
                {loading === plan.tier ? "Redirecting…" : plan.cta}
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="text-center space-y-2">
        <p className="text-xs text-text-muted">
          All plans include: real-time odds updates every 30s · Multi-sport (NBA, NFL, MLB, NHL) · No contracts
        </p>
        <p className="text-xs text-text-muted">
          Paid plans billed monthly. Cancel anytime from Settings.
        </p>
      </div>
    </div>
  );
}
