/**
 * navItems — single source of truth for the app's navigation.
 *
 * Shared by Sidebar (desktop, lg and up) and MobileNav (the drawer below lg),
 * so the two can never drift apart.
 */
import {
  Bot,
  Brain,
  Filter,
  Home,
  Megaphone,
  Repeat,
  Share2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  UserRound,
  UsersRound,
  Workflow
} from "lucide-react";
import type { ComponentType } from "react";

export interface NavItem {
  href: string;
  label: string;
  short: string;
  icon: ComponentType<{ size?: number }>;
}

// V1's exact sidebar order, with AI Intelligence + Evidence Hub appended.
export const NAV: NavItem[] = [
  { href: "/", label: "Home", short: "Home", icon: Home },
  { href: "/know-your-customer", label: "Know Your Customer", short: "KYC", icon: UserRound },
  { href: "/know-your-agent", label: "Know Your Agent", short: "KYA", icon: UsersRound },
  { href: "/campaign-effectiveness", label: "Campaign Effectiveness", short: "Campaigns", icon: Megaphone },
  { href: "/agent-performance", label: "Agent Performance Tracking", short: "Performance", icon: TrendingUp },
  { href: "/policy-lapse-risk", label: "Policy Lapse Risk", short: "Lapse Risk", icon: ShieldAlert },
  { href: "/ai-intelligence-v2", label: "AI Intelligence", short: "AI", icon: Sparkles },
  { href: "/agent-gallery-v2", label: "Agent Gallery", short: "Agents", icon: Bot },
  { href: "/governed-rules-v2", label: "Governed Rules", short: "Rules", icon: ShieldCheck },
  { href: "/insight-evidence-hub-v2", label: "Insight Evidence Hub", short: "Evidence", icon: Brain },
  { href: "/context-graph-v2", label: "Context Graph", short: "Graph", icon: Share2 }
];

// Prompt 19 — business-process insight pages (grouped under their own heading).
export const PROCESS_NAV: NavItem[] = [
  { href: "/lead-conversion-v2", label: "Lead-to-Conversion", short: "Funnel", icon: Workflow },
  { href: "/repurchase-v2", label: "Customer Repurchase", short: "Repurchase", icon: Repeat },
  { href: "/demand-v2", label: "Market Demand", short: "Demand", icon: TrendingUp },
  { href: "/campaign-process-v2", label: "Campaign Attribution", short: "Attribution", icon: Filter }
];

/** Active-route test: "/" must match exactly, others match by prefix. */
export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}
