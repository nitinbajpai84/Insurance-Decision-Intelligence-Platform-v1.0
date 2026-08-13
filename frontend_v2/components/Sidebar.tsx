"use client";

/**
 * Sidebar — dark navigation rail with the active item highlighted in the
 * brand accent color.
 *
 * Desktop only (`lg` and up). Below that the same links are served by
 * MobileNav's drawer; both read from components/navItems.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { NAV, PROCESS_NAV, isActive, type NavItem } from "./navItems";

export default function Sidebar() {
  const pathname = usePathname();

  const renderLink = (item: NavItem) => {
    const active = isActive(pathname, item.href);
    const Icon = item.icon;
    return (
      <Link
        key={item.href}
        href={item.href}
        aria-current={active ? "page" : undefined}
        className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
          active ? "bg-brand-orange text-white" : "text-gray-300 hover:bg-white/10 hover:text-white"
        }`}
      >
        <Icon size={18} />
        {item.label}
      </Link>
    );
  };

  return (
    <aside className="hidden w-72 shrink-0 flex-col bg-brand-sidebar text-white lg:flex">
      <div className="border-b border-white/10 px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-brand-orange shadow-glow">
            <ShieldCheck size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-yellow">Meridian</p>
            <h1 className="text-lg font-bold leading-tight">Decision Intelligence</h1>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-5 thin-scroll">
        {NAV.map(renderLink)}

        <p className="px-3 pb-1 pt-4 text-[10px] font-bold uppercase tracking-[0.16em] text-gray-500">Business Processes</p>
        {PROCESS_NAV.map(renderLink)}
      </nav>

      <div className="border-t border-white/10 p-5">
        <div className="rounded-lg border border-white/10 bg-white/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400">Live decision engine</p>
          <p className="mt-1 text-sm text-gray-200">Real-time context · streaming insight</p>
        </div>
      </div>
    </aside>
  );
}
