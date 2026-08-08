"use client";

/**
 * APIStatusBanner — real-time backend health from GET /api/v2/health.
 *
 * - all healthy  -> renders nothing (clean UI)
 * - partial      -> amber banner naming the degraded service
 * - fully down   -> red banner with last-known-good timestamp
 */
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { getHealth, type HealthStatus } from "@/services/apiV2";

const POLL_MS = 20000;

type Severity = "ok" | "partial" | "down";

function classify(h: HealthStatus | null): Severity {
  if (!h) return "down";
  const duck = h.duckdb?.status === "ok";
  const lance = h.lancedb?.status === "ok";
  const gemini = !!h.gemini?.api_key_present;
  if (duck && lance && gemini) return "ok";
  if (!duck && !lance && !gemini) return "down";
  return "partial";
}

export default function APIStatusBanner() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [reachable, setReachable] = useState(true);
  const lastGood = useRef<string | null>(null);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const h = await getHealth();
        if (!active) return;
        setHealth(h);
        setReachable(true);
        if (classify(h) === "ok") lastGood.current = new Date().toLocaleString();
      } catch {
        if (!active) return;
        setReachable(false);
        setHealth(null);
      }
    }
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const severity: Severity = reachable ? classify(health) : "down";
  if (severity === "ok") return null;

  if (severity === "down") {
    return (
      <div className="flex items-start gap-3 border border-pwc-rose/30 bg-pwc-rose/10 px-4 py-3 text-sm text-pwc-rose">
        <XCircle size={18} className="mt-0.5 shrink-0" />
        <div>
          <p className="font-semibold">V2 intelligence backend is unavailable.</p>
          <p className="mt-0.5 text-pwc-rose/90">
            Could not reach the agentic API. {lastGood.current ? `Last healthy: ${lastGood.current}.` : "No healthy response yet this session."}
          </p>
        </div>
      </div>
    );
  }

  // partial
  const services: { label: string; up: boolean; note: string }[] = [
    { label: "DuckDB", up: health?.duckdb?.status === "ok", note: "SQL execution unavailable — answers cannot run." },
    { label: "LanceDB", up: health?.lancedb?.status === "ok", note: "Vector search unavailable — answers may lack semantic context." },
    { label: "Gemini API", up: !!health?.gemini?.api_key_present, note: "LLM unavailable — SQL/insight generation will be degraded." }
  ];
  const down = services.filter((s) => !s.up);

  return (
    <div className="flex items-start gap-3 border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      <AlertTriangle size={18} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">Partial service.</span>
          {services.map((s) => (
            <span
              key={s.label}
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${
                s.up ? "bg-green-100 text-green-700" : "bg-pwc-rose/15 text-pwc-rose"
              }`}
            >
              {s.up ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
              {s.label}
            </span>
          ))}
        </div>
        <p className="mt-1 leading-5">{down.map((s) => s.note).join(" ")}</p>
      </div>
    </div>
  );
}
