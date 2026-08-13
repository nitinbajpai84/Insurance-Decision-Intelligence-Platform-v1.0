"use client";

/** Customer Repurchase process page (Prompt 19-B). */
import { useEffect, useState } from "react";
import Link from "next/link";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { HelpCircle, Loader2 } from "lucide-react";
import { getRepurchase, askWhyHref, type Repurchase } from "@/services/processApi";

const BUCKET_COLORS: Record<string, string> = { "0-6m": "#16a34a", "6-12m": "#D97706", "12-24m": "#3454D1", "24m+": "#9ca3af" };

export default function RepurchaseV2() {
  const [data, setData] = useState<Repurchase | null>(null);
  const [err, setErr] = useState("");
  const [role, setRole] = useState("Agency Manager");

  useEffect(() => {
    setData(null); setErr("");
    getRepurchase({ role }).then(setData).catch((e) => setErr(e.message));
  }, [role]);

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <p className="text-xs font-bold uppercase tracking-wide text-brand-orange">Business processes</p>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">Customer Repurchase</h1>
          <p className="mt-1 text-sm text-gray-500">Repeat-purchase rate, time-to-repurchase, and cross-sell by segment.</p>
        </div>
        <select value={role} onChange={(e) => setRole(e.target.value)} className="h-10 rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm font-semibold">
          {["Executive Leadership", "Agency Manager", "Sales Director", "Insurance Agent"].map((r) => <option key={r}>{r}</option>)}
        </select>
      </div>

      {err && <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{err}</div>}
      {!data && !err && <div className="mt-8 flex justify-center text-gray-400"><Loader2 className="animate-spin" /></div>}

      {data && (
        <>
          {data.scoped_to_agent && <p className="mt-3 inline-block rounded-full bg-brand-orange/10 px-3 py-1 text-xs font-bold text-brand-orange">Scoped to your own book (Insurance Agent)</p>}
          <div className="mt-5 grid gap-4 sm:grid-cols-4">
            <Kpi label="Repurchase rate (6-24mo)" value={`${data.repurchase_rate_pct}%`} q="What is our repurchase rate within 6 to 24 months?" role={role} />
            <Kpi label="Repurchasers" value={data.repurchasers.toLocaleString()} q="How many customers made a second purchase?" role={role} />
            <Kpi label="Cross-line %" value={`${data.cross_line_pct ?? "—"}%`} q="What share of repurchases were a different product line?" role={role} />
            <Kpi label="Cross-sell ratio" value={`${data.cross_sell_ratio ?? "—"}`} q="What is the average number of policies per customer?" role={role} />
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
              <h3 className="text-base font-bold text-gray-900">Repurchase rate by segment</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data.by_segment} layout="vertical" margin={{ left: 40, right: 40 }}>
                  <XAxis type="number" unit="%" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="segment" width={130} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => `${v}%`} />
                  <Bar dataKey="repurchase_rate_pct" fill="#3454D1" radius={[0, 4, 4, 0]}>
                    <LabelList dataKey="repurchase_rate_pct" position="right" formatter={(v) => `${v}%`} style={{ fontSize: 11 }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </section>

            <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
              <h3 className="text-base font-bold text-gray-900">Time-to-repurchase distribution</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data.time_to_repurchase_distribution} margin={{ left: 10, right: 10 }}>
                  <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {data.time_to_repurchase_distribution.map((d, i) => <Cell key={i} fill={BUCKET_COLORS[d.bucket] || "#3454D1"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-2 text-right">
                <Link href={askWhyHref("Which customer segments repurchase fastest and which products lead to a second purchase?", { role, process_id: "customer_repurchase", page: "repurchase" })}
                  className="inline-flex items-center gap-1 text-xs font-bold text-brand-orange hover:text-brand-orangeDark"><HelpCircle size={13} /> Ask why</Link>
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, q, role }: { label: string; value: string; q: string; role: string }) {
  return (
    <article className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-500">{label}</p>
        <Link href={askWhyHref(q, { role, process_id: "customer_repurchase", page: "repurchase" })} className="text-gray-300 hover:text-brand-orange"><HelpCircle size={15} /></Link>
      </div>
      <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
    </article>
  );
}
