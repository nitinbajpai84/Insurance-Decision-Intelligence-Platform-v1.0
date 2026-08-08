"use client";

/**
 * KnowYourAgentV2 — agent search → agent 360. Hero, 6 KPI tiles, MAPA trend,
 * and a customer-portfolio summary.
 */
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { UsersRound } from "lucide-react";
import { dataV2, money, num, pct, titleCase } from "@/services/dataV2";
import { AskWhy, BarList, Card, EmptyState, KpiTile, PageHeader, RoleSwitcher, SearchBar } from "@/components/workspace_ui";

export default function KnowYourAgentV2() {
  const [role, setRole] = useState("Agency Manager");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function search(qv = query) {
    setLoading(true);
    setError("");
    try {
      const r: any = await dataV2.agentsSearch(qv, role, 12);
      setResults(r.results || []);
      if (r.results?.length) selectAgent(r.results[0].agent_id);
      else { setSelected(null); setDetail(null); }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function selectAgent(id: string) {
    setSelected(id);
    try {
      setDetail(await dataV2.agent(id, role));
    } catch (e) {
      setError((e as Error).message);
      setDetail(null);
    }
  }

  useEffect(() => {
    void search("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  const a = detail?.profile;
  const mapa = (detail?.mapa || []).map((m: any) => ({ month: String(m.metric_month).slice(0, 7), meetings: m.meetings, activities: m.activities, proposals: m.proposals, applications: m.applications }));
  const port = detail?.portfolio || {};
  const mix = (detail?.product_mix || []).map((m: any) => ({ label: titleCase(m.line_of_business), value: m.premium }));

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="Know Your Agent" subtitle="Search an agent to see their performance, MAPA funnel, and book of business." />
        <RoleSwitcher role={role} setRole={setRole} />
      </div>

      <Card>
        <div className="flex flex-col gap-2 sm:flex-row">
          <SearchBar value={query} onChange={setQuery} onSubmit={() => search()} placeholder="Agent name or number" />
          <button onClick={() => search()} className="h-11 rounded-lg bg-pwc-orange px-5 text-sm font-bold text-white hover:bg-pwc-orangeDark">Search</button>
        </div>
        {results.length > 1 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {results.slice(0, 8).map((r) => (
              <button key={r.agent_id} onClick={() => selectAgent(r.agent_id)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold ${selected === r.agent_id ? "border-pwc-orange bg-pwc-orange/10 text-pwc-orange" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
                {r.display_name}
              </button>
            ))}
          </div>
        )}
      </Card>

      {loading && <p className="p-6 text-center text-sm text-gray-400">Loading…</p>}
      {error && <EmptyState message={error} onRetry={() => search()} />}

      {a && (
        <>
          <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-pwc-orange/10 text-pwc-orange"><UsersRound size={28} /></div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{a.display_name}</h2>
                  <p className="text-sm text-gray-500">{a.agent_number} · {titleCase(a.channel)} · {a.region} · branch {a.branch}</p>
                </div>
                <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-bold text-gray-700">{titleCase(a.status)} · {a.tenure_years}y tenure</span>
              </div>
              <AskWhy question={`Summarise agent ${a.display_name}'s performance and coaching priorities.`} role={role} />
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <KpiTile label="Monthly premium" term="new business premium" value={money(a.monthly_premium)} delta={a.monthly_premium_delta_pct} askWhy={`Why did ${a.display_name}'s premium change this month?`} role={role} />
              <KpiTile label="Policies sold" value={num(a.policies_sold_mtd)} />
              <KpiTile label="Conversion" term="conversion rate" value={pct((a.conversion_rate || 0) * 100)} />
              <KpiTile label="Persistency" term="persistency" value={pct(a.persistency_rate)} />
              <KpiTile label="Target achieved" value={pct(a.target_achievement_pct)} tone={a.target_achievement_pct >= 100 ? "good" : "warn"} />
              <KpiTile label="Commission (mo)" value={money(a.commission_rolling_month)} />
            </div>
          </section>

          <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
            <Card title="MAPA funnel (monthly trend)">
              {mapa.length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={mapa} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} width={36} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="meetings" stackId="a" fill="#D04A02" />
                    <Bar dataKey="activities" stackId="a" fill="#EB8C00" />
                    <Bar dataKey="proposals" stackId="a" fill="#FFB600" />
                    <Bar dataKey="applications" stackId="a" fill="#2D2D2D" />
                  </BarChart>
                </ResponsiveContainer>
              ) : <p className="text-sm text-gray-400">No MAPA data.</p>}
            </Card>

            <Card title="Customer portfolio">
              <div className="grid gap-3 sm:grid-cols-3">
                <KpiTile label="Customers" value={num(port.customers)} />
                <KpiTile label="Policies" value={num(port.policies)} />
                <KpiTile label="Premium" value={money(port.annual_premium)} />
              </div>
              {mix.length > 0 && (
                <div className="mt-4">
                  <p className="mb-2 text-xs font-bold uppercase tracking-wide text-gray-500">Premium by product line</p>
                  <BarList items={mix} color="bg-pwc-tangerine" />
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
