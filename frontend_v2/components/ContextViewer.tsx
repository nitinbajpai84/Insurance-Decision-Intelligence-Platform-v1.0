"use client";

/**
 * ContextViewer — "What I knew when answering this question".
 *
 * Three collapsible sections (schema / glossary / semantic docs), a 6000-token
 * budget bar with per-bucket breakdown, and a "Pin this context" toggle that
 * persists a preference in localStorage keyed by question type.
 */
import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Database, BookOpen, FileText, Pin, PinOff } from "lucide-react";
import type { GlossaryContextItem, SchemaContextItem, SemanticDocItem } from "@/services/apiV2";

const TOKEN_BUDGET = 6000;

export interface ContextViewerProps {
  schema: SchemaContextItem[];
  glossary: GlossaryContextItem[];
  docs: SemanticDocItem[];
  totalTokens?: number; // authoritative count from backend if available
  questionType?: string; // used as the localStorage pin key
}

function estTokens(parts: (string | undefined | null)[]): number {
  const text = parts.filter(Boolean).join(" ");
  return Math.max(0, Math.round(text.length / 4));
}

function Bar({ label, tokens, total, color }: { label: string; tokens: number; total: number; color: string }) {
  const pct = total > 0 ? Math.min(100, Math.round((tokens / total) * 100)) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-semibold text-gray-600">{label}</span>
        <span className="font-mono text-gray-500">{tokens} tok</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-100">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Section({
  icon,
  title,
  count,
  children
}: {
  icon: React.ReactNode;
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-gray-100">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2.5 text-left hover:bg-gray-50"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-gray-800">
          {icon}
          {title}
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-bold text-gray-500">{count}</span>
        </span>
        {open ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
      </button>
      {open && <div className="border-t border-gray-100 px-3 py-2">{children}</div>}
    </div>
  );
}

export default function ContextViewer({ schema, glossary, docs, totalTokens, questionType }: ContextViewerProps) {
  const [pinned, setPinned] = useState(false);
  const pinKey = `meridian_pin_ctx::${questionType || "default"}`;

  useEffect(() => {
    try {
      setPinned(localStorage.getItem(pinKey) === "1");
    } catch {
      /* ignore */
    }
  }, [pinKey]);

  function togglePin() {
    setPinned((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(pinKey, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  const schemaTokens = estTokens(schema.map((s) => `${s.table} ${s.column} ${s.description}`));
  const glossaryTokens = estTokens(glossary.map((g) => `${g.term} ${g.definition}`));
  const docTokens = estTokens(docs.map((d) => `${d.title} ${d.chunk}`));
  const computedTotal = schemaTokens + glossaryTokens + docTokens;
  const usedTotal = totalTokens ?? computedTotal;
  const usedPct = Math.min(100, Math.round((usedTotal / TOKEN_BUDGET) * 100));

  return (
    <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Transparency</p>
          <h3 className="mt-0.5 text-base font-bold text-gray-900">What I knew when answering this question</h3>
        </div>
        <button
          onClick={togglePin}
          className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${
            pinned ? "border-brand-orange/30 bg-brand-orange/10 text-brand-orange" : "border-gray-200 text-gray-500 hover:bg-gray-50"
          }`}
          title="Persist context preference for this question type"
        >
          {pinned ? <Pin size={12} /> : <PinOff size={12} />}
          {pinned ? "Pinned" : "Pin context"}
        </button>
      </div>

      {/* Token budget */}
      <div className="mt-4 rounded-md bg-gray-50 p-3">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className="font-bold uppercase tracking-wide text-gray-500">Token budget</span>
          <span className="font-mono text-gray-600">
            {usedTotal} / {TOKEN_BUDGET} ({usedPct}%)
          </span>
        </div>
        <div className="space-y-2">
          <Bar label="Schema" tokens={schemaTokens} total={TOKEN_BUDGET} color="bg-brand-orange" />
          <Bar label="Glossary" tokens={glossaryTokens} total={TOKEN_BUDGET} color="bg-brand-tangerine" />
          <Bar label="Docs" tokens={docTokens} total={TOKEN_BUDGET} color="bg-brand-yellow" />
        </div>
      </div>

      <div className="mt-4 space-y-2">
        <Section icon={<Database size={15} className="text-brand-orange" />} title="Schema context" count={schema.length}>
          {schema.length === 0 ? (
            <p className="text-sm text-gray-400">No schema retrieved.</p>
          ) : (
            <ul className="space-y-1.5">
              {schema.map((s, i) => (
                <li key={`${s.table}.${s.column}-${i}`} className="text-sm">
                  <span className="font-mono font-semibold text-gray-900">
                    {s.table}.{s.column}
                  </span>
                  {s.description && <span className="text-gray-600"> — {s.description}</span>}
                  {typeof s.score === "number" && (
                    <span className="ml-1 text-xs text-gray-400">({s.score.toFixed(2)})</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section icon={<BookOpen size={15} className="text-brand-tangerine" />} title="Glossary terms" count={glossary.length}>
          {glossary.length === 0 ? (
            <p className="text-sm text-gray-400">No glossary terms looked up.</p>
          ) : (
            <ul className="space-y-1.5">
              {glossary.map((g, i) => (
                <li key={`${g.term}-${i}`} className="text-sm">
                  <span className="font-semibold text-gray-900">{g.term}</span>
                  <span className="text-gray-600"> — {g.definition}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section icon={<FileText size={15} className="text-brand-yellow" />} title="Semantic documents" count={docs.length}>
          {docs.length === 0 ? (
            <p className="text-sm text-gray-400">No documents retrieved.</p>
          ) : (
            <ul className="space-y-2">
              {docs.map((d, i) => (
                <li key={`${d.title}-${i}`} className="text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-gray-900">{d.title}</span>
                    {typeof d.score === "number" && (
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-bold text-gray-500">
                        {d.score.toFixed(2)}
                      </span>
                    )}
                  </div>
                  {d.chunk && <p className="mt-0.5 line-clamp-2 text-gray-600">{d.chunk}</p>}
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </section>
  );
}
