"use client";

/**
 * ContextGraphV2 — interactive node-link view of the semantic/context model
 * with a governed feedback loop. Left: force-directed graph (colour by type,
 * size by degree, edge width by weight, filter chips). Right: GraphFeedbackPanel.
 * Top bar: Adaptation Log + (admin) Review Queue.
 *
 * Auto-applied changes (weights/cache) -> subtle "auto-tuned" toast.
 * Structural changes (edits/edges) -> "submitted for review" toast.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Activity, GitPullRequest, Loader2, ThumbsDown, ThumbsUp } from "lucide-react";
import {
  NODE_COLORS,
  getModel,
  postFeedback,
  type GraphLink,
  type GraphModel,
  type GraphNode
} from "@/services/graphApi";
import GraphFeedbackPanel from "@/components/GraphFeedbackPanel";
import ReviewQueueModal from "@/components/ReviewQueueModal";
import AdaptationLogModal from "@/components/AdaptationLogModal";

// react-force-graph-2d touches window/canvas — load client-side only.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const ADMIN_ROLES = ["Executive Leadership", "Data Analyst"];
const ROLES = ["Executive Leadership", "Agency Manager", "Campaign Manager", "Sales Director", "Insurance Agent", "Claims Manager", "Data Analyst"];

const SUBJECT_CHIPS: { label: string; match: string[] }[] = [
  { label: "Customer", match: ["customer"] },
  { label: "Policy", match: ["policy", "retention"] },
  { label: "Agent", match: ["distribution"] },
  { label: "Campaign", match: ["marketing"] },
  { label: "Claims", match: ["claims"] },
  { label: "ML", match: ["analytics", "decisioning"] }
];
const TYPE_CHIPS = ["term", "metric", "process", "decision", "entity_class"];

interface Toast {
  id: number;
  msg: string;
  kind: "auto" | "review" | "error";
}

export default function ContextGraphV2() {
  const [model, setModel] = useState<GraphModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [role, setRole] = useState("Executive Leadership");
  const [selected, setSelected] = useState<string | null>(null);
  const [showReview, setShowReview] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [edgeAction, setEdgeAction] = useState<GraphLink | null>(null);

  // filters
  const [activeSubjects, setActiveSubjects] = useState<string[]>([]);
  const [activeTypes, setActiveTypes] = useState<string[]>([]);
  const [lowHealthOnly, setLowHealthOnly] = useState(false);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 800, h: 600 });

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    function resize() {
      if (wrapRef.current) setDims({ w: wrapRef.current.clientWidth, h: wrapRef.current.clientHeight });
    }
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [selected]);

  async function load() {
    setLoading(true);
    try {
      setModel(await getModel());
    } catch (err) {
      toast((err as Error).message, "error");
    } finally {
      setLoading(false);
    }
  }

  function toast(msg: string, kind: Toast["kind"]) {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }

  const filtered = useMemo(() => {
    if (!model) return { nodes: [], links: [] };
    let nodes = model.nodes;
    if (activeTypes.length) nodes = nodes.filter((n) => activeTypes.includes(n.type));
    if (activeSubjects.length) {
      const matches = new Set(SUBJECT_CHIPS.filter((c) => activeSubjects.includes(c.label)).flatMap((c) => c.match));
      nodes = nodes.filter((n) => matches.has((n.group || "").toLowerCase()));
    }
    if (lowHealthOnly) nodes = nodes.filter((n) => n.health != null && n.health < 3);
    const ids = new Set(nodes.map((n) => n.id));
    const links = model.links.filter((l) => ids.has(srcId(l)) && ids.has(tgtId(l)));
    return {
      nodes: nodes.map((n) => ({ ...n, val: Math.max(1, n.degree), color: NODE_COLORS[n.type] || "#6b7280" })),
      links: links.map((l) => ({ ...l }))
    };
  }, [model, activeTypes, activeSubjects, lowHealthOnly]);

  async function edgeFeedback(link: GraphLink, type: "confirm" | "reject") {
    try {
      const r = (await postFeedback({ target_type: "edge", target_id: link.id, feedback_type: type, user_role: role })) as { new_weight?: number };
      toast(`Edge ${type}ed — auto-tuned to weight ${r.new_weight}`, "auto");
      setEdgeAction(null);
      await load();
    } catch (err) {
      toast((err as Error).message, "error");
    }
  }

  const isAdmin = ADMIN_ROLES.includes(role);

  return (
    <div className="flex h-[calc(100vh-110px)] flex-col">
      {/* top bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 bg-white px-5 py-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-pwc-orange">Business workspace</p>
          <h1 className="text-xl font-bold text-gray-900">Context Graph</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={role} onChange={(e) => setRole(e.target.value)} className="h-9 rounded-lg border border-gray-200 bg-gray-50 px-2 text-sm font-semibold">
            {ROLES.map((r) => <option key={r}>{r}</option>)}
          </select>
          <button onClick={() => setShowLog(true)} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-gray-200 px-3 text-sm font-bold text-gray-700 hover:bg-gray-50">
            <Activity size={15} /> Adaptation Log
          </button>
          {isAdmin && (
            <button onClick={() => setShowReview(true)} className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-pwc-orange px-3 text-sm font-bold text-white hover:bg-pwc-orangeDark">
              <GitPullRequest size={15} /> Review Queue
            </button>
          )}
        </div>
      </div>

      {/* filter chips */}
      <div className="flex flex-wrap items-center gap-2 border-b border-gray-100 bg-white px-5 py-2 text-xs">
        <span className="font-bold uppercase tracking-wide text-gray-400">Subject</span>
        {SUBJECT_CHIPS.map((c) => (
          <Chip key={c.label} active={activeSubjects.includes(c.label)} onClick={() => toggle(setActiveSubjects, c.label)}>{c.label}</Chip>
        ))}
        <span className="ml-3 font-bold uppercase tracking-wide text-gray-400">Type</span>
        {TYPE_CHIPS.map((t) => (
          <Chip key={t} active={activeTypes.includes(t)} color={NODE_COLORS[t]} onClick={() => toggle(setActiveTypes, t)}>{t}</Chip>
        ))}
        <Chip active={lowHealthOnly} onClick={() => setLowHealthOnly((v) => !v)}>low-health only</Chip>
        <span className="ml-auto text-gray-400">{filtered.nodes.length} nodes · {filtered.links.length} links</span>
      </div>

      {/* body */}
      <div className="flex min-h-0 flex-1">
        <div ref={wrapRef} className="relative min-w-0 flex-1 bg-gray-50">
          {loading ? (
            <div className="flex h-full items-center justify-center text-gray-400"><Loader2 className="animate-spin" /></div>
          ) : (
            <ForceGraph2D
              width={dims.w}
              height={dims.h}
              graphData={filtered}
              nodeId="id"
              nodeVal="val"
              nodeColor={(n: object) => (n as GraphNode & { color: string }).color}
              nodeLabel={(n: object) => {
                const nn = n as GraphNode;
                return `${nn.label} (${nn.type})${nn.health != null ? ` · health ${nn.health}` : ""}`;
              }}
              nodeRelSize={4}
              // nodeLabel above is only the hover tooltip — without this the canvas
              // renders unlabelled dots. Draw the name beside each node, gated so a
              // 300-node graph does not turn into a wall of text: hubs are always
              // labelled, everything else appears as you zoom in.
              nodeCanvasObjectMode={() => "after"}
              nodeCanvasObject={(n: object, ctx: CanvasRenderingContext2D, globalScale: number) => {
                const nn = n as GraphNode & { x?: number; y?: number };
                if (nn.x == null || nn.y == null) return;
                const isHub = (nn.degree ?? 0) >= 6;
                if (globalScale < 1.4 && !isHub) return;
                const text = nn.label || nn.id;
                const fontSize = Math.min(4.5, 11 / globalScale);
                ctx.font = `${fontSize}px ui-sans-serif, system-ui, sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                const y = nn.y + 5;
                // halo keeps text legible over links and overlapping nodes
                ctx.lineWidth = fontSize / 3;
                ctx.strokeStyle = "rgba(255,255,255,0.9)";
                ctx.strokeText(text, nn.x, y);
                ctx.fillStyle = "#334155";
                ctx.fillText(text, nn.x, y);
              }}
              linkWidth={(l: object) => Math.max(0.5, ((l as GraphLink).weight || 1) * 1.5)}
              linkColor={() => "#cbd5e1"}
              linkDirectionalArrowLength={3}
              linkDirectionalArrowRelPos={1}
              onNodeClick={(n: object) => setSelected((n as GraphNode).id)}
              onLinkClick={(l: object) => setEdgeAction(l as GraphLink)}
              cooldownTicks={100}
            />
          )}

          {/* edge inline confirm/reject */}
          {edgeAction && (
            <div className="absolute left-1/2 top-4 z-10 flex -translate-x-1/2 items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 shadow-executive">
              <span className="text-xs font-semibold text-gray-700">{edgeAction.type} (w{edgeAction.weight})</span>
              <button onClick={() => edgeFeedback(edgeAction, "confirm")} className="text-green-600 hover:text-green-800"><ThumbsUp size={15} /></button>
              <button onClick={() => edgeFeedback(edgeAction, "reject")} className="text-pwc-rose hover:opacity-70"><ThumbsDown size={15} /></button>
              <button onClick={() => setEdgeAction(null)} className="text-gray-400 hover:text-gray-700">✕</button>
            </div>
          )}

          {/* legend */}
          <div className="absolute bottom-3 left-3 flex flex-wrap gap-2 rounded-lg border border-gray-200 bg-white/90 px-3 py-1.5 text-[11px]">
            {Object.entries(NODE_COLORS).map(([t, c]) => (
              <span key={t} className="flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} /> {t}
              </span>
            ))}
          </div>
        </div>

        {selected && (
          <div className="w-[380px] shrink-0">
            <GraphFeedbackPanel
              nodeId={selected}
              nodes={model?.nodes || []}
              role={role}
              onClose={() => setSelected(null)}
              onToast={toast}
              onChanged={load}
            />
          </div>
        )}
      </div>

      {/* toasts */}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((t) => (
          <div key={t.id}
            className={`rounded-lg px-4 py-2.5 text-sm font-semibold shadow-executive ${
              t.kind === "auto" ? "bg-green-600 text-white" : t.kind === "review" ? "bg-pwc-orange text-white" : "bg-pwc-rose text-white"
            }`}>
            {t.kind === "auto" ? "⚡ " : t.kind === "review" ? "📋 " : "⚠ "}
            {t.msg}
          </div>
        ))}
      </div>

      {showReview && <ReviewQueueModal role={role} onClose={() => setShowReview(false)} onApplied={load} />}
      {showLog && <AdaptationLogModal onClose={() => setShowLog(false)} />}
    </div>
  );
}

function Chip({ active, color, onClick, children }: { active: boolean; color?: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick}
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 font-semibold transition ${
        active ? "border-pwc-orange bg-pwc-orange/10 text-pwc-orange" : "border-gray-200 text-gray-600 hover:bg-gray-50"
      }`}>
      {color && <span className="h-2 w-2 rounded-full" style={{ background: color }} />}
      {children}
    </button>
  );
}

function toggle(setter: React.Dispatch<React.SetStateAction<string[]>>, value: string) {
  setter((prev) => (prev.includes(value) ? prev.filter((x) => x !== value) : [...prev, value]));
}

function srcId(l: GraphLink): string {
  return typeof l.source === "string" ? l.source : (l.source as unknown as { id: string }).id;
}
function tgtId(l: GraphLink): string {
  return typeof l.target === "string" ? l.target : (l.target as unknown as { id: string }).id;
}
