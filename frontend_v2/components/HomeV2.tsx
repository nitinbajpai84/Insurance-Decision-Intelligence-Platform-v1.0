"use client";

/**
 * HomeV2 — Executive Command Center. Hero + Today's Decision Queue (top 3 NBAs),
 * 4 KPI tiles, portfolio momentum, sales mix, distribution channels, recommended
 * actions, and a clickable 5-step data-lineage panel.
 */
import Link from "next/link";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowRight, Sparkles } from "lucide-react";
import { dataV2, money, num, pct, titleCase } from "@/services/dataV2";
import { AskWhy, BarList, Card, EmptyState, KpiTile, PageHeader, useAsync, ViewEvidence } from "@/components/workspace_ui";

const LINEAGE = [
  { step: "Source tables", detail: "policies · customers · campaigns · model_scores" },
  { step: "Semantic views", detail: "v_home_kpis (DuckDB)" },
  { step: "Model scores", detail: "lapse_risk · propensity_to_buy" },
  { step: "Data product API", detail: "GET /api/v2/home/kpis" },
  { step: "This dashboard", detail: "Executive Command Center" }
];

export default function HomeV2() {
  const { data, loading, error, reload } = useAsync<any>(() => dataV2.homeKpis(), []);

  if (loading) return <Shell><p className="p-8 text-center text-sm text-gray-400">Loading command center…</p></Shell>;
  if (error || !data)
    return (
      <Shell>
        <EmptyState message={`Home KPIs unavailable: ${error || "no data"}`} onRetry={reload} />
      </Shell>
    );

  const momentum = (data.portfolio_momentum_monthly || []).map((m: any) => ({
    month: String(m.month).slice(0, 7),
    value: m.index_value
  }));
  const salesMix = (data.sales_mix_by_product_line || []).map((s: any) => ({ label: titleCase(s.line_of_business), pct: s.pct }));
  const channelMix = (data.distribution_channel_mix || []).map((c: any) => ({ label: titleCase(c.channel), pct: c.pct }));
  const queue = data.decision_queue || [];

  return (
    <Shell>
      {/* Hero */}
      <section className="rounded-lg bg-pwc-charcoal p-6 text-white shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-pwc-yellow">Executive Command Center</p>
            <h2 className="mt-1 text-2xl font-bold">New business momentum is {data.new_business_premium_delta_pct >= 0 ? "up" : "down"} this quarter</h2>
            <p className="mt-1 max-w-2xl text-sm text-gray-300">
              {money(data.new_business_premium_90d)} new-business premium in the last 90 days · {pct(data.persistency_13m)} 13-month persistency ·
              {" "}{num(data.high_lapse_exposure_count)} policies in high lapse exposure.
            </p>
          </div>
          <Link
            href="/ai-intelligence-v2?q=What%20is%20driving%20new%20business%20premium%20this%20quarter%3F&role=Executive%20Leadership"
            className="inline-flex items-center gap-2 rounded-lg bg-pwc-orange px-4 py-2.5 text-sm font-bold text-white hover:bg-pwc-orangeDark"
          >
            <Sparkles size={16} /> Ask the AI
          </Link>
        </div>
      </section>

      {/* Decision queue */}
      <Card title="Today's Decision Queue" right={<ViewEvidence label="View evidence" />}>
        {queue.length === 0 ? (
          <p className="text-sm text-gray-400">No open actions in the queue.</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-3">
            {queue.map((a: any, i: number) => (
              <article key={a.next_best_action_id || i} className="rounded-lg border border-gray-100 bg-gray-50 p-4">
                <div className="flex items-center justify-between">
                  <span className="rounded-full bg-pwc-orange/10 px-2 py-0.5 text-[11px] font-bold text-pwc-orange">{titleCase(a.action_type)}</span>
                  <span className="inline-flex items-center gap-0.5 rounded-full bg-green-50 px-2 py-0.5 text-xs font-bold text-green-700">
                    {Math.round((a.priority || 0) * 100)}%
                  </span>
                </div>
                <p className="mt-2 font-bold text-gray-900">{a.customer_name}</p>
                <p className="mt-1 line-clamp-2 text-sm text-gray-600">{a.reason || a.product_name}</p>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-500">{money(a.expected_value)} value</span>
                  <AskWhy question={`Why is ${a.customer_name} the top recommended action today?`} role="Executive Leadership" />
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>

      {/* KPI tiles */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiTile label="New business premium" term="new business premium" value={money(data.new_business_premium_90d)} delta={data.new_business_premium_delta_pct} tone="good" askWhy="Why did new business premium change in the last 90 days?" role="Executive Leadership" />
        <KpiTile label="Persistency (13m)" term="persistency" value={pct(data.persistency_13m)} tone="good" askWhy="What is driving 13-month persistency?" role="Executive Leadership" />
        <KpiTile label="High lapse exposure" term="lapse" value={num(data.high_lapse_exposure_count)} tone="warn" askWhy="Which policies are in high lapse exposure and why?" role="Executive Leadership" />
        <KpiTile label="Campaign conversion" term="conversion rate" value={pct(data.campaign_conversion_rate)} tone="neutral" askWhy="Which campaigns convert best?" role="Campaign Manager" />
      </div>

      {/* Momentum + mixes */}
      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr_1fr]">
        <Card title="Portfolio momentum (indexed)">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={momentum} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
              <XAxis dataKey="month" tick={{ fontSize: 10 }} interval={1} />
              <YAxis tick={{ fontSize: 11 }} width={36} />
              <Tooltip formatter={(v) => `index ${Number(v)}`} />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {momentum.map((_: any, i: number) => (
                  <Cell key={i} fill="#D04A02" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Sales mix by product line">
          {salesMix.length ? <BarList items={salesMix} /> : <p className="text-sm text-gray-400">No data</p>}
        </Card>
        <Card title="Distribution channels">
          {channelMix.length ? <BarList items={channelMix} color="bg-pwc-tangerine" /> : <p className="text-sm text-gray-400">No data</p>}
        </Card>
      </div>

      {/* Data lineage */}
      <Card title="Data lineage">
        <div className="grid gap-3 md:grid-cols-5">
          {LINEAGE.map((l, i) => (
            <Link
              key={l.step}
              href="/glossary-v2"
              className="group rounded-lg border border-gray-100 bg-gray-50 p-3 hover:border-pwc-orange/30 hover:bg-pwc-orange/5"
            >
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-pwc-orange text-xs font-bold text-white">{i + 1}</span>
                <span className="text-sm font-bold text-gray-900">{l.step}</span>
              </div>
              <p className="mt-1 text-xs text-gray-600">{l.detail}</p>
              <span className="mt-1 inline-flex items-center gap-0.5 text-[11px] font-semibold text-pwc-orange opacity-0 group-hover:opacity-100">
                definition <ArrowRight size={11} />
              </span>
            </Link>
          ))}
        </div>
      </Card>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <PageHeader title="Home" subtitle="Executive command center over the live DuckDB book of business." />
      {children}
    </div>
  );
}
