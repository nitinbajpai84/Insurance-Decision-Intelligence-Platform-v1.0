"use client";

/**
 * KnowYourCustomerV2 — search → customer 360. Hero, profile grid, policy
 * portfolio (KPIs + product mix + table), risk/opportunity scores, and the
 * recommended-action card with suggested message.
 */
import { useEffect, useState } from "react";
import { UserRound } from "lucide-react";
import { dataV2, money, num, pct, titleCase } from "@/services/dataV2";
import {
  AskWhy, BarList, Card, Chip, EmptyState, KpiTile, MetricLabel, PageHeader, RiskBadge, RoleSwitcher, SearchBar, ViewEvidence
} from "@/components/workspace_ui";

const CHIPS = ["high lapse", "affluent", "young professional", "retirement"];

export default function KnowYourCustomerV2() {
  const [role, setRole] = useState("Executive Leadership");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function search(q = query) {
    setLoading(true);
    setError("");
    try {
      const r: any = await dataV2.customersSearch(q, role, 12);
      setResults(r.results || []);
      if (r.results?.length) selectCustomer(r.results[0].customer_id);
      else { setSelected(null); setDetail(null); }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function selectCustomer(id: string) {
    setSelected(id);
    try {
      setDetail(await dataV2.customer(id, role));
    } catch (e) {
      setError((e as Error).message);
      setDetail(null);
    }
  }

  useEffect(() => {
    void search("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  const p = detail?.profile;
  const policies = detail?.policies || [];
  const action = detail?.recommended_action;
  const mix = (detail?.product_mix || []).map((m: any) => ({ label: titleCase(m.line_of_business), pct: m.pct }));

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="Know Your Customer" subtitle="Search a customer to see their 360 profile, portfolio, risk scores, and next best action." />
        <RoleSwitcher role={role} setRole={setRole} />
      </div>

      <Card>
        <div className="flex flex-col gap-2 sm:flex-row">
          <SearchBar value={query} onChange={setQuery} onSubmit={() => search()} placeholder="Name, customer ID, or policy number" />
          <button onClick={() => search()} className="h-11 rounded-lg bg-pwc-orange px-5 text-sm font-bold text-white hover:bg-pwc-orangeDark">Search</button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {CHIPS.map((c) => <Chip key={c} onClick={() => { setQuery(c); search(c); }}>{c}</Chip>)}
        </div>
        {results.length > 1 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {results.slice(0, 8).map((r) => (
              <button key={r.customer_id} onClick={() => selectCustomer(r.customer_id)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold ${selected === r.customer_id ? "border-pwc-orange bg-pwc-orange/10 text-pwc-orange" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
                {r.display_name}
              </button>
            ))}
          </div>
        )}
      </Card>

      {loading && <p className="p-6 text-center text-sm text-gray-400">Loading…</p>}
      {error && <EmptyState message={error} onRetry={() => search()} />}

      {p && (
        <>
          {/* Hero */}
          <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-pwc-orange/10 text-pwc-orange">
                  <UserRound size={28} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{p.display_name}</h2>
                  <p className="text-sm text-gray-500">{p.customer_number} · {titleCase(p.region)}</p>
                </div>
                <span className="rounded-full bg-pwc-orange/10 px-3 py-1 text-xs font-bold text-pwc-orange">{titleCase(p.customer_segment)}</span>
              </div>
              <AskWhy question={`Give me a 360 summary of customer ${p.display_name} and what I should do next.`} role={role} />
            </div>

            {/* profile grid */}
            <div className="mt-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Field label="Age" value={p.age ? `${p.age}` : "—"} />
              <Field label="Income band" value={titleCase(p.income_band)} />
              <Field label="Customer since" value={p.customer_since || "—"} />
              <Field label="Advisor" value={p.advisor_name || "—"} />
              <Field label="Location" value={p.city || titleCase(p.region)} />
              <Field label="Preferred channel" value={titleCase(p.preferred_channel)} />
            </div>
          </section>

          {/* portfolio + risk */}
          <div className="grid gap-5 xl:grid-cols-[1.3fr_1fr]">
            <Card title="Policy portfolio">
              <div className="grid gap-3 sm:grid-cols-3">
                <KpiTile label="Active policies" value={num(p.active_policy_count)} />
                <KpiTile label="Annual premium" term="annual premium" value={money(p.annual_premium)} />
                <KpiTile label="Sum assured" term="sum assured" value={money(p.total_sum_assured)} />
              </div>
              {mix.length > 0 && (
                <div className="mt-4">
                  <p className="mb-2 text-xs font-bold uppercase tracking-wide text-gray-500">Product mix</p>
                  <BarList items={mix} />
                </div>
              )}
              <div className="mt-4 overflow-x-auto thin-scroll">
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                    <th className="py-2 pr-3">Policy</th><th className="py-2 pr-3">Product</th><th className="py-2 pr-3">Status</th><th className="py-2 pr-3">Premium</th><th className="py-2">Sum assured</th>
                  </tr></thead>
                  <tbody>
                    {policies.slice(0, 8).map((po: any) => (
                      <tr key={po.policy_id} className="border-t border-gray-100">
                        <td className="py-2 pr-3 font-mono text-xs">{po.policy_number}</td>
                        <td className="py-2 pr-3">{po.product_name}</td>
                        <td className="py-2 pr-3">{titleCase(po.policy_status)}</td>
                        <td className="py-2 pr-3">{money(po.annual_premium)}</td>
                        <td className="py-2">{money(po.sum_assured)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card title="Risk & opportunity">
              <div className="grid gap-3 sm:grid-cols-2">
                <ScoreRow label="Propensity to buy" value={pct((p.propensity_to_buy || 0) * 100)} band={p.propensity_band} />
                <ScoreRow label="Churn risk" band={p.churn_risk_band} />
                <ScoreRow label="Lapse risk" band={p.lapse_risk_band} />
                <ScoreRow label="CLV band" band={p.clv_band} />
              </div>
              <div className="mt-4 rounded-lg border border-pwc-orange/15 bg-pwc-orange/5 p-3">
                <MetricLabel term="next best product">Next best product</MetricLabel>
                <p className="mt-1 text-base font-bold text-gray-900">{p.next_best_product || "—"}</p>
              </div>
            </Card>
          </div>

          {/* recommended action */}
          {action && (
            <Card title="Recommended action" right={<ViewEvidence />}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <span className="rounded-full bg-pwc-orange/10 px-2 py-0.5 text-[11px] font-bold text-pwc-orange">{titleCase(action.action_type)}</span>
                  <p className="mt-2 text-sm text-gray-700">{action.reason}</p>
                  {action.recommended_product && <p className="mt-1 text-sm font-semibold text-gray-900">Product: {action.recommended_product}</p>}
                </div>
                <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-1 text-xs font-bold text-green-700">{Math.round((action.confidence || 0) * 100)}% confidence</span>
              </div>
              {action.suggested_message && (
                <div className="mt-3 rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <p className="text-xs font-bold uppercase tracking-wide text-gray-500">Suggested message · {titleCase(action.preferred_channel)}</p>
                  <p className="mt-1 text-sm italic text-gray-700">“{action.suggested_message}”</p>
                </div>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-1 text-sm font-bold text-gray-900">{value}</p>
    </div>
  );
}

function ScoreRow({ label, value, band }: { label: string; value?: string; band?: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
      <MetricLabel term={label}>{label}</MetricLabel>
      <span className="flex items-center gap-2">
        {value && <span className="text-sm font-bold text-gray-900">{value}</span>}
        {band && <RiskBadge band={band} />}
      </span>
    </div>
  );
}
