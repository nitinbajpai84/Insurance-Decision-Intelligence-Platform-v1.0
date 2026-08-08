"use client";

/**
 * SqlBlock — read-only SQL viewer with lightweight keyword highlighting and a
 * Copy SQL button. Shared by the streaming panel, reasoning panel, and pages.
 */
import { useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";

const KEYWORDS = [
  "select", "from", "where", "group by", "order by", "having", "limit", "with",
  "as", "on", "and", "or", "not", "in", "join", "left join", "right join",
  "inner join", "full join", "cross join", "case", "when", "then", "else", "end",
  "cast", "sum", "count", "avg", "min", "max", "coalesce", "nullif", "distinct",
  "over", "partition by", "desc", "asc", "is null", "is not null", "between"
];

const KEYWORD_RE = new RegExp(`\\b(${KEYWORDS.sort((a, b) => b.length - a.length).join("|")})\\b`, "gi");

function highlight(sql: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let key = 0;
  sql.replace(KEYWORD_RE, (match, _g, offset: number) => {
    if (offset > last) nodes.push(<span key={`t${key++}`}>{sql.slice(last, offset)}</span>);
    nodes.push(
      <span key={`k${key++}`} className="font-bold text-pwc-yellow">
        {match.toUpperCase()}
      </span>
    );
    last = offset + match.length;
    return match;
  });
  if (last < sql.length) nodes.push(<span key={`t${key++}`}>{sql.slice(last)}</span>);
  return nodes;
}

export default function SqlBlock({ sql, maxHeight = "20rem" }: { sql: string; maxHeight?: string }) {
  const [copied, setCopied] = useState(false);
  const text = sql || "-- SQL will appear here after generation.";

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="relative">
      <button
        onClick={copy}
        className="absolute right-2 top-2 z-10 inline-flex items-center gap-1 rounded border border-white/15 bg-white/10 px-2 py-1 text-xs font-bold text-gray-100 hover:bg-white/20"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? "Copied" : "Copy SQL"}
      </button>
      <pre
        className="thin-scroll overflow-auto whitespace-pre-wrap break-words rounded-lg bg-pwc-charcoalDark p-4 pr-20 text-xs leading-6 text-gray-100"
        style={{ maxHeight }}
      >
        <code>{highlight(text)}</code>
      </pre>
    </div>
  );
}
