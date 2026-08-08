"""Batch scoring pipeline for insurance ML models.

This script loads the latest active model artifact, reads the latest feature
snapshot from Supabase Postgres, scores eligible entities, writes results to
model_scores, and creates operational next_best_actions.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import traceback
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row

try:
    import joblib
except ImportError:  # pragma: no cover - optional dependency
    joblib = None


META_COLUMNS = {
    "entity_id",
    "snapshot_date",
    "target_label",
    "training_window_start",
    "training_window_end",
    "prediction_window_start",
    "prediction_window_end",
    "customer_id",
    "policy_id",
    "agent_id",
    "lead_id",
    "campaign_id",
    "claim_id",
    "candidate_product_id",
    "candidate_line_of_business",
    "customer_segment",
    "channel",
    "campaign_type",
    "territory_code",
}


DEFAULT_MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    "propensity_to_buy": {
        "feature_table": "propensity_to_buy_features",
        "entity_type": "customer",
        "score_name": "propensity_to_buy",
        "model_type": "classification",
        "action_type": "offer_product",
        "action_high": "Offer relevant protection or savings product",
        "action_medium": "Add to nurture campaign",
        "action_low": "Monitor customer engagement",
    },
    "next_best_product": {
        "feature_table": "next_best_product_features",
        "entity_type": "customer",
        "score_name": "next_best_product",
        "model_type": "ranking",
        "action_type": "offer_product",
        "action_high": "Recommend next best product",
        "action_medium": "Send product education campaign",
        "action_low": "No immediate product offer",
    },
    "customer_churn": {
        "feature_table": "customer_churn_features",
        "entity_type": "customer",
        "score_name": "customer_churn_risk",
        "model_type": "classification",
        "action_type": "retention_outreach",
        "action_high": "Call customer for retention review",
        "action_medium": "Send service recovery message",
        "action_low": "Monitor for churn signals",
    },
    "policy_lapse": {
        "feature_table": "policy_lapse_features",
        "entity_type": "policy",
        "score_name": "policy_lapse_risk",
        "model_type": "classification",
        "action_type": "renewal_follow_up",
        "action_high": "Prioritize renewal follow-up",
        "action_medium": "Send payment reminder",
        "action_low": "Standard renewal journey",
    },
    "agent_performance": {
        "feature_table": "agent_performance_features",
        "entity_type": "agent",
        "score_name": "agent_performance",
        "model_type": "classification",
        "action_type": "agent_coaching",
        "action_high": "Assign stretch sales target",
        "action_medium": "Coach on conversion improvement",
        "action_low": "Schedule performance coaching",
    },
    "next_best_customer": {
        "feature_table": "next_best_customer_features",
        "entity_type": "agent",
        "score_name": "next_best_customer",
        "model_type": "ranking",
        "action_type": "call_customer",
        "action_high": "Call prioritized customer",
        "action_medium": "Schedule customer follow-up",
        "action_low": "Keep in nurture list",
    },
    "lead_conversion": {
        "feature_table": "lead_conversion_features",
        "entity_type": "lead",
        "score_name": "lead_conversion",
        "model_type": "classification",
        "action_type": "assign_lead",
        "action_high": "Assign lead for immediate follow-up",
        "action_medium": "Nurture lead with quote reminder",
        "action_low": "Suppress from urgent queue",
    },
    "agent_attrition": {
        "feature_table": "agent_attrition_features",
        "entity_type": "agent",
        "score_name": "agent_attrition_risk",
        "model_type": "classification",
        "action_type": "agent_coaching",
        "action_high": "Manager retention intervention",
        "action_medium": "Review agent engagement and commissions",
        "action_low": "Monitor agent stability",
    },
    "claim_prediction": {
        "feature_table": "claim_prediction_features",
        "entity_type": "customer",
        "score_name": "claim_occurrence_risk",
        "model_type": "classification",
        "action_type": "service_recovery",
        "action_high": "Offer risk prevention outreach",
        "action_medium": "Send preventive care content",
        "action_low": "No claim prevention action",
    },
    "fraud_detection": {
        "feature_table": "fraud_detection_features",
        "entity_type": "claim",
        "score_name": "fraud_risk",
        "model_type": "classification",
        "action_type": "fraud_review",
        "action_high": "Route claim to fraud review",
        "action_medium": "Add claim to adjuster watchlist",
        "action_low": "Standard claim handling",
    },
    "customer_lifetime_value": {
        "feature_table": "customer_lifetime_value_features",
        "entity_type": "customer",
        "score_name": "customer_lifetime_value",
        "model_type": "regression",
        "action_type": "call_customer",
        "action_high": "Prioritize customer for relationship review",
        "action_medium": "Offer loyalty engagement",
        "action_low": "Standard customer journey",
    },
    "campaign_response": {
        "feature_table": "campaign_response_features",
        "entity_type": "campaign",
        "score_name": "campaign_response",
        "model_type": "classification",
        "action_type": "send_campaign",
        "action_high": "Prioritize campaign send",
        "action_medium": "Send lower-cost channel campaign",
        "action_low": "Suppress from this campaign",
    },
}


@dataclass
class ModelArtifact:
    model_name: str
    model_version: str
    artifact_uri: str
    artifact_format: str
    feature_table: str
    entity_type: str
    score_name: str
    model_type: str
    feature_columns: list[str]
    metadata: dict[str, Any]


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    return str(value)


def connect(db_url: str, statement_timeout_ms: int) -> psycopg.Connection:
    conn = psycopg.connect(db_url, row_factory=dict_row, connect_timeout=30)
    with conn.cursor() as cur:
        cur.execute("set statement_timeout = %s", (statement_timeout_ms,))
    return conn


def create_job(conn: psycopg.Connection, args: argparse.Namespace) -> str:
    payload = {
        "requested_model": args.model_name,
        "snapshot_date": args.snapshot_date,
        "batch_size": args.batch_size,
        "refresh_snapshot": args.refresh_snapshot,
        "explain": args.explain,
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.model_scoring_jobs (
              job_name, job_status, scoring_mode, model_name, model_version, snapshot_date, job_payload
            )
            values (%s, 'started', %s, %s, null, %s, %s::jsonb)
            returning scoring_job_id
            """,
            (
                f"batch_scoring_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                "single_model" if args.model_name != "all" else "batch",
                None if args.model_name == "all" else args.model_name,
                args.snapshot_date,
                json.dumps(payload, default=json_default),
            ),
        )
        job_id = str(cur.fetchone()["scoring_job_id"])
    conn.commit()
    return job_id


def update_job(
    conn: psycopg.Connection,
    job_id: str,
    status: str,
    rows_scored: int = 0,
    rows_failed: int = 0,
    error_message: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update public.model_scoring_jobs
            set job_status = %s,
                rows_scored = %s,
                rows_failed = %s,
                error_message = %s,
                model_name = coalesce(%s, model_name),
                model_version = coalesce(%s, model_version),
                finished_at = case when %s in ('completed','failed','partial') then now() else finished_at end,
                updated_at = now()
            where scoring_job_id = %s
            """,
            (status, rows_scored, rows_failed, error_message, model_name, model_version, status, job_id),
        )
    conn.commit()


def load_artifacts_from_db(conn: psycopg.Connection, model_name: str) -> list[ModelArtifact]:
    where_clause = "where active_flag = true"
    params: list[Any] = []
    if model_name != "all":
        where_clause += " and model_name = %s"
        params.append(model_name)

    query = f"""
    select distinct on (model_name)
      model_name, model_version, artifact_uri, artifact_format, feature_table,
      entity_type, score_name, model_type, feature_columns, training_metrics
    from public.model_artifacts
    {where_clause}
    order by model_name, promoted_at desc nulls last, created_at desc
    """
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    artifacts: list[ModelArtifact] = []
    for row in rows:
        artifacts.append(
            ModelArtifact(
                model_name=row["model_name"],
                model_version=row["model_version"],
                artifact_uri=row["artifact_uri"],
                artifact_format=row["artifact_format"],
                feature_table=row["feature_table"],
                entity_type=row["entity_type"],
                score_name=row["score_name"],
                model_type=row["model_type"],
                feature_columns=list(row["feature_columns"] or []),
                metadata=dict(row["training_metrics"] or {}),
            )
        )
    return artifacts


def load_artifacts_from_files(model_dir: Path, model_name: str) -> list[ModelArtifact]:
    artifacts: list[ModelArtifact] = []
    metadata_files = sorted(model_dir.glob("*/metadata.json"))
    for metadata_file in metadata_files:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        if model_name != "all" and metadata.get("model_name") != model_name:
            continue

        model_config = DEFAULT_MODEL_CONFIGS.get(metadata["model_name"], {})
        artifacts.append(
            ModelArtifact(
                model_name=metadata["model_name"],
                model_version=metadata.get("model_version", "local"),
                artifact_uri=str((metadata_file.parent / metadata.get("artifact_file", "model.joblib")).resolve()),
                artifact_format=metadata.get("artifact_format", "joblib"),
                feature_table=metadata.get("feature_table", model_config.get("feature_table")),
                entity_type=metadata.get("entity_type", model_config.get("entity_type")),
                score_name=metadata.get("score_name", model_config.get("score_name", metadata["model_name"])),
                model_type=metadata.get("model_type", model_config.get("model_type", "classification")),
                feature_columns=metadata.get("feature_columns", []),
                metadata=metadata,
            )
        )

    artifacts.sort(key=lambda artifact: (artifact.model_name, artifact.model_version), reverse=True)
    latest_by_model: dict[str, ModelArtifact] = {}
    for artifact in artifacts:
        latest_by_model.setdefault(artifact.model_name, artifact)
    return list(latest_by_model.values())


def load_artifact(conn: psycopg.Connection, model_dir: Path, model_name: str) -> list[ModelArtifact]:
    artifacts = load_artifacts_from_db(conn, model_name)
    if artifacts:
        return artifacts
    return load_artifacts_from_files(model_dir, model_name)


def load_model(artifact: ModelArtifact) -> Any:
    if artifact.artifact_format == "rule_based":
        return None

    artifact_path = Path(artifact.artifact_uri)
    if not artifact_path.exists():
        raise FileNotFoundError(f"Model artifact not found: {artifact.artifact_uri}")

    if artifact.artifact_format in {"joblib", "sklearn_pipeline"}:
        if joblib is None:
            raise RuntimeError("joblib is required to load this model artifact")
        return joblib.load(artifact_path)

    if artifact.artifact_format == "pickle":
        with artifact_path.open("rb") as file:
            return pickle.load(file)

    raise ValueError(f"Unsupported artifact format: {artifact.artifact_format}")


def latest_snapshot(conn: psycopg.Connection, feature_table: str, requested_snapshot: str | None) -> date:
    if requested_snapshot:
        return date.fromisoformat(requested_snapshot)
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("select max(snapshot_date) as snapshot_date from public.{}").format(
                sql.Identifier(feature_table)
            )
        )
        snapshot = cur.fetchone()["snapshot_date"]
    if not snapshot:
        raise RuntimeError(f"No snapshots found in {feature_table}. Refresh feature tables before scoring.")
    return snapshot


def refresh_feature_snapshot(conn: psycopg.Connection, feature_table: str, snapshot_date: date) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "select * from public.refresh_ml_feature_snapshot(%s, %s)",
            (feature_table, snapshot_date),
        )
    conn.commit()


def read_features(
    conn: psycopg.Connection,
    feature_table: str,
    snapshot_date: date,
    limit: int | None,
) -> pd.DataFrame:
    limit_sql = sql.SQL(" limit {}").format(sql.Literal(limit)) if limit else sql.SQL("")
    query = sql.SQL("select * from public.{} where snapshot_date = {}{}").format(
        sql.Identifier(feature_table),
        sql.Literal(snapshot_date),
        limit_sql,
    )
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return pd.DataFrame(rows)


def infer_feature_columns(df: pd.DataFrame, artifact: ModelArtifact) -> list[str]:
    if artifact.feature_columns:
        missing = [column for column in artifact.feature_columns if column not in df.columns]
        if missing:
            raise RuntimeError(f"Missing model feature columns for {artifact.model_name}: {missing}")
        return artifact.feature_columns

    numeric_columns = [
        column
        for column in df.columns
        if column not in META_COLUMNS and pd.api.types.is_numeric_dtype(df[column])
    ]
    if not numeric_columns:
        raise RuntimeError(f"No numeric feature columns found for {artifact.feature_table}")
    return numeric_columns


def rule_based_scores(df: pd.DataFrame, artifact: ModelArtifact, feature_columns: list[str]) -> np.ndarray:
    weights = artifact.metadata.get("rule_weights", {})
    if weights:
        raw = np.zeros(len(df), dtype=float)
        for feature, weight in weights.items():
            if feature in df.columns:
                values = pd.to_numeric(df[feature], errors="coerce").fillna(0).to_numpy(dtype=float)
                scale = np.nanstd(values) or 1.0
                raw += float(weight) * (values / scale)
        return 1.0 / (1.0 + np.exp(-raw))

    matrix = df[feature_columns].apply(pd.to_numeric, errors="coerce").fillna(0)
    if matrix.empty:
        return np.zeros(len(df), dtype=float)
    normalized = (matrix - matrix.min()) / (matrix.max() - matrix.min()).replace(0, 1)
    return normalized.mean(axis=1).clip(0, 1).to_numpy(dtype=float)


def model_scores(model: Any, df: pd.DataFrame, artifact: ModelArtifact, feature_columns: list[str]) -> np.ndarray:
    if model is None:
        return rule_based_scores(df, artifact, feature_columns)

    x = df[feature_columns].apply(pd.to_numeric, errors="coerce").fillna(0)

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(x)
        if probabilities.ndim == 2 and probabilities.shape[1] > 1:
            return probabilities[:, 1].astype(float)
        return probabilities.reshape(-1).astype(float)

    predictions = model.predict(x)
    return np.asarray(predictions, dtype=float).reshape(-1)


def score_band(score: float, model_type: str, quantiles: dict[str, float] | None = None) -> str:
    if model_type == "regression" and quantiles:
        if score >= quantiles["q90"]:
            return "VERY_HIGH"
        if score >= quantiles["q70"]:
            return "HIGH"
        if score >= quantiles["q40"]:
            return "MEDIUM"
        return "LOW"

    if score >= 0.8:
        return "VERY_HIGH"
    if score >= 0.6:
        return "HIGH"
    if score >= 0.3:
        return "MEDIUM"
    return "LOW"


def extract_feature_importance(model: Any, artifact: ModelArtifact, feature_columns: list[str]) -> dict[str, float]:
    if "feature_importance" in artifact.metadata:
        return {str(k): float(v) for k, v in artifact.metadata["feature_importance"].items()}

    estimator = model
    if hasattr(model, "named_steps"):
        estimator = list(model.named_steps.values())[-1]

    if estimator is not None and hasattr(estimator, "feature_importances_"):
        return dict(zip(feature_columns, np.asarray(estimator.feature_importances_, dtype=float)))
    if estimator is not None and hasattr(estimator, "coef_"):
        coefs = np.asarray(estimator.coef_, dtype=float).reshape(-1)
        return dict(zip(feature_columns, np.abs(coefs)))
    return {feature: 1.0 for feature in feature_columns}


def top_reasons_for_row(
    row: pd.Series,
    feature_columns: list[str],
    feature_importance: dict[str, float],
) -> tuple[str | None, str | None, str | None, list[dict[str, Any]]]:
    contributions: list[dict[str, Any]] = []
    for feature in feature_columns:
        value = row.get(feature)
        numeric_value = float(value) if pd.notna(value) else 0.0
        importance = float(feature_importance.get(feature, 0.0))
        contribution = abs(numeric_value * importance)
        contributions.append(
            {
                "feature": feature,
                "value": numeric_value,
                "importance": importance,
                "contribution": contribution,
            }
        )
    contributions.sort(key=lambda item: item["contribution"], reverse=True)
    top = contributions[:3]
    reasons = [f"{item['feature']}={item['value']:.4g}" for item in top]
    while len(reasons) < 3:
        reasons.append(None)
    return reasons[0], reasons[1], reasons[2], top


def recommended_action(model_name: str, band: str) -> str:
    config = DEFAULT_MODEL_CONFIGS.get(model_name, {})
    if band in {"HIGH", "VERY_HIGH"}:
        return config.get("action_high", "Prioritize for action")
    if band == "MEDIUM":
        return config.get("action_medium", "Monitor and nurture")
    return config.get("action_low", "Monitor")


def action_type(model_name: str) -> str:
    return DEFAULT_MODEL_CONFIGS.get(model_name, {}).get("action_type", "call_customer")


def row_entity_references(row: pd.Series, entity_type: str) -> dict[str, Any]:
    refs = {
        "customer_id": row.get("customer_id") if "customer_id" in row else None,
        "agent_id": row.get("agent_id") if "agent_id" in row else None,
        "policy_id": row.get("policy_id") if "policy_id" in row else None,
        "lead_id": row.get("lead_id") if "lead_id" in row else None,
        "campaign_id": row.get("campaign_id") if "campaign_id" in row else None,
        "claim_id": row.get("claim_id") if "claim_id" in row else None,
        "product_id": row.get("candidate_product_id") if "candidate_product_id" in row else row.get("product_id"),
    }
    if entity_type == "customer":
        refs["customer_id"] = refs["customer_id"] or row["entity_id"]
    elif entity_type == "agent":
        refs["agent_id"] = refs["agent_id"] or row["entity_id"]
    elif entity_type == "policy":
        refs["policy_id"] = refs["policy_id"] or row["entity_id"]
    elif entity_type == "lead":
        refs["lead_id"] = refs["lead_id"] or row["entity_id"]
    elif entity_type == "campaign":
        refs["campaign_id"] = refs["campaign_id"] or row["entity_id"]
    elif entity_type == "claim":
        refs["claim_id"] = refs["claim_id"] or row["entity_id"]
    return refs


def clean_uuid(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def insert_scores_and_actions(
    conn: psycopg.Connection,
    job_id: str,
    artifact: ModelArtifact,
    df: pd.DataFrame,
    scores: np.ndarray,
    feature_columns: list[str],
    feature_importance: dict[str, float],
    batch_size: int,
) -> int:
    quantiles = None
    if artifact.model_type == "regression" and len(scores) > 0:
        quantiles = {
            "q40": float(np.quantile(scores, 0.40)),
            "q70": float(np.quantile(scores, 0.70)),
            "q90": float(np.quantile(scores, 0.90)),
        }

    rows_written = 0
    with conn.cursor() as cur:
        for start in range(0, len(df), batch_size):
            batch = df.iloc[start : start + batch_size]
            score_batch = scores[start : start + len(batch)]
            for (_, row), score in zip(batch.iterrows(), score_batch):
                score_float = float(score)
                band = score_band(score_float, artifact.model_type, quantiles)
                action = recommended_action(artifact.model_name, band)
                reason_1, reason_2, reason_3, top_contributions = top_reasons_for_row(
                    row, feature_columns, feature_importance
                )
                explanation = {
                    "snapshot_date": row["snapshot_date"],
                    "top_contributions": top_contributions,
                    "model_type": artifact.model_type,
                    "feature_columns": feature_columns,
                }
                refs = row_entity_references(row, artifact.entity_type)

                cur.execute(
                    """
                    insert into public.model_scores (
                      scoring_job_id, model_name, model_version, entity_type, entity_id,
                      score_name, score_value, probability, score_band, explanation,
                      top_reason_1, top_reason_2, top_reason_3, recommended_action
                    )
                    values (
                      %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s::jsonb,
                      %s, %s, %s, %s
                    )
                    returning model_score_id
                    """,
                    (
                        job_id,
                        artifact.model_name,
                        artifact.model_version,
                        artifact.entity_type,
                        clean_uuid(row["entity_id"]),
                        artifact.score_name,
                        score_float,
                        score_float if artifact.model_type != "regression" and 0 <= score_float <= 1 else None,
                        band,
                        json.dumps(explanation, default=json_default),
                        reason_1,
                        reason_2,
                        reason_3,
                        action,
                    ),
                )
                model_score_id = cur.fetchone()["model_score_id"]

                if band in {"MEDIUM", "HIGH", "VERY_HIGH"}:
                    cur.execute(
                        """
                        insert into public.next_best_actions (
                          model_score_id, scoring_job_id, customer_id, agent_id, policy_id,
                          lead_id, campaign_id, claim_id, product_id, action_type, action_rank,
                          priority_score, expected_value, due_date, action_status, action_reason
                        )
                        values (
                          %s, %s, %s, %s, %s,
                          %s, %s, %s, %s, %s, 1,
                          %s, %s, %s, 'recommended', %s
                        )
                        """,
                        (
                            model_score_id,
                            job_id,
                            clean_uuid(refs["customer_id"]),
                            clean_uuid(refs["agent_id"]),
                            clean_uuid(refs["policy_id"]),
                            clean_uuid(refs["lead_id"]),
                            clean_uuid(refs["campaign_id"]),
                            clean_uuid(refs["claim_id"]),
                            clean_uuid(refs["product_id"]),
                            action_type(artifact.model_name),
                            min(max(score_float, 0.0), 1.0) if artifact.model_type != "regression" else None,
                            score_float if artifact.model_type == "regression" else None,
                            date.today() + timedelta(days=7),
                            f"{action}. Drivers: {', '.join(reason for reason in [reason_1, reason_2, reason_3] if reason)}",
                        ),
                    )
                rows_written += 1
            conn.commit()
    return rows_written


def score_artifact(
    conn: psycopg.Connection,
    job_id: str,
    artifact: ModelArtifact,
    args: argparse.Namespace,
) -> int:
    snapshot = latest_snapshot(conn, artifact.feature_table, args.snapshot_date)
    if args.refresh_snapshot:
        refresh_feature_snapshot(conn, artifact.feature_table, snapshot)

    df = read_features(conn, artifact.feature_table, snapshot, args.limit)
    if df.empty:
        print(f"No eligible rows for {artifact.model_name} at snapshot {snapshot}")
        return 0

    model = load_model(artifact)
    feature_columns = infer_feature_columns(df, artifact)
    scores = model_scores(model, df, artifact, feature_columns)
    importance = extract_feature_importance(model, artifact, feature_columns)

    return insert_scores_and_actions(
        conn=conn,
        job_id=job_id,
        artifact=artifact,
        df=df,
        scores=scores,
        feature_columns=feature_columns,
        feature_importance=importance,
        batch_size=args.batch_size,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score trained insurance ML models.")
    parser.add_argument("--env-file", default=".env", help="Path to .env file.")
    parser.add_argument("--model-name", default="all", help="Model name to score, or all.")
    parser.add_argument("--model-dir", default="models", help="Local model artifact directory.")
    parser.add_argument("--snapshot-date", help="Feature snapshot date YYYY-MM-DD. Defaults to latest in table.")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per DB commit.")
    parser.add_argument("--limit", type=int, help="Optional max feature rows per model for test scoring.")
    parser.add_argument("--statement-timeout-ms", type=int, default=900000)
    parser.add_argument("--refresh-snapshot", action="store_true", help="Refresh feature table snapshot before scoring.")
    parser.add_argument("--explain", choices=["importance", "none"], default="importance")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("Missing SUPABASE_DB_URL in .env or environment.", file=sys.stderr)
        return 2

    with connect(db_url, args.statement_timeout_ms) as conn:
        job_id = create_job(conn, args)
        total_rows = 0
        failed_rows = 0
        try:
            update_job(conn, job_id, "running")
            artifacts = load_artifact(conn, Path(args.model_dir), args.model_name)
            if not artifacts:
                raise RuntimeError(
                    "No active model artifacts found. Insert rows into public.model_artifacts "
                    "or add metadata.json files under the models directory."
                )

            for artifact in artifacts:
                print(f"Scoring {artifact.model_name} v{artifact.model_version}")
                try:
                    rows = score_artifact(conn, job_id, artifact, args)
                    total_rows += rows
                    print(f"  wrote {rows} scores")
                except Exception as exc:
                    failed_rows += 1
                    print(f"  failed: {exc}", file=sys.stderr)
                    traceback.print_exc()

            status = "completed" if failed_rows == 0 else "partial"
            update_job(
                conn,
                job_id,
                status,
                rows_scored=total_rows,
                rows_failed=failed_rows,
                model_name=None if args.model_name == "all" else args.model_name,
            )
            print(f"Scoring job {job_id} finished with status {status}; rows_scored={total_rows}")
            return 0 if failed_rows == 0 else 1
        except Exception as exc:
            update_job(conn, job_id, "failed", total_rows, failed_rows, str(exc))
            print(f"Scoring job {job_id} failed: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
