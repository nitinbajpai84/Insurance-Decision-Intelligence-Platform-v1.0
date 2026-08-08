#!/usr/bin/env python3
"""Validate generated synthetic insurance ML data relationships."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def rate(rows: list[dict[str, str]], column: str) -> float:
    values = [int(r[column]) for r in rows if r.get(column) in {"0", "1"}]
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)

    customers = read_csv(data_dir / "customers.csv")
    labels = read_csv(data_dir / "ml_training_labels.csv")
    behavior = read_csv(data_dir / "customer_behavior_daily.csv")
    complaints = read_csv(data_dir / "customer_complaints.csv")
    policies = read_csv(data_dir / "policies.csv")
    products = read_csv(data_dir / "products.csv")
    policy_coverages = read_csv(data_dir / "policy_coverages.csv")
    premiums = read_csv(data_dir / "premiums.csv")

    customer_engagement = {r["customer_id"]: float(r["engagement_score"]) for r in customers}
    missed_by_customer = defaultdict(int)
    for row in behavior:
        if row["payment_missed_count_90d"]:
            missed_by_customer[row["customer_id"]] = max(missed_by_customer[row["customer_id"]], int(row["payment_missed_count_90d"]))
    complaints_by_customer = defaultdict(int)
    for row in complaints:
        complaints_by_customer[row["customer_id"]] += 1

    customer_labels = [r for r in labels if r["entity_type"] == "customer"]
    policy_labels = [r for r in labels if r["entity_type"] == "policy"]
    high_engagement = [r for r in customer_labels if customer_engagement.get(r["customer_id"], 0) >= 70]
    low_engagement = [r for r in customer_labels if customer_engagement.get(r["customer_id"], 0) < 45]
    complaint_customers = [r for r in customer_labels if complaints_by_customer[r["customer_id"]] > 0]
    no_complaint_customers = [r for r in customer_labels if complaints_by_customer[r["customer_id"]] == 0]
    missed_customers = {cid for cid, count in missed_by_customer.items() if count > 0}
    lapse_with_missed = [r for r in policy_labels if r["customer_id"] in missed_customers]
    lapse_without_missed = [r for r in policy_labels if r["customer_id"] not in missed_customers]

    product_ids = {r["product_id"] for r in products}
    policy_ids = {r["policy_id"] for r in policies}
    coverage_ids = {r["policy_coverage_id"] for r in policy_coverages}
    fk_issues = {
        "policy_product_missing": sum(1 for r in policies if r["product_id"] not in product_ids),
        "coverage_policy_missing": sum(1 for r in policy_coverages if r["policy_id"] not in policy_ids),
        "coverage_product_missing": sum(1 for r in policy_coverages if r["product_id"] and r["product_id"] not in product_ids),
        "premium_coverage_missing": sum(1 for r in premiums if r["policy_coverage_id"] and r["policy_coverage_id"] not in coverage_ids),
    }

    checks = {
        "counts": {
            "customers": len(customers),
            "policies": len(policies),
            "products": len(products),
            "policy_coverages": len(policy_coverages),
            "premiums": len(premiums),
            "ml_training_labels": len(labels),
        },
        "foreign_key_checks": fk_issues,
        "statistical_relationship_checks": {
            "high_engagement_propensity_rate": round(rate(high_engagement, "propensity_to_buy_label"), 4),
            "low_engagement_propensity_rate": round(rate(low_engagement, "propensity_to_buy_label"), 4),
            "complaint_customer_churn_rate": round(rate(complaint_customers, "churn_label"), 4),
            "no_complaint_customer_churn_rate": round(rate(no_complaint_customers, "churn_label"), 4),
            "missed_payment_policy_lapse_rate": round(rate(lapse_with_missed, "lapse_label"), 4),
            "no_missed_payment_policy_lapse_rate": round(rate(lapse_without_missed, "lapse_label"), 4),
        },
        "expectations": {
            "high_engagement_propensity_rate_should_exceed_low": rate(high_engagement, "propensity_to_buy_label") > rate(low_engagement, "propensity_to_buy_label"),
            "complaint_churn_rate_should_exceed_no_complaint": rate(complaint_customers, "churn_label") > rate(no_complaint_customers, "churn_label"),
            "missed_payment_lapse_rate_should_exceed_no_missed": rate(lapse_with_missed, "lapse_label") > rate(lapse_without_missed, "lapse_label"),
            "foreign_key_issues_should_be_zero": all(v == 0 for v in fk_issues.values()),
        },
    }
    output_path = data_dir / "validation_results.json"
    output_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
