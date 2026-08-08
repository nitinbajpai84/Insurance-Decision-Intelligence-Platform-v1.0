"use client";

/**
 * PolicyLapseRiskV2 — 3 filters, 7 KPI tiles, and a lapse-hotspots heatmap row
 * (5 dimension cards, red intensity by avg lapse score).
 */
import { useEffect, useState } from "react";
import { ShieldAlert } from "lucide-react";
import { dataV2, money, num, pct, titleCase } from "@/services/dataV2";
import { AskWhy, Card, EmptyState, KpiTile, PageHeader } from "@/components/workspace_ui";

const REGIONS = ["", "Singapore", "Hong Kong"];
const PRODUCTS = ["", "life", "health", "critical_illness", "wealth", "savings", "investment_linked"];
const SEGMENTS = ["", "family_protection", "young_professional", "affluent_wealth", "retirement_planner", "health_focused", "sme_owner"];

export default function PolicyLapseRiskV2() {
  const [region, setRegion] = useState("");
  const [product, setProduct] = useState("");
  const [segment, setSegment] = useState("");
  const [summary, setSummary] = useState<any | null>(null);
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const f = { region, product, segment };
      const [s, h]: any[] = await Promise.all([dataV2.lapseSummary(f), dataV2.lapseHotspots(f)]);
      setSummary(s);
      setHotspots(h.hotspots || []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const s = summary || {};

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <PageHeader title="Policy Lapse Risk" subtitle="Portfolio lapse exposure and the hotspots that need retention action." />

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <Filter label="Region" value={region} setValue={setRegion} options={REGIONS} />
          <Filter label="Product" value={product} setValue={setProduct} options={PRODUCTS} />
          <Filter label="Segment" value={segment} setValue={setSegment} options={SEGMENTS} />
          <button onClick={load} className="h-10 rounded-lg bg-pwc-orange px-4 text-sm font-bold text-white hover:bg-pwc-orangeDark">Apply</button>
          <div className="ml-auto"><AskWhy question="Which policies are most at risk of lapsing and what should we do?" role="Agency Manager" /></div>
        </div>
      </Card>

      {loading && <p className="p-6 text-center text-sm text-gray-400">Loading lapse risk…</p>}
      {error && <EmptyState message={error} onRetry={load} />}

      {!loading && !error && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            <KpiTile label="Policies at risk" term="lapse" value={num(s.policies_at_risk)} tone="warn" />
            <KpiTile label="Customers at risk" value={num(s.customers_at_risk)} tone="warn" />
            <KpiTile label="Premium at risk" term="premium at risk" value={money(s.premium_at_risk)} tone="bad" askWhy="What is driving premium at risk from lapse?" role="Agency Manager" />
            <KpiTile label="Revenue saved" value={money(s.revenue_saved)} tone="good" />
            <KpiTile label="Avg lapse prob." term="lapse" value={pct((s.avg_lapse_probability || 0) * 100)} />
            <KpiTile label="Top risk product" value={titleCase(s.top_risk_product)} />
            <KpiTile label="Top risk segment" value={titleCase(s.top_risk_segment)} />
          </div>

          <Card title="Lapse hotspots" right={<ShieldAlert size={16} className="text-pwc-rose" />}>
            {hotspots.length === 0 ? (
              <p className="text-sm text-gray-400">No hotspots for these filters.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                {hotspots.map((h) => <Hotspot key={h.dimension} h={h} />)}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function Hotspot({ h }: { h: any }) {
  const score = Number(h.avg_lapse_score) || 0; // 0..1
  // red intensity by score
  const bg = `rgba(208, 74, 2, ${Math.min(0.85, 0.15 + score * 0.8)})`;
  const dark = score > 0.45;
  return (
    <div className="rounded-lg border border-gray-100 p-4 shadow-sm" style={{ background: bg }}>
      <p className={`text-xs font-bold uppercase tracking-wide ${dark ? "text-white/80" : "text-gray-600"}`}>{titleCase(h.dimension)}</p>
      <p className={`mt-1 truncate text-base font-bold ${dark ? "text-white" : "text-gray-900"}`}>{titleCase(h.dimension_value)}</p>
      <div className={`mt-2 space-y-0.5 text-xs ${dark ? "text-white/90" : "text-gray-700"}`}>
        <p>{num(h.policy_count)} policies</p>
        <p>{money(h.premium_at_risk)} at risk</p>
        <p>avg score {(score * 100).toFixed(0)}%</p>
      </div>
    </div>
  );
}

function Filter({ label, value, setValue, options }: { label: string; value: string; setValue: (v: string) => void; options: string[] }) {
  return (
    <label className="block">
      <span className="text-xs font-bold uppercase tracking-wide text-gray-500">{label}</span>
      <select value={value} onChange={(e) => setValue(e.target.value)} className="mt-1 h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold outline-none focus:border-pwc-orange">
        {options.map((o) => <option key={o} value={o}>{o ? titleCase(o) : "All"}</option>)}
      </select>
    </label>
  );
}
