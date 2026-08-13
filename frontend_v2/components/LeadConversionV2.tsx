"use client";

/** Lead-to-Conversion funnel page (Prompt 19-B). */
import { useEffect, useState } from "react";
import Link from "next/link";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { HelpCircle, Loader2 } from "lucide-react";
import { getLeadConversion, askWhyHref, type LeadConversion } from "@/services/processApi";

const STAGE_COLORS = ["#3454D1", "#4A66DA", "#6178E4", "#D97706", "#F2AD5C", "#F5A623"];

export default function LeadConversionV2() {
  const [data, setData] = useState<LeadConversion | null>(null);
  const [err, setErr] = useState("");
  const [role, setRole] = useState("Sales Director");

  useEffect(() => {
    setData(null);
    setErr("");
    getLeadConversion({ role }).then(setData).catch((e) => setErr(e.message));
  }, [role]);

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <p className="text-xs font-bold uppercase tracking-wide text-brand-orange">Business processes</p>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="mt-1 text-2xl font-bold text-gray-900">Lead-to-Conversion</h1>
          <p className="mt-1 text-sm text-gray-500">New-business funnel from lead capture to issued policy.</p>
        </div>
        <select value={role} onChange={(e) => setRole(e.target.value)} className="h-10 rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm font-semibold">
          {["Executive Leadership", "Sales Director", "Agency Manager", "Insurance Agent"].map((r) => <option key={r}>{r}</option>)}
        </select>
      </div>

      {err && <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{err} <button onClick={() => setRole(role)} className="ml-2 font-bold underline">retry</button></div>}
      {!data && !err && <div className="mt-8 flex justify-center text-gray-400"><Loader2 className="animate-spin" /></div>}

      {data && (
        <>
          {data.scoped_to_agent && <p className="mt-3 inline-block rounded-full bg-brand-orange/10 px-3 py-1 text-xs font-bold text-brand-orange">Scoped to your own book (Insurance Agent)</p>}
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <Kpi label="Overall conversion" value={`${data.overall_conversion_pct ?? "—"}%`} q="What is our overall lead to conversion rate?" stage="issued_policy" role={role} />
            <Kpi label="Avg time-to-issue" value={`${data.avg_time_to_issue_days ?? "—"} days`} q="What is the average time to issue a policy from lead?" stage="issued_policy" role={role} />
            <Kpi label="Top drop-off" value={data.top_drop_off_reasons[0] || "—"} q="Where do leads drop off most in the funnel?" stage="opportunity" role={role} />
          </div>

          <section className="mt-5 rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
            <h3 className="text-base font-bold text-gray-900">Funnel (6 stages)</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.stages} layout="vertical" margin={{ left: 30, right: 60 }}>
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="stage_name" width={100} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => Number(v).toLocaleString()} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  <LabelList dataKey="count" position="right" formatter={(v) => Number(v).toLocaleString()} style={{ fontSize: 11, fill: "#374151" }} />
                  {data.stages.map((_, i) => <Cell key={i} fill={STAGE_COLORS[i % STAGE_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-3 overflow-x-auto thin-scroll">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs uppercase tracking-wide text-gray-500"><th className="px-2 py-1">Stage</th><th className="px-2 py-1">Count</th><th className="px-2 py-1">Conv. to next</th><th className="px-2 py-1">Drop-off reasons</th><th /></tr></thead>
                <tbody>
                  {data.stages.map((s) => (
                    <tr key={s.stage_name} className="border-t border-gray-100">
                      <td className="px-2 py-2 font-semibold text-gray-900">{s.stage_order}. {s.stage_name}</td>
                      <td className="px-2 py-2 font-mono">{s.count.toLocaleString()}</td>
                      <td className="px-2 py-2">{s.conversion_to_next_pct != null ? `${s.conversion_to_next_pct}%` : "—"}</td>
                      <td className="px-2 py-2 text-gray-500">{s.drop_off || "—"}</td>
                      <td className="px-2 py-2 text-right">
                        <Link href={askWhyHref(`Why is the ${s.stage_name} stage converting at ${s.conversion_to_next_pct ?? "this"}%?`, { role, process_id: "lead_to_conversion", stage: s.stage_name, page: "lead-conversion" })}
                          className="inline-flex items-center gap-1 text-xs font-bold text-brand-orange hover:text-brand-orangeDark">
                          <HelpCircle size={13} /> Ask why
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value, q, stage, role }: { label: string; value: string; q: string; stage: string; role: string }) {
  return (
    <article className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-500">{label}</p>
        <Link href={askWhyHref(q, { role, process_id: "lead_to_conversion", stage, page: "lead-conversion" })} className="text-gray-300 hover:text-brand-orange" title="Ask why"><HelpCircle size={15} /></Link>
      </div>
      <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
    </article>
  );
}
