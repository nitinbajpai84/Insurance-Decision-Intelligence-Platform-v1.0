"use client";

/**
 * CampaignEffectivenessV2 — campaign search + medium/date filters, campaign
 * chips, 4 KPI tiles, overview card, and the targeted→conversions funnel.
 */
import { useEffect, useState } from "react";
import { dataV2, money, num, pct, titleCase } from "@/services/dataV2";
import { AskWhy, Card, EmptyState, KpiTile, PageHeader, SearchBar, ViewEvidence } from "@/components/workspace_ui";

const MEDIUMS = ["", "email", "agent_call", "web", "app", "direct_mail", "social", "sms", "partner"];

export default function CampaignEffectivenessV2() {
  const [search, setSearch] = useState("");
  const [medium, setMedium] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [list, setList] = useState<any[]>([]);
  const [selected, setSelected] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const r: any = await dataV2.campaigns({ search, medium, from, to });
      setList(r.results || []);
      if (r.results?.length) selectCampaign(r.results[0].campaign_id);
      else setSelected(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function selectCampaign(id: string) {
    try {
      setSelected(await dataV2.campaign(id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const o = selected?.overview;
  const funnel: any[] = selected?.funnel || [];
  const maxF = Math.max(1, ...funnel.map((f) => f.count));

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <PageHeader title="Campaign Effectiveness" subtitle="Funnel, conversion, and ROI across marketing campaigns." />

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <SearchBar value={search} onChange={setSearch} onSubmit={load} placeholder="Campaign name or code" />
          <label className="block">
            <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Medium</span>
            <select value={medium} onChange={(e) => setMedium(e.target.value)} className="mt-1 h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm font-semibold outline-none focus:border-brand-orange">
              {MEDIUMS.map((m) => <option key={m} value={m}>{m ? titleCase(m) : "All"}</option>)}
            </select>
          </label>
          <DateField label="From" value={from} setValue={setFrom} />
          <DateField label="To" value={to} setValue={setTo} />
          <button onClick={load} className="h-10 rounded-lg bg-brand-orange px-4 text-sm font-bold text-white hover:bg-brand-orangeDark">Apply</button>
        </div>
      </Card>

      {loading && <p className="p-6 text-center text-sm text-gray-400">Loading campaigns…</p>}
      {error && <EmptyState message={error} onRetry={load} />}

      {!loading && !error && list.length > 0 && (
        <>
          <div className="flex flex-wrap gap-2">
            {list.slice(0, 12).map((c) => (
              <button key={c.campaign_id} onClick={() => selectCampaign(c.campaign_id)}
                className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${selected?.overview?.campaign_id === c.campaign_id ? "border-brand-orange bg-brand-orange/10 text-brand-orange" : "border-gray-200 bg-gray-50 text-gray-700 hover:text-brand-orange"}`}>
                {c.campaign_name}
              </button>
            ))}
          </div>

          {o && (
            <>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <KpiTile label="Targeted" value={num(o.targeted)} />
                <KpiTile label="Conversions" value={num(o.conversions)} tone="good" askWhy={`Why did ${o.campaign_name} convert at this rate?`} role="Campaign Manager" />
                <KpiTile label="Premium generated" term="conversion premium" value={money(o.premium_generated)} />
                <KpiTile label="ROI multiple" term="roi" value={`${num(o.roi_multiple)}x`} tone={o.roi_multiple >= 1 ? "good" : "bad"} />
              </div>

              <div className="grid gap-5 xl:grid-cols-[1fr_1.4fr]">
                <Card title="Campaign overview" right={<ViewEvidence />}>
                  <dl className="space-y-2 text-sm">
                    <Row k="Campaign" v={o.campaign_name} />
                    <Row k="Code" v={o.campaign_code} />
                    <Row k="Medium" v={titleCase(o.medium)} />
                    <Row k="Type" v={titleCase(o.campaign_type)} />
                    <Row k="Status" v={titleCase(o.status)} />
                    <Row k="Window" v={`${o.start_date} → ${o.end_date}`} />
                    <Row k="Budget" v={money(o.budget_amount)} />
                    <Row k="Response rate" v={pct(o.response_rate)} />
                    <Row k="Conversion rate" v={pct(o.conversion_rate)} />
                  </dl>
                </Card>

                <Card title="Funnel">
                  <div className="space-y-3">
                    {funnel.map((f, i) => (
                      <div key={f.stage}>
                        <div className="mb-1 flex items-center justify-between text-sm">
                          <span className="font-medium text-gray-700">{f.stage}</span>
                          <span className="font-bold text-gray-900">{num(f.count)}</span>
                        </div>
                        <div className="h-3 rounded-full bg-gray-100">
                          <div className="h-3 rounded-full" style={{ width: `${Math.max(2, Math.round((f.count / maxF) * 100))}%`, background: ["#0F172A", "#25399A", "#3454D1", "#D97706", "#F5A623", "#16a34a"][i % 6] }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            </>
          )}
        </>
      )}
      {!loading && !error && list.length === 0 && <EmptyState message="No campaigns match these filters." onRetry={load} />}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between border-b border-gray-50 pb-1">
      <dt className="text-gray-500">{k}</dt>
      <dd className="font-semibold text-gray-900">{v}</dd>
    </div>
  );
}

function DateField({ label, value, setValue }: { label: string; value: string; setValue: (v: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-bold uppercase tracking-wide text-gray-500">{label}</span>
      <input type="date" value={value} onChange={(e) => setValue(e.target.value)} className="mt-1 h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm outline-none focus:border-brand-orange" />
    </label>
  );
}
