# Insurance ML Scoring Pipeline

This scoring layer loads the latest active model artifact, reads the latest feature snapshot, scores eligible entities, writes model outputs to `model_scores`, and creates operational recommendations in `next_best_actions`.

## Files

- `014_ml_scoring_serving_schema.sql`: model artifact registry, scoring job log, scoring/action extensions, and latest-score view.
- `015_seed_baseline_model_artifacts.sql`: optional baseline `rule_based` model registry rows for scoring smoke tests.
- `ml_scoring_pipeline.py`: batch scoring pipeline.
- `sample_scored_output.csv`: example output shape.

## Apply SQL

Run this after the ML schema and feature table scripts:

```sql
-- 014_ml_scoring_serving_schema.sql
```

For a smoke test without trained model files, optionally run:

```sql
-- 015_seed_baseline_model_artifacts.sql
```

The baseline artifacts are deterministic rules, not production models. Replace them with real trained model records when training is complete.

## Register A Trained Model

Example registry insert for a trained joblib model:

```sql
insert into public.model_artifacts (
  model_name,
  model_version,
  artifact_uri,
  artifact_format,
  feature_table,
  entity_type,
  score_name,
  model_type,
  training_snapshot_date,
  training_metrics,
  feature_columns,
  active_flag,
  promoted_at
)
values (
  'propensity_to_buy',
  '2026.05.31',
  'C:/models/propensity_to_buy/2026.05.31/model.joblib',
  'joblib',
  'propensity_to_buy_features',
  'customer',
  'propensity_to_buy',
  'classification',
  date '2025-12-01',
  '{"auc": 0.81, "precision_at_10": 0.34}'::jsonb,
  '["engagement_score", "active_policy_count", "digital_events_90d", "quote_requests_180d", "positive_campaign_responses_prior", "complaint_count_prior", "missed_payment_count_prior", "tenure_days"]'::jsonb,
  true,
  now()
);
```

If `feature_columns` is empty, the scorer infers numeric columns from the feature table and excludes IDs, labels, dates, and metadata columns.

## Run Scoring

Set `.env`:

```bash
SUPABASE_DB_URL=postgresql://postgres.[project-ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Score all active models:

```bash
python ml_scoring_pipeline.py --model-name all --batch-size 500
```

Score one model:

```bash
python ml_scoring_pipeline.py --model-name propensity_to_buy --batch-size 500
```

Score a specific feature snapshot:

```bash
python ml_scoring_pipeline.py --model-name policy_lapse --snapshot-date 2025-12-01
```

Small test run:

```bash
python ml_scoring_pipeline.py --model-name fraud_detection --limit 100
```

## Outputs

`model_scores` receives:

- `entity_type`
- `entity_id`
- `model_name`
- `model_version`
- `score_value`
- `score_band`: `LOW`, `MEDIUM`, `HIGH`, `VERY_HIGH`
- `top_reason_1`
- `top_reason_2`
- `top_reason_3`
- `recommended_action`
- `explanation`
- `created_at`

`next_best_actions` receives medium/high/very-high recommendations with:

- linked `model_score_id`
- linked `scoring_job_id`
- entity references where available
- `action_type`
- `priority_score` or `expected_value`
- `due_date`
- `action_reason`

`model_scoring_jobs` records started/completed/failed/partial status and row counts.

## Validate

Recent scoring jobs:

```sql
select *
from public.model_scoring_jobs
order by started_at desc
limit 20;
```

Latest score counts:

```sql
select model_name, model_version, score_band, count(*) as score_count
from public.model_scores
group by model_name, model_version, score_band
order by model_name, score_band;
```

Recommended actions:

```sql
select action_type, action_status, count(*) as action_count
from public.next_best_actions
group by action_type, action_status
order by action_count desc;
```

Dashboard-ready latest scores:

```sql
select *
from public.v_latest_model_scores
order by score_ts desc
limit 100;
```

## Explainability

The scorer writes top reasons using this priority:

1. `feature_importance` supplied in artifact metadata.
2. `feature_importances_` from tree-based sklearn models.
3. Absolute `coef_` values from linear models.
4. Equal-weight fallback for rule-based or unsupported estimators.

The full explanation payload is stored in `model_scores.explanation`.

## Production Notes

- Store real artifacts in controlled object storage or a model registry, then write the artifact URI to `model_artifacts`.
- Use immutable `model_version` values and promote only one active model per model family unless you intentionally run champion/challenger scoring.
- Schedule scoring outside the Supabase SQL Editor for larger batches.
- Keep feature refresh and scoring as separate jobs so failures are easier to diagnose.
- Use `snapshot_date` to pin reproducible scoring runs.
