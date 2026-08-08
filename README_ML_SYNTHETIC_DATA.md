# ML-Ready Synthetic Insurance Data

The existing Faker-based generator now produces a three-year synthetic dataset for the insurance AI platform, including the core insurance tables plus ML-ready behavior, journey, sales, underwriting, agent, claims, model scoring, and next-best-action tables.

## Generate

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' generate_synthetic_insurance_data.py --output-dir data
```

Small dry run:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' generate_synthetic_insurance_data.py `
  --output-dir data_ml_test `
  --customers 120 `
  --policies 240 `
  --agents 70 `
  --campaigns 20 `
  --engagement-events 500 `
  --min-targets-per-campaign 5 `
  --max-targets-per-campaign 15
```

## Output Folder

The generator writes all CSVs to the selected output directory:

```text
data/
  core insurance CSVs
  customer_behavior_daily.csv
  customer_digital_events.csv
  customer_complaints.csv
  customer_satisfaction_surveys.csv
  customer_nps.csv
  customer_service_requests.csv
  policy_events.csv
  policy_renewals.csv
  policy_lapse_events.csv
  quotes.csv
  proposals.csv
  applications.csv
  underwriting_decisions.csv
  agent_calls.csv
  agent_meetings.csv
  agent_targets.csv
  agent_commissions.csv
  agent_training.csv
  agent_attrition_events.csv
  claim_parties.csv
  claim_assessments.csv
  claim_fraud_indicators.csv
  model_features.csv
  model_scores.csv
  model_predictions.csv
  next_best_actions.csv
  ml_training_labels.csv
  load_order.txt
  validation_checks.json
  validation_results.json
```

## Load Order

Use:

```text
data/load_order.txt
```

Apply schema first:

```sql
\i 005_ml_schema_enhancements.sql
```

Then load CSVs in the order listed in `load_order.txt`.

## Hidden Statistical Relationships

The data is not independent random noise. The generator creates latent customer and agent signals, then uses those signals across events and labels.

Patterns included:

- Customers with missed payments have higher policy lapse probability.
- Customers with high engagement have higher propensity-to-buy labels.
- Customers with complaints have higher churn labels and lower satisfaction/NPS.
- Agents with higher activity and performance have stronger conversion signals.
- Agents with declining commissions and chargebacks have higher attrition probability.
- Customers with prior claims have different renewal and claim/fraud risk behavior.
- Campaign responders have higher quote, proposal, and conversion probability.
- High-income customers have higher cross-sell and next-best-product potential.
- Long-tenure customers have higher retention probability.
- Policy premium increases increase lapse risk.

## Training Labels

`ml_training_labels.csv` contains derived label columns:

- `propensity_to_buy_label`
- `next_best_product_label`
- `churn_label`
- `lapse_label`
- `lead_conversion_label`
- `agent_attrition_label`
- `claim_occurrence_label`
- `fraud_label`
- `campaign_response_label`

These are wide labels for convenient supervised-learning extracts. The normalized model-serving tables are also generated:

- `model_features.csv`
- `model_scores.csv`
- `model_predictions.csv`
- `next_best_actions.csv`

## Validation

Run:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' validate_synthetic_data.py --data-dir data
```

This writes:

```text
data/validation_results.json
```

Validation checks include:

- selected referential integrity checks across products, policies, coverages, and premiums
- high-engagement vs low-engagement propensity rate
- complaint vs no-complaint churn rate
- missed-payment vs no-missed-payment lapse rate

## Assumptions

- `customer_behavior_daily` is generated as periodic daily-style snapshots across the three-year window rather than every customer every single day, to keep MVP volume manageable.
- `ml_training_labels.csv` is a training convenience table and can be loaded into `public.ml_training_labels` from `005_ml_schema_enhancements.sql`.
- `model_features.features`, `model_scores.explanation`, and `model_predictions.prediction_payload` intentionally use JSONB-style payloads so ML feature evolution does not require a schema migration for every experiment.
- All rows are synthetic and fictional.
