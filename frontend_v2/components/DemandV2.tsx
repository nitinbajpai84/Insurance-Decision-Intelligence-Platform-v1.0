"use client";

/** Market Demand process page (Prompt 19-B). */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { ArrowDownRight, ArrowUpRight, HelpCircle, Loader2, Minus } from "lucide-react";
import { getDemand, askWhyHref, type Demand } from "@/services/processApi";

const LINES = ["Health", "Savings", "Protection", "Investment"];
const LINE_COLORS: Record<string, string> = { Health: "#D04A02", Savings: "#EB8C00", Protection: "#7c3aed", Investment: "#16a34a" };

export default function DemandV2() {
  const [data, setData] = useState<Demand | null>(null);
  const [err, setErr] = useState("");
  const [region, setRegion] = useState("Singapore");

  useEffect(() => {
    setData(null); setErr("");
    getDemand({ region }).then(setData).catch((e) => setErr(e.message));
  }, [region]);

  // pivot: one row per month, a column per product line (demand_index)
  const pivot = useMemo(() => {
    if (!data) return [];
    const byMonth: Record<string, Record<string, number>> = {};
    for (const r of data.series) {
      byMonth[r.month] = byMonth[r.month] || { month: r.month };
      byMonth[r.month][r.product_line] = (byMonth[r.month][r.product_line] || 0) + (r.demand_index || 0);
    }
    return Object.values(byMonth).sort((a: any, b: any) => String(a.month).localeCompare(String(b.month)));
  }, [data]);

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <p className="text-xs font-bold uppercase tracking-wide text-pwc-orange">Business processes</p>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">Market Demand</h1>
          <p className="mt-1 text-sm text-gray-500">Demand index (quotes + leads + responses) by product line and region, vs realized policies.</p>
        </div>
        <select value={region} onChange={(e) => setRegion(e.target.value)} className="h-10 rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm font-semibold">
          {["Singapore", "Hong Kong"].map((r) => <option key={r}>{r}</option>)}
        </select>
      </div>

      {err && <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{err}</div>}
      {!data && !err && <div className="mt-8 flex justify-center text-gray-400"><Loader2 className="animate-spin" /></div>}

      {data && (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {data.demand_callouts.map((c) => (
              <article key={c.product_line} className="rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-wide text-gray-500">{c.product_line}</p>
                  <Link href={askWhyHref(`Why is demand for ${c.product_line} ${c.direction} in ${region}?`, { process_id: "market_demand", page: "demand" })} className="text-gray-300 hover:text-pwc-orange"><HelpCircle size={14} /></Link>
                </div>
                <p className={`mt-1 flex items-center gap-1 text-lg font-bold ${c.direction === "rising" ? "text-green-600" : c.direction === "falling" ? "text-red-600" : "text-gray-600"}`}>
                  {c.direction === "rising" ? <ArrowUpRight size={18} /> : c.direction === "falling" ? <ArrowDownRight size={18} /> : <Minus size={18} />}
                  {c.growth_pct ?? 0}%
                </p>
                <p className="text-xs text-gray-400">{c.direction} (last 3mo vs prior 3mo)</p>
              </article>
            ))}
          </div>

          <section className="mt-5 rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
            <h3 className="text-base font-bold text-gray-900">Demand index trend by product line — {region}</h3>
            <ResponsiveContainer width="100%" height={340}>
              <LineChart data={pivot} margin={{ left: 4, right: 20, top: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="month" tick={{ fontSize: 10 }} tickFormatter={(m) => String(m).slice(0, 7)} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                {LINES.map((l) => <Line key={l} type="monotone" dataKey={l} stroke={LINE_COLORS[l]} dot={false} strokeWidth={2} />)}
              </LineChart>
            </ResponsiveContainer>
          </section>
        </>
      )}
    </div>
  );
}
