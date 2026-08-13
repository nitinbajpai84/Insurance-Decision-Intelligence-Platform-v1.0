"use client";

/** Campaign Effectiveness — process / attribution view (Prompt 19-B). */
import { useEffect, useState } from "react";
import Link from "next/link";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { HelpCircle, Loader2 } from "lucide-react";
import { getCampaignProcess, askWhyHref, type CampaignProcess } from "@/services/processApi";

const FUNNEL_STEPS = ["targeted", "delivered", "opened", "clicked", "responded", "conversions"];

export default function CampaignEffectivenessProcessV2() {
  const [data, setData] = useState<CampaignProcess | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    getCampaignProcess().then(setData).catch((e) => setErr(e.message));
  }, []);

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <p className="text-xs font-bold uppercase tracking-wide text-brand-orange">Business processes</p>
      <h1 className="mt-1 text-2xl font-bold text-gray-900">Campaign Effectiveness — Attribution</h1>
      <p className="mt-1 text-sm text-gray-500">Full funnel with end-to-end premium attribution and ROI leaderboard.</p>

      {err && <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{err}</div>}
      {!data && !err && <div className="mt-8 flex justify-center text-gray-400"><Loader2 className="animate-spin" /></div>}

      {data && (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Conversions" value={Number(data.funnel.conversions || 0).toLocaleString()} q="How many campaign conversions did we get?" />
            <Kpi label="Premium generated" value={`S$${Math.round((data.funnel.premium_generated || 0) / 1000).toLocaleString()}K`} q="How much premium did campaigns generate?" />
            <Kpi label="Budget" value={`S$${Math.round((data.funnel.budget || 0) / 1000).toLocaleString()}K`} q="What was total campaign budget?" />
            <Kpi label="Blended ROI" value={`${data.funnel.roi_multiple ?? "—"}x`} q="What is our blended campaign ROI?" />
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
            <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
              <h3 className="text-base font-bold text-gray-900">Funnel</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={FUNNEL_STEPS.map((s) => ({ step: s, value: data.funnel[s] || 0 }))} layout="vertical" margin={{ left: 20, right: 50 }}>
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="step" width={90} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v) => Number(v).toLocaleString()} />
                  <Bar dataKey="value" fill="#3454D1" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </section>

            <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
              <h3 className="text-base font-bold text-gray-900">ROI by channel</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data.by_channel} margin={{ left: 10, right: 10 }}>
                  <XAxis dataKey="channel" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="roi" fill="#D97706" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </section>
          </div>

          <section className="mt-5 rounded-lg border border-gray-100 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
              <h3 className="text-base font-bold text-gray-900">ROI leaderboard</h3>
              <Link href={askWhyHref("Which campaigns, channels, and segments deliver the best ROI?", { process_id: "campaign_effectiveness", page: "campaign-process", role: "Campaign Manager" })}
                className="inline-flex items-center gap-1 text-xs font-bold text-brand-orange hover:text-brand-orangeDark"><HelpCircle size={13} /> Ask why</Link>
            </div>
            <div className="overflow-x-auto thin-scroll p-2">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-3 py-2">Campaign</th><th className="px-3 py-2">Channel</th><th className="px-3 py-2">Targeted</th><th className="px-3 py-2">Conv.</th><th className="px-3 py-2">Premium</th><th className="px-3 py-2">ROI</th></tr></thead>
                <tbody>
                  {data.roi_leaderboard.map((c, i) => (
                    <tr key={i} className="border-t border-gray-100">
                      <td className="px-3 py-2 font-semibold text-gray-900">{c.campaign}</td>
                      <td className="px-3 py-2 text-gray-600">{c.channel}</td>
                      <td className="px-3 py-2 font-mono">{c.targeted}</td>
                      <td className="px-3 py-2 font-mono">{c.conversions}</td>
                      <td className="px-3 py-2 font-mono">S${Math.round(c.premium_generated).toLocaleString()}</td>
                      <td className="px-3 py-2 font-bold text-brand-orange">{c.roi_multiple ?? "—"}x</td>
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

function Kpi({ label, value, q }: { label: string; value: string; q: string }) {
  return (
    <article className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <p className="text-xs uppercase tracking-wide text-gray-500">{label}</p>
        <Link href={askWhyHref(q, { process_id: "campaign_effectiveness", page: "campaign-process", role: "Campaign Manager" })} className="text-gray-300 hover:text-brand-orange"><HelpCircle size={15} /></Link>
      </div>
      <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
    </article>
  );
}
