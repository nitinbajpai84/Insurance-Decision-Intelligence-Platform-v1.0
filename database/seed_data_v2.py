"""Insurance PoC V2.0 — temporally-deep, domain-realistic SG life & health seed.

Generates 36 months of history with embedded process-analytics patterns:
  * lead -> opportunity -> quote -> proposal -> application -> issued policy
    (realistic stage conversion + day-lags + drop-off reasons)
  * repurchase: ~30% of customers buy a 2nd policy 6-24 months after the first
  * Q1/Q4 seasonality + campaign-driven spikes
  * ~8% lapse concentrated in specific products/segments, preceded by missed
    payments (payments + policy_lapse_events)
  * end-to-end campaign attribution (response -> lead -> conversion -> premium)
  * model layer (lapse / propensity / CLV / churn) CONSISTENT with the above

Usage:
    python database/seed_data_v2.py            # APPEND (safe; tags new rows)
    python database/seed_data_v2.py --reset    # TRUNCATE managed tables + reseed

Inserts use DuckDB `INSERT INTO t BY NAME` so only column NAMES must match.
Reproducible: RNG seeded. Prints integrity checks + a data profile at the end.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

try:
    from faker import Faker
except Exception:  # pragma: no cover
    print("Faker is required: pip install Faker", file=sys.stderr)
    raise

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = str(SCRIPT_DIR / "insurance_v2.duckdb")
SEED = 42

# ---- volumes -------------------------------------------------------------
N_CUSTOMERS = 5000
N_AGENTS = 800
N_PRODUCTS = 60
N_POLICIES = 12000
N_CAMPAIGNS = 200
N_CLAIMS = 3000
N_LEADS = 8000
N_OPPS = 5000
N_QUOTES = 4000
N_APPLICATIONS = 2500

MONTHS = 36
TODAY = date(2026, 6, 13)
CUR_MONTH = date(TODAY.year, TODAY.month, 1)

# tables this script owns (truncate order = children -> parents)
MANAGED_TABLES = [
    "next_best_actions", "model_predictions", "model_scores", "model_versions",
    "claim_assessments", "claim_fraud_indicators", "claims",
    "campaign_responses", "campaign_targets", "campaigns",
    "applications", "proposals", "quotes", "opportunities", "leads",
    "policy_lapse_events", "payments", "policies",
    "agent_targets", "agent_performance",
    "household_members", "households", "addresses", "customers", "agents", "products", "parties",
]

rng = np.random.default_rng(SEED)
fake = Faker()
Faker.seed(SEED)

SG_REGIONS = ["SG Central", "SG East", "SG West", "SG North", "SG North-East"]
HK_REGIONS = ["HK Island", "HK Kowloon", "HK New Territories"]
SEGMENTS = ["Mass", "Mass Affluent", "Affluent", "High Net Worth", "Young Family", "Established Professional", "Retiree"]
SEG_WEIGHTS = [0.28, 0.22, 0.14, 0.06, 0.14, 0.11, 0.05]
LINES = ["Health", "Savings", "Protection", "Investment"]
CHANNELS = ["agency", "bancassurance", "digital", "partner"]

NOW_TS = datetime(TODAY.year, TODAY.month, TODAY.day, 9, 0, 0)


def month_start(offset_from_first: int) -> date:
    """offset 0 = first month of the 36-month window."""
    first = CUR_MONTH
    # walk back MONTHS-1 then forward offset
    y = first.year
    m = first.month - (MONTHS - 1) + offset_from_first
    while m <= 0:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return date(y, m, 1)


def seasonal_month_weights() -> np.ndarray:
    w = np.ones(MONTHS)
    for i in range(MONTHS):
        mo = month_start(i).month
        if mo in (1, 2, 3):
            w[i] *= 1.35   # Q1 new-business push
        elif mo in (10, 11, 12):
            w[i] *= 1.25   # Q4 push
        w[i] *= rng.uniform(0.9, 1.1)
    return w / w.sum()


def rand_day_in_month(m: date) -> date:
    if m.month == 12:
        nxt = date(m.year + 1, 1, 1)
    else:
        nxt = date(m.year, m.month + 1, 1)
    span = (nxt - m).days
    return m + timedelta(days=int(rng.integers(0, span)))


def ts(d: date, hour_jitter=True) -> datetime:
    return datetime(d.year, d.month, d.day, int(rng.integers(8, 19)) if hour_jitter else 9, int(rng.integers(0, 60)))


def insert_df(con, table: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    con.register("seed_df", df)
    con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM seed_df")
    con.unregister("seed_df")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="TRUNCATE managed tables then reseed")
    args = ap.parse_args()
    tag = "" if args.reset else f"v2{uuid.uuid4().hex[:4]}_"

    con = duckdb.connect(DB_PATH, read_only=False)
    try:
        if args.reset:
            print("[reset] truncating managed tables...")
            for t in MANAGED_TABLES:
                try:
                    con.execute(f"DELETE FROM {t}")
                except Exception as exc:
                    print(f"  warn: {t}: {exc}")
            con.commit()

        cid = lambda i: f"{tag}cust_{i:05d}"
        aid = lambda i: f"{tag}agt_{i:04d}"
        pid = lambda i: f"{tag}prod_{i:03d}"
        polid = lambda i: f"{tag}pol_{i:05d}"
        pty = lambda s, i: f"{tag}pty_{s}_{i:05d}"

        # ---------------- PRODUCTS ----------------
        print("[gen] products")
        prod_rows = []
        per_line = N_PRODUCTS // len(LINES)
        sg_names = {
            "Health": ["PRUShield", "PRUExtra", "MediGuard", "HealthSecure", "CareFirst"],
            "Savings": ["Evergreen Wealth", "PRUSave", "SmartSaver", "GrowEasy", "FutureFund"],
            "Protection": ["PRUProtect", "TermGuard", "LifeSecure", "FamilyShield", "PRUActive"],
            "Investment": ["PRULink Vantage", "WealthLink", "InvestPlus", "PRULink Global", "EquityGro"],
        }
        prem_band = {"Health": (600, 3500), "Savings": (2400, 18000), "Protection": (400, 2600), "Investment": (3600, 30000)}
        idx = 0
        product_meta = {}
        for line in LINES:
            for j in range(per_line):
                base = sg_names[line][j % len(sg_names[line])]
                name = f"{base} {['', 'Plus', 'Prime', 'Elite', 'II', 'III'][j % 6]}".strip()
                is_rider = j % 5 == 4
                lo, hi = prem_band[line]
                prod_rows.append({
                    "product_id": pid(idx), "product_code": f"{line[:2].upper()}{idx:03d}",
                    "product_name": name, "line_of_business": line, "product_family": base,
                    "product_component_type": "rider" if is_rider else "base",
                    "rider_category": "supplementary" if is_rider else None,
                    "product_version": "v2", "effective_date": month_start(0), "expiration_date": None,
                    "active_flag": True, "created_at": NOW_TS, "updated_at": NOW_TS,
                })
                product_meta[pid(idx)] = {"line": line, "lo": lo, "hi": hi, "rider": is_rider}
                idx += 1
        # pad to exactly N_PRODUCTS
        while idx < N_PRODUCTS:
            line = LINES[idx % len(LINES)]
            lo, hi = prem_band[line]
            prod_rows.append({"product_id": pid(idx), "product_code": f"XX{idx:03d}", "product_name": f"FlexiPlan {idx}",
                              "line_of_business": line, "product_family": "FlexiPlan", "product_component_type": "base",
                              "product_version": "v2", "effective_date": month_start(0), "active_flag": True,
                              "created_at": NOW_TS, "updated_at": NOW_TS})
            product_meta[pid(idx)] = {"line": line, "lo": lo, "hi": hi, "rider": False}
            idx += 1
        base_products = [p for p, m in product_meta.items() if not m["rider"]]
        insert_df(con, "products", pd.DataFrame(prod_rows))

        # ---------------- AGENTS (+ parties) ----------------
        print("[gen] agents")
        party_rows, agent_rows = [], []
        agent_region = {}
        for i in range(N_AGENTS):
            p = pty("agt", i)
            fn, ln = fake.first_name(), fake.last_name()
            region = rng.choice(SG_REGIONS) if rng.random() < 0.82 else rng.choice(HK_REGIONS)
            agent_region[aid(i)] = region
            appt = month_start(0) - timedelta(days=int(rng.integers(60, 2000)))
            party_rows.append({"party_id": p, "party_type": "person", "display_name": f"{fn} {ln}",
                               "first_name": fn, "last_name": ln, "email": f"{fn}.{ln}{i}@agency.sg".lower(),
                               "phone": fake.msisdn()[:8], "created_at": NOW_TS, "updated_at": NOW_TS})
            agent_rows.append({"agent_id": aid(i), "party_id": p, "agent_number": f"A{i:05d}",
                               "channel": rng.choice(CHANNELS, p=[0.55, 0.25, 0.12, 0.08]), "territory_code": region,
                               "appointment_date": appt, "status": "active" if rng.random() < 0.93 else "inactive",
                               "created_at": NOW_TS, "updated_at": NOW_TS})
        insert_df(con, "parties", pd.DataFrame(party_rows))
        insert_df(con, "agents", pd.DataFrame(agent_rows))

        # ---------------- CUSTOMERS (+ parties + addresses) ----------------
        print("[gen] customers")
        cust_party_rows, cust_rows, addr_rows = [], [], []
        cust_segment, cust_region, cust_affluent, cust_acq = {}, {}, {}, {}
        seg_choices = rng.choice(SEGMENTS, size=N_CUSTOMERS, p=SEG_WEIGHTS)
        for i in range(N_CUSTOMERS):
            p = pty("cust", i)
            fn, ln = fake.first_name(), fake.last_name()
            seg = seg_choices[i]
            affluent = seg in ("Affluent", "High Net Worth", "Established Professional")
            age = int(np.clip(rng.normal(48 if seg == "Retiree" else 39, 12), 21, 85))
            dob = date(TODAY.year - age, int(rng.integers(1, 13)), int(rng.integers(1, 28)))
            region = rng.choice(SG_REGIONS) if rng.random() < 0.85 else rng.choice(HK_REGIONS)
            acq = month_start(0) - timedelta(days=int(rng.integers(0, 1500)))
            cust_segment[cid(i)] = seg
            cust_region[cid(i)] = region
            cust_affluent[cid(i)] = affluent
            cust_acq[cid(i)] = acq
            cust_party_rows.append({"party_id": p, "party_type": "person", "display_name": f"{fn} {ln}",
                                    "first_name": fn, "last_name": ln, "date_of_birth": dob,
                                    "email": f"{fn}.{ln}{i}@mail.sg".lower(), "phone": fake.msisdn()[:8],
                                    "created_at": NOW_TS, "updated_at": NOW_TS})
            cust_rows.append({"customer_id": cid(i), "party_id": p, "customer_number": f"C{i:06d}",
                              "customer_segment": seg, "lifecycle_stage": rng.choice(["onboarding", "active", "mature", "dormant"], p=[0.12, 0.5, 0.3, 0.08]),
                              "acquisition_date": acq, "risk_tier": rng.choice(["low", "medium", "high"], p=[0.45, 0.4, 0.15]),
                              "engagement_score": round(float(np.clip(rng.normal(0.62 if affluent else 0.5, 0.18), 0, 1)), 3),
                              "created_at": NOW_TS, "updated_at": NOW_TS})
            addr_rows.append({"address_id": f"{tag}addr_{i:05d}", "party_id": p, "address_type": "home",
                              "line1": fake.street_address()[:60], "city": region,
                              "state_code": region, "postal_code": str(rng.integers(100000, 829999)),
                              "country_code": "HK" if region.startswith("HK") else "SG", "is_current": True,
                              "effective_date": acq, "created_at": NOW_TS, "updated_at": NOW_TS})
        insert_df(con, "parties", pd.DataFrame(cust_party_rows))
        insert_df(con, "customers", pd.DataFrame(cust_rows))
        insert_df(con, "addresses", pd.DataFrame(addr_rows))

        # ---------------- HOUSEHOLDS ----------------
        print("[gen] households")
        hh_rows, hhm_rows = [], []
        n_hh = N_CUSTOMERS // 3
        cust_ids = [cid(i) for i in range(N_CUSTOMERS)]
        rng.shuffle(cust_ids)
        ptr = 0
        for h in range(n_hh):
            size = int(rng.choice([1, 2, 3, 4], p=[0.35, 0.3, 0.2, 0.15]))
            members = cust_ids[ptr:ptr + size]
            ptr += size
            if not members:
                break
            hh_id = f"{tag}hh_{h:05d}"
            hh_rows.append({"household_id": hh_id, "household_name": f"Household {h}", "primary_customer_id": members[0],
                            "household_segment": cust_segment[members[0]], "member_count": len(members),
                            "region": cust_region[members[0]], "created_at": NOW_TS, "updated_at": NOW_TS})
            for k, mcid in enumerate(members):
                hhm_rows.append({"household_member_id": f"{tag}hhm_{h:05d}_{k}", "household_id": hh_id,
                                 "customer_id": mcid, "relationship_to_head": "head" if k == 0 else rng.choice(["spouse", "child", "parent"]),
                                 "is_primary": k == 0, "joined_date": cust_acq[mcid], "created_at": NOW_TS, "updated_at": NOW_TS})
        insert_df(con, "households", pd.DataFrame(hh_rows))
        insert_df(con, "household_members", pd.DataFrame(hhm_rows))

        # ---------------- CAMPAIGNS ----------------
        print("[gen] campaigns")
        camp_rows = []
        for i in range(N_CAMPAIGNS):
            sm = month_start(int(rng.integers(0, MONTHS)))
            line = rng.choice(LINES)
            camp_rows.append({"campaign_id": f"{tag}camp_{i:04d}", "campaign_code": f"CMP{i:04d}",
                              "campaign_name": f"{line} {rng.choice(['Growth', 'Retention', 'Cross-sell', 'Awareness'])} {sm.strftime('%b%y')}",
                              "campaign_type": rng.choice(["acquisition", "retention", "cross_sell", "upsell"]),
                              "channel": rng.choice(["email", "sms", "agency", "social", "telemarketing"]),
                              "objective": "new_business", "target_line_of_business": line,
                              "start_date": sm, "end_date": sm + timedelta(days=int(rng.integers(20, 75))),
                              "budget_amount": round(float(rng.uniform(20000, 250000)), 2),
                              "status": "completed" if sm < CUR_MONTH - timedelta(days=40) else "active",
                              "created_at": NOW_TS, "updated_at": NOW_TS})
        insert_df(con, "campaigns", pd.DataFrame(camp_rows))
        camp_ids = [r["campaign_id"] for r in camp_rows]
        camp_line = {r["campaign_id"]: r["target_line_of_business"] for r in camp_rows}
        camp_start = {r["campaign_id"]: r["start_date"] for r in camp_rows}

        # ---------------- POLICIES (book + repurchase) ----------------
        print("[gen] policies (with repurchase chains)")
        mw = seasonal_month_weights()
        # number of policies per customer (affluent buy more)
        base_lambda = np.where([cust_affluent[cid(i)] for i in range(N_CUSTOMERS)], 2.2, 1.4)
        counts = 1 + rng.poisson(base_lambda)
        counts = np.clip(counts, 1, 7)
        # scale to hit N_POLICIES
        while counts.sum() > N_POLICIES:
            j = rng.integers(0, N_CUSTOMERS)
            if counts[j] > 1:
                counts[j] -= 1
        while counts.sum() < N_POLICIES:
            counts[rng.integers(0, N_CUSTOMERS)] += 1

        lapse_prone_lines = {"Investment", "Savings"}
        pol_rows, pol_idx = [], 0
        repurchase_gaps: list[int] = []
        cust_first_line: dict[str, str] = {}
        policy_customer, policy_product, policy_agent = {}, {}, {}
        policy_eff, policy_status, policy_prem = {}, {}, {}
        for i in range(N_CUSTOMERS):
            c = cid(i)
            n = int(counts[i])
            seg = cust_segment[c]
            affluent = cust_affluent[c]
            prev_eff = None
            prev_pol = None
            for k in range(n):
                product = rng.choice(base_products)
                meta = product_meta[product]
                if k == 0:
                    mo_i = int(rng.choice(MONTHS, p=mw))
                    eff = rand_day_in_month(month_start(mo_i))
                    # not before acquisition
                    if eff < cust_acq[c]:
                        eff = cust_acq[c] + timedelta(days=int(rng.integers(1, 30)))
                    cust_first_line[c] = meta["line"]
                else:
                    gap_days = int(rng.integers(180, 720)) if rng.random() < (0.38 if affluent else 0.22) else int(rng.choice([int(rng.integers(30, 179)), int(rng.integers(721, 1100))]))
                    eff = prev_eff + timedelta(days=gap_days)
                    if eff > TODAY:
                        eff = TODAY - timedelta(days=int(rng.integers(1, 120)))
                    if 180 <= (eff - prev_eff).days <= 730:
                        repurchase_gaps.append((eff - prev_eff).days)
                prem = round(float(np.clip(rng.normal((meta["lo"] + meta["hi"]) / 2 * (1.3 if affluent else 0.9), (meta["hi"] - meta["lo"]) / 4), meta["lo"], meta["hi"])), 2)
                # lapse: ~8%, concentrated
                lapse_p = 0.105
                if meta["line"] in lapse_prone_lines:
                    lapse_p += 0.06
                if seg in ("Mass", "Young Family"):
                    lapse_p += 0.04
                age_months = (TODAY.year - eff.year) * 12 + TODAY.month - eff.month
                is_lapsed = age_months >= 6 and rng.random() < lapse_p
                status = "lapsed" if is_lapsed else rng.choice(["active", "in_force", "issued"], p=[0.7, 0.2, 0.1])
                pol = polid(pol_idx)
                exp_d = date(eff.year + int(rng.choice([1, 5, 10, 20])), eff.month, min(eff.day, 28))
                pol_rows.append({
                    "policy_id": pol, "policy_number": f"POL-SG-{pol_idx:06d}", "customer_id": c,
                    "agent_id": aid(int(rng.integers(0, N_AGENTS))), "product_id": product,
                    "prior_policy_id": prev_pol, "policy_status": status, "effective_date": eff,
                    "expiration_date": exp_d, "issue_date": eff - timedelta(days=int(rng.integers(1, 21))),
                    "cancellation_date": (eff + timedelta(days=int(rng.integers(120, age_months * 30 + 30)))) if is_lapsed else None,
                    "source_channel": rng.choice(CHANNELS, p=[0.5, 0.28, 0.14, 0.08]),
                    "payment_plan": rng.choice(["annual", "monthly", "quarterly"], p=[0.45, 0.4, 0.15]),
                    "annual_premium": prem, "written_premium": prem, "created_at": NOW_TS, "updated_at": NOW_TS,
                })
                policy_customer[pol] = c
                policy_product[pol] = product
                policy_agent[pol] = pol_rows[-1]["agent_id"]
                policy_eff[pol] = eff
                policy_status[pol] = status
                policy_prem[pol] = prem
                prev_eff, prev_pol = eff, pol
                pol_idx += 1
        insert_df(con, "policies", pd.DataFrame(pol_rows))
        all_policies = list(policy_customer.keys())
        lapsed_policies = [p for p in all_policies if policy_status[p] == "lapsed"]

        # ---------------- PAYMENTS + LAPSE EVENTS ----------------
        print("[gen] payments + lapse events")
        pay_rows, lapse_rows = [], []
        for p in all_policies:
            eff = policy_eff[p]
            prem = policy_prem[p]
            n_pay = min(12, max(1, (TODAY.year - eff.year) * 12 + TODAY.month - eff.month))
            for k in range(n_pay):
                due = eff + timedelta(days=30 * (k + 1))
                if due > TODAY:
                    break
                missed = policy_status[p] == "lapsed" and k >= n_pay - 3
                pay_rows.append({"payment_id": f"{tag}pay_{len(pay_rows):07d}", "policy_id": p, "customer_id": policy_customer[p],
                                 "due_date": due, "payment_date": None if missed else due + timedelta(days=int(rng.integers(0, 8))),
                                 "payment_status": "missed" if missed else "paid", "payment_method": rng.choice(["giro", "card", "bank_transfer"]),
                                 "billed_amount": round(prem / 12, 2), "paid_amount": 0.0 if missed else round(prem / 12, 2),
                                 "created_at": NOW_TS, "updated_at": NOW_TS})
            if policy_status[p] == "lapsed":
                ld = (date.fromisoformat(str(policy_eff[p])) if isinstance(policy_eff[p], str) else policy_eff[p]) + timedelta(days=int(rng.integers(200, 900)))
                if ld > TODAY:
                    ld = TODAY - timedelta(days=int(rng.integers(1, 60)))
                lapse_rows.append({"policy_lapse_event_id": f"{tag}lap_{len(lapse_rows):06d}", "policy_id": p,
                                   "customer_id": policy_customer[p], "agent_id": policy_agent[p], "lapse_event_date": ld,
                                   "lapse_stage": "lapsed", "missed_payment_count": int(rng.integers(2, 5)),
                                   "days_past_due": int(rng.integers(60, 180)),
                                   "lapse_reason": rng.choice(["non_payment", "affordability", "dissatisfaction", "switched_provider"]),
                                   "intervention_type": rng.choice(["none", "call", "letter", "agent_visit"]),
                                   "created_at": NOW_TS, "updated_at": NOW_TS})
        insert_df(con, "payments", pd.DataFrame(pay_rows))
        insert_df(con, "policy_lapse_events", pd.DataFrame(lapse_rows))

        # ---------------- SALES FUNNEL (leads -> opp -> quote -> proposal -> app -> policy) ----------------
        print("[gen] sales funnel")
        # recent policies become "issued" endpoints of the funnel
        recent_policies = sorted(all_policies, key=lambda x: policy_eff[x], reverse=True)
        DROP = {
            "opp": "not_qualified", "quote": "price", "proposal": "no_response",
            "app": "underwriting_decline", "lead": "no_contact",
        }
        lead_rows, opp_rows, quote_rows, prop_rows, app_rows = [], [], [], [], []
        lead_to_policy = {}
        # leads
        for i in range(N_LEADS):
            c = cid(int(rng.integers(0, N_CUSTOMERS)))
            camp = rng.choice(camp_ids) if rng.random() < 0.6 else None
            recv = ts(rand_day_in_month(month_start(int(rng.choice(MONTHS, p=mw)))))
            prod = rng.choice(base_products)
            lead = f"{tag}lead_{i:05d}"
            converts = rng.random() < 0.45     # -> opportunity
            lead_rows.append({"lead_id": lead, "lead_number": f"L{i:06d}", "party_id": pty("cust", int(c.split('_')[-1]) if c.split('_')[-1].isdigit() else 0),
                              "customer_id": c, "campaign_id": camp, "assigned_agent_id": aid(int(rng.integers(0, N_AGENTS))),
                              "product_id": prod, "lead_source": rng.choice(["web", "referral", "campaign", "walk_in", "partner"]),
                              "lead_status": "converted" if converts else rng.choice(["new", "working", "lost"], p=[0.2, 0.3, 0.5]),
                              "received_at": recv, "qualified_at": recv + timedelta(days=int(rng.integers(1, 14))) if converts else None,
                              "score": round(float(np.clip(rng.normal(0.6 if converts else 0.4, 0.18), 0, 1)), 3),
                              "created_at": recv, "updated_at": NOW_TS})
            if converts:
                lead_to_policy[lead] = {"c": c, "prod": prod, "agent": lead_rows[-1]["assigned_agent_id"],
                                        "camp": camp, "recv": recv}

        # opportunities (from converted leads + some direct)
        conv_leads = list(lead_to_policy.keys())
        rng.shuffle(conv_leads)
        oi = 0
        opp_to_chain = {}
        for lead in conv_leads:
            info = lead_to_policy[lead]
            opened = (info["recv"] + timedelta(days=int(rng.integers(2, 20)))).date()
            to_proposal = rng.random() < 0.60
            opp = f"{tag}opp_{oi:05d}"
            opp_rows.append({"opportunity_id": opp, "opportunity_number": f"O{oi:06d}", "lead_id": lead,
                             "customer_id": info["c"], "agent_id": info["agent"], "campaign_id": info["camp"],
                             "product_id": info["prod"], "opportunity_stage": "won" if to_proposal else "lost",
                             "opened_date": opened, "close_date": opened + timedelta(days=int(rng.integers(5, 60))),
                             "estimated_premium": round(float(rng.uniform(*prem_band[product_meta[info['prod']]['line']])), 2),
                             "lost_reason": None if to_proposal else DROP["opp"], "created_at": NOW_TS, "updated_at": NOW_TS})
            opp_to_chain[opp] = {**info, "opened": opened, "advance": to_proposal}
            oi += 1
        # direct opportunities to top up toward N_OPPS
        while oi < min(N_OPPS, len(conv_leads) + 1500):
            c = cid(int(rng.integers(0, N_CUSTOMERS)))
            prod = rng.choice(base_products)
            opened = rand_day_in_month(month_start(int(rng.choice(MONTHS, p=mw))))
            opp = f"{tag}opp_{oi:05d}"
            advance = rng.random() < 0.55
            opp_rows.append({"opportunity_id": opp, "opportunity_number": f"O{oi:06d}", "lead_id": None,
                             "customer_id": c, "agent_id": aid(int(rng.integers(0, N_AGENTS))), "campaign_id": None,
                             "product_id": prod, "opportunity_stage": "won" if advance else "lost",
                             "opened_date": opened, "close_date": opened + timedelta(days=int(rng.integers(5, 60))),
                             "estimated_premium": round(float(rng.uniform(*prem_band[product_meta[prod]['line']])), 2),
                             "lost_reason": None if advance else DROP["opp"], "created_at": NOW_TS, "updated_at": NOW_TS})
            opp_to_chain[opp] = {"c": c, "prod": prod, "agent": opp_rows[-1]["agent_id"], "camp": None,
                                 "opened": opened, "advance": advance}
            oi += 1

        # quotes (subset of opportunities) — record opp -> quote linkage + premium
        qi = 0
        opp_list = list(opp_to_chain.keys())
        opp_quote = {}
        for opp in opp_list:
            if qi >= N_QUOTES:
                break
            ch = opp_to_chain[opp]
            qd = ch["opened"] + timedelta(days=int(rng.integers(1, 15)))
            prem = round(float(rng.uniform(*prem_band[product_meta[ch['prod']]['line']])), 2)
            quote = f"{tag}quote_{qi:05d}"
            quote_rows.append({"quote_id": quote, "quote_number": f"Q{qi:06d}", "lead_id": None, "opportunity_id": opp,
                               "customer_id": ch["c"], "agent_id": ch["agent"], "product_id": ch["prod"], "campaign_id": ch["camp"],
                               "quote_date": qd, "quote_status": "accepted" if ch["advance"] else "expired",
                               "quoted_premium": prem, "sum_assured": round(prem * rng.uniform(8, 25), 2),
                               "quote_channel": rng.choice(CHANNELS), "decline_reason": None if ch["advance"] else DROP["quote"],
                               "created_at": NOW_TS, "updated_at": NOW_TS})
            opp_quote[opp] = quote
            opp_to_chain[opp]["prem"] = prem
            opp_to_chain[opp]["quote_date"] = qd
            qi += 1

        # proposals -> applications (opportunity-driven funnel)
        #   opp -> proposal (~68%) -> application (~74%) -> issued (~85%)
        # Tuned to land applications near the target volume while keeping the
        # stage shape realistic; proposals/apps link back to opp + quote.
        pi2, ai, recent_ptr = 0, 0, 0
        P_PROPOSAL, P_APPLICATION, P_ISSUED = 0.68, 0.74, 0.85
        for opp in opp_list:
            ch = opp_to_chain[opp]
            if rng.random() >= P_PROPOSAL:
                continue
            qd = ch.get("quote_date", ch["opened"])
            prem = ch.get("prem", round(float(rng.uniform(*prem_band[product_meta[ch['prod']]['line']])), 2))
            pd_ = qd + timedelta(days=int(rng.integers(1, 12)))
            to_app = rng.random() < P_APPLICATION
            prop = f"{tag}prop_{pi2:05d}"
            prop_rows.append({"proposal_id": prop, "proposal_number": f"P{pi2:06d}", "quote_id": opp_quote.get(opp),
                              "opportunity_id": opp, "customer_id": ch["c"], "agent_id": ch["agent"], "product_id": ch["prod"],
                              "proposal_date": pd_, "proposal_status": "accepted" if to_app else "lapsed",
                              "proposed_premium": prem, "proposed_sum_assured": round(prem * rng.uniform(8, 25), 2),
                              "created_at": NOW_TS, "updated_at": NOW_TS})
            pi2 += 1
            if to_app and ai < N_APPLICATIONS:
                ad = pd_ + timedelta(days=int(rng.integers(1, 15)))
                issued = rng.random() < P_ISSUED
                app = f"{tag}app_{ai:05d}"
                app_rows.append({"application_id": app, "application_number": f"AP{ai:06d}", "proposal_id": prop,
                                 "quote_id": opp_quote.get(opp), "opportunity_id": opp, "customer_id": ch["c"], "agent_id": ch["agent"],
                                 "product_id": ch["prod"], "application_date": ad, "application_status": "issued" if issued else "declined",
                                 "requested_premium": prem, "requested_sum_assured": round(prem * rng.uniform(8, 25), 2),
                                 "medical_required": bool(rng.random() < 0.4), "created_at": NOW_TS, "updated_at": NOW_TS})
                ai += 1
        insert_df(con, "leads", pd.DataFrame(lead_rows))
        insert_df(con, "opportunities", pd.DataFrame(opp_rows))
        insert_df(con, "quotes", pd.DataFrame(quote_rows))
        insert_df(con, "proposals", pd.DataFrame(prop_rows))
        insert_df(con, "applications", pd.DataFrame(app_rows))

        # ---------------- CAMPAIGN TARGETS + RESPONSES (attribution) ----------------
        print("[gen] campaign targets + responses")
        ct_rows, cr_rows = [], []
        lead_by_campaign = {}
        for lr in lead_rows:
            if lr["campaign_id"]:
                lead_by_campaign.setdefault(lr["campaign_id"], []).append(lr)
        ti = 0
        ri = 0
        for camp in camp_ids:
            leads_c = lead_by_campaign.get(camp, [])
            n_targets = max(len(leads_c) + int(rng.integers(20, 120)), 30)
            for _ in range(n_targets):
                c = cid(int(rng.integers(0, N_CUSTOMERS)))
                ct = f"{tag}ct_{ti:06d}"
                lead_link = leads_c.pop() if leads_c and rng.random() < 0.7 else None
                ct_rows.append({"campaign_target_id": ct, "campaign_id": camp, "customer_id": c,
                                "lead_id": lead_link["lead_id"] if lead_link else None,
                                "agent_id": aid(int(rng.integers(0, N_AGENTS))),
                                "target_status": "selected", "selected_at": ts(camp_start[camp]),
                                "created_at": NOW_TS, "updated_at": NOW_TS})
                # response?
                if rng.random() < 0.35:
                    converted = lead_link is not None and lead_link["lead_status"] == "converted" and rng.random() < 0.5
                    conv_prem = round(float(rng.uniform(*prem_band[camp_line[camp] if camp_line[camp] in prem_band else "Health"])), 2) if converted else 0.0
                    cr_rows.append({"campaign_response_id": f"{tag}cr_{ri:06d}", "campaign_id": camp, "campaign_target_id": ct,
                                    "customer_id": c, "lead_id": lead_link["lead_id"] if lead_link else None,
                                    "response_ts": ts(camp_start[camp] + timedelta(days=int(rng.integers(1, 40)))),
                                    "response_type": rng.choice(["click", "call", "reply", "visit"]),
                                    "conversion_flag": converted, "conversion_premium": conv_prem,
                                    "created_at": NOW_TS, "updated_at": NOW_TS})
                    ri += 1
                ti += 1
        insert_df(con, "campaign_targets", pd.DataFrame(ct_rows))
        insert_df(con, "campaign_responses", pd.DataFrame(cr_rows))

        # ---------------- CLAIMS ----------------
        print("[gen] claims")
        claim_freq = {"Health": 0.62, "Protection": 0.30, "Savings": 0.12, "Investment": 0.12}
        claimable = [p for p in all_policies if rng.random() < claim_freq.get(product_meta[policy_product[p]]["line"], 0.1)]
        rng.shuffle(claimable)
        claimable = claimable[:N_CLAIMS]
        claim_rows, fraud_rows, assess_rows = [], [], []
        for i, p in enumerate(claimable):
            eff = policy_eff[p]
            loss = eff + timedelta(days=int(rng.integers(30, max(31, (TODAY - eff).days))))
            if loss > TODAY:
                loss = TODAY - timedelta(days=int(rng.integers(1, 200)))
            report = loss + timedelta(days=int(rng.integers(0, 20)))
            paid = round(float(np.clip(rng.lognormal(8.2, 1.0), 200, 200000)), 2)
            status = rng.choice(["open", "approved", "paid", "denied"], p=[0.2, 0.2, 0.5, 0.1])
            cl = f"{tag}clm_{i:05d}"
            claim_rows.append({"claim_id": cl, "claim_number": f"CLM{i:06d}", "policy_id": p, "customer_id": policy_customer[p],
                               "assigned_agent_id": policy_agent[p], "loss_date": loss, "report_date": report,
                               "close_date": report + timedelta(days=int(rng.integers(5, 90))) if status in ("paid", "denied") else None,
                               "claim_status": status, "loss_cause": rng.choice(["illness", "accident", "hospitalization", "surgery", "death", "critical_illness"]),
                               "paid_amount": paid if status in ("approved", "paid") else 0.0,
                               "reserve_amount": round(paid * rng.uniform(0.8, 1.2), 2), "litigation_flag": bool(rng.random() < 0.03),
                               "catastrophe_flag": bool(rng.random() < 0.01), "created_at": NOW_TS, "updated_at": NOW_TS})
            if rng.random() < 0.08:
                fraud_rows.append({"claim_fraud_indicator_id": f"{tag}fraud_{len(fraud_rows):05d}", "claim_id": cl, "customer_id": policy_customer[p],
                                   "indicator_date": report, "indicator_type": rng.choice(["duplicate_claim", "inflated_amount", "early_claim", "provider_flag"]),
                                   "indicator_source": "model", "indicator_score": round(float(rng.uniform(0.5, 0.98)), 3),
                                   "severity": rng.choice(["medium", "high", "critical"], p=[0.5, 0.35, 0.15]),
                                   "resolved_flag": bool(rng.random() < 0.4), "created_at": NOW_TS, "updated_at": NOW_TS})
            if status in ("approved", "paid", "denied"):
                assess_rows.append({"claim_assessment_id": f"{tag}asmt_{len(assess_rows):05d}", "claim_id": cl,
                                    "assessed_by_agent_id": policy_agent[p], "assessment_date": report + timedelta(days=int(rng.integers(2, 30))),
                                    "assessment_type": "desk_review", "severity_score": round(float(rng.uniform(0.1, 0.95)), 3),
                                    "liability_pct": round(float(rng.uniform(0, 100)), 1), "estimated_loss_amount": paid,
                                    "recommended_reserve_amount": round(paid * rng.uniform(0.8, 1.1), 2),
                                    "assessment_outcome": "approve" if status in ("approved", "paid") else "deny",
                                    "created_at": NOW_TS, "updated_at": NOW_TS})
        insert_df(con, "claims", pd.DataFrame(claim_rows))
        insert_df(con, "claim_fraud_indicators", pd.DataFrame(fraud_rows))
        insert_df(con, "claim_assessments", pd.DataFrame(assess_rows))

        # ---------------- MODEL LAYER ----------------
        print("[gen] model layer (scores/predictions/NBA)")
        mv_rows = []
        for name, algo in [("policy_lapse", "xgboost"), ("propensity_to_buy", "lightgbm"), ("customer_clv", "gbm"), ("churn_risk", "xgboost")]:
            mv_rows.append({"model_version_id": f"{tag}mv_{name}", "model_name": name, "model_version": "2.1.0", "algorithm": algo,
                            "training_date": CUR_MONTH - timedelta(days=30), "auc": round(float(rng.uniform(0.74, 0.9)), 3),
                            "precision_score": round(float(rng.uniform(0.6, 0.85)), 3), "recall_score": round(float(rng.uniform(0.55, 0.8)), 3),
                            "status": "production", "created_at": NOW_TS})
        insert_df(con, "model_versions", pd.DataFrame(mv_rows))

        def band(v):
            return "VERY_HIGH" if v >= 0.8 else "HIGH" if v >= 0.6 else "MEDIUM" if v >= 0.4 else "LOW"

        score_rows, pred_rows, nba_rows = [], [], []
        # last policy date per customer for repurchase-window propensity
        cust_last_eff = {}
        for p in all_policies:
            c = policy_customer[p]
            if c not in cust_last_eff or policy_eff[p] > cust_last_eff[c]:
                cust_last_eff[c] = policy_eff[p]

        # lapse scores on policies (consistent: lapsed/at-risk products higher)
        for p in all_policies:
            line = product_meta[policy_product[p]]["line"]
            base_l = 0.62 if policy_status[p] == "lapsed" else (0.42 if line in lapse_prone_lines else 0.22)
            v = float(np.clip(rng.normal(base_l, 0.16), 0.01, 0.99))
            score_rows.append({"model_score_id": f"{tag}ms_l_{len(score_rows):06d}", "model_name": "policy_lapse", "model_version": "2.1.0",
                               "entity_type": "policy", "entity_id": p, "score_ts": NOW_TS, "score_name": "lapse_risk",
                               "score_value": round(v, 4), "probability": round(v, 4), "score_band": band(v),
                               "explanation": "elevated lapse risk" if v >= 0.6 else "stable", "created_at": NOW_TS, "updated_at": NOW_TS})

        # propensity + clv + churn on customers (repurchase window -> high propensity)
        for i in range(N_CUSTOMERS):
            c = cid(i)
            affluent = cust_affluent[c]
            last = cust_last_eff.get(c)
            months_since = ((TODAY.year - last.year) * 12 + TODAY.month - last.month) if last else 99
            in_window = 5 <= months_since <= 9       # near typical repurchase window
            prop = float(np.clip(rng.normal(0.72 if in_window else (0.55 if affluent else 0.4), 0.15), 0.01, 0.99))
            churn = float(np.clip(rng.normal(0.55 if cust_segment[c] in ("Mass", "Young Family") else 0.35, 0.17), 0.01, 0.99))
            clvv = float(np.clip(rng.normal(0.78 if affluent else 0.45, 0.18), 0.01, 0.99))
            rec_prod = rng.choice(base_products)
            for nm, sc, val in [("propensity_to_buy", "propensity_to_buy", prop), ("customer_clv", "clv", clvv), ("churn_risk", "churn", churn)]:
                score_rows.append({"model_score_id": f"{tag}ms_c_{len(score_rows):06d}", "model_name": nm, "model_version": "2.1.0",
                                   "entity_type": "customer", "entity_id": c, "score_ts": NOW_TS, "score_name": sc,
                                   "score_value": round(val, 4), "probability": round(val, 4), "score_band": band(val),
                                   "explanation": "repurchase window" if (sc == "propensity_to_buy" and in_window) else nm,
                                   "created_at": NOW_TS, "updated_at": NOW_TS})
            # prediction + NBA for high-propensity (repurchase) or high-churn customers
            if prop >= 0.65 or churn >= 0.7:
                mp = f"{tag}mp_{i:06d}"
                pred_rows.append({"model_prediction_id": mp, "model_name": "propensity_to_buy" if prop >= 0.65 else "churn_risk",
                                  "model_version": "2.1.0", "prediction_type": "classification", "entity_type": "customer", "entity_id": c,
                                  "prediction_ts": NOW_TS, "prediction_horizon_days": 90,
                                  "predicted_label": "buy" if prop >= 0.65 else "churn", "probability": round(max(prop, churn), 4),
                                  "confidence_score": round(float(rng.uniform(0.6, 0.92)), 3), "recommended_product_id": rec_prod,
                                  "created_at": NOW_TS, "updated_at": NOW_TS})
                nba_rows.append({"next_best_action_id": f"{tag}nba_{i:06d}", "model_prediction_id": mp, "customer_id": c,
                                 "agent_id": aid(int(rng.integers(0, N_AGENTS))), "product_id": rec_prod,
                                 "action_type": "cross_sell" if prop >= 0.65 else "retention_outreach",
                                 "action_rank": 1, "priority_score": round(max(prop, churn), 4),
                                 "expected_value": round(float(rng.uniform(800, 9000)), 2), "due_date": TODAY + timedelta(days=int(rng.integers(3, 30))),
                                 "action_status": "open", "action_reason": "in repurchase window" if prop >= 0.65 else "elevated churn risk",
                                 "created_at": NOW_TS, "updated_at": NOW_TS})
        insert_df(con, "model_scores", pd.DataFrame(score_rows))
        insert_df(con, "model_predictions", pd.DataFrame(pred_rows))
        insert_df(con, "next_best_actions", pd.DataFrame(nba_rows))

        # ---------------- AGENT PERFORMANCE + TARGETS (monthly) ----------------
        print("[gen] agent performance + targets")
        # aggregate policies per agent-month for realistic rollups
        perf_rows, tgt_rows = [], []
        pol_df = pd.DataFrame([{"agent_id": policy_agent[p], "eff": policy_eff[p], "prem": policy_prem[p],
                                "lapsed": policy_status[p] == "lapsed"} for p in all_policies])
        pol_df["ym"] = pol_df["eff"].apply(lambda d: (d.year, d.month))
        grp = pol_df.groupby(["agent_id", "ym"]).agg(bound=("prem", "size"), nbp=("prem", "sum"), lapsed=("lapsed", "sum")).reset_index()
        gi = 0
        for _, r in grp.iterrows():
            y, m = r["ym"]
            quotes_c = int(r["bound"] * rng.uniform(1.5, 3))
            conv = round(r["bound"] / quotes_c, 3) if quotes_c else 0.0
            perf_rows.append({"agent_performance_id": f"{tag}perf_{gi:06d}", "agent_id": r["agent_id"], "metric_month": date(y, m, 1),
                              "leads_count": int(quotes_c * rng.uniform(1.2, 2)), "contacts_count": int(quotes_c * rng.uniform(1, 1.5)),
                              "quotes_count": quotes_c, "applications_count": int(r["bound"] * rng.uniform(1, 1.4)),
                              "policies_bound_count": int(r["bound"]), "new_business_premium": round(float(r["nbp"]), 2),
                              "renewal_premium": round(float(r["nbp"]) * rng.uniform(0.1, 0.5), 2),
                              "retained_policy_count": int(r["bound"] * rng.uniform(0.7, 1)), "lapsed_policy_count": int(r["lapsed"]),
                              "claims_count": int(rng.integers(0, 5)), "loss_ratio": round(float(rng.uniform(0.2, 0.9)), 3),
                              "conversion_rate": conv, "performance_band": "Top" if conv > 0.45 else "Stable" if conv > 0.3 else "Coaching",
                              "created_at": NOW_TS, "updated_at": NOW_TS})
            gi += 1
        # targets per agent for the latest 4 quarters
        for i in range(N_AGENTS):
            for qoff in range(4):
                start = month_start(MONTHS - 1 - qoff * 3 - 2)
                tgt = round(float(rng.uniform(80000, 500000)), 2)
                actual = round(tgt * float(np.clip(rng.normal(0.85, 0.3), 0.2, 1.6)), 2)
                tgt_rows.append({"agent_target_id": f"{tag}tgt_{i:04d}_{qoff}", "agent_id": aid(i), "target_period_start": start,
                                 "target_period_end": month_start(MONTHS - 1 - qoff * 3), "target_type": "new_business_premium",
                                 "target_value": tgt, "actual_value": actual, "attainment_pct": round(actual / tgt * 100, 1),
                                 "created_at": NOW_TS, "updated_at": NOW_TS})
        insert_df(con, "agent_performance", pd.DataFrame(perf_rows))
        insert_df(con, "agent_targets", pd.DataFrame(tgt_rows))

        con.commit()

        # ---------------- INTEGRITY + PROFILE ----------------
        print("\n" + "=" * 64)
        print("INTEGRITY CHECKS (orphan FK rows; must be 0)")
        checks = [
            ("policies.customer_id", "select count(*) from policies p left join customers c on c.customer_id=p.customer_id where p.customer_id is not null and c.customer_id is null"),
            ("policies.agent_id", "select count(*) from policies p left join agents a on a.agent_id=p.agent_id where p.agent_id is not null and a.agent_id is null"),
            ("policies.product_id", "select count(*) from policies p left join products pr on pr.product_id=p.product_id where p.product_id is not null and pr.product_id is null"),
            ("payments.policy_id", "select count(*) from payments x left join policies p on p.policy_id=x.policy_id where x.policy_id is not null and p.policy_id is null"),
            ("claims.policy_id", "select count(*) from claims x left join policies p on p.policy_id=x.policy_id where x.policy_id is not null and p.policy_id is null"),
            ("opportunities.lead_id", "select count(*) from opportunities o left join leads l on l.lead_id=o.lead_id where o.lead_id is not null and l.lead_id is null"),
            ("campaign_responses.campaign_id", "select count(*) from campaign_responses r left join campaigns c on c.campaign_id=r.campaign_id where r.campaign_id is not null and c.campaign_id is null"),
            ("model_scores.entity(policy)", "select count(*) from model_scores s left join policies p on p.policy_id=s.entity_id where s.entity_type='policy' and p.policy_id is null"),
            ("next_best_actions.customer_id", "select count(*) from next_best_actions n left join customers c on c.customer_id=n.customer_id where n.customer_id is not null and c.customer_id is null"),
        ]
        total_orphans = 0
        for label, q in checks:
            n = con.execute(q).fetchone()[0]
            total_orphans += n
            print(f"  {'OK ' if n == 0 else 'BAD'} {label}: {n}")

        print("\nDATA PROFILE (rows per table)")
        for t in ["parties", "customers", "agents", "products", "policies", "payments", "policy_lapse_events",
                  "leads", "opportunities", "quotes", "proposals", "applications", "campaigns", "campaign_targets",
                  "campaign_responses", "claims", "model_scores", "model_predictions", "next_best_actions",
                  "agent_performance", "agent_targets", "households"]:
            print(f"  {t:<26} {con.execute(f'select count(*) from {t}').fetchone()[0]:>8}")

        # funnel / repurchase / lapse
        n_leads = con.execute("select count(*) from leads").fetchone()[0]
        lead_conv = con.execute("""
            select count(distinct a.application_id)
            from applications a join proposals pr on pr.proposal_id=a.proposal_id
            join quotes q on q.quote_id=pr.quote_id join opportunities o on o.opportunity_id=q.opportunity_id
            where o.lead_id is not null and a.application_status='issued'
        """).fetchone()[0]
        opp_from_leads = con.execute("select count(*) from opportunities where lead_id is not null").fetchone()[0]
        n_months = con.execute("select count(distinct date_trunc('month', effective_date)) from policies").fetchone()[0]
        date_range = con.execute("select min(effective_date), max(effective_date) from policies").fetchone()
        total_pol = con.execute("select count(*) from policies").fetchone()[0]
        lapsed = con.execute("select count(*) from policies where policy_status='lapsed'").fetchone()[0]
        # repurchase: customers with a policy whose prior_policy_id gap is 180-730 days
        repurch = con.execute("""
            select count(distinct p.customer_id)
            from policies p join policies pp on pp.policy_id=p.prior_policy_id
            where date_diff('day', pp.effective_date, p.effective_date) between 180 and 730
        """).fetchone()[0]
        n_cust = con.execute("select count(*) from customers").fetchone()[0]

        print("\nFUNNEL / REPURCHASE / LAPSE (achieved)")
        print(f"  leads -> opportunities      : {opp_from_leads}/{n_leads} = {opp_from_leads/max(n_leads,1)*100:.1f}%")
        print(f"  lead -> issued policy       : {lead_conv}/{n_leads} = {lead_conv/max(n_leads,1)*100:.1f}%")
        print(f"  repurchase (2nd in 6-24mo)  : {repurch}/{n_cust} = {repurch/max(n_cust,1)*100:.1f}%")
        print(f"  lapse (lapsed/total policies): {lapsed}/{total_pol} = {lapsed/max(total_pol,1)*100:.1f}%")
        print(f"  policy months covered       : {n_months} (range {date_range[0]} .. {date_range[1]})")
        print("=" * 64)
        print(f"\nPrompt 14 complete. Dataset profile: {n_cust} customers, {total_pol} policies, "
              f"{n_leads} leads, {con.execute('select count(*) from claims').fetchone()[0]} claims | "
              f"lead->policy {lead_conv/max(n_leads,1)*100:.1f}%, repurchase {repurch/max(n_cust,1)*100:.1f}%, "
              f"lapse {lapsed/max(total_pol,1)*100:.1f}% | {n_months} months. Orphans={total_orphans}.")
        return 0 if total_orphans == 0 else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
