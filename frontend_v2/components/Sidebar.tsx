"use client";

/**
 * Sidebar — same nav structure as V1 (dark sidebar, active item highlighted),
 * re-toned to the PwC palette: charcoal background, PwC-orange active item.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, Filter, Home, Megaphone, Repeat, Share2, ShieldAlert, ShieldCheck, Sparkles, TrendingUp, UserRound, UsersRound, Workflow } from "lucide-react";
import type { ComponentType } from "react";

interface NavItem {
  href: string;
  label: string;
  short: string;
  icon: ComponentType<{ size?: number }>;
}

// V1's exact sidebar order, with AI Intelligence + Evidence Hub appended.
const NAV: NavItem[] = [
  { href: "/", label: "Home", short: "Home", icon: Home },
  { href: "/know-your-customer", label: "Know Your Customer", short: "KYC", icon: UserRound },
  { href: "/know-your-agent", label: "Know Your Agent", short: "KYA", icon: UsersRound },
  { href: "/campaign-effectiveness", label: "Campaign Effectiveness", short: "Campaigns", icon: Megaphone },
  { href: "/agent-performance", label: "Agent Performance Tracking", short: "Performance", icon: TrendingUp },
  { href: "/policy-lapse-risk", label: "Policy Lapse Risk", short: "Lapse Risk", icon: ShieldAlert },
  { href: "/ai-intelligence-v2", label: "AI Intelligence", short: "AI", icon: Sparkles },
  { href: "/insight-evidence-hub-v2", label: "Insight Evidence Hub", short: "Evidence", icon: Brain },
  { href: "/context-graph-v2", label: "Context Graph", short: "Graph", icon: Share2 }
];

// Prompt 19 — business-process insight pages (grouped in the sidebar).
const PROCESS_NAV: NavItem[] = [
  { href: "/lead-conversion-v2", label: "Lead-to-Conversion", short: "Funnel", icon: Workflow },
  { href: "/repurchase-v2", label: "Customer Repurchase", short: "Repurchase", icon: Repeat },
  { href: "/demand-v2", label: "Market Demand", short: "Demand", icon: TrendingUp },
  { href: "/campaign-process-v2", label: "Campaign Attribution", short: "Attribution", icon: Filter }
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden w-72 shrink-0 flex-col bg-pwc-charcoal text-white lg:flex">
      <div className="border-b border-white/10 px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-pwc-orange">
            <ShieldCheck size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-pwc-yellow">Insurance PoC</p>
            <h1 className="text-lg font-bold leading-tight">Intelligence · V2</h1>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-5 thin-scroll">
        {NAV.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
                active ? "bg-pwc-orange text-white" : "text-gray-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}

        <p className="px-3 pb-1 pt-4 text-[10px] font-bold uppercase tracking-[0.16em] text-gray-500">Business Processes</p>
        {PROCESS_NAV.map((item) => {
          const active = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
                active ? "bg-pwc-orange text-white" : "text-gray-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              <Icon size={18} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/10 p-5">
        <div className="rounded-lg border border-white/10 bg-white/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400">Agentic backend</p>
          <p className="mt-1 text-sm text-gray-200">Parallel context · streaming insight</p>
        </div>
      </div>
    </aside>
  );
}
