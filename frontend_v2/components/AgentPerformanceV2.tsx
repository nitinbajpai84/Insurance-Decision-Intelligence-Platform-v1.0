"use client";

/**
 * AgentPerformanceV2 — fleet view. 4 filters + refresh, 6 fleet KPI tiles,
 * leaderboard table, Rising Stars and MDRT panels.
 */
import { useEffect, useState } from "react";
import { RefreshCw, TrendingUp } from "lucide-react";
import { dataV2, money, num, pct, titleCase } from "@/services/dataV2";
import { AskWhy, Card, EmptyState, KpiTile, PageHeader } from "@/components/workspace_ui";

const REGIONS = ["", "Singapore", "Hong Kong"];
const SEGMENTS = ["", "family_protection", "young_professional", "affluent_wealth", "retirement_planner", "health_focused", "sme_owner"];
const PRODUCTS = ["", "life", "health", "critical_illness", "wealth", "savings", "investment_linked"];
const CHANNELS = ["", "exclusive", "partner", "independent", "broker", "direct"];

export default function AgentPerformanceV2() {
  const [region, setRegion] = useState("");
  const [segment, setSegment] = useState("");
  const [product, setProduct] = useState("");
  const [customerType, setCustomerType] = useState("");
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setData(await dataV2.leaderboard({ region, segment, product, customer_type: customerType }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [region]);

  const board: any[] = data?.leaderboard || [];
  const rising: any[] = data?.rising_stars || [];
  const mdrt: any[] = data?.mdrt || [];

  const fleet = {
    agents: board.length,
    premium: board.reduce((s, r) => s + (r.premium || 0), 0),
    policies: board.reduce((s, r) => s + (r.policies || 0), 0),
    conversion: board.length ? board.reduce((s, r) => s + (r.conversion_rate || 0), 0) / board.length : 0,
    persistency: board.length ? board.reduce((s, r) => s + (r.persistency_rate || 0), 0) / board.length : 0,
    mdrt: mdrt.length
  };

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <PageHeader title="Agent Performance Tracking" subtitle="Fleet productivity, leaderboard, and talent clusters across the distribution force." />

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <Filter label="Region" value={region} setValue={setRegion} options={REGIONS} />
          <Filter label="Segment" value={segment} setValue={setSegment} options={SEGMENTS} />
          <Filter label="Product" value={product} setValue={setProduct} options={PRODUCTS} />
          <Filter label="Channel" value={customerType} setValue={setCustomerType} options={CHANNELS} />
          <button onClick={load} className="inline-flex h-10 items-center gap-1.5 rounded-lg bg-brand-orange px-4 text-sm font-bold text-white hover:bg-brand-orangeDark">
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
        {data?.note && <p className="mt-2 text-xs text-gray-400">{data.note}</p>}
      </Card>

      {loading && <p className="p-6 text-center text-sm text-gray-400">Loading fleet…</p>}
      {error && <EmptyState message={error} onRetry={load} />}

      {!loading && !error && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <KpiTile label="Agents" value={num(fleet.agents)} />
            <KpiTile label="Premium (12m)" term="new business premium" value={money(fleet.premium)} askWhy="What is driving fleet premium?" role="Sales Director" />
            <KpiTile label="Policies (12m)" value={num(fleet.policies)} />
            <KpiTile label="Avg conversion" term="conversion rate" value={pct(fleet.conversion * 100)} />
            <KpiTile label="Avg persistency" term="persistency" value={pct(fleet.persistency)} />
            <KpiTile label="MDRT agents" value={num(fleet.mdrt)} tone="good" />
          </div>

          <Card title="Agent leaderboard">
            <div className="overflow-x-auto thin-scroll">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                  <th className="py-2 pr-3">#</th><th className="py-2 pr-3">Agent</th><th className="py-2 pr-3">Region</th>
                  <th className="py-2 pr-3">Premium</th><th className="py-2 pr-3">Policies</th><th className="py-2 pr-3">Conversion</th>
                  <th className="py-2 pr-3">Persistency</th><th className="py-2 pr-3">Growth</th><th className="py-2">Cluster</th>
                </tr></thead>
                <tbody>
                  {board.slice(0, 25).map((r) => (
                    <tr key={r.agent_id} className="border-t border-gray-100">
                      <td className="py-2 pr-3 font-bold text-gray-400">{r.premium_rank}</td>
                      <td className="py-2 pr-3 font-semibold text-gray-900">{r.display_name}</td>
                      <td className="py-2 pr-3">{r.region}</td>
                      <td className="py-2 pr-3">{money(r.premium)}</td>
                      <td className="py-2 pr-3">{num(r.policies)}</td>
                      <td className="py-2 pr-3">{pct((r.conversion_rate || 0) * 100)}</td>
                      <td className="py-2 pr-3">{pct(r.persistency_rate)}</td>
                      <td className={`py-2 pr-3 font-semibold ${r.growth_pct >= 0 ? "text-green-600" : "text-brand-rose"}`}>{pct(r.growth_pct)}</td>
                      <td className="py-2"><ClusterBadge cluster={r.cluster} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid gap-5 xl:grid-cols-2">
            <Card title="Rising Stars" right={<AskWhy question="Which agents are rising stars and why?" role="Sales Director" />}>
              <ClusterList rows={rising} accentLabel="growth" />
            </Card>
            <Card title="MDRT agents" right={<TrendingUp size={16} className="text-brand-orange" />}>
              <ClusterList rows={mdrt} accentLabel="premium" />
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function Filter({ label, value, setValue, options }: { label: string; value: string; setValue: (v: string) => void; options: string[] }) {
  return (
    <label className="block">
      <span className="text-xs font-bold uppercase tracking-wide text-gray-500">{label}</span>
      <select value={value} onChange={(e) => setValue(e.target.value)} className="mt-1 h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold outline-none focus:border-brand-orange">
        {options.map((o) => <option key={o} value={o}>{o ? titleCase(o) : "All"}</option>)}
      </select>
    </label>
  );
}

function ClusterBadge({ cluster }: { cluster: string }) {
  const cls = cluster === "MDRT" ? "bg-brand-orange/10 text-brand-orange" : cluster === "Elite" ? "bg-brand-tangerine/10 text-brand-tangerine" : cluster === "Rising Stars" ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-600";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${cls}`}>{cluster}</span>;
}

function ClusterList({ rows, accentLabel }: { rows: any[]; accentLabel: string }) {
  if (!rows.length) return <p className="text-sm text-gray-400">No agents in this cluster for the current filters.</p>;
  return (
    <ul className="space-y-2">
      {rows.slice(0, 8).map((r) => (
        <li key={r.agent_id} className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
          <span className="font-semibold text-gray-900">{r.display_name}</span>
          <span className="text-sm text-gray-600">{accentLabel === "growth" ? pct(r.growth_pct) : money(r.premium)}</span>
        </li>
      ))}
    </ul>
  );
}
