"use client";

/**
 * GovernedRulesEditor — the "avenue to change" the norms that gate agent
 * answers. decision_rules.threshold_json is what backend_v2/agents/
 * insight_agent.py and graph_sql_agent.py now cite verbatim instead of
 * letting the LLM invent a cut-off (see the norms/B1 work in DEPLOY history).
 *
 * Editing a rule always demotes it to draft server-side — a threshold change
 * cannot silently take effect. Activate is a separate, explicit, reasoned
 * step, same discipline as the Business Glossary editor's reason-required
 * pattern, plus one extra gate since rules directly drive business decisions.
 */
import { useEffect, useState } from "react";
import { editRule, fetchRules, setRuleStatus, type DecisionRule } from "@/services/rulesApi";

function StatusPill({ status }: { status: string }) {
  const active = status === "active";
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
        active
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-amber-200 bg-amber-50 text-amber-700"
      }`}
    >
      {active ? "Active — governs answers" : "Draft — not governing"}
    </span>
  );
}

export default function GovernedRulesEditor() {
  const [rules, setRules] = useState<DecisionRule[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [thresholds, setThresholds] = useState<Record<string, string>>({});
  const [actionText, setActionText] = useState("");
  const [reason, setReason] = useState("");
  const [updatedBy, setUpdatedBy] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  function load() {
    fetchRules().then(setRules).catch((e) => setError(String(e)));
  }
  useEffect(load, []);

  function startEdit(rule: DecisionRule) {
    setEditingId(rule.rule_id);
    const th: Record<string, string> = {};
    Object.entries(rule.threshold_json || {}).forEach(([k, v]) => (th[k] = String(v)));
    setThresholds(th);
    setActionText(rule.action_text || "");
    setReason("");
    setUpdatedBy("");
  }

  function cancelEdit() {
    setEditingId(null);
    setReason("");
  }

  async function saveEdit(rule: DecisionRule) {
    if (!reason.trim() || !updatedBy.trim()) {
      setToast("Name and reason are both required before saving.");
      return;
    }
    setBusy(true);
    try {
      const parsedThresholds: Record<string, number> = {};
      for (const [k, v] of Object.entries(thresholds)) {
        const n = parseFloat(v);
        if (!Number.isNaN(n)) parsedThresholds[k] = n;
      }
      await editRule(rule.rule_id, { threshold_json: parsedThresholds, action_text: actionText }, updatedBy, reason);
      setToast(`"${rule.name}" saved as draft — click Activate to make it governing.`);
      setEditingId(null);
      load();
    } catch (e) {
      setToast(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function toggleStatus(rule: DecisionRule) {
    const who = window.prompt("Your name (for the audit trail):", updatedBy || "");
    if (!who) return;
    const why = window.prompt(
      rule.status === "active" ? "Reason for deactivating this rule:" : "Reason for activating this rule:"
    );
    if (!why || why.trim().length < 3) {
      setToast("A reason of at least a few words is required.");
      return;
    }
    setBusy(true);
    try {
      await setRuleStatus(rule.rule_id, rule.status === "active" ? "deactivate" : "activate", who, why);
      setToast(`"${rule.name}" is now ${rule.status === "active" ? "draft" : "active"}.`);
      load();
    } catch (e) {
      setToast(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Could not load governed rules: {error}
      </p>
    );
  }
  if (!rules) return <p className="text-sm text-gray-500">Loading governed rules…</p>;

  return (
    <div className="space-y-3">
      {toast && (
        <div className="flex items-start justify-between gap-3 rounded-lg border border-brand-orange/30 bg-brand-orange/5 p-3 text-sm text-gray-800">
          <span>{toast}</span>
          <button onClick={() => setToast(null)} className="text-xs font-bold text-brand-orange">
            dismiss
          </button>
        </div>
      )}
      {rules.map((rule) => (
        <div key={rule.rule_id} className="rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-gray-900">{rule.name}</p>
              <p className="mt-0.5 text-xs text-gray-500">{rule.condition_text}</p>
            </div>
            <StatusPill status={rule.status} />
          </div>

          {editingId !== rule.rule_id && (
            <>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Object.entries(rule.threshold_json || {}).map(([k, v]) => (
                  <span
                    key={k}
                    className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[11px] font-semibold text-gray-700"
                  >
                    {k} = {v}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-xs text-gray-600">
                → {rule.action_text} <span className="text-gray-400">(owner: {rule.assigned_role || "unassigned"})</span>
              </p>
              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => startEdit(rule)}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:border-brand-orange hover:text-brand-orange"
                >
                  Edit threshold
                </button>
                <button
                  onClick={() => toggleStatus(rule)}
                  disabled={busy}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-50 ${
                    rule.status === "active"
                      ? "border border-amber-200 text-amber-700 hover:bg-amber-50"
                      : "bg-brand-orange text-white"
                  }`}
                >
                  {rule.status === "active" ? "Deactivate" : "Activate"}
                </button>
              </div>
            </>
          )}

          {editingId === rule.rule_id && (
            <div className="mt-3 space-y-3 rounded-lg border border-brand-orange/30 bg-brand-orange/5 p-3">
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.keys(thresholds).map((metric) => (
                  <label key={metric} className="text-xs">
                    <span className="mb-1 block font-semibold text-gray-600">{metric}</span>
                    <input
                      value={thresholds[metric]}
                      onChange={(e) => setThresholds((t) => ({ ...t, [metric]: e.target.value }))}
                      className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm outline-none focus:border-brand-orange"
                    />
                  </label>
                ))}
              </div>
              <label className="block text-xs">
                <span className="mb-1 block font-semibold text-gray-600">Escalation action</span>
                <input
                  value={actionText}
                  onChange={(e) => setActionText(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm outline-none focus:border-brand-orange"
                />
              </label>
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="text-xs">
                  <span className="mb-1 block font-semibold text-gray-600">Your name</span>
                  <input
                    value={updatedBy}
                    onChange={(e) => setUpdatedBy(e.target.value)}
                    placeholder="e.g. Head of Agency"
                    className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm outline-none focus:border-brand-orange"
                  />
                </label>
                <label className="text-xs">
                  <span className="mb-1 block font-semibold text-gray-600">Reason (required, audited)</span>
                  <input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Why is this changing?"
                    className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm outline-none focus:border-brand-orange"
                  />
                </label>
              </div>
              <p className="text-[11px] text-gray-500">
                Saving demotes this rule to draft. It stops governing answers until you click Activate.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => saveEdit(rule)}
                  disabled={busy}
                  className="rounded-lg bg-brand-orange px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                >
                  Save as draft
                </button>
                <button
                  onClick={cancelEdit}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
