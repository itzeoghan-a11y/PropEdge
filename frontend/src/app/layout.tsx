import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PropEdge Pro — Player Prop Analytics",
  description: "Statistical +EV player prop identification platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-[#0f1117] text-text-primary font-sans antialiased">
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-y-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}

function Sidebar() {
  return (
    <aside className="w-56 flex-shrink-0 border-r border-border bg-surface flex flex-col">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded bg-accent flex items-center justify-center text-white font-bold text-xs">P</span>
          <span className="font-semibold text-sm tracking-tight">PropEdge Pro</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <NavItem href="/" label="Dashboard" icon="grid" />
        <NavItem href="/market" label="Market Intel" icon="activity" />
        <NavItem href="/analytics" label="Analytics" icon="bar-chart" />
        <NavItem href="/players" label="Players" icon="users" />
      </nav>

      {/* User section */}
      <div className="px-4 py-3 border-t border-border">
        <a href="/settings" className="block text-xs text-text-secondary hover:text-text-primary transition-colors py-1">
          Settings
        </a>
        <a href="/pricing" className="block text-xs text-text-secondary hover:text-text-primary transition-colors py-1">
          Upgrade
        </a>
      </div>
    </aside>
  );
}

function NavItem({ href, label, icon }: { href: string; label: string; icon: string }) {
  return (
    <a
      href={href}
      className="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm text-text-secondary hover:text-text-primary hover:bg-surface-overlay transition-all group"
    >
      <span className="w-4 h-4 text-text-muted group-hover:text-text-secondary transition-colors">
        {/* Icons via CSS class — in production use lucide-react */}
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
          {icon === "grid" && <><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></>}
          {icon === "activity" && <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>}
          {icon === "bar-chart" && <><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></>}
          {icon === "users" && <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}
        </svg>
      </span>
      {label}
    </a>
  );
}
