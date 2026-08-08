"use client";

/**
 * BusinessGlossaryEditor — governed business-meaning editor (new in V2).
 *
 * Table of all business_glossary terms with search/filter, inline edit with a
 * red-strikethrough/green diff preview, a required "why" reason, and an audit
 * line under each term. Saving calls POST /api/v2/glossary/update (backend
 * re-embeds into LanceDB). Locked terms (inactive) need Admin mode to edit.
 */
import { useEffect, useMemo, useState } from "react";
import { Lock, Pencil, Save, Search, ShieldCheck, X } from "lucide-react";
import { getGlossary, updateGlossaryTerm, type GlossaryTerm } from "@/services/apiV2";

interface SessionAudit {
  by: string;
  reason: string;
  at: string;
}

function isLocked(term: GlossaryTerm): boolean {
  // No dedicated "locked" column in the schema; treat inactive terms as locked.
  return term.active_flag === false;
}

export default function BusinessGlossaryEditor() {
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [query, setQuery] = useState("");
  const [admin, setAdmin] = useState(false);
  const [updatedBy, setUpdatedBy] = useState("console.user");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [rowError, setRowError] = useState("");
  const [notice, setNotice] = useState("");
  const [sessionAudit, setSessionAudit] = useState<Record<string, SessionAudit>>({});

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    setLoadError("");
    try {
      setTerms(await getGlossary());
    } catch (err) {
      setLoadError((err as Error).message || "Failed to load glossary.");
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return terms;
    return terms.filter(
      (t) =>
        t.term.toLowerCase().includes(q) ||
        (t.domain || "").toLowerCase().includes(q) ||
        (t.definition || "").toLowerCase().includes(q)
    );
  }, [terms, query]);

  function startEdit(term: GlossaryTerm) {
    setEditingId(term.glossary_id);
    setDraft(term.definition);
    setReason("");
    setRowError("");
    setNotice("");
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft("");
    setReason("");
    setRowError("");
  }

  async function save(term: GlossaryTerm) {
    if (draft.trim() === term.definition.trim()) {
      setRowError("Definition is unchanged.");
      return;
    }
    if (reason.trim().length < 3) {
      setRowError("A reason (why you are changing this) is required.");
      return;
    }
    setSaving(true);
    setRowError("");
    try {
      const res = await updateGlossaryTerm(term.glossary_id, draft.trim(), updatedBy.trim() || "console.user", reason.trim());
      const at = new Date().toISOString();
      setSessionAudit((prev) => ({ ...prev, [term.glossary_id]: { by: updatedBy.trim() || "console.user", reason: reason.trim(), at } }));
      setTerms((prev) =>
        prev.map((t) => (t.glossary_id === term.glossary_id ? { ...t, definition: draft.trim(), updated_at: at } : t))
      );
      setNotice(
        res.reembedded
          ? `Updated "${res.term}" and re-embedded in LanceDB.`
          : `Updated "${res.term}". Re-embedding did not complete${res.embed_error ? `: ${res.embed_error}` : "."}`
      );
      cancelEdit();
    } catch (err) {
      setRowError((err as Error).message || "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-lg border border-gray-100 bg-white shadow-sm">
      {/* header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 p-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Governed semantics</p>
          <h3 className="mt-0.5 text-base font-bold text-gray-900">Business glossary editor</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-600">
            Editor
            <input
              value={updatedBy}
              onChange={(e) => setUpdatedBy(e.target.value)}
              className="h-8 w-32 rounded border border-gray-200 px-2 text-sm outline-none focus:border-pwc-orange"
            />
          </label>
          <button
            onClick={() => setAdmin((v) => !v)}
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1.5 text-xs font-bold ${
              admin ? "border-pwc-orange/30 bg-pwc-orange/10 text-pwc-orange" : "border-gray-200 text-gray-500 hover:bg-gray-50"
            }`}
            title="Admin mode can edit locked terms"
          >
            <ShieldCheck size={13} />
            {admin ? "Admin mode on" : "Admin mode off"}
          </button>
        </div>
      </div>

      {/* search */}
      <div className="border-b border-gray-100 p-4">
        <div className="relative max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by term, subject area, or definition"
            className="h-10 w-full rounded-lg border border-gray-200 pl-9 pr-3 text-sm outline-none focus:border-pwc-orange focus:ring-2 focus:ring-pwc-orange/20"
          />
        </div>
      </div>

      {notice && <p className="mx-5 mt-3 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{notice}</p>}
      {loadError && <p className="mx-5 mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">{loadError}</p>}

      {/* table */}
      <div className="thin-scroll overflow-x-auto p-2">
        {loading ? (
          <p className="p-6 text-center text-sm text-gray-400">Loading glossary…</p>
        ) : filtered.length === 0 ? (
          <p className="p-6 text-center text-sm text-gray-400">No terms match “{query}”.</p>
        ) : (
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="px-3 py-2 font-semibold">Term</th>
                <th className="px-3 py-2 font-semibold">Subject area</th>
                <th className="px-3 py-2 font-semibold">Definition</th>
                <th className="px-3 py-2 font-semibold" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((term) => {
                const locked = isLocked(term);
                const editing = editingId === term.glossary_id;
                const audit = sessionAudit[term.glossary_id];
                return (
                  <tr key={term.glossary_id} className="border-t border-gray-100 align-top">
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-1.5 font-semibold text-gray-900">
                        {locked && <Lock size={13} className="text-gray-400" />}
                        {term.term}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600">
                        {term.domain || "—"}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      {editing ? (
                        <div className="space-y-2">
                          {/* diff preview */}
                          <div className="rounded-md border border-gray-100 bg-gray-50 p-2 text-sm">
                            <p className="text-red-600 line-through">{term.definition}</p>
                            <p className="text-green-700">{draft || <span className="italic text-gray-400">empty</span>}</p>
                          </div>
                          <textarea
                            value={draft}
                            onChange={(e) => setDraft(e.target.value)}
                            rows={3}
                            className="w-full rounded border border-gray-200 p-2 text-sm outline-none focus:border-pwc-orange"
                          />
                          <input
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            placeholder="Why are you changing this? (required)"
                            className="w-full rounded border border-gray-200 p-2 text-sm outline-none focus:border-pwc-orange"
                          />
                          {rowError && <p className="text-xs font-semibold text-pwc-rose">{rowError}</p>}
                        </div>
                      ) : (
                        <div>
                          <p className="text-gray-700">{term.definition}</p>
                          <p className="mt-1 text-xs text-gray-400">
                            Last updated
                            {term.updated_at ? ` ${new Date(term.updated_at).toLocaleString()}` : " —"}
                            {term.owner ? ` · owner: ${term.owner}` : ""}
                            {audit ? ` · reason: ${audit.reason}` : ""}
                          </p>
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-right">
                      {editing ? (
                        <div className="flex justify-end gap-1.5">
                          <button
                            onClick={() => save(term)}
                            disabled={saving}
                            className="inline-flex items-center gap-1 rounded bg-pwc-orange px-2.5 py-1.5 text-xs font-bold text-white hover:bg-pwc-orangeDark disabled:opacity-50"
                          >
                            <Save size={13} />
                            {saving ? "Saving…" : "Save"}
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="inline-flex items-center gap-1 rounded border border-gray-200 px-2.5 py-1.5 text-xs font-bold text-gray-600 hover:bg-gray-50"
                          >
                            <X size={13} />
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => startEdit(term)}
                          disabled={locked && !admin}
                          title={locked && !admin ? "Locked — enable Admin mode to edit" : "Edit definition"}
                          className="inline-flex items-center gap-1 rounded border border-gray-200 px-2.5 py-1.5 text-xs font-bold text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {locked && !admin ? <Lock size={13} /> : <Pencil size={13} />}
                          Edit
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
