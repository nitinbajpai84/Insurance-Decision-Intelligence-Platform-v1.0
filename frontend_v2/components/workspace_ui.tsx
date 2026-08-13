"use client";

/**
 * Shared business-workspace UI primitives, including three AI affordances:
 *   - KpiTile: white tile + delta badge + "Ask why →" + glossary-popover label
 *   - MetricLabel: clickable label → popover with glossary definition + sources
 *   - AskWhy: routes to /ai-intelligence-v2 with a pre-filled contextual question
 *   - ViewEvidence: links a recommendation to the Insight Evidence Hub
 *
 * Accent: centralized in the `accent` helpers below — change the palette in
 * one place (tailwind.config.js `brand` colors) and every page updates.
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowDownRight, ArrowUpRight, HelpCircle, Info, RefreshCw, Search } from "lucide-react";

export const ROLES = [
  "Executive Leadership",
  "Agency Manager",
  "Campaign Manager",
  "Sales Director",
  "Insurance Agent",
  "Claims Manager",
  "Data Analyst"
];

// Centralized accent classes (brand indigo).
export const accent = {
  text: "text-brand-orange",
  bg: "bg-brand-orange",
  bgHover: "hover:bg-brand-orangeDark",
  ring: "focus:ring-brand-orange/20",
  soft: "bg-brand-orange/10",
  border: "border-brand-orange/30"
};

// ---------------------------------------------------------------------------
// Glossary cache + popover
// ---------------------------------------------------------------------------
let _glossaryCache: any[] | null = null;
let _glossaryPromise: Promise<any[]> | null = null;

async function loadGlossary(): Promise<any[]> {
  if (_glossaryCache) return _glossaryCache;
  if (!_glossaryPromise) {
    const { dataV2 } = await import("@/services/dataV2");
    _glossaryPromise = dataV2
      .glossary()
      .then((g) => {
        _glossaryCache = g || [];
        return _glossaryCache;
      })
      .catch(() => {
        _glossaryCache = [];
        return _glossaryCache;
      });
  }
  return _glossaryPromise;
}

export function MetricLabel({ children, term }: { children: React.ReactNode; term?: string }) {
  const [open, setOpen] = useState(false);
  const [entry, setEntry] = useState<any | null>(null);
  const [loaded, setLoaded] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const lookup = term || (typeof children === "string" ? children : "");

  useEffect(() => {
    if (!open || loaded) return;
    loadGlossary().then((g) => {
      const l = lookup.toLowerCase();
      setEntry(
        g.find((t) => (t.term || "").toLowerCase() === l) ||
          g.find((t) => (t.term || "").toLowerCase().includes(l) || l.includes((t.term || "").toLowerCase())) ||
          null
      );
      setLoaded(true);
    });
  }, [open, loaded, lookup]);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <span ref={ref} className="relative inline-flex items-center gap-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-gray-500 hover:text-gray-800"
      >
        {children}
        <Info size={11} className="text-gray-400" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 w-72 rounded-lg border border-gray-200 bg-white p-3 text-left shadow-lg">
          <p className="text-sm font-bold text-gray-900">{entry?.term || lookup}</p>
          {!loaded ? (
            <p className="mt-1 text-xs text-gray-400">Loading definition…</p>
          ) : entry ? (
            <>
              <p className="mt-1 text-sm leading-5 text-gray-700">{entry.definition}</p>
              {entry.synonyms && <p className="mt-2 text-xs text-gray-500">Also: {entry.synonyms}</p>}
              <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                Domain: {entry.domain || "—"} · source: business_glossary
              </p>
            </>
          ) : (
            <p className="mt-1 text-xs text-gray-500">
              Derived metric — computed in the DuckDB semantic view. No glossary entry yet.
            </p>
          )}
        </div>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Ask why + View evidence
// ---------------------------------------------------------------------------
export function AskWhy({ question, role }: { question: string; role?: string }) {
  const href = `/ai-intelligence-v2?${new URLSearchParams({ q: question, ...(role ? { role } : {}) }).toString()}`;
  return (
    <Link
      href={href}
      title="Ask the AI why"
      className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${accent.text} hover:underline`}
    >
      <HelpCircle size={12} /> Ask why
    </Link>
  );
}

export function ViewEvidence({ href = "/insight-evidence-hub-v2", label = "View evidence" }: { href?: string; label?: string }) {
  return (
    <Link href={href} className={`inline-flex items-center gap-1 text-xs font-semibold ${accent.text} hover:underline`}>
      {label} <ArrowUpRight size={13} />
    </Link>
  );
}

// ---------------------------------------------------------------------------
// KPI tile
// ---------------------------------------------------------------------------
export function KpiTile({
  label,
  value,
  delta,
  term,
  askWhy,
  role,
  tone = "neutral"
}: {
  label: string;
  value: string;
  delta?: number | null;
  term?: string;
  askWhy?: string;
  role?: string;
  tone?: "neutral" | "good" | "bad" | "warn";
}) {
  const toneRing =
    tone === "good" ? "border-green-100" : tone === "bad" ? "border-brand-rose/20" : tone === "warn" ? "border-amber-100" : "border-gray-100";
  const toneBar =
    tone === "good" ? "bg-green-400" : tone === "bad" ? "bg-brand-rose" : tone === "warn" ? "bg-amber-400" : "bg-brand-orange/40";
  return (
    <div className={`group relative overflow-hidden rounded-xl border ${toneRing} bg-white p-4 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:shadow-glow`}>
      <div className={`absolute inset-x-0 top-0 h-0.5 ${toneBar}`} />
      <div className="flex items-start justify-between gap-2">
        <MetricLabel term={term}>{label}</MetricLabel>
        {askWhy && <AskWhy question={askWhy} role={role} />}
      </div>
      <div className="mt-2 flex items-end justify-between gap-2">
        <span className="text-2xl font-bold tracking-tight text-gray-900">{value}</span>
        {delta !== undefined && delta !== null && Number.isFinite(delta) && (
          <span
            className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-bold ${
              delta >= 0 ? "bg-green-50 text-green-600" : "bg-brand-rose/10 text-brand-rose"
            }`}
          >
            {delta >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
            {Math.abs(delta).toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layout helpers
// ---------------------------------------------------------------------------
export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div>
      <p className={`text-xs font-bold uppercase tracking-wide ${accent.text}`}>Business workspace</p>
      <h1 className="mt-1 text-2xl font-bold text-gray-900">{title}</h1>
      {subtitle && <p className="mt-1 max-w-3xl text-sm text-gray-500">{subtitle}</p>}
    </div>
  );
}

export function Card({ title, children, right }: { title?: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-card transition-shadow duration-200 hover:shadow-executive">
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title && <h3 className="text-base font-bold tracking-tight text-gray-900">{title}</h3>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function RoleSwitcher({ role, setRole }: { role: string; setRole: (r: string) => void }) {
  return (
    <label className="flex items-center gap-2">
      <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Role</span>
      <select
        value={role}
        onChange={(e) => setRole(e.target.value)}
        className="h-9 rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold outline-none focus:border-brand-orange"
      >
        {ROLES.map((r) => (
          <option key={r}>{r}</option>
        ))}
      </select>
    </label>
  );
}

export function SearchBar({
  value,
  onChange,
  onSubmit,
  placeholder
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit?: () => void;
  placeholder?: string;
}) {
  return (
    <div className="relative flex-1">
      <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onSubmit?.()}
        placeholder={placeholder}
        className="h-11 w-full rounded-lg border border-gray-200 pl-9 pr-3 text-sm outline-none focus:border-brand-orange focus:ring-2 focus:ring-brand-orange/20"
      />
    </div>
  );
}

export function EmptyState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-gray-200 bg-white p-8 text-center">
      <p className="text-sm text-gray-500">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw size={14} /> Retry
        </button>
      )}
    </div>
  );
}

export function Chip({ active, onClick, children }: { active?: boolean; onClick?: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors duration-150 ${
        active ? "border-brand-orange/40 bg-brand-orange/10 text-brand-orange shadow-sm" : "border-gray-200 bg-gray-50 text-gray-700 hover:border-brand-orange/30 hover:text-brand-orange"
      }`}
    >
      {children}
    </button>
  );
}

export function RiskBadge({ band }: { band: string }) {
  const b = (band || "").toLowerCase();
  const cls =
    b === "very_high" || b === "high"
      ? "bg-brand-rose/10 text-brand-rose"
      : b === "medium"
        ? "bg-amber-50 text-amber-700"
        : "bg-green-50 text-green-700";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${cls}`}>{(band || "low").replace(/_/g, " ")}</span>;
}

export function BarList({ items, color = "bg-brand-orange" }: { items: { label: string; value: number; pct?: number }[]; color?: string }) {
  const max = Math.max(1, ...items.map((i) => i.pct ?? i.value));
  return (
    <div className="space-y-3">
      {items.map((it) => {
        const w = Math.max(2, Math.round(((it.pct ?? it.value) / max) * 100));
        return (
          <div key={it.label}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="font-medium text-gray-700">{it.label}</span>
              <span className="font-bold text-gray-900">{it.pct !== undefined ? `${it.pct}%` : it.value.toLocaleString()}</span>
            </div>
            <div className="h-2.5 rounded-full bg-gray-100">
              <div className={`h-2.5 rounded-full ${color} transition-[width] duration-500 ease-out`} style={{ width: `${w}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Tiny hook: run an async loader, expose {data, loading, error, reload}. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): {
  data: T | null;
  loading: boolean;
  error: string;
  reload: () => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    loader()
      .then((d) => active && setData(d))
      .catch((e) => active && setError((e as Error).message || "Request failed"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, loading, error, reload: () => setTick((t) => t + 1) };
}
