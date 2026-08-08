"use client";

import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  Bot,
  Brain,
  BriefcaseBusiness,
  CalendarClock,
  ChevronRight,
  CircleDollarSign,
  ClipboardList,
  Database,
  FileSearch,
  GitBranch,
  HeartPulse,
  Home,
  Layers3,
  Loader2,
  Mail,
  MapPin,
  MessageSquareText,
  PieChart,
  PhoneCall,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  UserRound,
  UsersRound
} from "lucide-react";
import { ComponentType, FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

type NavKey =
  | "home"
  | "customer"
  | "agent"
  | "campaign"
  | "agentPerformance"
  | "lapse"
  | "intelligence"
  | "evidenceHub";

type NavItem = {
  key: NavKey;
  label: string;
  shortLabel: string;
  icon: ComponentType<{ size?: number; className?: string }>;
};

type Kpi = {
  label: string;
  value: string;
  trend: string;
  tone: "red" | "green" | "amber" | "slate";
  helper: string;
};

type Recommendation = {
  title: string;
  owner: string;
  priority: "Critical" | "High" | "Medium";
  reason: string;
  action: string;
  confidence: number;
};

type ChartSeries = {
  label: string;
  value: number;
  color: string;
};

type AskResponse = {
  intent?: string;
  sql?: string | null;
  confidence_score?: number;
  answer_status?: string;
  strict_sql_validation?: Record<string, unknown>;
  sql_repair?: Record<string, unknown> | null;
  result_validation?: Record<string, unknown>;
  actual_tables_allowed?: string[];
  actual_columns_allowed?: string[];
  execution?: {
    rows?: Array<Record<string, unknown>>;
    row_count?: number;
    execution_status?: string;
    duration_ms?: number;
    error_message?: string;
  };
  business_insight?: {
    summary?: string;
    key_observations?: string[];
    caveats?: string[];
  };
  recommendations?: Array<{
    recommendation: string;
    reason: string;
    priority_score: number;
    source: string;
  }>;
  explainability?: {
    source_tables?: string[];
    ml_models_used?: string[];
    metrics_used?: string[];
    context_documents_used?: Array<Record<string, unknown>>;
  };
  sql_metadata?: Record<string, unknown>;
  lifecycle?: Array<Record<string, unknown>>;
  timings?: Record<string, unknown>;
  provider?: Record<string, unknown>;
  validation?: {
    referenced_tables?: string[];
    safety_decision?: string;
  } | null;
  retrieved_context?: Record<string, unknown> | null;
};

type DecisionIntelligencePayload = {
  role_code: string;
  role_name: string;
  executive_briefing: Record<string, unknown>;
  kpis: Array<Record<string, unknown>>;
  hidden_trends: Array<Record<string, unknown>>;
  opportunities: Array<Record<string, unknown>>;
  risks: Array<Record<string, unknown>>;
  questions: string[];
  recommendations: Array<Record<string, unknown>>;
  evidence: Record<string, unknown>;
  schema_additions: string[];
  services: string[];
  generated_at?: string;
};

type AiInsightV11Response = {
  role: string;
  question: string;
  answer_summary: string;
  key_data_points?: Array<Record<string, unknown>>;
  insights: Array<Record<string, unknown>>;
  recommendations: Array<Record<string, unknown>>;
  result_validation?: Record<string, unknown>;
  answer_status?: string;
  strict_sql_validation?: Record<string, unknown>;
  sql_repair?: Record<string, unknown> | null;
  lifecycle?: Array<Record<string, unknown>>;
  actual_tables_allowed?: string[];
  actual_columns_allowed?: string[];
  suggested_follow_up_questions?: string[];
  generated_sql: string;
  sql_validation_status: string;
  sql_execution_status: string;
  row_count: number;
  result_preview: Array<Record<string, unknown>>;
  related_tables: string[];
  related_columns: Array<Record<string, unknown>>;
  related_context: Array<Record<string, unknown>>;
  models_used: Array<Record<string, unknown>>;
  insight_id?: string | null;
  business_data_limitations?: string[];
  context_limitations?: string[];
  model_limitations?: string[];
  technical_warnings?: string[];
  fallback_used?: boolean;
  gemini_available?: boolean;
  gemini_quota_exhausted?: boolean;
  evidence_summary?: Record<string, unknown>;
  missing_data_points: string[];
  assumptions: string[];
  limitations: string[];
  confidence_score: number;
  latency_ms: number;
  provider_used: string;
  model_used: string;
};

type InsightEvidenceHubPayload = {
  insight_id?: string | null;
  role?: string | null;
  question?: string | null;
  timestamp?: string | null;
  recent_insight_runs?: Array<Record<string, unknown>>;
  related_tables?: Array<Record<string, unknown>>;
  related_columns?: Array<Record<string, unknown>>;
  semantic_context?: Array<Record<string, unknown>>;
  data_lineage?: Array<Record<string, unknown>>;
  underlying_models?: Array<Record<string, unknown>>;
  sql_evidence?: Record<string, unknown>;
  result_validation?: Record<string, unknown>;
  answer_status?: string;
  related_facts?: Array<Record<string, unknown>>;
  limitations?: {
    business_data_limitations?: string[];
    context_limitations?: string[];
    model_limitations?: string[];
    technical_warnings?: string[];
  };
  technical_diagnostics?: Record<string, unknown>;
  final_answer?: string;
  recommendations?: Array<Record<string, unknown>>;
  confidence_score?: number | null;
};

type Entity360Payload = {
  entity_type: string;
  entity_id: string;
  summary: Record<string, unknown>;
  sections: Record<string, unknown>;
  generated_at: string;
};

type CustomerSearchOption = {
  id: string;
  name: string;
  customerNumber: string;
  policyNumber: string;
};

type AgentSearchOption = {
  id: string;
  name: string;
  agentNumber: string;
  territory: string;
};

type CampaignSearchOption = {
  id: string;
  name: string;
  code: string;
  channel: string;
  startDate: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_INTELLIGENCE_API_URL ||
  process.env["NEXT_PUBLIC_" + "COPILOT_API_URL"] ||
  "http://127.0.0.1:8071";

const navItems: NavItem[] = [
  { key: "home", label: "Home", shortLabel: "Home", icon: Home },
  { key: "customer", label: "Know Your Customer", shortLabel: "KYC", icon: UserRound },
  { key: "agent", label: "Know Your Agent", shortLabel: "KYA", icon: UsersRound },
  { key: "campaign", label: "Campaign Effectiveness", shortLabel: "Campaigns", icon: Target },
  { key: "agentPerformance", label: "Agent Performance Tracking", shortLabel: "Performance", icon: TrendingUp },
  { key: "lapse", label: "Policy Lapse Risk", shortLabel: "Lapse Risk", icon: ShieldAlert },
  { key: "intelligence", label: "AI Intelligence", shortLabel: "AI Intelligence", icon: Sparkles },
  { key: "evidenceHub", label: "Insight Evidence Hub", shortLabel: "Evidence Hub", icon: Brain }
];

const navPaths: Record<NavKey, string> = {
  home: "/",
  customer: "/?view=customer",
  agent: "/?view=agent",
  campaign: "/?view=campaign",
  agentPerformance: "/?view=agent-performance",
  lapse: "/?view=lapse-risk",
  intelligence: "/ai-intelligence",
  evidenceHub: "/insight-evidence-hub"
};

const roles = [
  "Executive Leadership",
  "Sales Director",
  "Agency Manager",
  "Insurance Agent",
  "Campaign Manager",
  "Claims Manager",
  "Data Analyst"
];

function navKeyFromLocation(pathname: string, search = ""): NavKey {
  if (pathname === "/ai-intelligence") return "intelligence";
  if (pathname === "/insight-evidence-hub") return "evidenceHub";
  const view = new URLSearchParams(search).get("view");
  if (view === "customer") return "customer";
  if (view === "agent") return "agent";
  if (view === "campaign") return "campaign";
  if (view === "agent-performance") return "agentPerformance";
  if (view === "lapse-risk") return "lapse";
  return "home";
}

const kpis: Kpi[] = [
  { label: "New business premium", value: "S$42.8M", trend: "+12.4%", tone: "green", helper: "Rolling 90 days" },
  { label: "Persistency", value: "91.6%", trend: "+1.8 pts", tone: "green", helper: "13 month policy view" },
  { label: "High lapse exposure", value: "1,284", trend: "-8.2%", tone: "amber", helper: "Policies needing action" },
  { label: "Campaign conversion", value: "14.7%", trend: "+3.1 pts", tone: "red", helper: "Best offer cohorts" }
];

const recommendations: Recommendation[] = [
  {
    title: "Prioritize renewal conversations",
    owner: "Agency Manager",
    priority: "Critical",
    reason: "289 high-value policies renew within 60 days and show missed-payment signals.",
    action: "Assign senior agents and prepare retention offers.",
    confidence: 0.91
  },
  {
    title: "Launch health cross-sell follow-up",
    owner: "Campaign Manager",
    priority: "High",
    reason: "High-propensity affluent families responded to recent medical upgrade journeys.",
    action: "Create call list for top 600 customers.",
    confidence: 0.87
  },
  {
    title: "Coach agents with falling activity",
    owner: "Sales Director",
    priority: "Medium",
    reason: "MAPA contacts and quote-to-bind are declining for selected partner teams.",
    action: "Schedule branch coaching and monitor next two cycles.",
    confidence: 0.82
  }
];

const salesMix: ChartSeries[] = [
  { label: "Health", value: 38, color: "bg-red-600" },
  { label: "Savings", value: 27, color: "bg-slate-700" },
  { label: "Protection", value: 21, color: "bg-red-400" },
  { label: "Investment", value: 14, color: "bg-slate-400" }
];

const channelSeries: ChartSeries[] = [
  { label: "Agency", value: 46, color: "bg-red-600" },
  { label: "Bancassurance", value: 29, color: "bg-slate-700" },
  { label: "Digital", value: 16, color: "bg-red-400" },
  { label: "Partner", value: 9, color: "bg-slate-400" }
];

const monthlyTrend = [62, 66, 64, 71, 76, 73, 81, 84, 82, 89, 92, 95];

const customerSegments = [
  { name: "Emerging affluent", customers: "3,420", opportunity: "Health starter", risk: "Low", value: "S$8.4M" },
  { name: "Young families", customers: "2,180", opportunity: "Education and medical", risk: "Medium", value: "S$12.1M" },
  { name: "Established professionals", customers: "1,960", opportunity: "Retirement income", risk: "Low", value: "S$16.7M" },
  { name: "Value retention watch", customers: "740", opportunity: "Payment support", risk: "High", value: "S$5.6M" }
];

const agentRows = [
  { name: "Alicia Tan", territory: "SG Central", nbu: "S$1.28M", mapa: "High", risk: "Low", conversion: "18.4%" },
  { name: "Dennis Blake", territory: "HK Island", nbu: "S$0.42M", mapa: "Declining", risk: "Medium", conversion: "7.8%" },
  { name: "Mei Wong", territory: "SG East", nbu: "S$0.91M", mapa: "Stable", risk: "Low", conversion: "14.2%" },
  { name: "Aaron Lim", territory: "Kowloon", nbu: "S$0.37M", mapa: "Low", risk: "High", conversion: "6.1%" }
];

type AgentRecord = {
  name: string;
  code: string;
  region: string;
  branch: string;
  manager: string;
  tenure: string;
  status: string;
  tier: string;
  kpis: Kpi[];
  mapa: {
    meetings: number;
    activities: number;
    proposals: number;
    applications: number;
    trend: number[];
    bars: ChartSeries[];
  };
  portfolio: {
    assignedCustomers: string;
    highPropensity: string;
    highLapseRisk: string;
    highClv: string;
    segments: ChartSeries[];
  };
  movements: Array<{
    date: string;
    type: string;
    from: string;
    to: string;
    impact: string;
  }>;
  risks: Array<{
    label: string;
    value: number;
    display: string;
    tone: CustomerScore["tone"];
    helper: string;
  }>;
  actions: Array<{
    title: string;
    type: string;
    reason: string;
    confidence: number;
    priority: Recommendation["priority"];
  }>;
  evidence: Array<{
    sourceTable: string;
    modelScore: string;
    rationale: string;
    confidence: number;
  }>;
};

const agentRecords: AgentRecord[] = [
  {
    name: "Alicia Tan",
    code: "AGT-SG-01482",
    region: "Singapore",
    branch: "SG Central Premier",
    manager: "Grace Lee",
    tenure: "8.4 years",
    status: "Active, growth leader",
    tier: "Premier agency leader",
    kpis: [
      { label: "Monthly premium", value: "S$1.28M", trend: "+14.8%", tone: "green", helper: "Above branch average" },
      { label: "Policies sold", value: "86", trend: "+9", tone: "green", helper: "Current month" },
      { label: "Conversion rate", value: "18.4%", trend: "+2.1 pts", tone: "green", helper: "Quote to bind" },
      { label: "Persistency rate", value: "94.2%", trend: "+1.4 pts", tone: "green", helper: "13 month view" },
      { label: "Target achievement", value: "112%", trend: "+12 pts", tone: "red", helper: "Monthly sales target" },
      { label: "Commission", value: "S$84K", trend: "+10.6%", tone: "green", helper: "Rolling month" }
    ],
    mapa: {
      meetings: 142,
      activities: 386,
      proposals: 94,
      applications: 71,
      trend: [64, 68, 73, 70, 78, 82, 85, 88, 91, 94, 97, 103],
      bars: [
        { label: "Meetings", value: 86, color: "bg-red-600" },
        { label: "Activities", value: 92, color: "bg-slate-800" },
        { label: "Proposals", value: 74, color: "bg-red-400" },
        { label: "Applications", value: 69, color: "bg-slate-400" }
      ]
    },
    portfolio: {
      assignedCustomers: "1,420",
      highPropensity: "326",
      highLapseRisk: "84",
      highClv: "218",
      segments: [
        { label: "Established professionals", value: 35, color: "bg-red-600" },
        { label: "Young families", value: 29, color: "bg-slate-800" },
        { label: "Emerging affluent", value: 24, color: "bg-red-400" },
        { label: "Retention watch", value: 12, color: "bg-amber-500" }
      ]
    },
    movements: [
      { date: "2026-03-01", type: "Promotion", from: "Senior advisor", to: "Premier agency leader", impact: "Team premium +12%" },
      { date: "2025-08-15", type: "Territory change", from: "SG East", to: "SG Central", impact: "High CLV book added" },
      { date: "2024-04-01", type: "Branch change", from: "SG Orchard", to: "SG Central Premier", impact: "Persistency improved" }
    ],
    risks: [
      { label: "Attrition risk", value: 18, display: "Low", tone: "green", helper: "Stable commissions and strong activity" },
      { label: "Declining activity", value: 22, display: "Low", tone: "green", helper: "MAPA momentum is positive" },
      { label: "Target miss risk", value: 16, display: "Low", tone: "green", helper: "Above monthly target run rate" }
    ],
    actions: [
      { title: "Allocate high-CLV health leads", type: "Lead allocation", reason: "Strong conversion and high persistency make this agent suitable for valuable health cross-sell leads.", confidence: 0.92, priority: "High" },
      { title: "Use as branch coaching mentor", type: "Coaching", reason: "MAPA discipline and quote-to-bind quality are above peer benchmark.", confidence: 0.88, priority: "Medium" }
    ],
    evidence: [
      { sourceTable: "agent_mapa_metrics", modelScore: "agent_performance_v1: 0.91", rationale: "Meetings, proposals, and applications are trending upward.", confidence: 0.91 },
      { sourceTable: "agent_commissions", modelScore: "agent_attrition_v1: 0.18", rationale: "Commission pattern is stable with low attrition signal.", confidence: 0.86 },
      { sourceTable: "policies", modelScore: "persistency_metric: 94.2%", rationale: "High retained-policy ratio across assigned book.", confidence: 0.89 }
    ]
  }
];

const campaigns = [
  { name: "VHIS medical upgrade", channel: "Agent call", conversion: "9.2%", premium: "S$1.01M", status: "Scale" },
  { name: "Retirement income review", channel: "Email and call", conversion: "7.8%", premium: "S$814K", status: "Optimize" },
  { name: "Family protection refresh", channel: "Digital", conversion: "6.4%", premium: "S$629K", status: "Watch" }
];

type CampaignRecord = {
  id: string;
  name: string;
  code: string;
  product: string;
  channel: string;
  targetSegment: string;
  startDate: string;
  endDate: string;
  budget: string;
  status: string;
  objective: string;
  funnel: {
    targeted: number;
    delivered: number;
    opened: number;
    clicked: number;
    responded: number;
    leadsCreated: number;
    quotesCreated: number;
    policiesIssued: number;
  };
  analytics: {
    responseRate: string;
    leadConversionRate: string;
    policyConversionRate: string;
    costPerLead: string;
    costPerPolicy: string;
    premiumGenerated: string;
    roi: string;
  };
  performance: {
    segments: ChartSeries[];
    regions: ChartSeries[];
    products: ChartSeries[];
    channels: ChartSeries[];
    agents: ChartSeries[];
  };
  insights: Array<{
    title: string;
    value: string;
    detail: string;
    tone: "red" | "green" | "amber" | "slate";
  }>;
  recommendations: Array<{
    title: string;
    type: string;
    reason: string;
    confidence: number;
    priority: Recommendation["priority"];
  }>;
  lineage: Array<{
    sourceTable: string;
    sourceColumn: string;
    metric: string;
    model: string;
    timestamp: string;
  }>;
};

type AgentPerformanceDashboard = {
  filters?: Record<string, unknown>;
  region_options?: string[];
  region_option_details?: Array<Record<string, unknown>>;
  kpis: Record<string, unknown>;
  leaderboard: Array<Record<string, unknown>>;
  mapa_productivity: Record<string, unknown>;
  trends: Array<Record<string, unknown>>;
  clusters: Array<Record<string, unknown>>;
  customer_product_clusters: Array<Record<string, unknown>>;
  rising_stars: Array<Record<string, unknown>>;
  mdrt_agents: Array<Record<string, unknown>>;
  risk_alerts: Array<Record<string, unknown>>;
  coaching_recommendations: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
  generated_at?: string;
};

type PolicyLapseDashboard = {
  kpis: Record<string, unknown>;
  trends: Record<string, unknown>;
  hotspots: Record<string, Array<Record<string, unknown>>>;
  top_products: Array<Record<string, unknown>>;
  top_customers: Array<Record<string, unknown>>;
  agents: Array<Record<string, unknown>>;
  root_causes: Array<Record<string, unknown>>;
  cross_sell: Array<Record<string, unknown>>;
  action_center: Array<Record<string, unknown>>;
  explanation: Record<string, unknown>;
  scenario_simulator: Array<Record<string, unknown>>;
  schema_additions: string[];
  ml_enhancements: string[];
  generated_at?: string;
};

const campaignRecords: CampaignRecord[] = [
  {
    id: "CMP-SG-HEALTH-001",
    name: "VHIS medical upgrade",
    code: "CMP-SG-HEALTH-001",
    product: "Health and medical riders",
    channel: "Agent call",
    targetSegment: "Young families and established professionals",
    startDate: "2026-03-01",
    endDate: "2026-05-31",
    budget: "S$420,000",
    status: "Active",
    objective: "Convert engaged health prospects into policy upgrades.",
    funnel: {
      targeted: 12400,
      delivered: 11620,
      opened: 6410,
      clicked: 3280,
      responded: 2140,
      leadsCreated: 980,
      quotesCreated: 520,
      policiesIssued: 316
    },
    analytics: {
      responseRate: "17.3%",
      leadConversionRate: "45.8%",
      policyConversionRate: "2.5%",
      costPerLead: "S$429",
      costPerPolicy: "S$1,329",
      premiumGenerated: "S$1.01M",
      roi: "2.4x"
    },
    performance: {
      segments: [
        { label: "Young families", value: 36, color: "bg-red-600" },
        { label: "Established professionals", value: 29, color: "bg-slate-800" },
        { label: "Emerging affluent", value: 22, color: "bg-red-400" },
        { label: "Retention watch", value: 13, color: "bg-slate-400" }
      ],
      regions: [
        { label: "SG / Central", value: 34, color: "bg-red-600" },
        { label: "HK / Island", value: 27, color: "bg-slate-800" },
        { label: "SG / East", value: 21, color: "bg-red-400" },
        { label: "HK / Kowloon", value: 18, color: "bg-slate-400" }
      ],
      products: [
        { label: "Health", value: 48, color: "bg-red-600" },
        { label: "Protection", value: 24, color: "bg-slate-800" },
        { label: "Savings", value: 18, color: "bg-red-400" },
        { label: "Investment", value: 10, color: "bg-slate-400" }
      ],
      channels: [
        { label: "Agent call", value: 52, color: "bg-red-600" },
        { label: "Email", value: 28, color: "bg-slate-800" },
        { label: "App", value: 14, color: "bg-red-400" },
        { label: "SMS", value: 6, color: "bg-slate-400" }
      ],
      agents: [
        { label: "Top agents", value: 42, color: "bg-red-600" },
        { label: "Core agents", value: 35, color: "bg-slate-800" },
        { label: "New agents", value: 15, color: "bg-red-400" },
        { label: "Unassigned", value: 8, color: "bg-slate-400" }
      ]
    },
    insights: [
      { title: "Likely to convert", value: "1,240", detail: "High response score and no active health rider.", tone: "red" },
      { title: "Best follow-up", value: "Advisor call", detail: "Human contact performs best for high-CLV cohorts.", tone: "green" },
      { title: "Next product", value: "Medical rider", detail: "Coverage gap detected across family segments.", tone: "slate" },
      { title: "Response score", value: "0.86", detail: "Campaign response model band is high.", tone: "amber" }
    ],
    recommendations: [
      { title: "Continue campaign", type: "Scale", reason: "Policy conversion and premium generated exceed the target run rate.", confidence: 0.9, priority: "High" },
      { title: "Assign leads to agents", type: "Follow-up", reason: "High-response leads should receive advisor follow-up within seven days.", confidence: 0.87, priority: "Critical" },
      { title: "Suppress low-response segment", type: "Optimization", reason: "Reduce repeat outreach for customers with no response and service issues.", confidence: 0.78, priority: "Medium" }
    ],
    lineage: [
      { sourceTable: "campaigns", sourceColumn: "campaign_name", metric: "campaign_overview", model: "None", timestamp: "2026-05-31" },
      { sourceTable: "campaign_targets", sourceColumn: "campaign_target_id", metric: "targeted_customers", model: "None", timestamp: "2026-05-31" },
      { sourceTable: "campaign_responses", sourceColumn: "response_type", metric: "response_rate", model: "campaign_response_v1", timestamp: "2026-05-31" },
      { sourceTable: "model_scores", sourceColumn: "score", metric: "campaign_response_score", model: "campaign_response_v1", timestamp: "2026-05-31" }
    ]
  }
];

const agentPerformanceSample: AgentPerformanceDashboard = {
  region_options: [
    "SG-01",
    "SG-03",
    "SG-09",
    "SG-11",
    "SG-12",
    "SG-16",
    "SG-18",
    "SG-19",
    "SG-22",
    "SG-25",
    "HK-CW",
    "HK-EA",
    "HK-IS",
    "HK-KC",
    "HK-SK",
    "HK-ST",
    "HK-TM",
    "HK-TW",
    "HK-WC",
    "HK-YT"
  ],
  kpis: {
    total_agents: 6000,
    active_agents: 5259,
    premium_generated: 297143903,
    policies_sold: 20984,
    average_conversion_rate: 0.41,
    average_persistency_rate: 0.831
  },
  leaderboard: [
    {
      rank: 1,
      agent_name: "Alicia Tan",
      region: "SG Central",
      premium: 2480000,
      policies_sold: 118,
      conversion_rate: 0.47,
      persistency_rate: 0.94,
      target_achievement: 1.22,
      agent_cluster: "MDRT / elite producers",
      customer_focus: "affluent_wealth",
      product_focus: "health"
    },
    {
      rank: 2,
      agent_name: "Mei Wong",
      region: "SG East",
      premium: 1420000,
      policies_sold: 86,
      conversion_rate: 0.39,
      persistency_rate: 0.91,
      target_achievement: 1.08,
      agent_cluster: "Rising stars",
      customer_focus: "family_protection",
      product_focus: "life"
    }
  ],
  mapa_productivity: { meetings: 82000, activities: 145000, proposals: 52000, applications: 31000, policy_issuance: 20984 },
  trends: [
    { metric_month: "2025-07-01", premium: 18200000, conversion_rate: 0.34, persistency_rate: 0.81, target_achievement: 0.87 },
    { metric_month: "2025-08-01", premium: 19600000, conversion_rate: 0.36, persistency_rate: 0.82, target_achievement: 0.91 },
    { metric_month: "2025-09-01", premium: 21500000, conversion_rate: 0.39, persistency_rate: 0.83, target_achievement: 0.96 },
    { metric_month: "2025-10-01", premium: 23800000, conversion_rate: 0.41, persistency_rate: 0.84, target_achievement: 1.02 },
    { metric_month: "2025-11-01", premium: 26100000, conversion_rate: 0.43, persistency_rate: 0.84, target_achievement: 1.07 },
    { metric_month: "2025-12-01", premium: 28200000, conversion_rate: 0.45, persistency_rate: 0.85, target_achievement: 1.12 }
  ],
  clusters: [
    { agent_cluster: "MDRT / elite producers", agent_count: 184, premium: 96000000, conversion_rate: 0.49, persistency_rate: 0.93, dominant_customer_segment: "affluent_wealth", dominant_product_focus: "wealth" },
    { agent_cluster: "Rising stars", agent_count: 420, premium: 72000000, conversion_rate: 0.44, persistency_rate: 0.88, dominant_customer_segment: "young_professional", dominant_product_focus: "health" },
    { agent_cluster: "Core multi-line advisors", agent_count: 3100, premium: 129000000, conversion_rate: 0.36, persistency_rate: 0.81, dominant_customer_segment: "family_protection", dominant_product_focus: "life" }
  ],
  customer_product_clusters: [
    { customer_focus: "affluent_wealth", product_focus: "wealth", agent_count: 380, premium: 104000000, policies_sold: 4200, conversion_rate: 0.45 },
    { customer_focus: "family_protection", product_focus: "life", agent_count: 1420, premium: 86000000, policies_sold: 6100, conversion_rate: 0.39 },
    { customer_focus: "health_focused", product_focus: "health", agent_count: 940, premium: 64000000, policies_sold: 5300, conversion_rate: 0.42 }
  ],
  rising_stars: [
    { agent_name: "Mei Wong", region: "SG East", premium: 1420000, policies_sold: 86, growth_rate: 0.62, product_focus: "health", customer_focus: "family_protection" },
    { agent_name: "Aaron Lim", region: "HK Kowloon", premium: 980000, policies_sold: 64, growth_rate: 0.47, product_focus: "life", customer_focus: "young_professional" }
  ],
  mdrt_agents: [
    { agent_name: "Alicia Tan", region: "SG Central", premium: 2480000, policies_sold: 118, conversion_rate: 0.47, persistency_rate: 0.94, product_focus: "wealth", customer_focus: "affluent_wealth" }
  ],
  risk_alerts: [
    { alert_type: "Underperforming agents", agent_count: 246, severity: "High" },
    { alert_type: "Agents with declining activities", agent_count: 184, severity: "Medium" },
    { alert_type: "Agents with poor persistency", agent_count: 119, severity: "High" }
  ],
  coaching_recommendations: [
    {
      agent_name: "Dennis Blake",
      region: "HK Island",
      intervention: "MAPA activity coaching",
      why: "Recent meetings, activities, proposals, and applications are declining.",
      suggested_intervention: "Schedule weekly pipeline inspection and next-best-customer review.",
      expected_impact: "Improve conversion, retained policy count, and target attainment next month.",
      performance_score: 0.42,
      attrition_score: 0.68
    }
  ],
  evidence: [
    { source_table: "agent_mapa_metrics", facts: "MAPA activity and production measures.", models_used: ["agent_performance"] },
    { source_table: "policies, customers, products", facts: "Customer and product mix for peer clustering.", models_used: ["next_best_customer"] }
  ],
  generated_at: "2026-06-01"
};

const policyLapseSample: PolicyLapseDashboard = {
  kpis: {
    policies_at_risk: 178,
    customers_at_risk: 44,
    premium_revenue_at_risk: 5162596,
    revenue_saved_through_interventions: 1300163,
    average_lapse_probability: 0.74,
    top_vulnerable_product: "Evergreen Wealth Multi-Currency Plan",
    top_vulnerable_segment: "SME owner"
  },
  trends: { current_month_risk: 84, previous_month_proxy: 93, current_premium_risk: 2400000, previous_premium_proxy: 2700000 },
  hotspots: {
    region: [{ dimension: "HK-KC", at_risk_policies: 28, premium_at_risk: 825000, average_lapse_score: 0.77 }],
    branch: [{ dimension: "Premier Agency", at_risk_policies: 22, premium_at_risk: 640000, average_lapse_score: 0.74 }],
    product: [{ dimension: "Evergreen Wealth", at_risk_policies: 31, premium_at_risk: 910000, average_lapse_score: 0.78 }],
    agent: [{ dimension: "Diane Lyons", at_risk_policies: 9, premium_at_risk: 280000, average_lapse_score: 0.73 }],
    customer_segment: [{ dimension: "SME owner", at_risk_policies: 42, premium_at_risk: 1200000, average_lapse_score: 0.76 }]
  },
  top_products: [
    { product: "Evergreen Wealth Multi-Currency Plan", active_policies: 842, high_risk_policies: 31, annual_premium: 12400000, lapse_probability: 0.78, missed_payments: 48, recommendation: "Above portfolio average due to premium increases and missed payments." }
  ],
  top_customers: [
    { customer: "John Tan", customer_segment: "SME owner", agent: "Diane Lyons", product: "Evergreen Wealth", premium: 42000, lapse_score: 0.91, reason: "Premium Increase", cross_sell_opportunity: "Medical Rider", recommended_action: "Retention Call", confidence_score: 0.89 }
  ],
  agents: [
    { agent: "Diane Lyons", customers_at_risk: 9, premium_at_risk: 280000, retention_success_rate: 0.7, mapa_score: 0.42, recommended_coaching_action: "Increase agent contact cadence" }
  ],
  root_causes: [
    { driver: "Missed Payments", count: 66, premium_exposure: 1800000, contribution: 0.37 },
    { driver: "Premium Increase", count: 42, premium_exposure: 1200000, contribution: 0.24 },
    { driver: "Complaint History", count: 31, premium_exposure: 860000, contribution: 0.17 }
  ],
  cross_sell: [
    { customer: "John Tan", current_product: "Life", recommended_product: "Health Rider", expected_conversion_probability: 0.61, expected_premium: 9200, reason: "At-risk customer with premium increase signal and product-fit opportunity." }
  ],
  action_center: [
    { customer: "John Tan", agent: "Diane Lyons", policy: "POL-HK-10291", action: "Retention Call", expected_impact: 18000, confidence: 0.89, due_date: "2026-06-12" }
  ],
  explanation: {
    customer: "John Tan",
    policy_number: "POL-HK-10291",
    product_name: "Evergreen Wealth",
    lapse_score: 0.91,
    primary_lapse_reason: "Premium Increase",
    supporting_facts: ["Premium increase", "No agent contact", "Recent payment delay"],
    source_tables: ["policies", "payments", "model_scores", "next_best_actions"],
    source_columns: ["annual_premium", "payment_status", "score_value", "action_type"],
    context_documents_used: ["Policy Lapse Risk Context", "Next Best Action Context"],
    confidence_score: 0.89
  },
  scenario_simulator: [
    { scenario: "10% premium reduction", policies_saved: 32, premium_saved: 826015, expected_conversion: 0.22 },
    { scenario: "Additional agent outreach", policies_saved: 43, premium_saved: 1084145, expected_conversion: 0.28 },
    { scenario: "Retention campaign", policies_saved: 27, premium_saved: 619512, expected_conversion: 0.19 },
    { scenario: "Policy bundling", policies_saved: 36, premium_saved: 929267, expected_conversion: 0.25 }
  ],
  schema_additions: ["retention_interventions", "retention_offers", "retention_outcomes", "policy_health_score", "customer_health_score"],
  ml_enhancements: ["lapse_risk", "retention_success_probability", "next_best_product", "agent_retention_effectiveness"],
  generated_at: "2026-06-01"
};

const modelCards = [
  { name: "Propensity to buy", status: "Healthy", auc: "0.82", drift: "Low", coverage: "9,842 customers" },
  { name: "Policy lapse risk", status: "Healthy", auc: "0.79", drift: "Medium", coverage: "18,920 policies" },
  { name: "Agent performance", status: "Monitor", auc: "0.74", drift: "Medium", coverage: "5,740 agents" },
  { name: "Campaign response", status: "Healthy", auc: "0.81", drift: "Low", coverage: "800 campaigns" }
];

const lineageSteps = [
  { label: "Source data", detail: "Customers, policies, payments, claims, campaigns" },
  { label: "Feature layer", detail: "Snapshot features with leakage controls" },
  { label: "Model score", detail: "Latest eligible score and score band" },
  { label: "Business rules", detail: "Suppression, priority, ownership, expiry" },
  { label: "Recommendation", detail: "Action, reason, confidence, next step" }
];

type CustomerScore = {
  label: string;
  value: number;
  display: string;
  tone: "red" | "green" | "amber" | "slate";
  helper: string;
};

type CustomerRecord = {
  id: string;
  policyNumber: string;
  name: string;
  age: number | string;
  segment: string;
  incomeBand: string;
  location: string;
  customerSince: string;
  preferredChannel: string;
  status: string;
  advisor: string;
  portfolio: {
    activePolicies: number;
    annualPremium: string;
    sumAssured: string;
    nextRenewal: string;
    productMix: ChartSeries[];
    policies: Array<{
      product: string;
      status: string;
      premium: string;
      sumAssured: string;
      renewalDate: string;
      policyNumber: string;
    }>;
  };
  scores: CustomerScore[];
  nextBestProduct: string;
  timeline: Array<{
    type: string;
    date: string;
    title: string;
    detail: string;
    tone: "red" | "green" | "amber" | "slate";
  }>;
  recommendations: Array<{
    action: string;
    product: string;
    reason: string;
    confidence: number;
    message: string;
    priority: Recommendation["priority"];
  }>;
  lineage: Array<{
    sourceTable: string;
    sourceColumn: string;
    metric: string;
    model: string;
    timestamp: string;
  }>;
};

const customerRecords: CustomerRecord[] = [
  {
    id: "CUS-SG-10291",
    policyNumber: "POL-SG-884210",
    name: "Amanda Lim",
    age: 42,
    segment: "Established professional",
    incomeBand: "S$180K-S$250K",
    location: "Singapore, Central",
    customerSince: "2017-04-18",
    preferredChannel: "Advisor call",
    status: "Active, high value",
    advisor: "Alicia Tan",
    portfolio: {
      activePolicies: 3,
      annualPremium: "S$18,420",
      sumAssured: "S$1.45M",
      nextRenewal: "2026-07-21",
      productMix: [
        { label: "Health", value: 42, color: "bg-red-600" },
        { label: "Savings", value: 26, color: "bg-slate-800" },
        { label: "Protection", value: 22, color: "bg-red-400" },
        { label: "Investment", value: 10, color: "bg-slate-400" }
      ],
      policies: [
        { product: "PRUShield Premier", status: "Active", premium: "S$5,280", sumAssured: "S$500K", renewalDate: "2026-07-21", policyNumber: "POL-SG-884210" },
        { product: "PRULife Vantage", status: "Active", premium: "S$9,840", sumAssured: "S$750K", renewalDate: "2026-11-14", policyNumber: "POL-SG-332810" },
        { product: "PRUActive Protect", status: "Active", premium: "S$3,300", sumAssured: "S$200K", renewalDate: "2027-02-03", policyNumber: "POL-SG-771034" }
      ]
    },
    scores: [
      { label: "Propensity to buy", value: 88, display: "88%", tone: "green", helper: "Recent health campaign engagement" },
      { label: "Churn risk", value: 24, display: "Low", tone: "green", helper: "Strong tenure and response history" },
      { label: "Lapse risk", value: 31, display: "Medium", tone: "amber", helper: "Renewal due within 60 days" },
      { label: "Customer lifetime value", value: 91, display: "Very high", tone: "red", helper: "High premium and multi-policy book" },
      { label: "Next best product", value: 84, display: "Medical rider", tone: "slate", helper: "Coverage gap in family rider layer" }
    ],
    nextBestProduct: "Medical rider upgrade",
    timeline: [
      { type: "Campaign open", date: "2026-05-29", title: "Opened medical upgrade email", detail: "Clicked benefit comparison twice.", tone: "green" },
      { type: "Call", date: "2026-05-24", title: "Advisor renewal check-in", detail: "Customer asked for family coverage options.", tone: "slate" },
      { type: "Service request", date: "2026-05-11", title: "Changed payment card", detail: "Resolved same day.", tone: "green" },
      { type: "Meeting", date: "2026-04-21", title: "Annual portfolio review", detail: "Discussed retirement income and health riders.", tone: "slate" }
    ],
    recommendations: [
      {
        action: "Schedule renewal and rider conversation",
        product: "Medical rider upgrade",
        reason: "High CLV, strong campaign response, and renewal is inside 60 days.",
        confidence: 0.91,
        message: "Hi Amanda, your PRUShield renewal is coming up. I can walk you through a medical rider option that may better fit your family coverage needs.",
        priority: "Critical"
      }
    ],
    lineage: [
      { sourceTable: "model_scores", sourceColumn: "score_band", metric: "propensity_to_buy", model: "propensity_to_buy_v1", timestamp: "2026-05-31 09:10" },
      { sourceTable: "policies", sourceColumn: "renewal_date", metric: "renewal_window_days", model: "business_rule_renewal_60d", timestamp: "2026-05-31 09:10" },
      { sourceTable: "campaign_responses", sourceColumn: "clicked_at", metric: "recent_campaign_engagement", model: "campaign_response_v1", timestamp: "2026-05-31 09:08" }
    ]
  },
  {
    id: "CUS-HK-20984",
    policyNumber: "POL-HK-673552",
    name: "Daniel Wong",
    age: 51,
    segment: "Value retention watch",
    incomeBand: "HK$900K-HK$1.3M",
    location: "Hong Kong, Kowloon",
    customerSince: "2014-09-02",
    preferredChannel: "WhatsApp",
    status: "Service recovery",
    advisor: "Mei Wong",
    portfolio: {
      activePolicies: 2,
      annualPremium: "HK$118,600",
      sumAssured: "HK$6.2M",
      nextRenewal: "2026-06-28",
      productMix: [
        { label: "Protection", value: 48, color: "bg-red-600" },
        { label: "Savings", value: 34, color: "bg-slate-800" },
        { label: "Health", value: 12, color: "bg-red-400" },
        { label: "Investment", value: 6, color: "bg-slate-400" }
      ],
      policies: [
        { product: "PRULife YourChoice", status: "Active", premium: "HK$72,400", sumAssured: "HK$4.8M", renewalDate: "2026-06-28", policyNumber: "POL-HK-673552" },
        { product: "PRUWealth Builder", status: "Active", premium: "HK$46,200", sumAssured: "HK$1.4M", renewalDate: "2026-12-18", policyNumber: "POL-HK-447129" }
      ]
    },
    scores: [
      { label: "Propensity to buy", value: 46, display: "46%", tone: "slate", helper: "Sales suppressed by service issue" },
      { label: "Churn risk", value: 82, display: "High", tone: "red", helper: "Complaint unresolved and renewal near" },
      { label: "Lapse risk", value: 87, display: "High", tone: "red", helper: "Two late payments in 90 days" },
      { label: "Customer lifetime value", value: 78, display: "High", tone: "amber", helper: "Long-tenure protection book" },
      { label: "Next best product", value: 58, display: "Retention offer", tone: "amber", helper: "Stabilize before cross-sell" }
    ],
    nextBestProduct: "Retention service package",
    timeline: [
      { type: "Complaint", date: "2026-05-30", title: "Claim follow-up complaint", detail: "Open complaint awaiting manager callback.", tone: "red" },
      { type: "Service request", date: "2026-05-27", title: "Payment holiday enquiry", detail: "Customer asked for premium flexibility.", tone: "amber" },
      { type: "Call", date: "2026-05-18", title: "Missed payment follow-up", detail: "Promised payment next cycle.", tone: "amber" },
      { type: "Campaign open", date: "2026-04-29", title: "Ignored savings upgrade journey", detail: "No click after two sends.", tone: "slate" }
    ],
    recommendations: [
      {
        action: "Service recovery call",
        product: "Retention service package",
        reason: "High lapse and churn risk with unresolved complaint; sales action is suppressed.",
        confidence: 0.89,
        message: "Hi Daniel, I am following up personally on your open service concern and renewal timing so we can resolve this before your next premium cycle.",
        priority: "Critical"
      }
    ],
    lineage: [
      { sourceTable: "customer_complaints", sourceColumn: "status", metric: "unresolved_complaint_flag", model: "business_rule_service_suppression", timestamp: "2026-05-31 09:16" },
      { sourceTable: "payments", sourceColumn: "payment_status", metric: "missed_payment_count_90d", model: "policy_lapse_v1", timestamp: "2026-05-31 09:15" },
      { sourceTable: "model_scores", sourceColumn: "score", metric: "churn_risk", model: "customer_churn_v1", timestamp: "2026-05-31 09:12" }
    ]
  },
  {
    id: "CUS-SG-11742",
    policyNumber: "POL-SG-551709",
    name: "Priya Menon",
    age: 35,
    segment: "Young family",
    incomeBand: "S$120K-S$180K",
    location: "Singapore, East",
    customerSince: "2021-01-12",
    preferredChannel: "Mobile app",
    status: "Growth opportunity",
    advisor: "Aaron Lim",
    portfolio: {
      activePolicies: 1,
      annualPremium: "S$6,240",
      sumAssured: "S$420K",
      nextRenewal: "2026-10-04",
      productMix: [
        { label: "Protection", value: 56, color: "bg-red-600" },
        { label: "Health", value: 0, color: "bg-red-400" },
        { label: "Savings", value: 28, color: "bg-slate-800" },
        { label: "Investment", value: 16, color: "bg-slate-400" }
      ],
      policies: [
        { product: "PRUActive Protect", status: "Active", premium: "S$6,240", sumAssured: "S$420K", renewalDate: "2026-10-04", policyNumber: "POL-SG-551709" }
      ]
    },
    scores: [
      { label: "Propensity to buy", value: 93, display: "93%", tone: "red", helper: "High engagement and product gap" },
      { label: "Churn risk", value: 18, display: "Low", tone: "green", helper: "Frequent app engagement" },
      { label: "Lapse risk", value: 22, display: "Low", tone: "green", helper: "No missed payments" },
      { label: "Customer lifetime value", value: 72, display: "High", tone: "amber", helper: "Young family growth segment" },
      { label: "Next best product", value: 92, display: "Health plan", tone: "red", helper: "No active health coverage" }
    ],
    nextBestProduct: "PRUShield health plan",
    timeline: [
      { type: "Campaign open", date: "2026-05-26", title: "Clicked family health guide", detail: "Viewed hospital coverage page.", tone: "green" },
      { type: "Meeting", date: "2026-05-07", title: "Video review completed", detail: "Discussed child protection needs.", tone: "green" },
      { type: "Service request", date: "2026-04-18", title: "Beneficiary update", detail: "Completed through mobile app.", tone: "green" },
      { type: "Call", date: "2026-03-30", title: "Follow-up requested", detail: "Customer asked for health quote timing.", tone: "slate" }
    ],
    recommendations: [
      {
        action: "Health cross-sell follow-up",
        product: "PRUShield health plan",
        reason: "High propensity, no active health policy, strong app engagement, and recent health content clicks.",
        confidence: 0.94,
        message: "Hi Priya, based on your recent interest in family health coverage, I can prepare a simple comparison for a PRUShield option that fits your family needs.",
        priority: "High"
      }
    ],
    lineage: [
      { sourceTable: "policies", sourceColumn: "product_category", metric: "health_policy_gap", model: "next_best_product_v1", timestamp: "2026-05-31 09:11" },
      { sourceTable: "customer_engagement_events", sourceColumn: "event_type", metric: "engagement_score_30d", model: "propensity_to_buy_v1", timestamp: "2026-05-31 09:10" },
      { sourceTable: "campaign_responses", sourceColumn: "response_type", metric: "campaign_response_score", model: "campaign_response_v1", timestamp: "2026-05-31 09:09" }
    ]
  }
];

export default function Page() {
  const [active, setActive] = useState<NavKey>("home");
  const [role, setRole] = useState(roles[0]);
  const [question, setQuestion] = useState("Which customers should I contact first today?");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeItem = useMemo(() => navItems.find((item) => item.key === active) || navItems[0], [active]);

  useEffect(() => {
    const syncFromLocation = () => setActive(navKeyFromLocation(window.location.pathname, window.location.search));
    syncFromLocation();
    window.addEventListener("popstate", syncFromLocation);
    return () => window.removeEventListener("popstate", syncFromLocation);
  }, []);

  function setActiveWithRoute(key: NavKey, query = "") {
    setActive(key);
    if (typeof window !== "undefined") {
      const path = `${navPaths[key]}${query}`;
      window.history.pushState(null, "", path);
    }
  }

  async function submitQuestion(event?: FormEvent) {
    event?.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/intelligence/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          role_code: role.toLowerCase().replaceAll(" ", "_"),
          include_context: true,
          include_debug: false,
          row_limit: 25,
          execute_sql: true
        })
      });
      if (!response.ok) throw new Error(`Intelligence API returned ${response.status}`);
      const payload = (await response.json()) as AskResponse;
      setAnswer(payload);
    } catch (exc) {
      setAnswer(mockIntelligenceAnswer(question));
      setError("Intelligence API is not available. Showing platform sample response.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900">
      <div className="flex min-h-screen">
        <aside className="hidden w-80 shrink-0 border-r border-slate-200 bg-slate-950 text-white lg:flex lg:flex-col">
          <div className="border-b border-white/10 px-6 py-6">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-red-600">
                <ShieldCheck size={24} />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-red-200">Insurance Decision</p>
                <h1 className="text-lg font-bold leading-tight">Intelligence Platform</h1>
              </div>
            </div>
          </div>

          <nav className="flex-1 space-y-1 px-4 py-5">
            {navItems.map((item) => (
              <SidebarButton key={item.key} item={item} active={active === item.key} onClick={() => setActiveWithRoute(item.key)} />
            ))}
          </nav>

          <div className="border-t border-white/10 p-5">
            <div className="rounded-lg border border-white/10 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">User profile</p>
              <div className="mt-3 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-600 text-sm font-bold">NB</div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold">Nitin Bajpai</p>
                  <p className="truncate text-xs text-slate-400">Regional Analytics Lead</p>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <TopHeader activeItem={activeItem} role={role} setRole={setRole} active={active} setActive={setActiveWithRoute} />

          <section className="mx-auto w-full max-w-[1500px] px-4 py-5 sm:px-6 lg:px-8">
            {error && (
              <div className="mb-4 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <AlertTriangle className="mt-0.5 shrink-0" size={18} />
                <span>{error}</span>
              </div>
            )}

            {active === "home" && <HomeView setActive={setActiveWithRoute} />}
            {active === "customer" && <CustomerView />}
            {active === "agent" && <AgentView />}
            {active === "campaign" && <CampaignView />}
            {active === "agentPerformance" && <AgentPerformanceView />}
            {active === "lapse" && <LapseRiskView />}
            {active === "intelligence" && <AiInsightV10View role={role} setRole={setRole} setActive={setActiveWithRoute} />}
            {active === "evidenceHub" && <InsightEvidenceHubView />}
          </section>

        </section>
      </div>
    </main>
  );
}

function TopHeader({
  activeItem,
  role,
  setRole,
  active,
  setActive
}: {
  activeItem: NavItem;
  role: string;
  setRole: (role: string) => void;
  active: NavKey;
  setActive: (key: NavKey) => void;
}) {
  const Icon = activeItem.icon;
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-700">
              <Icon size={22} />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-red-700">Insurance Decision Intelligence Platform</p>
              <h2 className="truncate text-2xl font-bold text-slate-950">{activeItem.label}</h2>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label className="flex min-w-64 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <BriefcaseBusiness size={17} className="text-slate-500" />
              <select
                className="w-full bg-transparent text-sm font-semibold text-slate-800 outline-none"
                value={role}
                onChange={(event) => setRole(event.target.value)}
              >
                {roles.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">NB</div>
              <div className="hidden sm:block">
                <p className="text-sm font-semibold">Nitin Bajpai</p>
                <p className="text-xs text-slate-500">Insurance intelligence platform</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex gap-2 overflow-x-auto pb-1 lg:hidden">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={classNames(
                "flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold",
                active === item.key ? "border-red-200 bg-red-50 text-red-700" : "border-slate-200 bg-white text-slate-600"
              )}
              onClick={() => setActive(item.key)}
            >
              <item.icon size={16} />
              {item.shortLabel}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}

function SidebarButton({ item, active, onClick }: { item: NavItem; active: boolean; onClick: () => void }) {
  const Icon = item.icon;
  return (
    <button
      className={classNames(
        "group flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm font-semibold transition",
        active ? "bg-red-600 text-white shadow-lg shadow-red-950/30" : "text-slate-300 hover:bg-white/10 hover:text-white"
      )}
      onClick={onClick}
    >
      <Icon size={19} />
      <span className="min-w-0 flex-1 truncate">{item.label}</span>
      <ChevronRight size={16} className={active ? "opacity-100" : "opacity-0 group-hover:opacity-70"} />
    </button>
  );
}

function HomeView({ setActive }: { setActive: (key: NavKey) => void }) {
  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-xl bg-slate-950 text-white shadow-xl">
        <div className="grid gap-6 p-6 lg:grid-cols-[1.2fr_0.8fr] lg:p-8">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-red-300">Executive command center</p>
            <h2 className="mt-3 max-w-3xl text-4xl font-bold leading-tight lg:text-5xl">
              Turn insurance data, model scores, and next-best-actions into confident decisions.
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">
              AI-enabled platform for customer intelligence, agent productivity, campaign effectiveness, lapse risk monitoring, model governance, and decision insights.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button className="rounded-lg bg-red-600 px-4 py-3 text-sm font-bold text-white hover:bg-red-700" onClick={() => setActive("intelligence")}>
                To AI Insight Platform
              </button>
              <button className="rounded-lg border border-white/15 px-4 py-3 text-sm font-bold text-white hover:bg-white/10" onClick={() => setActive("evidenceHub")}>
                Review the Underlying Models and Insights
              </button>
            </div>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-5">
            <p className="text-sm font-semibold text-slate-300">Today’s decision queue</p>
            <div className="mt-5 space-y-4">
              {recommendations.map((item) => (
                <div key={item.title} className="rounded-lg bg-white/10 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold">{item.title}</p>
                    <ConfidenceBadge value={item.confidence} />
                  </div>
                  <p className="mt-2 text-sm text-slate-300">{item.reason}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <KpiGrid items={kpis} />

      <section className="grid gap-5 xl:grid-cols-3">
        <ChartCard title="Portfolio momentum" subtitle="Indexed monthly performance" icon={<TrendingUp size={20} />}>
          <Sparkline values={monthlyTrend} />
        </ChartCard>
        <ChartCard title="Sales mix by product" subtitle="New business premium share" icon={<PieChart size={20} />}>
          <HorizontalBars data={salesMix} />
        </ChartCard>
        <ChartCard title="Distribution channels" subtitle="Policy conversion contribution" icon={<BarChart3 size={20} />}>
          <HorizontalBars data={channelSeries} />
        </ChartCard>
      </section>

      <section className="grid gap-5 xl:grid-cols-[1fr_0.8fr]">
        <RecommendationPanel />
        <DataLineagePanel />
      </section>
    </div>
  );
}

function CustomerView() {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<CustomerSearchOption[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerRecord | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [loadMessage, setLoadMessage] = useState("");

  useEffect(() => {
    void searchCustomerRecords("", true);
  }, []);

  async function searchCustomerRecords(searchText = query, selectFirst = false) {
    setIsSearching(true);
    setLoadMessage("");
    try {
      const rows = await apiGet<Array<Record<string, unknown>>>(`/customers/search?q=${encodeURIComponent(searchText)}&limit=8`);
      const options = rows.map(mapCustomerSearchOption);
      setMatches(options);
      if ((selectFirst || !selectedCustomer) && options[0]) {
        await loadCustomer360(options[0].id);
      }
    } catch {
      const fallbackOptions = customerRecords.map((customer) => ({
        id: customer.id,
        name: customer.name,
        customerNumber: customer.id,
        policyNumber: customer.policyNumber
      }));
      setMatches(fallbackOptions);
      setSelectedCustomer(customerRecords[0]);
      setSelectedCustomerId(customerRecords[0].id);
      setLoadMessage("Live customer API is unavailable. Showing platform sample data.");
    } finally {
      setIsSearching(false);
    }
  }

  async function loadCustomer360(customerId: string) {
    setSelectedCustomerId(customerId);
    try {
      const payload = await apiGet<Entity360Payload>(`/customers/${customerId}/360`);
      setSelectedCustomer(mapCustomer360(payload));
    } catch {
      const fallback = customerRecords.find((customer) => customer.id === customerId) || customerRecords[0];
      setSelectedCustomer(fallback);
      setLoadMessage("Live customer 360 API is unavailable. Showing platform sample data.");
    }
  }

  async function searchCustomer(event?: FormEvent) {
    event?.preventDefault();
    await searchCustomerRecords(query, true);
  }

  return (
    <SectionFrame
      title="Know Your Customer"
      description="A customer 360 workspace for agents and managers to review profile, portfolio, risks, opportunities, recommended actions, and evidence."
    >
      <CustomerSearchPanel
        query={query}
        setQuery={setQuery}
        matches={matches}
        selectedCustomerId={selectedCustomerId}
        onSelectCustomer={loadCustomer360}
        isSearching={isSearching}
        onSearch={searchCustomer}
      />
      {loadMessage && <InlineNotice message={loadMessage} />}

      {selectedCustomer ? (
        <>
          <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <CustomerProfilePanel customer={selectedCustomer} />
            <PolicyPortfolioPanel customer={selectedCustomer} />
          </div>

          <div className="grid gap-5 xl:grid-cols-[1fr_0.9fr]">
            <RiskOpportunityPanel customer={selectedCustomer} />
            <CustomerRecommendationPanel customer={selectedCustomer} />
          </div>

          <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
            <EngagementTimelinePanel customer={selectedCustomer} />
            <EvidenceLineagePanel customer={selectedCustomer} />
          </div>
        </>
      ) : (
        <LoadingPanel label="Loading customer intelligence from backend data tables" />
      )}
    </SectionFrame>
  );
}

function CustomerSearchPanel({
  query,
  setQuery,
  matches,
  selectedCustomerId,
  onSelectCustomer,
  isSearching,
  onSearch
}: {
  query: string;
  setQuery: (value: string) => void;
  matches: CustomerSearchOption[];
  selectedCustomerId: string;
  onSelectCustomer: (id: string) => void;
  isSearching: boolean;
  onSearch: (event?: FormEvent) => void;
}) {
  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr] xl:items-end">
        <form onSubmit={onSearch}>
          <label className="text-sm font-bold text-slate-950">Customer search</label>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                className="h-12 w-full rounded-lg border border-slate-200 bg-slate-50 pl-10 pr-3 text-sm outline-none focus:border-red-500 focus:ring-4 focus:ring-red-100"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by name, customer ID, or policy number"
              />
            </div>
            <button className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700" type="submit">
              {isSearching ? <Loader2 className="animate-spin" size={18} /> : <Search size={18} />}
              Search
            </button>
          </div>
        </form>

        <div className="flex flex-wrap gap-2 xl:justify-end">
          {matches.slice(0, 3).map((customer) => (
            <button
              key={customer.id}
              className={classNames(
                "rounded-lg border px-3 py-2 text-left text-sm font-semibold",
                selectedCustomerId === customer.id ? "border-red-300 bg-red-50 text-red-700" : "border-slate-200 bg-slate-50 text-slate-700 hover:border-red-200"
              )}
              onClick={() => onSelectCustomer(customer.id)}
            >
              <span className="block">{customer.name}</span>
              <span className="block text-xs font-medium text-slate-500">{customer.policyNumber}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function CustomerProfilePanel({ customer }: { customer: CustomerRecord }) {
  return (
    <article className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="bg-slate-950 p-5 text-white">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-600 text-xl font-bold">
              {customer.name
                .split(" ")
                .map((part) => part[0])
                .join("")
                .slice(0, 2)}
            </div>
            <div>
              <h3 className="text-2xl font-bold">{customer.name}</h3>
              <p className="mt-1 text-sm text-slate-300">{customer.id} | {customer.status}</p>
            </div>
          </div>
          <span className="w-fit rounded-full bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-red-100">
            {customer.segment}
          </span>
        </div>
      </div>
      <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
        <MetricBox label="Age" value={`${customer.age}`} />
        <MetricBox label="Income band" value={customer.incomeBand} />
        <MetricBox label="Customer since" value={customer.customerSince} />
        <MetricBox label="Advisor" value={customer.advisor} />
      </div>
      <div className="grid gap-3 border-t border-slate-100 p-5 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
        <CustomerFact icon={<MapPin size={17} />} label="Location" value={customer.location} />
        <CustomerFact icon={<PhoneCall size={17} />} label="Preferred channel" value={customer.preferredChannel} />
      </div>
    </article>
  );
}

function CustomerFact({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg bg-slate-50 p-3">
      <div className="rounded-lg bg-red-50 p-2 text-red-700">{icon}</div>
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</p>
        <p className="mt-1 text-sm font-bold text-slate-950">{value}</p>
      </div>
    </div>
  );
}

function PolicyPortfolioPanel({ customer }: { customer: CustomerRecord }) {
  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Policy portfolio</h3>
          <p className="mt-1 text-sm text-slate-500">Active policies, product mix, premium, sum assured, and renewal timing.</p>
        </div>
        <HeartPulse className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <MetricBox label="Active policies" value={`${customer.portfolio.activePolicies}`} />
        <MetricBox label="Annual premium" value={customer.portfolio.annualPremium} />
        <MetricBox label="Sum assured" value={customer.portfolio.sumAssured} />
        <MetricBox label="Next renewal" value={customer.portfolio.nextRenewal} />
      </div>
      <div className="mt-5">
        <HorizontalBars data={customer.portfolio.productMix} />
      </div>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
            <tr>
              {["Policy", "Product", "Premium", "Sum assured", "Renewal"].map((column) => (
                <th className="px-3 py-3 font-bold" key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {customer.portfolio.policies.map((policy) => (
              <tr key={policy.policyNumber}>
                <td className="px-3 py-3 font-semibold text-slate-950">{policy.policyNumber}</td>
                <td className="px-3 py-3 text-slate-600">{policy.product}</td>
                <td className="px-3 py-3 text-slate-600">{policy.premium}</td>
                <td className="px-3 py-3 text-slate-600">{policy.sumAssured}</td>
                <td className="px-3 py-3 text-slate-600">{policy.renewalDate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RiskOpportunityPanel({ customer }: { customer: CustomerRecord }) {
  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Risk and opportunity scores</h3>
          <p className="mt-1 text-sm text-slate-500">Model signals translated into practical sales and service priorities.</p>
        </div>
        <Activity className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {customer.scores.map((score) => (
          <ScoreTile key={score.label} score={score} />
        ))}
      </div>
    </section>
  );
}

function ScoreTile({ score }: { score: CustomerScore }) {
  const color = {
    red: "bg-red-600",
    green: "bg-emerald-500",
    amber: "bg-amber-500",
    slate: "bg-slate-700"
  }[score.tone];
  return (
    <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="font-bold text-slate-950">{score.label}</h4>
          <p className="mt-1 text-sm text-slate-500">{score.helper}</p>
        </div>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-700 ring-1 ring-slate-200">{score.display}</span>
      </div>
      <div className="mt-4 h-2 rounded-full bg-white">
        <div className={classNames("h-2 rounded-full", color)} style={{ width: `${score.value}%` }} />
      </div>
    </article>
  );
}

function CustomerRecommendationPanel({ customer }: { customer: CustomerRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Recommended action</h3>
          <p className="mt-1 text-sm text-slate-500">Prioritized using model scores, business rules, channel preference, and service constraints.</p>
        </div>
        <Sparkles className="text-red-600" size={22} />
      </div>
      <div className="mt-5 space-y-4">
        {customer.recommendations.map((item) => (
          <article key={item.action} className="rounded-lg border border-red-100 bg-red-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h4 className="font-bold text-slate-950">{item.action}</h4>
              <div className="flex items-center gap-2">
                <PriorityBadge value={item.priority} />
                <ConfidenceBadge value={item.confidence} />
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <MetricBox label="Recommended product" value={item.product} />
              <MetricBox label="Preferred channel" value={customer.preferredChannel} />
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-700">{item.reason}</p>
            <div className="mt-4 rounded-lg border border-white bg-white p-4">
              <div className="flex items-start gap-3">
                <Mail className="mt-0.5 text-red-600" size={18} />
                <p className="text-sm leading-6 text-slate-700">{item.message}</p>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function EngagementTimelinePanel({ customer }: { customer: CustomerRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">Engagement timeline</h3>
      <div className="mt-5 space-y-4">
        {customer.timeline.map((event, index) => (
          <div key={`${event.date}-${event.title}`} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className={classNames("h-3 w-3 rounded-full", timelineTone(event.tone))} />
              {index < customer.timeline.length - 1 && <div className="h-full w-px bg-slate-200" />}
            </div>
            <div className="pb-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-bold text-slate-950">{event.title}</p>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">{event.type}</span>
              </div>
              <p className="mt-1 text-xs font-semibold uppercase tracking-[0.1em] text-slate-400">{event.date}</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">{event.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function EvidenceLineagePanel({ customer }: { customer: CustomerRecord }) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 pb-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-bold text-slate-950">Evidence and data lineage</h3>
            <p className="mt-1 text-sm text-slate-500">Source facts behind the customer recommendation and model scores.</p>
          </div>
          <GitBranch className="text-red-600" size={22} />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
            <tr>
              {["Source table", "Source column", "Metric", "Model used", "Timestamp"].map((column) => (
                <th className="px-5 py-3 font-bold" key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {customer.lineage.map((row) => (
              <tr key={`${row.sourceTable}-${row.metric}`}>
                <td className="px-5 py-4 font-semibold text-slate-950">{row.sourceTable}</td>
                <td className="px-5 py-4 text-slate-600">{row.sourceColumn}</td>
                <td className="px-5 py-4 text-slate-600">{row.metric}</td>
                <td className="px-5 py-4 text-slate-600">{row.model}</td>
                <td className="px-5 py-4 text-slate-600">{row.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function timelineTone(tone: CustomerRecord["timeline"][number]["tone"]) {
  return {
    red: "bg-red-600",
    green: "bg-emerald-500",
    amber: "bg-amber-500",
    slate: "bg-slate-500"
  }[tone];
}

function AgentView() {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<AgentSearchOption[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [agent, setAgent] = useState<AgentRecord | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [loadMessage, setLoadMessage] = useState("");

  useEffect(() => {
    void searchAgentRecords("", true);
  }, []);

  async function searchAgentRecords(searchText = query, selectFirst = false) {
    setIsSearching(true);
    setLoadMessage("");
    try {
      const rows = await apiGet<Array<Record<string, unknown>>>(`/agents/search?q=${encodeURIComponent(searchText)}&limit=8`);
      const options = rows.map(mapAgentSearchOption);
      setMatches(options);
      if ((selectFirst || !agent) && options[0]) {
        await loadAgent360(options[0].id);
      }
    } catch {
      const fallbackOptions = agentRecords.map((item) => ({
        id: item.code,
        name: item.name,
        agentNumber: item.code,
        territory: item.region
      }));
      setMatches(fallbackOptions);
      setAgent(agentRecords[0]);
      setSelectedAgentId(agentRecords[0].code);
      setLoadMessage("Live agent API is unavailable. Showing platform sample data.");
    } finally {
      setIsSearching(false);
    }
  }

  async function loadAgent360(agentId: string) {
    setSelectedAgentId(agentId);
    try {
      const payload = await apiGet<Entity360Payload>(`/agents/${agentId}/360`);
      setAgent(mapAgent360(payload));
    } catch {
      const fallback = agentRecords.find((item) => item.code === agentId) || agentRecords[0];
      setAgent(fallback);
      setLoadMessage("Live agent 360 API is unavailable. Showing platform sample data.");
    }
  }

  async function searchAgent(event?: FormEvent) {
    event?.preventDefault();
    await searchAgentRecords(query, true);
  }

  return (
    <SectionFrame
      title="Know Your Agent"
      description="A distribution intelligence workspace for managers to understand agent profile, productivity, pipeline, movement, risk, and next actions."
    >
      <AgentSearchPanel
        query={query}
        setQuery={setQuery}
        matches={matches}
        selectedAgentId={selectedAgentId}
        onSelectAgent={loadAgent360}
        isSearching={isSearching}
        onSearch={searchAgent}
      />
      {loadMessage && <InlineNotice message={loadMessage} />}

      {agent ? (
        <>
          <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
            <AgentProfilePanel agent={agent} />
            <AgentKpiPanel agent={agent} />
          </div>

          <div className="grid gap-5 xl:grid-cols-[1fr_0.9fr]">
            <MapaMetricsPanel agent={agent} />
            <AgentPortfolioPanel agent={agent} />
          </div>

          <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
            <AgentMovementPanel agent={agent} />
            <AgentRiskPanel agent={agent} />
          </div>

          <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
            <ManagerActionsPanel agent={agent} />
            <AgentEvidencePanel agent={agent} />
          </div>
        </>
      ) : (
        <LoadingPanel label="Loading agent intelligence from backend data tables" />
      )}
    </SectionFrame>
  );
}

function AgentSearchPanel({
  query,
  setQuery,
  matches,
  selectedAgentId,
  onSelectAgent,
  isSearching,
  onSearch
}: {
  query: string;
  setQuery: (value: string) => void;
  matches: AgentSearchOption[];
  selectedAgentId: string;
  onSelectAgent: (id: string) => void;
  isSearching: boolean;
  onSearch: (event?: FormEvent) => void;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr] xl:items-end">
        <form onSubmit={onSearch}>
          <label className="text-sm font-bold text-slate-950">Agent search</label>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                className="h-12 w-full rounded-lg border border-slate-200 bg-slate-50 pl-10 pr-3 text-sm outline-none focus:border-red-500 focus:ring-4 focus:ring-red-100"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by agent name, agent code, branch, or region"
              />
            </div>
            <button className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700" type="submit">
              {isSearching ? <Loader2 className="animate-spin" size={18} /> : <Search size={18} />}
              Search
            </button>
          </div>
        </form>

        <div className="flex flex-wrap gap-2 xl:justify-end">
          {matches.slice(0, 3).map((item) => (
            <button
              key={item.id}
              className={classNames(
                "rounded-lg border px-3 py-2 text-left text-sm font-semibold",
                selectedAgentId === item.id ? "border-red-300 bg-red-50 text-red-700" : "border-slate-200 bg-slate-50 text-slate-700 hover:border-red-200"
              )}
              onClick={() => onSelectAgent(item.id)}
            >
              <span className="block">{item.name}</span>
              <span className="block text-xs font-medium text-slate-500">{item.agentNumber} | {item.territory}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function AgentProfilePanel({ agent }: { agent: AgentRecord }) {
  return (
    <article className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="bg-slate-950 p-5 text-white">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-600 text-xl font-bold">
            {agent.name
              .split(" ")
              .map((part) => part[0])
              .join("")
              .slice(0, 2)}
          </div>
          <div>
            <h3 className="text-2xl font-bold">{agent.name}</h3>
            <p className="mt-1 text-sm text-slate-300">{agent.code} | {agent.status}</p>
          </div>
        </div>
        <p className="mt-4 w-fit rounded-full bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-red-100">
          {agent.tier}
        </p>
      </div>
      <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
        <MetricBox label="Region" value={agent.region} />
        <MetricBox label="Branch" value={agent.branch} />
        <MetricBox label="Manager" value={agent.manager} />
        <MetricBox label="Tenure" value={agent.tenure} />
      </div>
    </article>
  );
}

function AgentKpiPanel({ agent }: { agent: AgentRecord }) {
  return (
    <section className="grid gap-4 md:grid-cols-2">
      {agent.kpis.map((item) => (
        <KpiCard key={item.label} item={item} />
      ))}
    </section>
  );
}

function MapaMetricsPanel({ agent }: { agent: AgentRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">MAPA metrics</h3>
          <p className="mt-1 text-sm text-slate-500">Meetings, activities, proposals, applications, and productivity trend.</p>
        </div>
        <ClipboardList className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-4">
        <MetricBox label="Meetings" value={`${agent.mapa.meetings}`} />
        <MetricBox label="Activities" value={`${agent.mapa.activities}`} />
        <MetricBox label="Proposals" value={`${agent.mapa.proposals}`} />
        <MetricBox label="Applications" value={`${agent.mapa.applications}`} />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_0.9fr]">
        <Sparkline values={agent.mapa.trend} />
        <HorizontalBars data={agent.mapa.bars} />
      </div>
    </section>
  );
}

function AgentPortfolioPanel({ agent }: { agent: AgentRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Customer portfolio</h3>
          <p className="mt-1 text-sm text-slate-500">Assigned book quality and lead-action potential.</p>
        </div>
        <UsersRound className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <MetricBox label="Assigned customers" value={agent.portfolio.assignedCustomers} />
        <MetricBox label="High propensity" value={agent.portfolio.highPropensity} />
        <MetricBox label="High lapse risk" value={agent.portfolio.highLapseRisk} />
        <MetricBox label="High CLV" value={agent.portfolio.highClv} />
      </div>
      <div className="mt-5">
        <HorizontalBars data={agent.portfolio.segments} />
      </div>
    </section>
  );
}

function AgentMovementPanel({ agent }: { agent: AgentRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="border-b border-slate-200 pb-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-bold text-slate-950">Agent movement</h3>
            <p className="mt-1 text-sm text-slate-500">Branch changes, region movement, promotions, and territory changes.</p>
          </div>
          <GitBranch className="text-red-600" size={22} />
        </div>
      </div>
      <div className="mt-5 space-y-3">
        {agent.movements.map((item) => (
          <article key={`${item.date}-${item.type}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-bold text-slate-950">{item.type}</p>
                <p className="mt-1 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{item.date}</p>
              </div>
              <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-red-700 ring-1 ring-red-100">{item.impact}</span>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <MetricBox label="From" value={item.from} />
              <MetricBox label="To" value={item.to} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function AgentRiskPanel({ agent }: { agent: AgentRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Agent risk</h3>
          <p className="mt-1 text-sm text-slate-500">Attrition, declining activity, and target miss risk.</p>
        </div>
        <ShieldAlert className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
        {agent.risks.map((risk) => (
          <ScoreTile key={risk.label} score={risk} />
        ))}
      </div>
    </section>
  );
}

function ManagerActionsPanel({ agent }: { agent: AgentRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Recommended manager actions</h3>
          <p className="mt-1 text-sm text-slate-500">Coaching, lead allocation, product training, and retention actions.</p>
        </div>
        <Sparkles className="text-red-600" size={22} />
      </div>
      <div className="mt-5 space-y-3">
        {agent.actions.map((item) => (
          <article key={item.title} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h4 className="font-bold text-slate-950">{item.title}</h4>
              <div className="flex items-center gap-2">
                <PriorityBadge value={item.priority} />
                <ConfidenceBadge value={item.confidence} />
              </div>
            </div>
            <p className="mt-2 text-xs font-bold uppercase tracking-[0.12em] text-red-700">{item.type}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">{item.reason}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function AgentEvidencePanel({ agent }: { agent: AgentRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="border-b border-slate-200 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-bold text-slate-950">Evidence panel</h3>
            <p className="mt-1 text-sm text-slate-500">Source tables, model scores, rationale, and confidence.</p>
          </div>
          <FileSearch className="text-red-600" size={22} />
        </div>
      </div>
      <div className="mt-5 space-y-3">
        {agent.evidence.map((row) => (
          <article key={`${row.sourceTable}-${row.modelScore}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-bold text-slate-950">{row.sourceTable}</p>
                <p className="mt-1 text-sm text-slate-500">{row.modelScore}</p>
              </div>
              <ConfidenceBadge value={row.confidence} />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">{row.rationale}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function CampaignView() {
  const [query, setQuery] = useState("");
  const [channel, setChannel] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [options, setOptions] = useState<CampaignSearchOption[]>([]);
  const [campaign, setCampaign] = useState<CampaignRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    void searchCampaignRecords("", true);
  }, []);

  async function searchCampaignRecords(searchText = query, selectFirst = false) {
    setLoading(true);
    setNotice("");
    const params = new URLSearchParams({ q: searchText, limit: "8" });
    if (channel !== "all") params.set("channel", channel);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    try {
      const rows = await apiGet<Array<Record<string, unknown>>>(`/campaigns/search?${params.toString()}`);
      const mapped = rows.map(mapCampaignSearchOption);
      setOptions(mapped);
      if (selectFirst && mapped[0]) await loadCampaign(mapped[0].id);
      if (!mapped.length) setNotice("No campaigns matched the selected filters. Broaden the date range or channel.");
    } catch (error) {
      setNotice(`Campaign API unavailable, showing platform sample data. ${error instanceof Error ? error.message : ""}`);
      setOptions(campaignRecords.map((item) => ({ id: item.id, name: item.name, code: item.code, channel: item.channel, startDate: item.startDate })));
      if (selectFirst) setCampaign(campaignRecords[0]);
    } finally {
      setLoading(false);
    }
  }

  async function loadCampaign(campaignId: string) {
    setLoading(true);
    setNotice("");
    try {
      const payload = await apiGet<Entity360Payload>(`/campaigns/${campaignId}/360`);
      setCampaign(mapCampaign360(payload));
    } catch (error) {
      const fallback = campaignRecords.find((item) => item.id === campaignId) || campaignRecords[0];
      setCampaign(fallback);
      setNotice(`Campaign detail API unavailable, showing platform sample data. ${error instanceof Error ? error.message : ""}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(event?: FormEvent) {
    event?.preventDefault();
    await searchCampaignRecords(query, true);
  }

  const activeCampaign = campaign || campaignRecords[0];
  const kpiItems: Kpi[] = [
    { label: "Targeted customers", value: formatCount(activeCampaign.funnel.targeted), trend: "+0", tone: "slate", helper: "Selected audience for campaign" },
    { label: "Response rate", value: activeCampaign.analytics.responseRate, trend: "+0 pts", tone: "green", helper: "Responses divided by targets" },
    { label: "Policy conversions", value: formatCount(activeCampaign.funnel.policiesIssued), trend: "+0", tone: "red", helper: "Attributed policies issued" },
    { label: "Premium generated", value: activeCampaign.analytics.premiumGenerated, trend: activeCampaign.analytics.roi, tone: "green", helper: "Conversion premium and ROI" }
  ];

  return (
    <SectionFrame
      title="Campaign Effectiveness"
      description="A marketing intelligence workspace to evaluate campaign performance, lead quality, conversion economics, and next-best-follow-up."
    >
      <CampaignFilterPanel
        query={query}
        setQuery={setQuery}
        channel={channel}
        setChannel={setChannel}
        dateFrom={dateFrom}
        setDateFrom={setDateFrom}
        dateTo={dateTo}
        setDateTo={setDateTo}
        options={options}
        selectedId={activeCampaign.id}
        loading={loading}
        onSearch={handleSearch}
        onSelect={loadCampaign}
      />
      {notice && <InlineNotice message={notice} />}
      <KpiGrid items={kpiItems} />
      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <CampaignOverviewPanel campaign={activeCampaign} />
        <CampaignFunnelMetricsPanel campaign={activeCampaign} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <CampaignConversionPanel campaign={activeCampaign} />
        <CampaignSegmentPerformancePanel campaign={activeCampaign} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <CampaignMlInsightsPanel campaign={activeCampaign} />
        <CampaignRecommendationsPanel campaign={activeCampaign} />
      </div>
      <CampaignLineagePanel campaign={activeCampaign} />
    </SectionFrame>
  );
}

function CampaignFilterPanel({
  query,
  setQuery,
  channel,
  setChannel,
  dateFrom,
  setDateFrom,
  dateTo,
  setDateTo,
  options,
  selectedId,
  loading,
  onSearch,
  onSelect
}: {
  query: string;
  setQuery: (value: string) => void;
  channel: string;
  setChannel: (value: string) => void;
  dateFrom: string;
  setDateFrom: (value: string) => void;
  dateTo: string;
  setDateTo: (value: string) => void;
  options: CampaignSearchOption[];
  selectedId: string;
  loading: boolean;
  onSearch: (event?: FormEvent) => void;
  onSelect: (campaignId: string) => void;
}) {
  const channelOptions = ["all", "email", "sms", "direct_mail", "agent_call", "web", "app", "social", "partner"];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end">
        <form className="grid flex-1 gap-3 md:grid-cols-[1.2fr_0.7fr_0.65fr_0.65fr_auto]" onSubmit={onSearch}>
          <label className="block">
            <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Campaign search</span>
            <div className="relative mt-2">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                className="h-11 w-full rounded-lg border border-slate-200 bg-slate-50 pl-10 pr-3 text-sm outline-none focus:border-red-500 focus:ring-4 focus:ring-red-100"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by campaign name, code, product, or objective"
              />
            </div>
          </label>
          <label className="block">
            <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Medium</span>
            <select
              className="mt-2 h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm outline-none focus:border-red-500 focus:ring-4 focus:ring-red-100"
              value={channel}
              onChange={(event) => setChannel(event.target.value)}
            >
              {channelOptions.map((item) => (
                <option key={item} value={item}>
                  {item === "all" ? "All mediums" : titleCase(item)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">From</span>
            <input
              className="mt-2 h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm outline-none focus:border-red-500 focus:ring-4 focus:ring-red-100"
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">To</span>
            <input
              className="mt-2 h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm outline-none focus:border-red-500 focus:ring-4 focus:ring-red-100"
              type="date"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </label>
          <button className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700" disabled={loading}>
            {loading ? <Loader2 className="animate-spin" size={17} /> : <Search size={17} />}
            Filter
          </button>
        </form>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {options.slice(0, 8).map((item) => (
          <button
            key={item.id}
            className={classNames(
              "rounded-lg border p-3 text-left transition hover:border-red-300 hover:bg-red-50",
              selectedId === item.id ? "border-red-300 bg-red-50" : "border-slate-200 bg-slate-50"
            )}
            type="button"
            onClick={() => onSelect(item.id)}
          >
            <p className="line-clamp-1 text-sm font-bold text-slate-950">{item.name}</p>
            <p className="mt-1 text-xs text-slate-500">{item.code || "No code"} | {titleCase(item.channel || "medium")} | {dateOnly(item.startDate)}</p>
          </button>
        ))}
      </div>
    </section>
  );
}

function CampaignOverviewPanel({ campaign }: { campaign: CampaignRecord }) {
  const overview = [
    ["Campaign name", campaign.name],
    ["Product", campaign.product],
    ["Channel", titleCase(campaign.channel)],
    ["Target segment", campaign.targetSegment],
    ["Start date", campaign.startDate],
    ["End date", campaign.endDate],
    ["Budget", campaign.budget],
    ["Status", titleCase(campaign.status)]
  ];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Campaign overview</h3>
          <p className="mt-1 text-sm text-slate-500">{campaign.objective}</p>
        </div>
        <CalendarClock className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {overview.map(([label, value]) => (
          <MetricBox key={label} label={label} value={value || "Not captured"} />
        ))}
      </div>
    </section>
  );
}

function CampaignFunnelMetricsPanel({ campaign }: { campaign: CampaignRecord }) {
  const rows = [
    ["Targeted", campaign.funnel.targeted],
    ["Delivered", campaign.funnel.delivered],
    ["Opened", campaign.funnel.opened],
    ["Clicked", campaign.funnel.clicked],
    ["Responded", campaign.funnel.responded],
    ["Leads created", campaign.funnel.leadsCreated],
    ["Quotes created", campaign.funnel.quotesCreated],
    ["Policies issued", campaign.funnel.policiesIssued]
  ] as const;
  const max = Math.max(...rows.map(([, value]) => value), 1);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Funnel metrics</h3>
          <p className="mt-1 text-sm text-slate-500">Audience progression from targeting to policies issued.</p>
        </div>
        <Target className="text-red-600" size={22} />
      </div>
      <div className="mt-5 space-y-3">
        {rows.map(([label, value], index) => (
          <div key={label} className="rounded-lg bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-semibold text-slate-700">{label}</span>
              <span className="font-bold text-slate-950">{formatCount(value)}</span>
            </div>
            <div className="mt-2 h-3 rounded-full bg-white">
              <div className={classNames("h-3 rounded-full", index < 2 ? "bg-slate-800" : "bg-red-600")} style={{ width: `${Math.max(5, (value / max) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function CampaignConversionPanel({ campaign }: { campaign: CampaignRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Conversion analytics</h3>
          <p className="mt-1 text-sm text-slate-500">Response quality, lead economics, policy conversion, and premium return.</p>
        </div>
        <PieChart className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <MetricBox label="Response rate" value={campaign.analytics.responseRate} />
        <MetricBox label="Lead conversion rate" value={campaign.analytics.leadConversionRate} />
        <MetricBox label="Policy conversion rate" value={campaign.analytics.policyConversionRate} />
        <MetricBox label="Cost per lead" value={campaign.analytics.costPerLead} />
        <MetricBox label="Cost per policy" value={campaign.analytics.costPerPolicy} />
        <MetricBox label="Premium generated" value={campaign.analytics.premiumGenerated} />
        <MetricBox label="ROI" value={campaign.analytics.roi} />
      </div>
    </section>
  );
}

function CampaignSegmentPerformancePanel({ campaign }: { campaign: CampaignRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Segment performance</h3>
          <p className="mt-1 text-sm text-slate-500">Conversion strength by segment, region, product, channel, and agent group.</p>
        </div>
        <BarChart3 className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <MiniPerformance title="Customer segment" data={campaign.performance.segments} />
        <MiniPerformance title="Region" data={campaign.performance.regions} />
        <MiniPerformance title="Product" data={campaign.performance.products} />
        <MiniPerformance title="Channel" data={campaign.performance.channels} />
        <div className="xl:col-span-2">
          <MiniPerformance title="Agent" data={campaign.performance.agents} />
        </div>
      </div>
    </section>
  );
}

function MiniPerformance({ title, data }: { title: string; data: ChartSeries[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <p className="mb-3 text-sm font-bold text-slate-950">{title}</p>
      <HorizontalBars data={data} />
    </div>
  );
}

function CampaignMlInsightsPanel({ campaign }: { campaign: CampaignRecord }) {
  const toneClass = {
    red: "bg-red-50 text-red-700 border-red-100",
    green: "bg-emerald-50 text-emerald-700 border-emerald-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
    slate: "bg-slate-50 text-slate-700 border-slate-100"
  };
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">ML-driven insights</h3>
          <p className="mt-1 text-sm text-slate-500">Predicted conversion audiences and recommended follow-up posture.</p>
        </div>
        <Sparkles className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {campaign.insights.map((item) => (
          <article key={item.title} className={classNames("rounded-lg border p-4", toneClass[item.tone])}>
            <p className="text-xs font-bold uppercase tracking-[0.12em] opacity-80">{item.title}</p>
            <p className="mt-2 text-2xl font-bold">{item.value}</p>
            <p className="mt-2 text-sm leading-6">{item.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function CampaignRecommendationsPanel({ campaign }: { campaign: CampaignRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Recommendations</h3>
          <p className="mt-1 text-sm text-slate-500">Next-best-follow-up decisions for campaign managers and sales teams.</p>
        </div>
        <Mail className="text-red-600" size={22} />
      </div>
      <div className="mt-5 space-y-3">
        {campaign.recommendations.map((item) => (
          <article key={item.title} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h4 className="font-bold text-slate-950">{item.title}</h4>
              <div className="flex items-center gap-2">
                <PriorityBadge value={item.priority} />
                <ConfidenceBadge value={item.confidence} />
              </div>
            </div>
            <p className="mt-2 text-xs font-bold uppercase tracking-[0.12em] text-red-700">{item.type}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">{item.reason}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function CampaignLineagePanel({ campaign }: { campaign: CampaignRecord }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Data lineage</h3>
          <p className="mt-1 text-sm text-slate-500">Source tables and model signals used by campaign intelligence.</p>
        </div>
        <GitBranch className="text-red-600" size={22} />
      </div>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
            <tr>
              {["Source table", "Source column", "Metric", "Model used", "Timestamp"].map((column) => (
                <th className="px-4 py-3 font-bold" key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {campaign.lineage.map((row) => (
              <tr key={`${row.sourceTable}-${row.metric}`} className="hover:bg-red-50/40">
                <td className="px-4 py-3 font-semibold text-slate-950">{row.sourceTable}</td>
                <td className="px-4 py-3 text-slate-600">{row.sourceColumn}</td>
                <td className="px-4 py-3 text-slate-600">{row.metric}</td>
                <td className="px-4 py-3 text-slate-600">{row.model}</td>
                <td className="px-4 py-3 text-slate-600">{row.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {["campaigns", "campaign_targets", "campaign_responses", "leads", "opportunities", "policies", "model_scores"].map((item) => (
          <span key={item} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{item}</span>
        ))}
      </div>
    </section>
  );
}

function AgentPerformanceView() {
  const [dashboard, setDashboard] = useState<AgentPerformanceDashboard>(agentPerformanceSample);
  const [region, setRegion] = useState("all");
  const [cluster, setCluster] = useState("all");
  const [customerFocus, setCustomerFocus] = useState("all");
  const [productFocus, setProductFocus] = useState("all");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    void loadDashboard();
  }, []);

  async function loadDashboard(selectedRegion = region) {
    setLoading(true);
    setNotice("");
    const params = new URLSearchParams();
    if (selectedRegion !== "all") params.set("region", selectedRegion);
    try {
      const payload = await apiGet<AgentPerformanceDashboard>(`/agents/performance-dashboard${params.toString() ? `?${params.toString()}` : ""}`);
      setDashboard(payload);
    } catch (error) {
      setDashboard(agentPerformanceSample);
      setNotice(`Agent performance API unavailable, showing platform sample data. ${error instanceof Error ? error.message : ""}`);
    } finally {
      setLoading(false);
    }
  }

  function handleRegionChange(value: string) {
    setRegion(value);
    void loadDashboard(value);
  }

  const leaderboard = dashboard.leaderboard.filter((row) => {
    const clusterMatch = cluster === "all" || asText(row.agent_cluster) === cluster;
    const customerMatch = customerFocus === "all" || asText(row.customer_focus) === customerFocus;
    const productMatch = productFocus === "all" || asText(row.product_focus) === productFocus;
    return clusterMatch && customerMatch && productMatch;
  });
  const backendRegionOptions = dashboard.region_options ?? [];
  const regionOptions = uniqueOptionsInOrder(
    (backendRegionOptions.length ? backendRegionOptions : dashboard.leaderboard.map((row) => asText(row.region))).filter(Boolean)
  );
  const clusterOptions = uniqueOptions(dashboard.clusters.map((row) => asText(row.agent_cluster)).filter(Boolean));
  const customerOptions = uniqueOptions(dashboard.customer_product_clusters.map((row) => asText(row.customer_focus)).filter(Boolean));
  const productOptions = uniqueOptions(dashboard.customer_product_clusters.map((row) => asText(row.product_focus)).filter(Boolean));

  return (
    <SectionFrame
      title="Agent Performance Tracking"
      description="Track agent productivity, target achievement, conversion, persistency, peer clusters, MDRT performance, rising stars, and coaching needs."
    >
      <AgentPerformanceFilters
        region={region}
        setRegion={handleRegionChange}
        cluster={cluster}
        setCluster={setCluster}
        customerFocus={customerFocus}
        setCustomerFocus={setCustomerFocus}
        productFocus={productFocus}
        setProductFocus={setProductFocus}
        loading={loading}
        regionOptions={regionOptions}
        clusterOptions={clusterOptions}
        customerOptions={customerOptions}
        productOptions={productOptions}
        onRefresh={() => loadDashboard(region)}
      />
      {notice && <InlineNotice message={notice} />}
      <AgentExecutiveKpiStrip dashboard={dashboard} />
      <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <AgentLeaderboardPanel rows={leaderboard} />
        <AgentGrowthRecognitionPanel dashboard={dashboard} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
        <MapaProductivityDashboardPanel dashboard={dashboard} />
        <AgentPerformanceTrendsPanel dashboard={dashboard} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <AgentClusterComparisonPanel dashboard={dashboard} />
        <AgentRiskAlertsPanel dashboard={dashboard} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1fr_0.9fr]">
        <AgentCoachingRecommendationsPanel dashboard={dashboard} />
        <AgentPerformanceEvidencePanel dashboard={dashboard} />
      </div>
    </SectionFrame>
  );
}

function AgentPerformanceFilters({
  region,
  setRegion,
  cluster,
  setCluster,
  customerFocus,
  setCustomerFocus,
  productFocus,
  setProductFocus,
  loading,
  regionOptions,
  clusterOptions,
  customerOptions,
  productOptions,
  onRefresh
}: {
  region: string;
  setRegion: (value: string) => void;
  cluster: string;
  setCluster: (value: string) => void;
  customerFocus: string;
  setCustomerFocus: (value: string) => void;
  productFocus: string;
  setProductFocus: (value: string) => void;
  loading: boolean;
  regionOptions: string[];
  clusterOptions: string[];
  customerOptions: string[];
  productOptions: string[];
  onRefresh: () => void;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[0.8fr_1fr_1fr_1fr_auto]">
        <SelectFilter label="Region" value={region} onChange={setRegion} options={regionOptions} />
        <SelectFilter label="Agent segment" value={cluster} onChange={setCluster} options={clusterOptions} />
        <SelectFilter label="Customer type" value={customerFocus} onChange={setCustomerFocus} options={customerOptions} />
        <SelectFilter label="Product focus" value={productFocus} onChange={setProductFocus} options={productOptions} />
        <button className="inline-flex h-11 items-center justify-center gap-2 self-end rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 className="animate-spin" size={17} /> : <Activity size={17} />}
          Refresh
        </button>
      </div>
    </section>
  );
}

function SelectFilter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
  return (
    <label className="block">
      <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</span>
      <select
        className="mt-2 h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm outline-none focus:border-red-500 focus:ring-4 focus:ring-red-100"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="all">All {label.toLowerCase()}</option>
        {options.map((item) => (
          <option key={item} value={item}>
            {formatFilterOptionLabel(item)}
          </option>
        ))}
      </select>
    </label>
  );
}

function AgentExecutiveKpiStrip({ dashboard }: { dashboard: AgentPerformanceDashboard }) {
  const kpis = dashboard.kpis;
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
      {[
        { label: "Total agents", value: formatCount(kpis.total_agents), helper: "Full distribution force" },
        { label: "Active agents", value: formatCount(kpis.active_agents), helper: "Currently active" },
        { label: "Premium generated", value: formatCurrency(toNumber(kpis.premium_generated)), helper: "Selected period NBP" },
        { label: "Policies sold", value: formatCount(kpis.policies_sold), helper: "Bound policies" },
        { label: "Avg conversion", value: formatDashboardPercent(kpis.average_conversion_rate), helper: "Quote to bind" },
        { label: "Avg persistency", value: formatDashboardPercent(kpis.average_persistency_rate), helper: "Retained over retained plus lapsed" }
      ].map((item) => (
        <article key={item.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{item.label}</p>
          <p className="mt-2 text-2xl font-bold text-slate-950">{item.value}</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">{item.helper}</p>
        </article>
      ))}
    </section>
  );
}

function AgentLeaderboardPanel({ rows }: { rows: Array<Record<string, unknown>> }) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-bold text-slate-950">Agent leaderboard</h3>
            <p className="mt-1 text-sm text-slate-500">Ranked by premium, policies sold, conversion, persistency, and target achievement.</p>
          </div>
          <BadgeCheck className="text-red-600" size={22} />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
            <tr>
              {["Rank", "Agent", "Region", "Cluster", "Premium", "Policies", "Conversion", "Persistency", "Target"].map((column) => (
                <th className="px-4 py-3 font-bold" key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.slice(0, 12).map((row, index) => (
              <tr key={`${asText(row.agent_id, asText(row.agent_name))}-${index}`} className="hover:bg-red-50/40">
                <td className="px-4 py-3 font-bold text-red-700">{formatCount(row.rank || index + 1)}</td>
                <td className="px-4 py-3 font-semibold text-slate-950">{asText(row.agent_name, "Agent")}</td>
                <td className="px-4 py-3 text-slate-600">{asText(row.region, "Unassigned")}</td>
                <td className="px-4 py-3 text-slate-600">{titleCase(asText(row.agent_cluster, "Core advisor"))}</td>
                <td className="px-4 py-3 font-semibold text-slate-950">{formatCurrency(toNumber(row.premium))}</td>
                <td className="px-4 py-3 text-slate-600">{formatCount(row.policies_sold)}</td>
                <td className="px-4 py-3 text-slate-600">{formatDashboardPercent(row.conversion_rate)}</td>
                <td className="px-4 py-3 text-slate-600">{formatDashboardPercent(row.persistency_rate)}</td>
                <td className="px-4 py-3 text-slate-600">{formatDashboardPercent(row.target_achievement)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AgentGrowthRecognitionPanel({ dashboard }: { dashboard: AgentPerformanceDashboard }) {
  return (
    <section className="space-y-5">
      <AgentSpotlight title="Rising stars" icon={<TrendingUp size={20} />} rows={dashboard.rising_stars} description="Fastest-growing agents based on recent premium momentum versus their prior peer baseline." metricKey="growth_rate" metricLabel="Growth" />
      <AgentSpotlight title="MDRT agents" icon={<CircleDollarSign size={20} />} rows={dashboard.mdrt_agents} description="Elite producers using a million-dollar premium proxy for MDRT-style segmentation." metricKey="premium" metricLabel="Premium" currency />
    </section>
  );
}

function AgentSpotlight({
  title,
  description,
  rows,
  icon,
  metricKey,
  metricLabel,
  currency = false
}: {
  title: string;
  description: string;
  rows: Array<Record<string, unknown>>;
  icon: ReactNode;
  metricKey: string;
  metricLabel: string;
  currency?: boolean;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">{title}</h3>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
        <div className="rounded-lg bg-red-50 p-2 text-red-700">{icon}</div>
      </div>
      <div className="mt-4 space-y-3">
        {rows.slice(0, 4).map((row, index) => (
          <article key={`${title}-${asText(row.agent_name)}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-bold text-slate-950">{asText(row.agent_name, "Agent")}</p>
                <p className="mt-1 text-xs text-slate-500">{asText(row.region, "Unassigned")} | {titleCase(asText(row.customer_focus, "mixed book"))} | {titleCase(asText(row.product_focus, "generalist"))}</p>
              </div>
              <div className="text-right">
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{metricLabel}</p>
                <p className="font-bold text-red-700">{currency ? formatCurrency(toNumber(row[metricKey])) : formatDashboardPercent(row[metricKey])}</p>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function MapaProductivityDashboardPanel({ dashboard }: { dashboard: AgentPerformanceDashboard }) {
  const mapa = dashboard.mapa_productivity;
  const total = Math.max(toNumber(mapa.meetings), toNumber(mapa.activities), toNumber(mapa.proposals), toNumber(mapa.applications), toNumber(mapa.policy_issuance), 1);
  const data = [
    { label: "Meetings", value: Math.round((toNumber(mapa.meetings) / total) * 100), color: "bg-red-600", raw: mapa.meetings },
    { label: "Activities", value: Math.round((toNumber(mapa.activities) / total) * 100), color: "bg-slate-800", raw: mapa.activities },
    { label: "Proposals", value: Math.round((toNumber(mapa.proposals) / total) * 100), color: "bg-red-400", raw: mapa.proposals },
    { label: "Applications", value: Math.round((toNumber(mapa.applications) / total) * 100), color: "bg-slate-500", raw: mapa.applications },
    { label: "Policy issuance", value: Math.round((toNumber(mapa.policy_issuance) / total) * 100), color: "bg-amber-500", raw: mapa.policy_issuance }
  ];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">MAPA productivity</h3>
          <p className="mt-1 text-sm text-slate-500">Meetings, activities, proposals, applications, and policy issuance.</p>
        </div>
        <ClipboardList className="text-red-600" size={22} />
      </div>
      <div className="mt-5 space-y-4">
        {data.map((item) => (
          <div key={item.label}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="font-semibold text-slate-700">{item.label}</span>
              <span className="font-bold text-slate-950">{formatCount(item.raw)}</span>
            </div>
            <div className="h-3 rounded-full bg-slate-100">
              <div className={classNames("h-3 rounded-full", item.color)} style={{ width: `${Math.max(3, item.value)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AgentPerformanceTrendsPanel({ dashboard }: { dashboard: AgentPerformanceDashboard }) {
  const trends = dashboard.trends.slice(-12);
  const latestTrendValue = (key: string) => [...trends].reverse().find((row) => toNumber(row[key]) > 0)?.[key];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Performance trends</h3>
          <p className="mt-1 text-sm text-slate-500">Monthly premium, target versus actual, conversion, and persistency movement.</p>
        </div>
        <BarChart3 className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <TrendMiniCard title="Monthly premium trend" values={trends.map((row) => toNumber(row.premium))} value={formatCurrency(toNumber(latestTrendValue("premium")))} />
        <TrendMiniCard title="Target vs actual" values={trends.map((row) => toNumber(row.target_achievement) * 100)} value={formatDashboardPercent(latestTrendValue("target_achievement"))} />
        <TrendMiniCard title="Conversion trend" values={trends.map((row) => toNumber(row.conversion_rate) * 100)} value={formatDashboardPercent(latestTrendValue("conversion_rate"))} />
        <TrendMiniCard title="Persistency trend" values={trends.map((row) => toNumber(row.persistency_rate) * 100)} value={formatDashboardPercent(latestTrendValue("persistency_rate") || dashboard.kpis.average_persistency_rate)} />
      </div>
    </section>
  );
}

function TrendMiniCard({ title, values, value }: { title: string; values: number[]; value: string }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-3">
        <h4 className="font-bold text-slate-950">{title}</h4>
        <span className="font-bold text-red-700">{value}</span>
      </div>
      <div className="mt-3">
        <Sparkline values={values.length ? values.map((item) => Math.max(1, Math.round(item))) : [1]} />
      </div>
    </article>
  );
}

function AgentClusterComparisonPanel({ dashboard }: { dashboard: AgentPerformanceDashboard }) {
  const clusterBars = chartFromRows(dashboard.clusters, "agent_cluster", "premium", "agent_count");
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Agent peer clusters</h3>
          <p className="mt-1 text-sm text-slate-500">Industry-style segmentation by MDRT, rising stars, product specialization, persistency, and client mix.</p>
        </div>
        <UsersRound className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-5 xl:grid-cols-[0.75fr_1.25fr]">
        <HorizontalBars data={clusterBars} />
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
              <tr>
                {["Customer type", "Product focus", "Agents", "Premium", "Conversion", "Growth insight"].map((column) => (
                  <th className="px-4 py-3 font-bold" key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {dashboard.customer_product_clusters.slice(0, 8).map((row, index) => (
                <tr key={`${asText(row.customer_focus)}-${asText(row.product_focus)}-${index}`}>
                  <td className="px-4 py-3 font-semibold text-slate-950">{titleCase(asText(row.customer_focus, "Mixed book"))}</td>
                  <td className="px-4 py-3 text-slate-600">{titleCase(asText(row.product_focus, "Generalist"))}</td>
                  <td className="px-4 py-3 text-slate-600">{formatCount(row.agent_count)}</td>
                  <td className="px-4 py-3 text-slate-600">{formatCurrency(toNumber(row.premium))}</td>
                  <td className="px-4 py-3 text-slate-600">{formatDashboardPercent(row.conversion_rate)}</td>
                  <td className="px-4 py-3 text-slate-600">{clusterGrowthInsight(row)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function AgentRiskAlertsPanel({ dashboard }: { dashboard: AgentPerformanceDashboard }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Risk alerts</h3>
          <p className="mt-1 text-sm text-slate-500">Underperformance, attrition risk, declining activity, and persistency watchlists.</p>
        </div>
        <ShieldAlert className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {dashboard.risk_alerts.map((row) => (
          <article key={asText(row.alert_type)} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-bold text-slate-950">{asText(row.alert_type)}</p>
                <p className="mt-1 text-sm text-slate-500">{formatCount(row.agent_count)} agents</p>
              </div>
              <PriorityBadge value={asText(row.severity) === "High" ? "Critical" : "Medium"} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function AgentCoachingRecommendationsPanel({ dashboard }: { dashboard: AgentPerformanceDashboard }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Coaching recommendations</h3>
          <p className="mt-1 text-sm text-slate-500">Whom to coach, why, intervention, and expected impact.</p>
        </div>
        <Sparkles className="text-red-600" size={22} />
      </div>
      <div className="mt-5 space-y-3">
        {dashboard.coaching_recommendations.slice(0, 6).map((row, index) => (
          <article key={`${asText(row.agent_name)}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-bold text-slate-950">{asText(row.agent_name, "Agent")}</p>
                <p className="mt-1 text-xs font-bold uppercase tracking-[0.12em] text-red-700">{asText(row.intervention, "Coaching")}</p>
              </div>
              <ConfidenceBadge value={1 - clampScore(toNumber(row.attrition_score, 0.3)) / 2} />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">{asText(row.why)}</p>
            <p className="mt-2 text-sm font-semibold text-slate-900">{asText(row.suggested_intervention)}</p>
            <p className="mt-2 text-sm text-slate-500">{asText(row.expected_impact)}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function AgentPerformanceEvidencePanel({ dashboard }: { dashboard: AgentPerformanceDashboard }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Data evidence</h3>
          <p className="mt-1 text-sm text-slate-500">Supporting facts, models used, and source data.</p>
        </div>
        <FileSearch className="text-red-600" size={22} />
      </div>
      <div className="mt-5 space-y-3">
        {dashboard.evidence.map((row) => (
          <article key={asText(row.source_table)} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="font-bold text-slate-950">{asText(row.source_table)}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">{asText(row.facts)}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {Array.isArray(row.models_used) &&
                row.models_used.map((model) => (
                  <span key={String(model)} className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-200">
                    {String(model)}
                  </span>
                ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function LapseRiskView() {
  const [dashboard, setDashboard] = useState<PolicyLapseDashboard>(policyLapseSample);
  const [region, setRegion] = useState("all");
  const [product, setProduct] = useState("all");
  const [segment, setSegment] = useState("all");
  const [selectedCustomer, setSelectedCustomer] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    void loadLapseDashboard();
  }, []);

  async function loadLapseDashboard(nextRegion = region, nextProduct = product, nextSegment = segment) {
    setLoading(true);
    setNotice("");
    const params = new URLSearchParams();
    if (nextRegion !== "all") params.set("region", nextRegion);
    if (nextProduct !== "all") params.set("product", nextProduct);
    if (nextSegment !== "all") params.set("segment", nextSegment);
    try {
      const payload = await apiGet<PolicyLapseDashboard>(`/policies/lapse-dashboard${params.toString() ? `?${params.toString()}` : ""}`);
      setDashboard(payload);
      setSelectedCustomer(payload.top_customers[0] || null);
    } catch (error) {
      setDashboard(policyLapseSample);
      setSelectedCustomer(policyLapseSample.top_customers[0]);
      setNotice(`Policy lapse API unavailable, showing platform sample data. ${error instanceof Error ? error.message : ""}`);
    } finally {
      setLoading(false);
    }
  }

  const regionOptions = uniqueOptions((dashboard.hotspots.region || []).map((row) => asText(row.dimension)).filter(Boolean));
  const productOptions = uniqueOptions(dashboard.top_products.map((row) => asText(row.product)).filter(Boolean));
  const segmentOptions = uniqueOptions((dashboard.hotspots.customer_segment || []).map((row) => asText(row.dimension)).filter(Boolean));

  return (
    <SectionFrame
      title="Policy Lapse Risk"
      description="A retention decision intelligence product to identify vulnerable customers, exposed premium, responsible agents, lapse drivers, cross-sell options, and actions that prevent business loss."
    >
      <PolicyLapseFilters
        region={region}
        product={product}
        segment={segment}
        setRegion={(value) => {
          setRegion(value);
          void loadLapseDashboard(value, product, segment);
        }}
        setProduct={(value) => {
          setProduct(value);
          void loadLapseDashboard(region, value, segment);
        }}
        setSegment={(value) => {
          setSegment(value);
          void loadLapseDashboard(region, product, value);
        }}
        regionOptions={regionOptions}
        productOptions={productOptions}
        segmentOptions={segmentOptions}
        loading={loading}
        onRefresh={() => loadLapseDashboard(region, product, segment)}
      />
      {notice && <InlineNotice message={notice} />}
      <PolicyLapseExecutiveSummary dashboard={dashboard} />
      <LapseHotspotsPanel dashboard={dashboard} />
      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <TopProductsAtRiskPanel dashboard={dashboard} />
        <TopCustomersAtRiskPanel dashboard={dashboard} onSelect={setSelectedCustomer} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <AssociatedAgentsPanel dashboard={dashboard} />
        <RootCauseAnalysisPanel dashboard={dashboard} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <CrossSellOpportunitiesPanel dashboard={dashboard} />
        <RetentionActionCenterPanel dashboard={dashboard} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <LapseExplanationPanel dashboard={dashboard} selectedCustomer={selectedCustomer} />
        <ScenarioSimulatorPanel dashboard={dashboard} />
      </div>
      <LapseRoadmapPanel dashboard={dashboard} />
    </SectionFrame>
  );
}

function PolicyLapseFilters({
  region,
  product,
  segment,
  setRegion,
  setProduct,
  setSegment,
  regionOptions,
  productOptions,
  segmentOptions,
  loading,
  onRefresh
}: {
  region: string;
  product: string;
  segment: string;
  setRegion: (value: string) => void;
  setProduct: (value: string) => void;
  setSegment: (value: string) => void;
  regionOptions: string[];
  productOptions: string[];
  segmentOptions: string[];
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[0.8fr_1.2fr_1fr_auto]">
        <SelectFilter label="Region" value={region} onChange={setRegion} options={regionOptions} />
        <SelectFilter label="Product" value={product} onChange={setProduct} options={productOptions} />
        <SelectFilter label="Customer segment" value={segment} onChange={setSegment} options={segmentOptions} />
        <button className="inline-flex h-11 items-center justify-center gap-2 self-end rounded-lg bg-red-600 px-5 text-sm font-bold text-white hover:bg-red-700" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 className="animate-spin" size={17} /> : <ShieldAlert size={17} />}
          Refresh
        </button>
      </div>
    </section>
  );
}

function PolicyLapseExecutiveSummary({ dashboard }: { dashboard: PolicyLapseDashboard }) {
  const kpis = dashboard.kpis;
  const trends = dashboard.trends;
  const riskTrend = trendDisplay(toNumber(trends.current_month_risk), toNumber(trends.previous_month_proxy));
  const premiumTrend = trendDisplay(toNumber(trends.current_premium_risk), toNumber(trends.previous_premium_proxy));
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {[
        { label: "Policies at risk", value: formatCount(kpis.policies_at_risk), helper: "High or very-high lapse risk", trend: riskTrend },
        { label: "Customers at risk", value: formatCount(kpis.customers_at_risk), helper: "Distinct vulnerable customers", trend: riskTrend },
        { label: "Premium at risk", value: formatCurrency(toNumber(kpis.premium_revenue_at_risk)), helper: "Annual premium exposure", trend: premiumTrend },
        { label: "Revenue saved", value: formatCurrency(toNumber(kpis.revenue_saved_through_interventions)), helper: "Expected retained value", trend: "+intervention" },
        { label: "Avg lapse probability", value: formatDashboardPercent(kpis.average_lapse_probability), helper: "Mean score for risk book", trend: "model" },
        { label: "Top product", value: titleCase(asText(kpis.top_vulnerable_product, "Not captured")), helper: "Highest average risk", trend: "hotspot" },
        { label: "Top segment", value: titleCase(asText(kpis.top_vulnerable_segment, "Not captured")), helper: "Most vulnerable cohort", trend: "segment" }
      ].map((item) => (
        <article key={item.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{item.label}</p>
            <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-bold uppercase text-red-700">{item.trend}</span>
          </div>
          <p className="mt-2 line-clamp-3 text-2xl font-bold leading-tight text-slate-950">{item.value}</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">{item.helper}</p>
        </article>
      ))}
    </section>
  );
}

function LapseHotspotsPanel({ dashboard }: { dashboard: PolicyLapseDashboard }) {
  const rows = [
    ...heatmapRows("Region", dashboard.hotspots.region),
    ...heatmapRows("Branch", dashboard.hotspots.branch),
    ...heatmapRows("Product", dashboard.hotspots.product),
    ...heatmapRows("Agent", dashboard.hotspots.agent),
    ...heatmapRows("Customer Segment", dashboard.hotspots.customer_segment)
  ].slice(0, 20);
  const maxPremium = Math.max(...rows.map((row) => row.premium), 1);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Lapse hotspots</h3>
          <p className="mt-1 text-sm text-slate-500">Heatmap view across region, branch, product, agent, and customer segment.</p>
        </div>
        <MapPin className="text-red-600" size={22} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {rows.map((row) => (
          <article key={`${row.group}-${row.label}`} className="rounded-lg border border-slate-200 p-3" style={{ backgroundColor: heatColor(row.premium / maxPremium) }}>
            <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-600">{row.group}</p>
            <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm font-bold text-slate-950">{titleCase(row.label)}</p>
            <div className="mt-3 grid gap-1.5 text-xs">
              <span className="flex items-center justify-between gap-2"><b>{formatCount(row.policies)}</b><span>policies</span></span>
              <span className="flex items-center justify-between gap-2"><b>{formatCurrency(row.premium)}</b><span>premium</span></span>
              <span className="flex items-center justify-between gap-2"><b>{formatDashboardPercent(row.score)}</b><span>score</span></span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function TopProductsAtRiskPanel({ dashboard }: { dashboard: PolicyLapseDashboard }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Top products at risk</h3>
          <p className="mt-1 text-sm text-slate-500">Ranked by lapse probability, premium exposure, customer count, and missed payments.</p>
        </div>
        <Layers3 className="text-red-600" size={22} />
      </div>
      <div className="mt-5 space-y-3">
        {dashboard.top_products.slice(0, 7).map((row) => (
          <article key={asText(row.product)} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-bold text-slate-950">{asText(row.product)}</p>
                <p className="mt-1 text-sm text-slate-500">{asText(row.recommendation)}</p>
              </div>
              <span className="rounded-full bg-red-600 px-3 py-1 text-xs font-bold text-white">{formatDashboardPercent(row.lapse_probability)}</span>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              <MetricBox label="Active policies" value={formatCount(row.active_policies)} />
              <MetricBox label="High-risk policies" value={formatCount(row.high_risk_policies)} />
              <MetricBox label="Annual premium" value={formatCurrency(toNumber(row.annual_premium))} />
              <MetricBox label="Missed payments" value={formatCount(row.missed_payments)} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function TopCustomersAtRiskPanel({ dashboard, onSelect }: { dashboard: PolicyLapseDashboard; onSelect: (row: Record<string, unknown>) => void }) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 p-5">
        <h3 className="font-bold text-slate-950">Top customers at risk</h3>
        <p className="mt-1 text-sm text-slate-500">Prioritized by premium exposure, lapse score, reason, cross-sell fit, and action.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
            <tr>
              {["Customer", "Segment", "Agent", "Product", "Premium", "Lapse", "Reason", "Cross-sell", "Action"].map((column) => (
                <th className="px-4 py-3 font-bold" key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {dashboard.top_customers.slice(0, 12).map((row) => (
              <tr key={asText(row.policy_id, asText(row.customer))} className="cursor-pointer hover:bg-red-50/40" onClick={() => onSelect(row)}>
                <td className="px-4 py-3 font-semibold text-slate-950">{asText(row.customer)}</td>
                <td className="px-4 py-3 text-slate-600">{titleCase(asText(row.customer_segment))}</td>
                <td className="px-4 py-3 text-slate-600">{asText(row.agent, "Unassigned")}</td>
                <td className="px-4 py-3 text-slate-600">{asText(row.product)}</td>
                <td className="px-4 py-3 text-slate-600">{formatCurrency(toNumber(row.premium))}</td>
                <td className="px-4 py-3 font-bold text-red-700">{formatDashboardPercent(row.lapse_score)}</td>
                <td className="px-4 py-3 text-slate-600">{asText(row.reason)}</td>
                <td className="px-4 py-3 text-slate-600">{asText(row.cross_sell_opportunity)}</td>
                <td className="px-4 py-3 text-slate-600">{asText(row.recommended_action)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AssociatedAgentsPanel({ dashboard }: { dashboard: PolicyLapseDashboard }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Associated agents</h3>
          <p className="mt-1 text-sm text-slate-500">Agents responsible for high-risk customers, retention success, MAPA, and coaching action.</p>
        </div>
        <UsersRound className="text-red-600" size={22} />
      </div>
      <div className="mt-5 space-y-3">
        {dashboard.agents.slice(0, 8).map((row) => (
          <article key={asText(row.agent)} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap justify-between gap-3">
              <p className="font-bold text-slate-950">{asText(row.agent)}</p>
              <PriorityBadge value={toNumber(row.retention_success_rate) < 0.35 ? "Critical" : "Medium"} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
              <MetricBox label="Customers at risk" value={formatCount(row.customers_at_risk)} />
              <MetricBox label="Premium at risk" value={formatCurrency(toNumber(row.premium_at_risk))} />
              <MetricBox label="Retention success" value={formatDashboardPercent(row.retention_success_rate)} />
              <MetricBox label="MAPA score" value={formatDashboardPercent(row.mapa_score)} />
            </div>
            <p className="mt-3 text-sm font-semibold text-red-700">{asText(row.recommended_coaching_action)}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function RootCauseAnalysisPanel({ dashboard }: { dashboard: PolicyLapseDashboard }) {
  const data = dashboard.root_causes.map((row) => ({
    driver: titleCase(asText(row.driver)),
    count: toNumber(row.count),
    premium: Math.round(toNumber(row.premium_exposure)),
    contribution: Math.round(toNumber(row.contribution) * 100)
  }));
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Root cause analysis</h3>
          <p className="mt-1 text-sm text-slate-500">Missed payments, premium increase, complaints, service, renewal windows, and engagement drivers.</p>
        </div>
        <ShieldAlert className="text-red-600" size={22} />
      </div>
      <div className="mt-5 h-72">
        <ResponsiveContainer width="100%" height="100%">
          <RechartsBarChart data={data} layout="vertical" margin={{ top: 8, right: 16, bottom: 8, left: 28 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" hide />
            <YAxis dataKey="driver" type="category" width={130} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(value, name) => [name === "premium" ? formatCurrency(Number(value)) : value, titleCase(String(name))]} />
            <Bar dataKey="premium" radius={[0, 6, 6, 0]}>
              {data.map((_, index) => <Cell key={index} fill={["#dc2626", "#fb7185", "#f59e0b", "#1f2937", "#94a3b8"][index % 5]} />)}
            </Bar>
          </RechartsBarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid gap-2 md:grid-cols-3">
        {dashboard.root_causes.slice(0, 6).map((row) => (
          <MetricBox key={asText(row.driver)} label={titleCase(asText(row.driver))} value={`${formatCount(row.count)} | ${formatDashboardPercent(row.contribution)}`} />
        ))}
      </div>
    </section>
  );
}

function CrossSellOpportunitiesPanel({ dashboard }: { dashboard: PolicyLapseDashboard }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">Cross-sell opportunities</h3>
      <p className="mt-1 text-sm text-slate-500">Next best product and propensity-informed recovery opportunity for at-risk customers.</p>
      <div className="mt-5 space-y-3">
        {dashboard.cross_sell.slice(0, 6).map((row) => (
          <article key={`${asText(row.customer)}-${asText(row.recommended_product)}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-bold text-slate-950">{asText(row.customer)}</p>
                <p className="mt-1 text-sm text-slate-500">{asText(row.current_product)} to {asText(row.recommended_product)}</p>
              </div>
              <ConfidenceBadge value={clampScore(toNumber(row.expected_conversion_probability))} />
            </div>
            <p className="mt-3 text-sm text-slate-600">{asText(row.reason)}</p>
            <p className="mt-2 text-sm font-bold text-red-700">Expected premium {formatCurrency(toNumber(row.expected_premium))}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function RetentionActionCenterPanel({ dashboard }: { dashboard: PolicyLapseDashboard }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">Retention action center</h3>
      <p className="mt-1 text-sm text-slate-500">Prioritized actions with expected impact, confidence, and due date.</p>
      <div className="mt-5 space-y-3">
        {dashboard.action_center.slice(0, 7).map((row) => (
          <article key={`${asText(row.policy)}-${asText(row.action)}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <p className="font-bold text-slate-950">{asText(row.action)}: {asText(row.customer)}</p>
                <p className="mt-1 text-sm text-slate-500">{asText(row.agent, "Unassigned")} | {asText(row.policy)}</p>
              </div>
              <ConfidenceBadge value={clampScore(toNumber(row.confidence))} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <MetricBox label="Expected impact" value={formatCurrency(toNumber(row.expected_impact))} />
              <MetricBox label="Due date" value={dateOnly(row.due_date)} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function LapseExplanationPanel({ dashboard, selectedCustomer }: { dashboard: PolicyLapseDashboard; selectedCustomer: Record<string, unknown> | null }) {
  const explanation = dashboard.explanation || {};
  const selectedName = asText(selectedCustomer?.customer, asText(explanation.customer, "Selected customer"));
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">AI explanation panel</h3>
      <p className="mt-1 text-sm text-slate-500">Why lapse risk is high, with facts, rules, lineage, context, and confidence.</p>
      <div className="mt-5 rounded-lg border border-red-100 bg-red-50 p-4">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-red-700">Why risk is high</p>
        <p className="mt-2 text-lg font-bold text-slate-950">{selectedName}: {asText(explanation.primary_lapse_reason, asText(selectedCustomer?.reason, "High lapse score"))}</p>
        <p className="mt-2 text-sm text-slate-600">Lapse score {formatDashboardPercent(selectedCustomer?.lapse_score || explanation.lapse_score)} with confidence {formatDashboardPercent(explanation.confidence_score || selectedCustomer?.confidence_score)}.</p>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <EvidenceList title="Supporting facts" values={asStringList(explanation.supporting_facts)} />
        <EvidenceList title="Business rules" values={asStringList(explanation.business_rules)} />
        <EvidenceList title="Source tables" values={asStringList(explanation.source_tables)} />
        <EvidenceList title="Source columns" values={asStringList(explanation.source_columns)} />
        <EvidenceList title="Context documents" values={asStringList(explanation.context_documents_used)} />
      </div>
    </section>
  );
}

function EvidenceList({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {(values.length ? values : ["Not captured"]).map((value) => (
          <span key={value} className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-200">{value}</span>
        ))}
      </div>
    </div>
  );
}

function ScenarioSimulatorPanel({ dashboard }: { dashboard: PolicyLapseDashboard }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">Scenario simulator</h3>
      <p className="mt-1 text-sm text-slate-500">Estimate policies saved, premium saved, and expected conversion for retention scenarios.</p>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {dashboard.scenario_simulator.map((row) => (
          <article key={asText(row.scenario)} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="font-bold text-slate-950">{asText(row.scenario)}</p>
            <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
              <span><b>{formatCount(row.policies_saved)}</b><br />saved</span>
              <span><b>{formatCurrency(toNumber(row.premium_saved))}</b><br />premium</span>
              <span><b>{formatDashboardPercent(row.expected_conversion)}</b><br />conversion</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function LapseRoadmapPanel({ dashboard }: { dashboard: PolicyLapseDashboard }) {
  return (
    <section className="grid gap-5 xl:grid-cols-2">
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-bold text-slate-950">Schema additions proposed</h3>
        <div className="mt-4 flex flex-wrap gap-2">
          {dashboard.schema_additions.map((item) => <span key={item} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">{item}</span>)}
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-bold text-slate-950">ML enhancements proposed</h3>
        <div className="mt-4 flex flex-wrap gap-2">
          {dashboard.ml_enhancements.map((item) => <span key={item} className="rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-700">{titleCase(item)}</span>)}
        </div>
      </div>
    </section>
  );
}

function IntelligenceView({
  role,
  question,
  setQuestion,
  answer,
  loading,
  submitQuestion
}: {
  role: string;
  question: string;
  setQuestion: (value: string) => void;
  answer: AskResponse | null;
  loading: boolean;
  submitQuestion: (event?: FormEvent) => void;
}) {
  const [briefing, setBriefing] = useState<DecisionIntelligencePayload>(() => sampleDecisionIntelligence(role));
  const [briefingLoading, setBriefingLoading] = useState(false);
  const roleCode = role.toLowerCase().replaceAll(" ", "_");
  const rows = answer?.execution?.rows || [];
  const insight = answer?.business_insight?.summary || asText(briefing.executive_briefing.narrative);
  const evidence = briefing.evidence || {};

  useEffect(() => {
    let cancelled = false;
    async function loadBriefing() {
      setBriefingLoading(true);
      try {
        const payload = await apiGet<DecisionIntelligencePayload>(`/intelligence/briefing?role=${encodeURIComponent(roleCode)}`);
        if (!cancelled) setBriefing(payload);
      } catch {
        if (!cancelled) setBriefing(sampleDecisionIntelligence(role));
      } finally {
        if (!cancelled) setBriefingLoading(false);
      }
    }
    void loadBriefing();
    setQuestion(sampleDecisionIntelligence(role).questions[0] || "What should we prioritize this week?");
    return () => {
      cancelled = true;
    };
  }, [role, roleCode, setQuestion]);

  return (
    <SectionFrame
      title="AI Intelligence Platform"
      description="A role-aware decision workspace that proactively surfaces executive briefings, hidden trends, risks, opportunities, recommendations, evidence, lineage, and next actions."
    >
      <IntelligenceAskHero
        role={briefing.role_name}
        questions={briefing.questions}
        question={question}
        setQuestion={setQuestion}
        loading={loading}
        submitQuestion={submitQuestion}
      />
      {briefingLoading && <LoadingPanel label="Refreshing role-aware intelligence..." />}
      <SqlLifecyclePanel answer={answer} />
      <ExecutiveBriefingPanel briefing={briefing} />
      <DecisionKpiStrip items={briefing.kpis} />

      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <DiscoveryPanel
          title="Hidden trends"
          subtitle="Automatically detected changes before they become obvious in static dashboards."
          icon={<TrendingDown size={20} />}
          rows={briefing.hidden_trends}
          titleKey="trend"
          detailKeys={["reason", "business_impact", "recommended_action"]}
        />
        <DiscoveryPanel
          title="Opportunity discovery"
          subtitle="Growth pools ranked by premium potential, customer count, confidence, and recommended action."
          icon={<Target size={20} />}
          rows={briefing.opportunities}
          titleKey="opportunity"
          detailKeys={["potential_premium", "customer_count", "recommended_action"]}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <DiscoveryPanel
          title="Risk discovery"
          subtitle="Business risks surfaced from policy, customer, agent, campaign, claims, and model signals."
          icon={<ShieldAlert size={20} />}
          rows={briefing.risks}
          titleKey="risk"
          detailKeys={["impact", "root_cause", "recommended_action"]}
        />
        <RecommendationCardsPanel recommendations={briefing.recommendations} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 className="font-bold text-slate-950">Role-specific questions</h3>
              <p className="mt-1 text-sm text-slate-500">Suggested prompts change with the selected role and decision context.</p>
            </div>
            <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-700">{briefing.role_name}</span>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {briefing.questions.map((item) => (
              <button
                key={item}
                className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-red-200 hover:bg-red-50 hover:text-red-700"
                onClick={() => setQuestion(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </section>

        <EvidencePanel evidence={evidence} answer={answer} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <AnswerInsightPanel answer={answer} fallbackSummary={insight} />
        <TableCard
          title="Result preview"
          columns={rows.length ? Object.keys(rows[0]).slice(0, 5) : ["Metric", "Value", "Signal"]}
          rows={
            rows.length
              ? rows.slice(0, 6).map((row) => Object.keys(row).slice(0, 5).map((key) => formatValue(row[key])))
              : [
                  ["Revenue at risk", asText(briefing.executive_briefing.revenue_at_risk), "Retention focus"],
                  ["Revenue opportunity", asText(briefing.executive_briefing.revenue_opportunity), "Cross-sell upside"],
                  ["Agent productivity", asText(briefing.executive_briefing.agent_productivity_trend), "Coaching signal"]
                ]
          }
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <GeneratedSqlPanel answer={answer} role={role} />
        <PerformanceAndContextPanel answer={answer} briefing={briefing} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <ExplainabilityPanel evidence={evidence} answer={answer} />
        <DataLineagePanel compact answer={answer} />
      </div>

      <PlatformArchitecturePanel briefing={briefing} />
    </SectionFrame>
  );
}

function IntelligenceAskHero({
  role,
  questions,
  question,
  setQuestion,
  loading,
  submitQuestion
}: {
  role: string;
  questions: string[];
  question: string;
  setQuestion: (value: string) => void;
  loading: boolean;
  submitQuestion: (event?: FormEvent) => void;
}) {
  return (
    <section className="rounded-2xl border border-red-100 bg-white p-5 shadow-sm ring-1 ring-red-50">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-4xl">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-red-700">SQL-backed insurance intelligence</p>
          <h3 className="mt-2 text-3xl font-bold text-slate-950">Ask your Insurance Intelligence Platform</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Ask questions across customers, agents, policies, campaigns, claims, lapse risk, and model scores.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {["SQL-backed insight", "Using live Supabase data", "Model scores included", role].map((badge) => (
              <span key={badge} className="rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-700 ring-1 ring-red-100">
                {badge}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 xl:w-[420px]">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">What you get</p>
          <div className="mt-3 grid gap-2 text-sm text-slate-700">
            {["Generated SQL", "Validation status", "Result preview", "Evidence and lineage"].map((item) => (
              <span key={item} className="flex items-center gap-2"><BadgeCheck className="text-red-600" size={15} />{item}</span>
            ))}
          </div>
        </div>
      </div>
      <form className="mt-5 flex flex-col gap-3 lg:flex-row" onSubmit={submitQuestion}>
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={22} />
          <input
            className="h-16 w-full rounded-xl border border-slate-200 bg-white pl-12 pr-4 text-base font-semibold text-slate-900 outline-none shadow-sm focus:border-red-500 focus:ring-4 focus:ring-red-100"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask for a decision, SQL-backed insight, risk, opportunity, KPI, or evidence"
          />
        </div>
        <button className="inline-flex h-16 items-center justify-center gap-2 rounded-xl bg-red-600 px-8 text-base font-bold text-white shadow-sm hover:bg-red-700" disabled={loading}>
          {loading ? <Loader2 className="animate-spin" size={21} /> : <Sparkles size={21} />}
          Ask
        </button>
      </form>
      <div className="mt-4 flex flex-wrap gap-2">
        {questions.map((item) => (
          <button
            key={item}
            className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-red-200 hover:bg-red-50 hover:text-red-700"
            onClick={() => setQuestion(item)}
          >
            {item}
          </button>
        ))}
      </div>
    </section>
  );
}

function SqlLifecyclePanel({ answer }: { answer: AskResponse | null }) {
  const steps = answer?.lifecycle?.length
    ? answer.lifecycle
    : [
        { step: "Context retrieved", status: "ready", detail: "Waiting for question" },
        { step: "SQL generated", status: "ready", detail: "Query will appear below" },
        { step: "SQL validated", status: "ready", detail: "Read-only safety check" },
        { step: "SQL executed", status: "ready", detail: "Live Supabase execution" },
        { step: "Insight generated", status: "ready", detail: "Business explanation" }
      ];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h3 className="font-bold text-slate-950">SQL lifecycle status</h3>
          <p className="mt-1 text-sm text-slate-500">Visible proof that context retrieval, SQL generation, validation, execution, and insight generation ran.</p>
        </div>
        <SqlConfidenceBadge value={asText(answer?.sql_metadata?.sql_confidence, answer ? "Medium" : "Pending")} />
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-5">
        {steps.map((item, index) => (
          <article key={asText(item.step)} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center gap-2">
              <span className={classNames("flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white", lifecycleTone(asText(item.status)))}>
                {index + 1}
              </span>
              <p className="text-sm font-bold text-slate-950">{asText(item.step)}</p>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-500">{asText(item.detail)}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function SqlConfidenceBadge({ value }: { value: string }) {
  const tone = value === "High" ? "bg-emerald-50 text-emerald-700 ring-emerald-100" : value === "Low" ? "bg-amber-50 text-amber-700 ring-amber-100" : "bg-red-50 text-red-700 ring-red-100";
  return <span className={classNames("rounded-full px-3 py-1 text-xs font-bold ring-1", tone)}>SQL confidence: {value}</span>;
}

function lifecycleTone(status: string): string {
  if (status === "complete") return "bg-emerald-600";
  if (status === "failed" || status === "blocked") return "bg-red-600";
  if (status === "warning") return "bg-amber-500";
  return "bg-slate-400";
}

function ExecutiveBriefingPanel({ briefing }: { briefing: DecisionIntelligencePayload }) {
  const executive = briefing.executive_briefing;
  return (
    <section className="rounded-xl border border-red-100 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-red-700">Executive briefing</p>
          <h3 className="mt-2 text-2xl font-bold text-slate-950">{briefing.role_name} decision priorities</h3>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">{asText(executive.narrative)}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:w-[520px]">
          <MetricBox label="Revenue at risk" value={asText(executive.revenue_at_risk)} />
          <MetricBox label="Revenue opportunity" value={asText(executive.revenue_opportunity)} />
          <MetricBox label="Customer growth" value={asText(executive.customer_growth)} />
          <MetricBox label="Agent productivity" value={asText(executive.agent_productivity_trend)} />
        </div>
      </div>
      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <BriefingList title="Top 3 risks" tone="risk" items={asStringList(executive.top_risks)} />
        <BriefingList title="Top 3 opportunities" tone="opportunity" items={asStringList(executive.top_opportunities)} />
      </div>
    </section>
  );
}

function BriefingList({ title, tone, items }: { title: string; tone: "risk" | "opportunity"; items: string[] }) {
  return (
    <div className={classNames("rounded-lg border p-4", tone === "risk" ? "border-red-100 bg-red-50" : "border-emerald-100 bg-emerald-50")}>
      <h4 className="font-bold text-slate-950">{title}</h4>
      <div className="mt-3 space-y-2">
        {items.slice(0, 3).map((item) => (
          <p key={item} className="flex gap-2 text-sm leading-6 text-slate-700">
            <BadgeCheck className={classNames("mt-1 shrink-0", tone === "risk" ? "text-red-600" : "text-emerald-600")} size={16} />
            {item}
          </p>
        ))}
      </div>
    </div>
  );
}

function DecisionKpiStrip({ items }: { items: Array<Record<string, unknown>> }) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <article key={asText(item.label)} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-500">{asText(item.label)}</p>
              <p className="mt-2 text-3xl font-bold text-slate-950">{asText(item.value)}</p>
            </div>
            <span className="rounded-full border border-red-100 bg-red-50 px-2.5 py-1 text-xs font-bold text-red-700">{asText(item.trend)}</span>
          </div>
          <p className="mt-4 text-sm text-slate-500">{asText(item.helper)}</p>
        </article>
      ))}
    </section>
  );
}

function DiscoveryPanel({
  title,
  subtitle,
  icon,
  rows,
  titleKey,
  detailKeys
}: {
  title: string;
  subtitle: string;
  icon: ReactNode;
  rows: Array<Record<string, unknown>>;
  titleKey: string;
  detailKeys: string[];
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">{title}</h3>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
        </div>
        <div className="rounded-lg bg-red-50 p-2 text-red-700">{icon}</div>
      </div>
      <div className="mt-5 space-y-3">
        {rows.slice(0, 4).map((row) => (
          <article key={asText(row[titleKey])} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <h4 className="font-bold text-slate-950">{asText(row[titleKey])}</h4>
              <ConfidenceBadge value={clampScore(toNumber(row.confidence, 0.75))} />
            </div>
            <div className="mt-3 space-y-2">
              {detailKeys.map((key) => (
                <p key={key} className="text-sm leading-6 text-slate-600">
                  <span className="font-bold text-slate-700">{titleCase(key.replaceAll("_", " "))}: </span>
                  {formatValue(row[key])}
                </p>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function RecommendationCardsPanel({ recommendations }: { recommendations: Array<Record<string, unknown>> }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Recommendation cards</h3>
          <p className="mt-1 text-sm text-slate-500">Every recommendation includes impact, reason, owner, confidence, due date, and expected outcome.</p>
        </div>
        <Sparkles className="text-red-600" size={21} />
      </div>
      <div className="mt-5 space-y-3">
        {recommendations.slice(0, 4).map((item) => (
          <article key={asText(item.title)} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h4 className="font-bold text-slate-950">{asText(item.title)}</h4>
                <p className="mt-1 text-sm font-bold text-red-700">{asText(item.business_impact)}</p>
              </div>
              <ConfidenceBadge value={clampScore(toNumber(item.confidence, 0.75))} />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">{asText(item.reason)}</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Owner</p>
                <p className="mt-1 text-sm font-bold text-slate-950">{asText(item.owner)}</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Due date</p>
                <p className="mt-1 text-sm font-bold text-slate-950">{dateOnly(item.due_date)}</p>
              </div>
            </div>
            <p className="mt-3 rounded-lg border border-slate-200 bg-white p-3 text-sm leading-6 text-slate-700">
              <span className="font-bold text-slate-950">Expected outcome: </span>
              {asText(item.expected_outcome)}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

function EvidencePanel({ evidence, answer }: { evidence: Record<string, unknown>; answer?: AskResponse | null }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">Evidence panel</h3>
      <p className="mt-1 text-sm text-slate-500">Source tables, rules, models, context, confidence, and timestamp used in the decision.</p>
      <div className="mt-4 grid gap-3">
        <EvidenceList title="Source tables" values={answer?.explainability?.source_tables || asStringList(evidence.source_tables)} />
        <EvidenceList title="Source columns" values={asStringList(evidence.source_columns)} />
        <EvidenceList title="Business rules used" values={asStringList(evidence.business_rules_used)} />
        <EvidenceList title="ML models used" values={answer?.explainability?.metrics_used || asStringList(evidence.ml_models_used)} />
      </div>
      <div className="mt-4 flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-3">
        <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Confidence</span>
        <ConfidenceBadge value={clampScore(toNumber(answer?.confidence_score || evidence.confidence, 0.87))} />
      </div>
      <p className="mt-3 text-xs text-slate-500">Timestamp: {dateOnly(evidence.timestamp)}</p>
    </section>
  );
}

function AnswerInsightPanel({ answer, fallbackSummary }: { answer: AskResponse | null; fallbackSummary: string }) {
  const observations = answer?.business_insight?.key_observations?.length
    ? answer.business_insight.key_observations
    : [
        "Prioritize high-value renewal customers before sales outreach.",
        "Route high-CLV actions to human agents rather than automated journeys.",
        "Use context and lineage to separate model signal from business rule suppression."
      ];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Decision answer</h3>
          <p className="mt-1 text-sm text-slate-500">Executive summary, key insights, business impact, actions, confidence, and follow-up questions.</p>
        </div>
        <ConfidenceBadge value={answer?.confidence_score || 0.88} />
      </div>
      <div className="mt-5 rounded-lg border border-red-100 bg-red-50 p-4">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-red-700">{answer?.intent || "Proactive briefing"}</p>
        <p className="mt-2 text-sm leading-6 text-slate-700">{fallbackSummary}</p>
      </div>
      <div className="mt-4 space-y-3">
        {observations.map((item) => (
          <p key={item} className="flex gap-2 text-sm leading-6 text-slate-700">
            <BadgeCheck className="mt-1 shrink-0 text-red-600" size={16} />
            {item}
          </p>
        ))}
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <MetricBox label="Business impact" value={answer ? "SQL-backed quantified answer" : "Proactive role briefing"} />
        <MetricBox label="Follow-up questions" value="Generated from role context" />
      </div>
      {answer?.sql && (
        <details className="mt-5 rounded-lg border border-slate-200 bg-slate-950 p-4 text-white">
          <summary className="cursor-pointer text-sm font-semibold">Generated SQL</summary>
          <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-200">{answer.sql}</pre>
        </details>
      )}
    </section>
  );
}

function GeneratedSqlPanel({ answer, role }: { answer: AskResponse | null; role: string }) {
  const [copied, setCopied] = useState(false);
  const sql = answer?.sql || "Ask a question to generate validated read-only SQL.";
  const metadata = answer?.sql_metadata || {};
  const isDataAnalyst = role === "Data Analyst";
  async function copySql() {
    if (!answer?.sql || typeof navigator === "undefined") return;
    await navigator.clipboard.writeText(answer.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Generated SQL panel</h3>
          <p className="mt-1 text-sm text-slate-500">SQL is visible, validated, timed, and traceable to tables and columns.</p>
        </div>
        <button className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50" onClick={copySql} disabled={!answer?.sql}>
          {copied ? "Copied" : "Copy SQL"}
        </button>
      </div>
      <details className="mt-4 rounded-lg border border-slate-200 bg-slate-950 p-4 text-white" open={isDataAnalyst || Boolean(answer?.sql)}>
        <summary className="cursor-pointer text-sm font-semibold">Validated read-only query</summary>
        <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-xs leading-6 text-slate-100">{highlightSql(sql)}</pre>
      </details>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <MetricBox label="Validation" value={asText(metadata.validation_status, answer?.validation?.safety_decision || "Pending")} />
        <MetricBox label="Execution time" value={metadata.execution_time_ms ? `${formatCount(metadata.execution_time_ms)} ms` : formatTiming(answer?.execution?.duration_ms)} />
        <MetricBox label="Row count" value={formatCount(metadata.row_count ?? answer?.execution?.row_count ?? 0)} />
        <MetricBox label="SQL confidence" value={asText(metadata.sql_confidence, "Pending")} />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <EvidenceList title="Tables used" values={stringListFromUnknown(metadata.tables_used || answer?.validation?.referenced_tables || answer?.explainability?.source_tables)} />
        <EvidenceList title="Columns used" values={stringListFromUnknown(metadata.columns_used)} />
      </div>
      {answer?.execution?.execution_status === "failed" && (
        <InlineNotice message={`SQL execution failed: ${answer.execution.error_message || "Unknown execution error"}. Corrected SQL and fallback query will appear here when available.`} />
      )}
    </section>
  );
}

function PerformanceAndContextPanel({ answer, briefing }: { answer: AskResponse | null; briefing: DecisionIntelligencePayload }) {
  const timings = answer?.timings || {};
  const provider = answer?.provider || {};
  const contextDocuments = contextTitles(answer?.retrieved_context).slice(0, 10);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">Performance, models, and context</h3>
      <p className="mt-1 text-sm text-slate-500">Request timings, provider details, model usage, and retrieved semantic context.</p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <MetricBox label="Total latency" value={formatTiming(timings.total_latency_ms)} />
        <MetricBox label="SQL generation" value={formatTiming(timings.sql_generation_ms)} />
        <MetricBox label="SQL validation" value={formatTiming(timings.sql_validation_ms)} />
        <MetricBox label="SQL execution" value={formatTiming(timings.sql_execution_ms || answer?.execution?.duration_ms)} />
        <MetricBox label="Provider" value={asText(provider.provider_used, "Configured")} />
        <MetricBox label="Model" value={asText(provider.model_used, "Configured")} />
      </div>
      <div className="mt-4 grid gap-3">
        <EvidenceList title="Models used" values={stringListFromUnknown(answer?.sql_metadata?.models_used || answer?.explainability?.ml_models_used || briefing.evidence.ml_models_used)} />
        <EvidenceList title="Retrieved context" values={contextDocuments.length ? contextDocuments : asStringList(briefing.evidence.context_documents_used)} />
        <EvidenceList title="Suggested follow-up questions" values={briefing.questions.slice(0, 4)} />
      </div>
    </section>
  );
}

function ExplainabilityPanel({ evidence, answer }: { evidence: Record<string, unknown>; answer: AskResponse | null }) {
  const contexts = answer?.explainability?.context_documents_used?.map((item) => asText(item.title)).filter(Boolean) || asStringList(evidence.context_documents_used);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">AI explainability</h3>
      <p className="mt-1 text-sm text-slate-500">Explains why a recommendation was produced and which data, models, rules, and context were used.</p>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <EvidenceList title="Why" values={["Risk, value, urgency, and propensity signals are ranked together."]} />
        <EvidenceList title="Data used" values={asStringList(evidence.source_tables)} />
        <EvidenceList title="Models used" values={asStringList(evidence.ml_models_used)} />
        <EvidenceList title="Rules used" values={asStringList(evidence.business_rules_used)} />
        <EvidenceList title="Context documents" values={contexts} />
      </div>
    </section>
  );
}

function PlatformArchitecturePanel({ briefing }: { briefing: DecisionIntelligencePayload }) {
  return (
    <section className="grid gap-5 xl:grid-cols-2">
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-bold text-slate-950">Backend services enabled</h3>
        <p className="mt-1 text-sm text-slate-500">Service architecture for proactive intelligence generation.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {briefing.services.map((item) => <span key={item} className="rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-700">{item}</span>)}
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-bold text-slate-950">Schema additions proposed</h3>
        <p className="mt-1 text-sm text-slate-500">Tables to operationalize role templates, proactive insights, and action tracking.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {briefing.schema_additions.map((item) => <span key={item} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">{item}</span>)}
        </div>
      </div>
    </section>
  );
}

const aiInsightV10Questions: Record<string, string[]> = {
  "Insurance Agent": [
    "Which customers should I contact first this week?",
    "Which customers should I call this week?",
    "What is our current lapse rate?"
  ],
  "Agency Manager": [
    "Which agents need coaching this month?",
    "Which agents have the highest premium at risk?",
    "Which branch has the highest lapse exposure?"
  ],
  "Campaign Manager": [
    "Which campaign generated the highest policy conversion?",
    "What are the bad campaigns?",
    "What is campaign conversion rate by channel?"
  ],
  "Claims Manager": [
    "Which products have the highest claims ratio?",
    "Which claims have high fraud risk?",
    "Which regions show unusual claims growth?"
  ],
  "Sales Director": [
    "What product line has the largest premium concentration?",
    "What is campaign conversion rate by channel?",
    "What is our current lapse rate?"
  ],
  "Executive Leadership": [
    "What is our current lapse rate?",
    "What product line has the largest premium concentration?",
    "What is campaign conversion rate by channel?"
  ],
  "Data Analyst": [
    "Show internal premium by line of business.",
    "Show campaign conversion rate by channel.",
    "Show policies sold in Singapore."
  ]
};

function AiInsightV10View({
  role,
  setRole,
  setActive
}: {
  role: string;
  setRole: (role: string) => void;
  setActive: (key: NavKey, query?: string) => void;
}) {
  const [question, setQuestion] = useState(aiInsightV10Questions[role]?.[0] || aiInsightV10Questions["Executive Leadership"][0]);
  const [answer, setAnswer] = useState<AiInsightV11Response | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const questions = aiInsightV10Questions[role] || aiInsightV10Questions["Executive Leadership"];

  useEffect(() => {
    setQuestion(aiInsightV10Questions[role]?.[0] || aiInsightV10Questions["Executive Leadership"][0]);
    setAnswer(null);
    setError("");
  }, [role]);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/ai-insight-v11/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, question })
      });
      if (!response.ok) throw new Error(`AI Insight API returned ${response.status}`);
      setAnswer((await response.json()) as AiInsightV11Response);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "AI Insight API is unavailable.");
      setAnswer(sampleAiInsightV10Response(role, question));
    } finally {
      setLoading(false);
    }
  }

  function openFullEvidence() {
    const query = answer?.insight_id ? `?insight_id=${encodeURIComponent(answer.insight_id)}` : "";
    setActive("evidenceHub", query);
  }

  return (
    <SectionFrame
      title="AI Intelligence"
      description="Ask insurance business questions using live data, semantic context, and LLM-generated SQL."
    >
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-red-700">Focused AI insight workspace</p>
            <h3 className="mt-2 text-3xl font-bold text-slate-950">Ask a business question</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Converts natural language into validated SQL, executes against Supabase, and returns business insights with related context.
            </p>
          </div>
          <label className="block min-w-[260px]">
            <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Selected role</span>
            <select
              className="mt-2 h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm font-semibold outline-none focus:border-red-500 focus:ring-4 focus:ring-red-100"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              {roles.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        </div>
        <form className="mt-5 flex flex-col gap-3 lg:flex-row" onSubmit={submit}>
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={21} />
            <input
              className="h-16 w-full rounded-xl border border-slate-200 bg-white pl-12 pr-4 text-base font-semibold outline-none shadow-sm focus:border-red-500 focus:ring-4 focus:ring-red-100"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Type any insurance business question"
            />
          </div>
          <button className="inline-flex h-16 items-center justify-center gap-2 rounded-xl bg-red-600 px-7 text-base font-bold text-white hover:bg-red-700" disabled={loading}>
            {loading ? <Loader2 className="animate-spin" size={20} /> : <Sparkles size={20} />}
            Generate Insight
          </button>
        </form>
        <div className="mt-4">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Try asking</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {questions.map((item) => (
              <button
                key={item}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-red-200 hover:bg-red-50 hover:text-red-700"
                onClick={() => setQuestion(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      </section>

      {error && <InlineNotice message={`${error} Showing a sample response so the page remains usable.`} />}
      {answer?.technical_warnings && answer.technical_warnings.length > 0 && (
        <section className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 shrink-0" size={18} />
          <div>
            <p className="font-bold">Technical warning</p>
            <p className="mt-1 leading-6">{answer.technical_warnings[0]}</p>
          </div>
        </section>
      )}

      <AiInsightValidationPipeline answer={answer} />

      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <AiInsightAnswerSummary answer={answer} />
        <AiInsightSqlCard answer={answer} />
      </div>
      <AiInsightKeyDataPointsCard answer={answer} />
      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <AiInsightListCard
          title="Insights"
          rows={answer?.insights || []}
          titleKey="title"
          descriptionKey="description"
          emptyText={answer ? "No insight cards were published because validation did not find enough supporting SQL evidence." : undefined}
        />
        <AiInsightListCard
          title="Recommendations"
          rows={answer?.recommendations || []}
          titleKey="title"
          descriptionKey="recommended_action"
          emptyText={answer ? "No recommendation was published because it was not supported by the SQL result." : undefined}
        />
      </div>
      <AiInsightEvidenceSummaryCard answer={answer} onOpenEvidence={openFullEvidence} />
      <AiInsightResultPreview answer={answer} />
    </SectionFrame>
  );
}

function hasAiInsightMissingData(answer: AiInsightV11Response): boolean {
  const status = asText(answer.answer_status || answer.result_validation?.validation_status).toUpperCase();
  return Boolean(answer.missing_data_points.length || answer.limitations.length || answer.assumptions.length || status === "PARTIAL" || status === "FAIL" || status === "NOT_SUPPORTED");
}

function AiInsightValidationPipeline({ answer }: { answer: AiInsightV11Response | null }) {
  const defaultSteps = [
    { step: "Context retrieved", status: "pending", detail: "Waiting for question" },
    { step: "SQL generated", status: "pending", detail: "Waiting for SQL" },
    { step: "SQL validated", status: "pending", detail: "Actual schema check pending" },
    { step: "SQL executed", status: "pending", detail: "Execution pending" },
    { step: "Result validated", status: "pending", detail: "Relevance check pending" },
    { step: "Insight generated", status: "pending", detail: "Insight pending" }
  ];
  const rawSteps = answer?.lifecycle?.length ? answer.lifecycle : defaultSteps;
  const hasResultStep = rawSteps.some((item) => asText(item.step).toLowerCase().includes("result validated"));
  const steps = hasResultStep
    ? rawSteps
    : [
        ...rawSteps.slice(0, Math.max(0, rawSteps.length - 1)),
        {
          step: "Result validated",
          status: answer ? (asText(answer.answer_status || answer.result_validation?.validation_status).toUpperCase() === "VALIDATED" ? "complete" : "warning") : "pending",
          detail: asText(answer?.answer_status || answer?.result_validation?.validation_status, "Pending")
        },
        ...rawSteps.slice(Math.max(0, rawSteps.length - 1))
      ];
  const strict = answer?.strict_sql_validation || {};
  const repair = answer?.sql_repair || {};
  const repairAttempted = Boolean(answer?.sql_repair && Object.keys(answer.sql_repair).length);
  const status = asText(answer?.answer_status || answer?.result_validation?.validation_status, "PENDING");
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="font-bold text-slate-950">Validation-first execution path</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            SQL is generated from verified schema context, structurally validated, checked with Supabase EXPLAIN, and only then executed.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ValidationBadge status={status} />
          {answer && <ValidationBadge status={asText(strict.validation_status, "SQL pending")} />}
        </div>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {steps.map((item, index) => (
          <article key={`${asText(item.step)}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center gap-2">
              <span className={classNames("flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white", lifecycleTone(asText(item.status)))}>
                {index + 1}
              </span>
              <p className="text-sm font-bold text-slate-950">{asText(item.step)}</p>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-500">{asText(item.detail)}</p>
          </article>
        ))}
      </div>
      {answer && (
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <MetricBox label="EXPLAIN passed" value={asText(strict.explain_passed, "Pending")} />
          <MetricBox label="Repair status" value={asText(repair.repair_status, repairAttempted ? "Attempted" : "Not needed")} />
          <MetricBox label="Actual tables" value={formatCount(answer.actual_tables_allowed?.length || answer.related_tables?.length || 0)} />
          <MetricBox label="Actual columns" value={formatCount(answer.actual_columns_allowed?.length || 0)} />
        </div>
      )}
    </section>
  );
}

function AiInsightAnswerSummary({ answer }: { answer: AiInsightV11Response | null }) {
  const validationStatus = asText(answer?.answer_status || answer?.result_validation?.validation_status, "Pending");
  const normalized = validationStatus.toUpperCase();
  const blocked = normalized === "NOT_SUPPORTED" || normalized === "FAIL" || normalized.includes("FAILED");
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Answer summary</h3>
          <p className="mt-1 text-sm text-slate-500">Human-readable business answer grounded in SQL evidence and semantic context.</p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <ValidationBadge status={validationStatus} />
          <ConfidenceBadge value={answer?.confidence_score || 0.75} />
        </div>
      </div>
      <p className={classNames("mt-4 rounded-lg border p-4 text-sm leading-6", blocked ? "border-red-200 bg-red-50 text-red-900" : "border-red-100 bg-red-50 text-slate-700")}>
        {blocked
          ? answer?.answer_summary || "This question cannot be answered with the current available schema."
          : answer?.answer_summary || "Ask a question to generate a SQL-backed business answer."}
      </p>
      {answer && (
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <MetricBox label="Role" value={answer.role} />
          <MetricBox label="Rows" value={formatCount(answer.row_count)} />
          <MetricBox label="Latency" value={formatTiming(answer.latency_ms)} />
        </div>
      )}
      {blocked && (
        <div className="mt-4 grid gap-3">
          <EvidenceList title="Missing schema or data" values={stringListFromUnknown(answer?.result_validation?.missing_data_points || answer?.missing_data_points || [])} />
          <EvidenceList title="Validation issues" values={stringListFromUnknown(answer?.result_validation?.issues || answer?.strict_sql_validation?.errors || [])} />
        </div>
      )}
    </section>
  );
}

function AiInsightKeyDataPointsCard({ answer }: { answer: AiInsightV11Response | null }) {
  const points = answer?.key_data_points || [];
  const followUps = answer?.suggested_follow_up_questions || [];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="font-bold text-slate-950">Key data points used</h3>
          <p className="mt-1 text-sm text-slate-500">The numbers and source fields that ground the answer.</p>
        </div>
        {answer && <ValidationBadge status={asText(answer.result_validation?.validation_status, "Pending")} />}
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {(points.length ? points : [{ metric: "Waiting for SQL evidence", value: "-", comparison: "Ask a question to extract supporting data points.", source: "Supabase SQL result" }]).slice(0, 6).map((point, index) => (
          <article key={`${asText(point.metric)}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{asText(point.metric)}</p>
            <p className="mt-2 text-xl font-bold text-slate-950">{asText(point.value)}</p>
            <p className="mt-2 text-sm leading-5 text-slate-600">{asText(point.comparison)}</p>
            <p className="mt-3 text-xs font-semibold text-red-700">{asText(point.source)}</p>
          </article>
        ))}
      </div>
      {followUps.length > 0 && (
        <div className="mt-5">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Suggested follow-up questions</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {followUps.slice(0, 4).map((item) => (
              <span key={item} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700">
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function AiInsightListCard({
  title,
  rows,
  titleKey,
  descriptionKey,
  emptyText
}: {
  title: string;
  rows: Array<Record<string, unknown>>;
  titleKey: string;
  descriptionKey: string;
  emptyText?: string;
}) {
  const displayRows = rows.length ? rows : [{ title: "Waiting for question", description: emptyText || "Insights and recommendations will appear after SQL execution." }];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">{title}</h3>
      <div className="mt-4 space-y-3">
        {displayRows.slice(0, 5).map((row, index) => (
          <article key={`${asText(row[titleKey])}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-start justify-between gap-3">
              <h4 className="font-bold text-slate-950">{asText(row[titleKey])}</h4>
              {row.confidence_score !== undefined && <ConfidenceBadge value={clampScore(toNumber(row.confidence_score))} />}
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">{asText(row[descriptionKey] || row.rationale)}</p>
            {Array.isArray(row.data_points_used) && row.data_points_used.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {row.data_points_used.slice(0, 4).map((item) => (
                  <span key={String(item)} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                    {String(item)}
                  </span>
                ))}
              </div>
            )}
            {Boolean(row.business_impact) && <p className="mt-2 text-sm font-bold text-red-700">{asText(row.business_impact)}</p>}
            {Boolean(row.expected_impact) && <p className="mt-2 text-sm font-bold text-red-700">{asText(row.expected_impact)}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}

function AiInsightSqlCard({ answer }: { answer: AiInsightV11Response | null }) {
  const [copied, setCopied] = useState(false);
  const strict = answer?.strict_sql_validation || {};
  const repair = answer?.sql_repair || {};
  const repairAttempted = Boolean(answer?.sql_repair && Object.keys(answer.sql_repair).length);
  const missingTables = stringListFromUnknown(strict.missing_tables || []);
  const missingColumns = stringListFromUnknown(strict.missing_columns || []);
  async function copySql() {
    if (!answer?.generated_sql || typeof navigator === "undefined") return;
    await navigator.clipboard.writeText(answer.generated_sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">SQL generated</h3>
          <p className="mt-1 text-sm text-slate-500">Validated read-only SQL and execution status.</p>
        </div>
        <button className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50" onClick={copySql} disabled={!answer?.generated_sql}>
          {copied ? "Copied" : "Copy SQL"}
        </button>
      </div>
      <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100">
        {highlightSql(answer?.generated_sql || "SQL appears here after you generate an insight.")}
      </pre>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <MetricBox label="Validation" value={formatStatus(asText(strict.validation_status, answer?.sql_validation_status || "Pending"))} />
        <MetricBox label="Execution" value={formatStatus(answer?.sql_execution_status || "Pending")} />
        <MetricBox label="Row count" value={formatCount(answer?.row_count || 0)} />
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <MetricBox label="EXPLAIN" value={asText(strict.explain_passed, "Pending")} />
        <MetricBox label="Repair" value={asText(repair.repair_status, repairAttempted ? "Attempted" : "Not needed")} />
        <MetricBox label="Answer status" value={asText(answer?.answer_status, "Pending")} />
      </div>
      {(missingTables.length > 0 || missingColumns.length > 0 || stringListFromUnknown(strict.errors || []).length > 0) && (
        <div className="mt-4 grid gap-3">
          <EvidenceList title="Missing tables" values={missingTables.length ? missingTables : ["No missing table references."]} />
          <EvidenceList title="Missing columns" values={missingColumns.length ? missingColumns : ["No missing column references."]} />
          <EvidenceList title="Validator messages" values={stringListFromUnknown(strict.errors || [])} />
        </div>
      )}
    </section>
  );
}

function AiInsightEvidenceSummaryCard({
  answer,
  onOpenEvidence
}: {
  answer: AiInsightV11Response | null;
  onOpenEvidence: () => void;
}) {
  const contextNames = (answer?.related_context || []).map((item) => asText(item.title)).filter(Boolean).slice(0, 3);
  const modelNames = (answer?.models_used || []).map((item) => asText(item.model_name)).filter(Boolean);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="font-bold text-slate-950">Evidence summary</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
            Compact trace of the source tables, context, model use, and validation behind this answer.
          </p>
        </div>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-3 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          onClick={onOpenEvidence}
          disabled={!answer}
        >
          <FileSearch size={17} />
          View Full Evidence
        </button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <MetricBox label="Tables" value={formatCount(answer?.actual_tables_allowed?.length || answer?.related_tables?.length || 0)} />
        <MetricBox label="Columns" value={formatCount(answer?.actual_columns_allowed?.length || answer?.related_columns?.length || 0)} />
        <MetricBox label="Context" value={formatCount(answer?.related_context?.length || 0)} />
        <MetricBox label="Models" value={modelNames.length ? formatCount(modelNames.length) : "No score required"} />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <EvidenceList title="Top context" values={contextNames.length ? contextNames : ["No semantic context selected yet"]} />
        <EvidenceList title="Models used" values={modelNames.length ? modelNames : ["No model score was required for this answer."]} />
        <EvidenceList
          title="Business data limitations"
          values={(answer?.business_data_limitations || []).length ? answer?.business_data_limitations || [] : ["No major missing business data identified."]}
        />
        <EvidenceList title="Actual-schema tables used" values={(answer?.actual_tables_allowed || []).length ? answer?.actual_tables_allowed || [] : answer?.related_tables || []} />
        <EvidenceList title="Actual-schema columns used" values={(answer?.actual_columns_allowed || []).length ? answer?.actual_columns_allowed || [] : ["Column lineage is available when SQL validation extracts explicit columns."]} />
      </div>
    </section>
  );
}

function AiInsightContextCard({ answer }: { answer: AiInsightV11Response | null }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">Related tables and context</h3>
      <div className="mt-4 grid gap-3">
        <EvidenceList title="Related tables" values={answer?.related_tables || []} />
        <EvidenceList title="Related columns" values={(answer?.related_columns || []).map((item) => `${asText(item.table)}.${asText(item.column)} (${asText(item.usage)})`)} />
        <EvidenceList title="Models used" values={(answer?.models_used || []).map((item) => asText(item.model_name))} />
        <EvidenceList title="Context documents" values={(answer?.related_context || []).map((item) => asText(item.title))} />
      </div>
    </section>
  );
}

function AiInsightMissingDataCard({ answer }: { answer: AiInsightV11Response | null }) {
  const missing = answer?.missing_data_points || [];
  const limitations = answer?.limitations || [];
  const assumptions = answer?.assumptions || [];
  const validationIssues = stringListFromUnknown(answer?.result_validation?.issues || []);
  const unsupportedClaims = stringListFromUnknown(answer?.result_validation?.unsupported_claims || []);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="font-bold text-slate-950">Missing data and limitations</h3>
      <p className="mt-1 text-sm text-slate-500">Shown when the answer is partial or would improve with more data.</p>
      <div className="mt-4 grid gap-3">
        <EvidenceList title="Missing data" values={missing.length ? missing : ["No major missing data identified for this answer."]} />
        {validationIssues.length > 0 && <EvidenceList title="Validation findings" values={validationIssues} />}
        {unsupportedClaims.length > 0 && <EvidenceList title="Unsupported claims blocked" values={unsupportedClaims} />}
        <EvidenceList title="Assumptions" values={assumptions.length ? assumptions : ["SQL uses current internal synthetic insurance data."]} />
        <EvidenceList title="Limitations" values={limitations.length ? limitations : ["MVP synthetic data should be validated before production decisions."]} />
      </div>
    </section>
  );
}

function AiInsightResultPreview({ answer }: { answer: AiInsightV11Response | null }) {
  const rows = answer?.result_preview || [];
  const columns = rows.length ? Object.keys(rows[0]).slice(0, 6) : ["Result preview"];
  return (
    <TableCard
      title="Result preview"
      columns={columns}
      rows={rows.length ? rows.map((row) => columns.map((column) => formatValue(row[column]))) : [["Run a question to preview the first 10 SQL result rows."]]}
    />
  );
}

function sampleAiInsightV10Response(role: string, question: string): AiInsightV11Response {
  return {
    role,
    question,
    answer_summary: "I can partially answer this using the current data. The strongest available signal is concentrated in retention risk, campaign response, and model-score driven next actions.",
    key_data_points: [
      { metric: "Top signal", value: "Sample", comparison: "Shown only when API is unavailable", source: "sample response" }
    ],
    insights: [
      { title: "Top signal", description: "High-risk policies and high-propensity customers should be prioritized first.", data_points_used: ["Sample only"], business_impact: "Premium protection and growth", confidence_score: 0.74 },
      { title: "Context coverage", description: "Semantic context and glossary terms were available for the main insurance domains.", business_impact: "Improved SQL grounding", confidence_score: 0.7 }
    ],
    recommendations: [
      { title: "Prioritize next actions", recommended_action: "Review the top SQL result rows and route them to the appropriate owner.", rationale: "The current data supports a ranked operational follow-up.", data_points_used: ["Sample only"], expected_impact: "Better retention and conversion focus", confidence_score: 0.72 }
    ],
    result_validation: { validation_status: "PARTIAL", publish_allowed: true, issues: ["Live API response unavailable"], unsupported_claims: [] },
    answer_status: "PARTIAL",
    strict_sql_validation: { validation_status: "sample", explain_passed: false, errors: ["Live API response unavailable"] },
    sql_repair: null,
    lifecycle: [
      { step: "Context retrieved", status: "warning", detail: "Sample mode" },
      { step: "SQL generated", status: "warning", detail: "Sample SQL" },
      { step: "SQL validated", status: "warning", detail: "Not live validated" },
      { step: "SQL executed", status: "warning", detail: "Not executed" },
      { step: "Result validated", status: "warning", detail: "Sample response" },
      { step: "Insight generated", status: "warning", detail: "Sample only" }
    ],
    actual_tables_allowed: ["public.policies", "public.products"],
    actual_columns_allowed: ["public.products.product_name", "public.policies.policy_status"],
    suggested_follow_up_questions: ["Which rows support this answer?", "What missing data would improve confidence?"],
    generated_sql: "select product_name, count(*) as policy_count from public.products group by product_name limit 10",
    sql_validation_status: "sample",
    sql_execution_status: "sample",
    row_count: 0,
    result_preview: [],
    related_tables: ["policies", "products", "model_scores", "semantic_documents"],
    related_columns: [
      { table: "products", column: "product_name", usage: "selected", business_description: "Insurance product name used for result grouping." },
      { table: "policies", column: "policy_status", usage: "filtered", business_description: "Policy lifecycle status used to scope active or issued policies." }
    ],
    related_context: [{ title: "Policy Analytics Context", document_type: "semantic_document", business_domain: "policy", relevance_score: 0.7 }],
    models_used: [
      {
        model_name: "policy_lapse_risk",
        model_type: "binary_classification",
        entity_type: "policy",
        used_in: "sample",
        score_interpretation: "Higher score means higher probability of lapse.",
        source_table: "model_scores"
      }
    ],
    insight_id: null,
    business_data_limitations: ["Live API response unavailable."],
    context_limitations: [],
    model_limitations: [],
    technical_warnings: ["AI Insight API was unavailable, so a sample response was shown."],
    fallback_used: true,
    gemini_available: false,
    gemini_quota_exhausted: false,
    evidence_summary: {},
    missing_data_points: ["Live API response unavailable"],
    assumptions: ["Sample response is shown only when backend is unavailable."],
    limitations: ["Validate with live Supabase data before using for decisions."],
    confidence_score: 0.72,
    latency_ms: 0,
    provider_used: "sample",
    model_used: "sample"
  };
}

function InsightEvidenceHubView() {
  const [insightId, setInsightId] = useState("");
  const [payload, setPayload] = useState<InsightEvidenceHubPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const idFromRoute = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("insight_id") || "" : "";
    setInsightId(idFromRoute);
    void loadEvidence(idFromRoute);
  }, []);

  async function loadEvidence(id = insightId) {
    setLoading(true);
    setError("");
    try {
      const query = id ? `?insight_id=${encodeURIComponent(id)}` : "";
      setPayload(await apiGet<InsightEvidenceHubPayload>(`/debug/latest-insight-evidence${query}`));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Evidence hub API is unavailable.");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }

  const recentRuns = payload?.recent_insight_runs || [];
  const sqlEvidence = payload?.sql_evidence || {};
  const strictEvidence = asRecord(sqlEvidence.strict_sql_validation);
  const repairEvidence = asRecord(sqlEvidence.sql_repair);
  const repairAttempted = Object.keys(repairEvidence).length > 0;
  const resultValidation = payload?.result_validation || {};
  const diagnostics = payload?.technical_diagnostics || {};
  const limitations = payload?.limitations || {};
  const columns = payload?.related_columns || [];
  const models = payload?.underlying_models || [];
  const context = payload?.semantic_context || [];
  const facts = payload?.related_facts || [];
  const lineage = payload?.data_lineage || [];

  return (
    <SectionFrame
      title="Insight Evidence Hub"
      description="Trace AI Intelligence answers from source tables, SQL, context, models, facts, and diagnostics."
    >
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-red-700">Evidence workspace</p>
            <h3 className="mt-2 text-2xl font-bold text-slate-950">Full answer traceability</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Load the latest insight or paste an insight ID from AI Intelligence to inspect data, SQL, model, context, and technical evidence.
            </p>
          </div>
          <div className="flex w-full flex-col gap-2 sm:flex-row lg:w-auto">
            <input
              className="h-11 min-w-72 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm font-semibold outline-none focus:border-red-500 focus:ring-4 focus:ring-red-100"
              value={insightId}
              onChange={(event) => setInsightId(event.target.value)}
              placeholder="insight_id"
            />
            <button className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 text-sm font-bold text-white hover:bg-red-700" onClick={() => loadEvidence()} disabled={loading}>
              {loading ? <Loader2 className="animate-spin" size={17} /> : <FileSearch size={17} />}
              Load Evidence
            </button>
          </div>
        </div>
      </section>

      {error && <InlineNotice message={error} />}
      {loading && (
        <section className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm font-semibold text-slate-500 shadow-sm">
          Loading evidence...
        </section>
      )}

      {!loading && payload && (
        <>
          <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-bold text-slate-950">Selected insight run</h3>
                  <p className="mt-1 text-sm text-slate-500">{payload.question || "No question captured for this evidence run."}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <ValidationBadge status={asText(payload.answer_status || resultValidation.answer_status || sqlEvidence.validation_status, "Pending")} />
                  <ValidationBadge status={asText(strictEvidence.validation_status, asText(sqlEvidence.validation_status, "Pending"))} />
                  <ConfidenceBadge value={clampScore(toNumber(payload.confidence_score, 0))} />
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <MetricBox label="Role" value={asText(payload.role, "-")} />
                <MetricBox label="Provider" value={asText(diagnostics.provider_used, "-")} />
                <MetricBox label="Model" value={asText(diagnostics.model_used, "-")} />
                <MetricBox label="Timestamp" value={dateOnly(payload.timestamp)} />
              </div>
              <p className="mt-4 rounded-lg border border-red-100 bg-red-50 p-4 text-sm leading-6 text-slate-700">
                {payload.final_answer || "Final answer text was not captured."}
              </p>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-bold text-slate-950">Recent Insight Runs</h3>
              <div className="mt-4 space-y-3">
                {(recentRuns.length ? recentRuns : [{ question: "No recent runs captured yet.", role: "-", snapshot_id: "" }]).slice(0, 6).map((run, index) => {
                  const runId = asText(run.snapshot_id);
                  return (
                    <button
                      key={`${runId}-${index}`}
                      className="block w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-left hover:border-red-200 hover:bg-red-50"
                      onClick={() => {
                        if (!runId) return;
                        setInsightId(runId);
                        void loadEvidence(runId);
                      }}
                    >
                      <p className="line-clamp-2 text-sm font-bold text-slate-950">{asText(run.question)}</p>
                      <p className="mt-1 text-xs font-semibold text-slate-500">
                        {asText(run.role)} | {dateOnly(run.created_at)} | {asText(run.provider_used, "provider unknown")}
                      </p>
                    </button>
                  );
                })}
              </div>
            </section>
          </div>

          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <MetricBox label="Tables used" value={formatCount(payload.related_tables?.length || 0)} />
            <MetricBox label="Columns used" value={formatCount(columns.length)} />
            <MetricBox label="Context documents" value={formatCount(context.length)} />
            <MetricBox label="SQL row count" value={formatCount(sqlEvidence.row_count || 0)} />
          </div>

          <section className="space-y-4">
            <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 className="font-bold text-slate-950">Data, Models & Context Architecture</h3>
                <p className="mt-1 max-w-4xl text-sm leading-6 text-slate-500">
                  This answer was generated using live Supabase data, verified schema context, model score tables, SQL validation, and LLM-based summarization.
                </p>
              </div>
              <span className="rounded-full border border-red-100 bg-red-50 px-3 py-1.5 text-xs font-bold text-red-700">
                Audit-ready AI workflow
              </span>
            </div>
            <div className="mt-5 grid gap-4 xl:grid-cols-4">
              <ArchitectureLayerCard
                title="Supabase Tables Used"
                columns={["Table", "Purpose"]}
                rows={(payload.related_tables || [])
                  .slice(0, 5)
                  .map((table) => [
                    `${asText(table.schema_name, "public")}.${asText(table.table_name)}`,
                    asText(table.why_it_was_used, asText(table.subject_area, "Business source data"))
                  ])}
              />
              <ArchitectureLayerCard
                title="Model Layer"
                columns={["Asset", "Use"]}
                rows={[
                  ["model_scores", "Risk, propensity, CLV, campaign response, and agent scoring outputs."],
                  ["model_predictions", "Entity-level model predictions when batch scoring is available."],
                  ["next_best_actions", "Operational recommendations generated from rules and model scores."]
                ]}
              />
              <ArchitectureLayerCard
                title="Context Layer"
                columns={["Asset", "Use"]}
                rows={[
                  ["semantic_documents", "Business, metric, model, table, and SQL template context with pgvector embeddings."],
                  ["business_glossary", "Human-readable insurance terms used to ground the answer."],
                  ["verified schema catalog", "Actual Supabase tables and columns used before SQL is allowed to execute."]
                ]}
              />
              <ArchitectureLayerCard
                title="AI Layer"
                columns={["Capability", "Status"]}
                rows={[
                  ["Primary LLM", asText(diagnostics.model_used, "Gemini")],
                  ["SQL generation", asText(strictEvidence.validation_status, "Schema validation pending")],
                  ["Result validation", asText(resultValidation.validation_status || payload.answer_status, "Pending")],
                  ["Fallback policy", "Controlled demo fallback only if live service is unavailable."]
                ]}
              />
            </div>
          </section>

          <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
            <TableCard
              title="Related Tables"
              columns={["Table", "Subject Area", "Why Used", "Row Count"]}
              rows={(payload.related_tables || []).map((table) => [
                `${asText(table.schema_name, "public")}.${asText(table.table_name)}`,
                asText(table.subject_area),
                asText(table.why_it_was_used),
                asText(table.row_count, "-")
              ])}
            />
            <TableCard
              title="Related Columns"
              columns={["Table", "Column", "Usage", "Business Description"]}
              rows={columns.map((column) => [
                asText(column.table, "unknown"),
                asText(column.column, "unknown"),
                asText(column.usage, "unknown"),
                asText(column.business_description, "See generated SQL.")
              ])}
            />
          </div>

          <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-bold text-slate-950">Semantic Context</h3>
              <div className="mt-4 space-y-3">
                {(context.length ? context : [{ title: "No context documents captured", document_type: "-", business_domain: "-", reason_retrieved: "-" }]).slice(0, 8).map((item, index) => (
                  <article key={`${asText(item.title)}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-bold text-slate-950">{asText(item.title)}</p>
                        <p className="mt-1 text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">
                          {asText(item.document_type)} | {asText(item.business_domain)}
                        </p>
                      </div>
                      <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-200">
                        {formatScore(item.relevance_score)}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{asText(item.reason_retrieved, "Retrieved because it matched the business question.")}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {asStringList(item.related_tables).slice(0, 5).map((table) => <span key={table} className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">{table}</span>)}
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-bold text-slate-950">Underlying Models</h3>
              <div className="mt-4 space-y-3">
                {(models.length ? models : [{ model_name: "No model score was required for this answer.", model_type: "-", entity_type: "-", used_in: "-" }]).slice(0, 8).map((model, index) => (
                  <article key={`${asText(model.model_name)}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-bold text-slate-950">{asText(model.model_name)}</p>
                        <p className="mt-1 text-sm text-slate-500">{asText(model.score_interpretation, "Model score interpretation was not needed or not captured.")}</p>
                      </div>
                      <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-200">{asText(model.used_in, "not used")}</span>
                    </div>
                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                      <MetricBox label="Type" value={asText(model.model_type, "-")} />
                      <MetricBox label="Entity" value={asText(model.entity_type, "-")} />
                      <MetricBox label="Source" value={asText(model.source_table, "-")} />
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>

          <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-bold text-slate-950">Data Lineage</h3>
              <div className="mt-5 space-y-3">
                {(lineage.length ? lineage : [{ step: "source data", detail: "No lineage captured" }]).map((item, index) => (
                  <div key={`${asText(item.step)}-${index}`} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white">{index + 1}</div>
                      {index < lineage.length - 1 && <div className="h-full w-px bg-slate-200" />}
                    </div>
                    <div className="pb-3">
                      <p className="font-semibold text-slate-900">{asText(item.step)}</p>
                      <p className="text-sm leading-6 text-slate-500">{asText(item.detail)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-bold text-slate-950">SQL Evidence</h3>
              <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100">
                {highlightSql(asText(sqlEvidence.generated_sql, "SQL was not captured."))}
              </pre>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <MetricBox label="Validation" value={asText(strictEvidence.validation_status, asText(sqlEvidence.validation_status, "Pending"))} />
                <MetricBox label="Execution" value={asText(sqlEvidence.execution_status, "Pending")} />
                <MetricBox label="Latency" value={formatTiming(sqlEvidence.execution_time)} />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <MetricBox label="EXPLAIN" value={asText(strictEvidence.explain_passed, "Pending")} />
                <MetricBox label="Repair" value={asText(repairEvidence.repair_status, repairAttempted ? "Attempted" : "Not needed")} />
                <MetricBox label="Answer status" value={asText(payload.answer_status || resultValidation.answer_status, "Pending")} />
              </div>
              <div className="mt-4 grid gap-3">
                <EvidenceList title="Actual-schema tables" values={stringListFromUnknown(sqlEvidence.tables_used || [])} />
                <EvidenceList title="Actual-schema columns" values={stringListFromUnknown(sqlEvidence.columns_used || [])} />
                <EvidenceList title="Validation messages" values={stringListFromUnknown(strictEvidence.errors || [])} />
              </div>
            </section>
          </div>

          <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
            <TableCard
              title="Related Facts"
              columns={["Metric", "Value", "Comparison", "Source"]}
              rows={(facts.length ? facts : [{ metric: "No facts captured", value: "-", comparison: "-", source: "-" }]).slice(0, 8).map((fact) => [
                asText(fact.metric),
                asText(fact.value),
                asText(fact.comparison),
                asText(fact.source)
              ])}
            />
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="font-bold text-slate-950">Technical Diagnostics</h3>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <MetricBox label="Gemini available" value={asText(diagnostics.gemini_available, "-")} />
                <MetricBox label="Gemini quota exhausted" value={asText(diagnostics.gemini_quota_exhausted, "-")} />
                <MetricBox label="Fallback used" value={asText(diagnostics.fallback_used, "-")} />
                <MetricBox label="Latency" value={formatTiming(diagnostics.latency_ms)} />
              </div>
              <div className="mt-4 grid gap-3">
                <EvidenceList title="Technical warnings" values={(limitations.technical_warnings || []).length ? limitations.technical_warnings || [] : ["No technical warnings captured."]} />
                <EvidenceList title="Business data limitations" values={(limitations.business_data_limitations || []).length ? limitations.business_data_limitations || [] : ["No major missing business data identified."]} />
                <EvidenceList title="Context limitations" values={(limitations.context_limitations || []).length ? limitations.context_limitations || [] : ["No context limitation captured."]} />
                <EvidenceList title="Model limitations" values={(limitations.model_limitations || []).length ? limitations.model_limitations || [] : ["No model limitation captured."]} />
              </div>
            </section>
          </div>
        </>
      )}
    </SectionFrame>
  );
}

function SectionFrame({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-red-700">Business workspace</p>
        <h2 className="mt-2 text-2xl font-bold text-slate-950">{title}</h2>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">{description}</p>
      </div>
      {children}
    </div>
  );
}

function KpiGrid({ items }: { items: Kpi[] }) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <KpiCard key={item.label} item={item} />
      ))}
    </section>
  );
}

function KpiCard({ item }: { item: Kpi }) {
  const tone = {
    red: "bg-red-50 text-red-700 border-red-100",
    green: "bg-emerald-50 text-emerald-700 border-emerald-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
    slate: "bg-slate-50 text-slate-700 border-slate-100"
  }[item.tone];
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">{item.label}</p>
          <p className="mt-2 text-3xl font-bold text-slate-950">{item.value}</p>
        </div>
        <span className={classNames("rounded-full border px-2.5 py-1 text-xs font-bold", tone)}>{item.trend}</span>
      </div>
      <p className="mt-4 text-sm text-slate-500">{item.helper}</p>
    </article>
  );
}

function ChartCard({ title, subtitle, icon, children }: { title: string; subtitle: string; icon: ReactNode; children: ReactNode }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">{title}</h3>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
        </div>
        <div className="rounded-lg bg-red-50 p-2 text-red-700">{icon}</div>
      </div>
      <div className="mt-5">{children}</div>
    </article>
  );
}

function HorizontalBars({ data }: { data: ChartSeries[] }) {
  return (
    <div className="space-y-4">
      {data.map((item) => (
        <div key={item.label}>
          <div className="mb-1 flex items-center justify-between gap-3 text-sm">
            <span className="font-semibold text-slate-700">{item.label}</span>
            <span className="font-bold text-slate-950">{item.value}%</span>
          </div>
          <div className="h-3 rounded-full bg-slate-100">
            <div className={classNames("h-3 rounded-full", item.color)} style={{ width: `${item.value}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function Sparkline({ values, danger = false }: { values: number[]; danger?: boolean }) {
  const max = Math.max(...values);
  return (
    <div className="flex h-40 items-end gap-2 rounded-lg bg-slate-50 p-4">
      {values.map((value, index) => (
        <div
          key={`${value}-${index}`}
          className={classNames("flex-1 rounded-t-md", danger ? "bg-red-500" : "bg-slate-800")}
          style={{ height: `${Math.max(12, (value / max) * 100)}%` }}
          title={`${value}`}
        />
      ))}
    </div>
  );
}

function Funnel() {
  const rows = [
    ["Targeted", 100],
    ["Engaged", 64],
    ["Quoted", 38],
    ["Converted", 15]
  ] as const;
  return (
    <div className="space-y-3">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-lg bg-slate-50 p-3">
          <div className="flex items-center justify-between text-sm font-semibold">
            <span>{label}</span>
            <span>{value}%</span>
          </div>
          <div className="mt-2 h-3 rounded-full bg-white">
            <div className="h-3 rounded-full bg-red-600" style={{ width: `${value}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function RecommendationPanel({ compact = false }: { compact?: boolean }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Recommended actions</h3>
          <p className="mt-1 text-sm text-slate-500">Prioritized by value, risk, confidence, and business rules.</p>
        </div>
        <Sparkles className="text-red-600" size={21} />
      </div>
      <div className="mt-5 space-y-3">
        {recommendations.slice(0, compact ? 2 : 3).map((item) => (
          <RecommendationCard key={item.title} item={item} />
        ))}
      </div>
    </section>
  );
}

function RecommendationCard({ item }: { item: Recommendation }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h4 className="font-bold text-slate-950">{item.title}</h4>
        <div className="flex items-center gap-2">
          <PriorityBadge value={item.priority} />
          <ConfidenceBadge value={item.confidence} />
        </div>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">{item.reason}</p>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">{item.owner}</span>
        <button className="inline-flex items-center gap-1 text-sm font-bold text-red-700 hover:text-red-800">
          {item.action}
          <ArrowRight size={15} />
        </button>
      </div>
    </article>
  );
}

function DataLineagePanel({ compact = false, answer }: { compact?: boolean; answer?: AskResponse | null }) {
  const sourceTables = answer?.explainability?.source_tables || ["customers", "policies", "model_scores", "next_best_actions"];
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-slate-950">Data lineage</h3>
          <p className="mt-1 text-sm text-slate-500">Trace every insight from data source to recommendation.</p>
        </div>
        <GitBranch className="text-red-600" size={21} />
      </div>
      <div className="mt-5 space-y-3">
        {(compact ? lineageSteps.slice(0, 4) : lineageSteps).map((item, index) => (
          <div key={item.label} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white">{index + 1}</div>
              {index < (compact ? 3 : lineageSteps.length - 1) && <div className="h-full w-px bg-slate-200" />}
            </div>
            <div className="pb-3">
              <p className="font-semibold text-slate-900">{item.label}</p>
              <p className="text-sm text-slate-500">{item.detail}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {sourceTables.slice(0, 6).map((item) => (
          <span key={item} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
            {item}
          </span>
        ))}
      </div>
    </section>
  );
}

function ProfileCard() {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-600 text-xl font-bold text-white">AT</div>
        <div>
          <h3 className="text-xl font-bold text-slate-950">Alicia Tan</h3>
          <p className="text-sm text-slate-500">Premier agency leader, SG Central</p>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-3">
        <MetricBox label="Book value" value="S$8.4M" />
        <MetricBox label="Persistency" value="94.2%" />
        <MetricBox label="Capacity" value="Healthy" />
        <MetricBox label="Risk" value="Low" />
      </div>
      <p className="mt-5 rounded-lg bg-red-50 p-4 text-sm leading-6 text-red-900">
        Best suited for high-CLV renewal outreach and health cross-sell conversion.
      </p>
    </article>
  );
}

function TableCard({ title, columns, rows }: { title: string; columns: string[]; rows: string[][] }) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 p-5">
        <h3 className="font-bold text-slate-950">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
            <tr>
              {columns.map((column) => (
                <th className="px-5 py-3 font-bold" key={column}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row, index) => (
              <tr key={`${row[0]}-${index}`} className="hover:bg-red-50/40">
                {row.map((cell, cellIndex) => (
                  <td className={classNames("px-5 py-4", cellIndex === 0 ? "font-semibold text-slate-950" : "text-slate-600")} key={`${cell}-${cellIndex}`}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ArchitectureLayerCard({ title, columns, rows }: { title: string; columns: string[]; rows: string[][] }) {
  return (
    <article className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-3">
        <h3 className="text-sm font-bold text-slate-950">{title}</h3>
      </div>
      <div className="divide-y divide-slate-100">
        {(rows.length ? rows : [["-", "No evidence captured for this layer yet."]]).slice(0, 5).map((row, index) => (
          <div key={`${title}-${index}`} className="grid gap-3 px-4 py-3 text-sm md:grid-cols-[0.85fr_1.15fr]">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">{columns[0]}</p>
              <p className="mt-1 break-words font-semibold text-slate-950">{row[0]}</p>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500">{columns[1]}</p>
              <p className="mt-1 leading-5 text-slate-600">{row[1]}</p>
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className="mt-1 break-words text-lg font-bold text-slate-950">{value}</p>
    </div>
  );
}

function PriorityBadge({ value }: { value: Recommendation["priority"] }) {
  const color =
    value === "Critical"
      ? "bg-red-600 text-white"
      : value === "High"
      ? "bg-red-50 text-red-700"
      : "bg-slate-100 text-slate-700";
  return <span className={classNames("rounded-full px-2.5 py-1 text-xs font-bold", color)}>{value}</span>;
}

function ConfidenceBadge({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-700 ring-1 ring-slate-200">
      <Activity size={13} className="text-red-600" />
      {percent}%
    </span>
  );
}

function ValidationBadge({ status }: { status: string }) {
  const normalized = status.toUpperCase();
  const isValidated = normalized === "PASS" || normalized === "VALIDATED" || normalized.includes("ALLOWED") || normalized === "EXECUTED" || normalized === "COMPLETE";
  const styles =
    isValidated
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
    : normalized === "PARTIAL"
      ? "bg-amber-50 text-amber-700 ring-amber-200"
      : normalized === "FAIL" || normalized === "NOT_SUPPORTED" || normalized.includes("FAILED")
      ? "bg-red-50 text-red-700 ring-red-200"
      : "bg-slate-50 text-slate-600 ring-slate-200";
  const label = isValidated ? "Validated" : normalized === "PARTIAL" ? "Partial" : normalized === "NOT_SUPPORTED" ? "Not supported" : normalized === "FAIL" || normalized.includes("FAILED") ? "Failed" : status || "Pending";
  return <span className={classNames("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold ring-1", styles)}>{label}</span>;
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return (await response.json()) as T;
}

function mapCustomerSearchOption(row: Record<string, unknown>): CustomerSearchOption {
  return {
    id: asText(row.customer_id),
    name: asText(row.display_name, "Customer"),
    customerNumber: asText(row.customer_number),
    policyNumber: asText(row.policy_number, asText(row.customer_number))
  };
}

function mapAgentSearchOption(row: Record<string, unknown>): AgentSearchOption {
  return {
    id: asText(row.agent_id),
    name: asText(row.display_name, "Agent"),
    agentNumber: asText(row.agent_number),
    territory: asText(row.territory_code, asText(row.channel, "Unassigned"))
  };
}

function mapCampaignSearchOption(row: Record<string, unknown>): CampaignSearchOption {
  return {
    id: asText(row.campaign_id),
    name: asText(row.campaign_name, "Campaign"),
    code: asText(row.campaign_code),
    channel: asText(row.channel),
    startDate: dateOnly(row.start_date)
  };
}

function mapCustomer360(payload: Entity360Payload): CustomerRecord {
  const summary = payload.summary;
  const sections = payload.sections;
  const policies = asArray(sections.policies);
  const claims = asArray(sections.claims);
  const scores = asArray(sections.model_scores);
  const actions = asArray(sections.next_best_actions);
  const annualPremium = sumNumbers(policies, "annual_premium");
  const productMix = makeProductMix(policies, "line_of_business");
  const firstAction = actions[0] || {};

  return {
    id: asText(summary.customer_number, payload.entity_id),
    policyNumber: asText(policies[0]?.policy_number, asText(summary.customer_number, payload.entity_id)),
    name: asText(summary.display_name, "Customer"),
    age: "Not captured",
    segment: asText(summary.customer_segment, "Unsegmented"),
    incomeBand: asText(summary.risk_tier, "Not captured"),
    location: asText(summary.location, "Not captured"),
    customerSince: dateOnly(summary.acquisition_date),
    preferredChannel: asText(summary.preferred_contact_method, "Not captured"),
    status: asText(summary.lifecycle_stage, "Unknown"),
    advisor: "Assigned through policy book",
    portfolio: {
      activePolicies: policies.length,
      annualPremium: formatCurrency(annualPremium),
      sumAssured: "Not captured",
      nextRenewal: dateOnly(firstTruthy(policies.map((policy) => policy.expiration_date))),
      productMix,
      policies: policies.slice(0, 8).map((policy) => ({
        product: asText(policy.product_name, "Policy product"),
        status: asText(policy.policy_status, "Unknown"),
        premium: formatCurrency(toNumber(policy.annual_premium)),
        sumAssured: "Not captured",
        renewalDate: dateOnly(policy.expiration_date),
        policyNumber: asText(policy.policy_number)
      }))
    },
    scores: mapCustomerScores(summary, scores),
    nextBestProduct: asText(firstAction.recommended_product_id, "Recommended action"),
    timeline: [
      ...policies.slice(0, 2).map((policy) => ({
        type: "Policy",
        date: dateOnly(policy.effective_date),
        title: `${asText(policy.product_name, "Policy")} ${asText(policy.policy_status, "")}`.trim(),
        detail: `Annual premium ${formatCurrency(toNumber(policy.annual_premium))}`,
        tone: "slate" as const
      })),
      ...claims.slice(0, 2).map((claim) => ({
        type: "Claim",
        date: dateOnly(claim.report_date),
        title: asText(claim.loss_cause, "Claim event"),
        detail: `${asText(claim.claim_status, "Unknown")} | incurred ${formatCurrency(toNumber(claim.incurred_amount))}`,
        tone: claim.claim_status === "closed" ? ("green" as const) : ("amber" as const)
      }))
    ],
    recommendations: [
      {
        action: asText(firstAction.recommended_action, asText(firstAction.action_type, "Review customer opportunity")),
        product: asText(firstAction.recommended_product_id, "Best available product"),
        reason: asText(firstAction.business_reason, asText(firstAction.action_reason, "Recommendation from next-best-action rules.")),
        confidence: clampScore(toNumber(firstAction.confidence_score, 0.82)),
        message: asText(firstAction.suggested_message, "Use the customer's preferred channel and review current policy needs before outreach."),
        priority: priorityFromScore(toNumber(firstAction.priority_score, 0.7))
      }
    ],
    lineage: scores.slice(0, 4).map((score) => ({
      sourceTable: "v_latest_model_scores",
      sourceColumn: "score",
      metric: asText(score.score_name, asText(score.model_name, "model_score")),
      model: `${asText(score.model_name, "model")}:${asText(score.model_version, "v1")}`,
      timestamp: dateOnly(score.score_ts)
    }))
  };
}

function mapAgent360(payload: Entity360Payload): AgentRecord {
  const summary = payload.summary;
  const sections = payload.sections;
  const mapaRows = asArray(sections.mapa_metrics);
  const latestMapa = mapaRows[0] || {};
  const movements = asArray(sections.movements);
  const scores = asArray(sections.model_scores);
  const actions = asArray(sections.recommendations);
  const commissions = asArray(sections.commissions);
  const targets = asArray(sections.targets);
  const portfolio = asRecord(sections.customer_portfolio);
  const commissionTotal = sumNumbers(commissions, "commission_amount");
  const target = targets[0] || {};

  return {
    name: asText(summary.display_name, "Agent"),
    code: asText(summary.agent_number, payload.entity_id),
    region: asText(summary.territory_code, "Unassigned"),
    branch: asText(summary.agency_name, asText(summary.channel, "Unassigned")),
    manager: "Distribution manager",
    tenure: tenureFromDate(summary.appointment_date),
    status: asText(summary.status, "Unknown"),
    tier: asText(summary.channel, "Distribution"),
    kpis: [
      { label: "Monthly premium", value: formatCurrency(toNumber(latestMapa.new_business_premium)), trend: "+0.0%", tone: "green", helper: "Latest MAPA month" },
      { label: "Policies sold", value: formatCount(latestMapa.policies_bound_count), trend: "+0", tone: "green", helper: "Latest MAPA month" },
      { label: "Conversion rate", value: percentRatio(toNumber(latestMapa.policies_bound_count), toNumber(latestMapa.quotes_count)), trend: "+0 pts", tone: "green", helper: "Quote to bind" },
      { label: "Persistency rate", value: percentRatio(toNumber(latestMapa.retained_policy_count), toNumber(latestMapa.retained_policy_count) + toNumber(latestMapa.lapsed_policy_count)), trend: "+0 pts", tone: "green", helper: "Retained over retained plus lapsed" },
      { label: "Target achievement", value: formatPercent(toNumber(target.attainment_pct)), trend: "+0 pts", tone: "amber", helper: asText(target.target_type, "Latest target") },
      { label: "Commission", value: formatCurrency(commissionTotal), trend: "+0.0%", tone: "green", helper: "Recent commission records" }
    ],
    mapa: {
      meetings: toNumber(latestMapa.contacts_count),
      activities: toNumber(latestMapa.leads_count),
      proposals: toNumber(latestMapa.quotes_count),
      applications: toNumber(latestMapa.applications_count),
      trend: mapaRows.slice(0, 12).reverse().map((row) => toNumber(row.new_business_premium)),
      bars: [
        { label: "Meetings", value: scaleMetric(latestMapa.contacts_count, 200), color: "bg-red-600" },
        { label: "Activities", value: scaleMetric(latestMapa.leads_count, 400), color: "bg-slate-800" },
        { label: "Proposals", value: scaleMetric(latestMapa.quotes_count, 150), color: "bg-red-400" },
        { label: "Applications", value: scaleMetric(latestMapa.applications_count, 120), color: "bg-slate-400" }
      ]
    },
    portfolio: {
      assignedCustomers: formatCount(portfolio.assigned_customers),
      highPropensity: formatCount(portfolio.high_propensity_customers),
      highLapseRisk: formatCount(portfolio.high_lapse_risk_customers),
      highClv: formatCount(portfolio.high_clv_customers),
      segments: [
        { label: "High propensity", value: scaleMetric(portfolio.high_propensity_customers, portfolio.assigned_customers), color: "bg-red-600" },
        { label: "High CLV", value: scaleMetric(portfolio.high_clv_customers, portfolio.assigned_customers), color: "bg-slate-800" },
        { label: "High lapse risk", value: scaleMetric(portfolio.high_lapse_risk_customers, portfolio.assigned_customers), color: "bg-amber-500" }
      ]
    },
    movements: movements.slice(0, 5).map((movement) => ({
      date: dateOnly(movement.effective_date),
      type: titleCase(asText(movement.movement_type, "Movement")),
      from: asText(movement.from_territory_code, "Not captured"),
      to: asText(movement.to_territory_code, "Not captured"),
      impact: asText(movement.reason, "Movement recorded")
    })),
    risks: mapAgentRisks(scores),
    actions: actions.length
      ? actions.slice(0, 3).map((action) => ({
          title: asText(action.recommended_action, asText(action.action_type, "Manager review")),
          type: asText(action.action_type, "Manager action"),
          reason: asText(action.business_reason, asText(action.action_reason, "Recommended from operational decisioning.")),
          confidence: clampScore(toNumber(action.confidence_score, 0.82)),
          priority: priorityFromScore(toNumber(action.priority_score, 0.7))
        }))
      : [
          { title: "Review agent pipeline", type: "Coaching", reason: "No open next-best-action record was returned for this agent.", confidence: 0.72, priority: "Medium" }
        ],
    evidence: scores.slice(0, 5).map((score) => ({
      sourceTable: "v_latest_model_scores",
      modelScore: `${asText(score.model_name, "model")}: ${formatScore(score.score)}`,
      rationale: [score.top_reason_1, score.top_reason_2, score.top_reason_3].map((item) => asText(item)).filter(Boolean).join(" | ") || asText(score.score_name, "Latest model score"),
      confidence: clampScore(toNumber(score.score, 0.8))
    }))
  };
}

function mapCampaign360(payload: Entity360Payload): CampaignRecord {
  const summary = payload.summary;
  const sections = payload.sections;
  const funnel = asRecord(sections.funnel);
  const responses = asArray(sections.responses);
  const segmentRows = asArray(sections.segment_performance);
  const regionRows = asArray(sections.region_performance);
  const productRows = asArray(sections.product_performance);
  const agentRows = asArray(sections.agent_performance);
  const scores = asArray(sections.model_scores);
  const targeted = toNumber(funnel.targets);
  const delivered = toNumber(funnel.delivered);
  const opened = toNumber(funnel.opened);
  const clicked = toNumber(funnel.clicked);
  const responded = toNumber(funnel.responses);
  const leadsCreated = toNumber(funnel.leads_created);
  const quotesCreated = toNumber(funnel.quotes_created);
  const policiesIssued = toNumber(funnel.policies_issued);
  const budget = toNumber(summary.budget_amount);
  const premiumGenerated = toNumber(funnel.conversion_premium);
  const topScore = scores[0] || {};
  const topSegment = segmentRows[0] || {};
  const topProduct = productRows[0] || {};

  return {
    id: payload.entity_id,
    name: asText(summary.campaign_name, "Campaign"),
    code: asText(summary.campaign_code, payload.entity_id),
    product: titleCase(asText(summary.target_line_of_business, asText(topProduct.product, "Not captured"))),
    channel: asText(summary.channel, "Not captured"),
    targetSegment: titleCase(asText(topSegment.segment, "All eligible customers")),
    startDate: dateOnly(summary.start_date),
    endDate: dateOnly(summary.end_date),
    budget: formatCurrency(budget),
    status: asText(summary.status, "Unknown"),
    objective: asText(summary.objective, "Measure campaign response, conversion quality, and next follow-up."),
    funnel: {
      targeted,
      delivered,
      opened,
      clicked,
      responded,
      leadsCreated,
      quotesCreated,
      policiesIssued
    },
    analytics: {
      responseRate: percentRatio(responded, targeted),
      leadConversionRate: percentRatio(leadsCreated, Math.max(responded, 1)),
      policyConversionRate: percentRatio(policiesIssued, targeted),
      costPerLead: leadsCreated ? formatCurrency(budget / leadsCreated) : "Not captured",
      costPerPolicy: policiesIssued ? formatCurrency(budget / policiesIssued) : "Not captured",
      premiumGenerated: formatCurrency(premiumGenerated),
      roi: budget && premiumGenerated ? `${Math.round((premiumGenerated / budget) * 10) / 10}x` : "Not captured"
    },
    performance: {
      segments: chartFromRows(segmentRows, "segment", "conversions", "responses"),
      regions: chartFromRows(regionRows, "region", "conversions", "responses"),
      products: chartFromRows(productRows, "product", "policies", "premium"),
      channels: chartFromRows(responses, "response_type", "conversions", "response_count"),
      agents: chartFromRows(agentRows, "agent_name", "conversions", "responses")
    },
    insights: [
      {
        title: "Customers likely to convert",
        value: formatCount(Math.max(responded, leadsCreated, policiesIssued)),
        detail: "Prioritize responders with quote, click, call, or conversion signals.",
        tone: "red"
      },
      {
        title: "Best follow-up channel",
        value: titleCase(asText(summary.channel, "Advisor follow-up")),
        detail: "Use the campaign medium as the primary follow-up path unless customer preference overrides it.",
        tone: "green"
      },
      {
        title: "Next best product",
        value: titleCase(asText(topProduct.product, asText(summary.target_line_of_business, "Product review"))),
        detail: "Product recommendation follows attributed quotes, policies, and target line of business.",
        tone: "slate"
      },
      {
        title: "Campaign response score",
        value: formatScore(topScore.score),
        detail: asText(topScore.top_reason_1, asText(topScore.score_band, "Latest response score context from model scores when available.")),
        tone: "amber"
      }
    ],
    recommendations: campaignRecommendations(responded, policiesIssued, premiumGenerated, budget, segmentRows),
    lineage: [
      { sourceTable: "campaigns", sourceColumn: "campaign_name, channel, start_date, end_date, budget_amount", metric: "campaign_overview", model: "None", timestamp: dateOnly(payload.generated_at) },
      { sourceTable: "campaign_targets", sourceColumn: "campaign_target_id, target_status", metric: "targeted_customers", model: "None", timestamp: dateOnly(payload.generated_at) },
      { sourceTable: "campaign_responses", sourceColumn: "response_type, conversion_flag, conversion_premium", metric: "response_rate, conversion_rate, premium_generated", model: "campaign_response_v1", timestamp: dateOnly(payload.generated_at) },
      { sourceTable: "leads", sourceColumn: "lead_id, lead_status, campaign_id", metric: "leads_created", model: "lead_conversion_v1", timestamp: dateOnly(payload.generated_at) },
      { sourceTable: "opportunities", sourceColumn: "opportunity_stage, quoted_premium", metric: "quotes_created", model: "lead_conversion_v1", timestamp: dateOnly(payload.generated_at) },
      { sourceTable: "policies", sourceColumn: "policy_id, annual_premium", metric: "policies_issued", model: "None", timestamp: dateOnly(payload.generated_at) },
      { sourceTable: "model_scores", sourceColumn: "score, score_band", metric: asText(topScore.score_name, "campaign_response_score"), model: asText(topScore.model_name, "campaign_response_v1"), timestamp: dateOnly(topScore.score_ts) }
    ]
  };
}

function chartFromRows(
  rows: Array<Record<string, unknown>>,
  labelKey: string,
  primaryValueKey: string,
  fallbackValueKey: string
): ChartSeries[] {
  const colors = ["bg-red-600", "bg-slate-800", "bg-red-400", "bg-slate-400", "bg-amber-500"];
  const values = rows
    .map((row) => ({
      label: titleCase(asText(row[labelKey], "Not captured")),
      rawValue: toNumber(row[primaryValueKey]) || toNumber(row[fallbackValueKey])
    }))
    .filter((item) => item.rawValue > 0)
    .slice(0, 5);
  if (!values.length) return [{ label: "Not captured", value: 100, color: "bg-slate-300" }];
  const total = values.reduce((sum, item) => sum + item.rawValue, 0) || 1;
  return values.map((item, index) => ({
    label: item.label,
    value: Math.max(4, Math.round((item.rawValue / total) * 100)),
    color: colors[index % colors.length]
  }));
}

function campaignRecommendations(
  responses: number,
  policies: number,
  premium: number,
  budget: number,
  segmentRows: Array<Record<string, unknown>>
): CampaignRecord["recommendations"] {
  const responseRateProxy = responses > 0 ? policies / Math.max(responses, 1) : 0;
  const topSegment = titleCase(asText(segmentRows[0]?.segment, "highest-response segment"));
  const roi = budget ? premium / budget : 0;
  return [
    {
      title: roi >= 1.5 ? "Continue campaign" : "Retarget segment",
      type: roi >= 1.5 ? "Scale" : "Optimization",
      reason:
        roi >= 1.5
          ? "Premium generated is ahead of campaign investment, so scale the highest-performing audiences."
          : `Retarget ${topSegment} and reduce spend on audiences with weak response or conversion.`,
      confidence: clampScore(roi >= 1.5 ? 0.88 : 0.78),
      priority: roi >= 1.5 ? "High" : "Medium"
    },
    {
      title: "Assign leads to agents",
      type: "Follow-up",
      reason: "Customers who opened, clicked, called, or requested a quote should be routed for advisor follow-up within seven days.",
      confidence: clampScore(Math.max(0.72, Math.min(0.92, responseRateProxy + 0.72))),
      priority: "Critical"
    },
    {
      title: "Suppress low-response segment",
      type: "Suppression",
      reason: "Suppress repeated campaign touches for non-responsive customers or customers with recent service friction.",
      confidence: 0.76,
      priority: "Medium"
    },
    {
      title: "Create retention campaign",
      type: "Retention",
      reason: "Use responders with renewal or lapse-risk signals as a separate retention audience before sales outreach.",
      confidence: 0.74,
      priority: "Medium"
    }
  ];
}

function InlineNotice({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <AlertTriangle className="mt-0.5 shrink-0" size={18} />
      <span>{message}</span>
    </div>
  );
}

function LoadingPanel({ label }: { label: string }) {
  return (
    <section className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-5 text-sm font-semibold text-slate-600 shadow-sm">
      <Loader2 className="animate-spin text-red-600" size={18} />
      {label}
    </section>
  );
}

function sampleDecisionIntelligence(role: string): DecisionIntelligencePayload {
  const roleCode = role.toLowerCase().replaceAll(" ", "_");
  const roleQuestions: Record<string, string[]> = {
    insurance_agent: ["Which customers should I call today?", "Which customers are likely to lapse?", "What should I cross-sell?"],
    agency_manager: ["Which agents need coaching?", "Which regions are declining?", "Where should I reallocate leads?"],
    campaign_manager: ["Which campaign should receive more budget?", "Which segments are showing fatigue?", "Which leads should be routed to agents?"],
    claims_manager: ["Which regions have high claims ratios?", "Which claims need fraud review?", "Which customers need claims service recovery?"],
    sales_director: ["Which agents are rising stars?", "Which agents can reach MDRT?", "Where is productivity falling?"],
    data_analyst: ["Which models have the strongest signal?", "Which feature tables need refresh?", "Show lineage for latest recommendations."],
    executive_leadership: ["What trends should concern me?", "What opportunities should we prioritize?", "What revenue is at risk?"]
  };
  return {
    role_code: roleCode,
    role_name: role,
    executive_briefing: {
      narrative: "The strongest agenda is to reduce lapse exposure while scaling high-conversion health and wealth opportunities.",
      top_risks: ["High-value lapse risk is concentrated in renewal cohorts.", "Agent activity is declining in selected branches.", "Campaign fatigue is emerging in repeated medical journeys."],
      top_opportunities: ["Health rider cross-sell can unlock S$3.8M expected premium.", "MDRT-near agents can close the productivity gap.", "Service recovery before renewal can protect high-CLV customers."],
      revenue_at_risk: "S$5.2M",
      revenue_opportunity: "S$14.6M",
      customer_growth: "8.7%",
      lapse_trend: "-7.1%",
      campaign_trend: "+3.4 pts",
      agent_productivity_trend: "+4 pts"
    },
    kpis: [
      { label: "Revenue at risk", value: "S$5.2M", trend: "-7.1%", helper: "High-risk lapse exposure" },
      { label: "Revenue opportunity", value: "S$14.6M", trend: "+10.4%", helper: "Cross-sell and renewal upside" },
      { label: "Customer growth", value: "8.7%", trend: "+1.2 pts", helper: "Net growth momentum" },
      { label: "Agent productivity", value: "73%", trend: "+4 pts", helper: "MAPA-weighted productivity" }
    ],
    hidden_trends: [
      { trend: "Health product lapse increasing", reason: "Missed payments and premium increase events are clustered in health protection products.", business_impact: "S$1.8M premium exposure", confidence: 0.86, recommended_action: "Trigger renewal rescue journeys and manager review." },
      { trend: "Agency productivity falling", reason: "Meetings and proposals are falling faster than lead volume.", business_impact: "4.2 point conversion drag", confidence: 0.82, recommended_action: "Coach agents and reassign hot leads." },
      { trend: "High-value customer engagement dropping", reason: "Digital visits and campaign opens are down for affluent wealth customers.", business_impact: "S$2.6M retention exposure", confidence: 0.79, recommended_action: "Prioritize human outreach." }
    ],
    opportunities: [
      { opportunity: "Customers likely to buy health rider", potential_premium: "S$3.8M", customer_count: 824, confidence: 0.88, recommended_action: "Create advisor call lists by product gap." },
      { opportunity: "Renewal-ready high-CLV customers", potential_premium: "S$4.9M", customer_count: 391, confidence: 0.84, recommended_action: "Assign senior agents for review conversations." },
      { opportunity: "Campaign segments with high conversion potential", potential_premium: "S$2.4M", customer_count: 1160, confidence: 0.81, recommended_action: "Increase budget for high-response segments." }
    ],
    risks: [
      { risk: "High lapse risk customers", impact: "S$5.2M premium at risk", root_cause: "Missed payments, renewal window, and reduced agent contact.", confidence: 0.89, recommended_action: "Launch retention call sequence within seven days." },
      { risk: "Underperforming agents", impact: "S$6.1M productivity gap", root_cause: "MAPA activity decline and lower proposal conversion.", confidence: 0.83, recommended_action: "Schedule coaching and route leads based on peer fit." },
      { risk: "Campaign fatigue emerging", impact: "18% response degradation", root_cause: "Repeated touches to low-intent segments.", confidence: 0.78, recommended_action: "Suppress fatigued segments." }
    ],
    questions: roleQuestions[roleCode] || roleQuestions.executive_leadership,
    recommendations: [
      { title: "Protect high-value renewal customers", business_impact: "S$1.3M expected retained value", reason: "High lapse probability, premium exposure, and renewal urgency are concentrated in 60-day windows.", owner: role, confidence: 0.91, due_date: "2026-06-08", expected_outcome: "Reduce near-term lapse and protect premium revenue." },
      { title: "Scale health cross-sell to engaged customers", business_impact: "S$3.8M expected new premium", reason: "Customers with strong engagement and no health product show high propensity.", owner: role, confidence: 0.87, due_date: "2026-06-08", expected_outcome: "Increase conversion using existing customer intent." }
    ],
    evidence: {
      source_tables: ["customers", "policies", "payments", "agent_mapa_metrics", "campaign_responses", "model_scores", "next_best_actions", "semantic_documents"],
      source_columns: ["customer_segment", "annual_premium", "payment_status", "metric_month", "response_type", "score", "recommended_action"],
      business_rules_used: ["Prioritize high CLV with human contact.", "Suppress sales action when unresolved complaint exists.", "Escalate renewal within 60 days when lapse risk is high."],
      ml_models_used: ["policy_lapse", "propensity_to_buy", "campaign_response", "agent_performance", "customer_lifetime_value"],
      context_documents_used: ["Policy Lapse Risk Context", "Next Best Action Context", "Customer Segmentation Context", "MAPA Metrics Context"],
      confidence: 0.87,
      timestamp: "2026-06-01T00:00:00Z"
    },
    schema_additions: ["role_insight_templates", "role_action_templates", "proactive_insight_log", "trend_discovery_results", "opportunity_discovery_results", "risk_discovery_results"],
    services: ["trend_discovery_service", "opportunity_discovery_service", "risk_discovery_service", "executive_briefing_service", "role_personalization_service", "recommendation_generation_service"],
    generated_at: "2026-06-01T00:00:00Z"
  };
}

function mockIntelligenceAnswer(question: string): AskResponse {
  return {
    intent: question.toLowerCase().includes("lapse") ? "KPI_LOOKUP" : "RECOMMENDATION",
    confidence_score: 0.89,
    sql: "select customer_id, recommended_action, priority_score from next_best_actions order by priority_score desc limit 25",
    execution: {
      execution_status: "sample",
      row_count: 3,
      rows: [
        { customer: "C-10291", action: "Retention call", priority: "0.94", reason: "Renewal within 60 days" },
        { customer: "C-10984", action: "Health cross-sell", priority: "0.91", reason: "High propensity and no health policy" },
        { customer: "C-11742", action: "Service recovery", priority: "0.88", reason: "Unresolved complaint" }
      ]
    },
    business_insight: {
      summary: "The strongest immediate opportunity is to protect high-value renewal customers while cross-selling health coverage to engaged segments.",
      key_observations: ["High CLV customers should be routed to human agents.", "Open complaints suppress sales actions.", "Campaign responders show stronger conversion probability."],
      caveats: ["Platform sample response shown when API is unavailable."]
    },
    recommendations: [
      { recommendation: "Create agent call list", reason: "Highest value actions are concentrated in renewal and health cross-sell cohorts.", priority_score: 0.91, source: "sample" }
    ],
    explainability: {
      source_tables: ["customers", "policies", "payments", "model_scores", "next_best_actions"],
      metrics_used: ["propensity_to_buy", "lapse_risk", "customer_lifetime_value"],
      context_documents_used: [{ title: "Next Best Action Context" }, { title: "Policy Lapse Risk Context" }]
    }
  };
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 4 });
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatTiming(value: unknown): string {
  const numberValue = toNumber(value, -1);
  if (numberValue < 0) return "Pending";
  if (numberValue >= 1000) return `${Math.round(numberValue / 100) / 10}s`;
  return `${Math.round(numberValue)} ms`;
}

function formatStatus(value: string): string {
  return value.replaceAll("_", " ");
}

function highlightSql(sql: string): string {
  return sql
    .replace(/\b(select|from|where|join|left join|group by|order by|limit|with|as|on|and|or)\b/gi, (match) => match.toUpperCase())
    .replace(/\s+/g, " ")
    .replace(/\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|LIMIT|WITH)\b/g, "\n$1")
    .trim();
}

function stringListFromUnknown(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") return asText((item as Record<string, unknown>).title || (item as Record<string, unknown>).name || JSON.stringify(item));
        return asText(item);
      })
      .filter(Boolean)
      .slice(0, 12);
  }
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .flatMap(([key, item]) => Array.isArray(item) ? item.map((child) => `${key}.${asText(child)}`) : [`${key}.${asText(item)}`])
      .filter(Boolean)
      .slice(0, 12);
  }
  return asText(value) ? [asText(value)] : [];
}

function contextTitles(context: Record<string, unknown> | null | undefined): string[] {
  if (!context) return [];
  return Object.values(context)
    .flatMap((bucket) => Array.isArray(bucket) ? bucket : [])
    .filter((item): item is Record<string, unknown> => item !== null && typeof item === "object" && !Array.isArray(item))
    .map((item) => asText(item.title || item.document_title || item.document_type))
    .filter(Boolean);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => item !== null && typeof item === "object" && !Array.isArray(item)) : [];
}

function asText(value: unknown, fallback = ""): string {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function toNumber(value: unknown, fallback = 0): number {
  const numberValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numberValue) ? numberValue : fallback;
}

function sumNumbers(rows: Array<Record<string, unknown>>, key: string): number {
  return rows.reduce((total, row) => total + toNumber(row[key]), 0);
}

function formatCurrency(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "Not captured";
  if (value >= 1_000_000) return `S$${(value / 1_000_000).toFixed(value >= 10_000_000 ? 0 : 1)}M`;
  if (value >= 1_000) return `S$${Math.round(value / 1_000).toLocaleString()}K`;
  return `S$${Math.round(value).toLocaleString()}`;
}

function formatCount(value: unknown): string {
  const numberValue = toNumber(value);
  return Math.round(numberValue).toLocaleString();
}

function formatScore(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not scored";
  const numberValue = toNumber(value);
  return numberValue <= 1 ? numberValue.toFixed(2) : `${Math.round(numberValue)}%`;
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "Not captured";
  return value <= 1 ? `${Math.round(value * 100)}%` : `${Math.round(value)}%`;
}

function formatDashboardPercent(value: unknown): string {
  const numberValue = toNumber(value);
  if (!Number.isFinite(numberValue)) return "Not captured";
  const normalized = numberValue <= 2 ? numberValue * 100 : numberValue;
  return `${Math.round(normalized * 10) / 10}%`;
}

function percentRatio(numerator: number, denominator: number): string {
  if (!denominator) return "Not captured";
  return `${Math.round((numerator / denominator) * 1000) / 10}%`;
}

function dateOnly(value: unknown): string {
  const text = asText(value);
  return text ? text.slice(0, 10) : "Not captured";
}

function firstTruthy(values: unknown[]): unknown {
  return values.find((value) => value !== null && value !== undefined && value !== "");
}

function uniqueOptions(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function uniqueOptionsInOrder(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => asText(item).trim())
    .filter(Boolean);
}

function trendDisplay(current: number, previous: number): string {
  if (!Number.isFinite(current) || !Number.isFinite(previous) || previous <= 0) return "new";
  const movement = ((current - previous) / previous) * 100;
  const rounded = Math.abs(Math.round(movement * 10) / 10);
  if (rounded < 0.5) return "flat";
  return movement > 0 ? `+${rounded}%` : `-${rounded}%`;
}

function heatmapRows(group: string, values: Array<Record<string, unknown>> | undefined) {
  return (values || []).map((row) => ({
    group,
    label: asText(row.dimension, "Not captured"),
    policies: toNumber(row.at_risk_policies),
    premium: toNumber(row.premium_at_risk),
    score: toNumber(row.average_lapse_score)
  }));
}

function heatColor(intensity: number): string {
  const value = Math.max(0.08, Math.min(1, intensity));
  const alpha = Math.round((0.08 + value * 0.2) * 100) / 100;
  return `rgba(220, 38, 38, ${alpha})`;
}

function clusterGrowthInsight(row: Record<string, unknown>): string {
  const conversion = clampScore(toNumber(row.conversion_rate));
  const premium = toNumber(row.premium);
  if (conversion >= 0.45) return "Use as peer benchmark for lead allocation.";
  if (premium >= 50000000) return "Large book; improve conversion through focused coaching.";
  if (/health/i.test(asText(row.product_focus))) return "Health-led cross-sell runway is strong.";
  if (/wealth|investment/i.test(asText(row.product_focus))) return "Prioritize high-CLV wealth reviews.";
  return "Compare against adjacent cluster for next growth play.";
}

function clampScore(value: number): number {
  if (!Number.isFinite(value)) return 0.75;
  return value > 1 ? Math.min(1, value / 100) : Math.max(0, Math.min(1, value));
}

function priorityFromScore(value: number): Recommendation["priority"] {
  const score = clampScore(value);
  if (score >= 0.85) return "Critical";
  if (score >= 0.65) return "High";
  return "Medium";
}

function scaleMetric(value: unknown, denominator: unknown): number {
  const numerator = toNumber(value);
  const denom = toNumber(denominator);
  if (!denom) return Math.min(100, Math.max(0, Math.round(numerator)));
  return Math.min(100, Math.max(0, Math.round((numerator / denom) * 100)));
}

function makeProductMix(rows: Array<Record<string, unknown>>, key: string): ChartSeries[] {
  if (!rows.length) return [{ label: "Not captured", value: 100, color: "bg-slate-300" }];
  const counts = new Map<string, number>();
  rows.forEach((row) => {
    const label = asText(row[key], "Other");
    counts.set(label, (counts.get(label) || 0) + 1);
  });
  const colors = ["bg-red-600", "bg-slate-800", "bg-red-400", "bg-slate-400"];
  return Array.from(counts.entries()).map(([label, count], index) => ({
    label: titleCase(label),
    value: Math.round((count / rows.length) * 100),
    color: colors[index % colors.length]
  }));
}

function mapCustomerScores(summary: Record<string, unknown>, scores: Array<Record<string, unknown>>): CustomerScore[] {
  const modelScores = scores.slice(0, 4).map((score) => {
    const rawScore = clampScore(toNumber(score.score, 0.5));
    const band = asText(score.score_band, rawScore >= 0.75 ? "High" : rawScore >= 0.45 ? "Medium" : "Low");
    return {
      label: titleCase(asText(score.score_name, asText(score.model_name, "Model score"))),
      value: Math.round(rawScore * 100),
      display: titleCase(band),
      tone: scoreTone(rawScore),
      helper: [score.top_reason_1, score.top_reason_2].map((item) => asText(item)).filter(Boolean).join(" | ") || "Latest backend model score"
    };
  });
  return modelScores.length
    ? modelScores
    : [
        {
          label: "Engagement score",
          value: Math.round(toNumber(summary.engagement_score)),
          display: `${Math.round(toNumber(summary.engagement_score))}%`,
          tone: "slate",
          helper: "Customer master engagement signal"
        },
        {
          label: "Risk tier",
          value: 60,
          display: titleCase(asText(summary.risk_tier, "Unknown")),
          tone: asText(summary.risk_tier).includes("high") ? "red" : "green",
          helper: "Customer master risk classification"
        }
      ];
}

function mapAgentRisks(scores: Array<Record<string, unknown>>): AgentRecord["risks"] {
  const riskScores = scores.filter((score) => /attrition|risk|performance|target/i.test(asText(score.score_name) + asText(score.model_name))).slice(0, 3);
  const mapped = riskScores.map((score) => {
    const rawScore = clampScore(toNumber(score.score, 0.5));
    return {
      label: titleCase(asText(score.score_name, asText(score.model_name, "Agent risk"))),
      value: Math.round(rawScore * 100),
      display: titleCase(asText(score.score_band, rawScore >= 0.75 ? "High" : rawScore >= 0.45 ? "Medium" : "Low")),
      tone: scoreTone(rawScore),
      helper: [score.top_reason_1, score.top_reason_2].map((item) => asText(item)).filter(Boolean).join(" | ") || "Latest backend model score"
    };
  });
  return mapped.length
    ? mapped
    : [
        { label: "Attrition risk", value: 50, display: "Not scored", tone: "slate", helper: "No latest model score returned" },
        { label: "Declining activity", value: 50, display: "Not scored", tone: "slate", helper: "No latest model score returned" },
        { label: "Target miss risk", value: 50, display: "Not scored", tone: "slate", helper: "No latest model score returned" }
      ];
}

function scoreTone(score: number): CustomerScore["tone"] {
  if (score >= 0.75) return "red";
  if (score >= 0.45) return "amber";
  return "green";
}

function titleCase(value: string): string {
  const titled = value
    .replaceAll("_", " ")
    .replace(/\w\S*/g, (word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
  return titled.replace(/\b(Mdrt|Mapa|Clv|Nbp|Kpi|Ai|Ml|Sql|Api|Hk|Sg)\b/g, (match) => match.toUpperCase());
}

function formatFilterOptionLabel(value: string): string {
  const text = value.trim();
  if (/^(SG|HK)-/i.test(text)) return text.toUpperCase();
  if (text === text.toUpperCase() && text.length <= 6) return text;
  return titleCase(text);
}

function tenureFromDate(value: unknown): string {
  const date = new Date(asText(value));
  if (Number.isNaN(date.getTime())) return "Not captured";
  const years = (Date.now() - date.getTime()) / (365.25 * 24 * 60 * 60 * 1000);
  return `${Math.max(0, Math.round(years * 10) / 10)} years`;
}

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}
