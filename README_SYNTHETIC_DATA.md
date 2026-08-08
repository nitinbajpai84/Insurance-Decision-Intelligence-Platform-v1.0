# Synthetic Insurance Data Generator

This workspace contains a Python generator for the Supabase insurance analytics MVP schema in `001_insurance_analytics_mvp_schema.sql`.

The dataset is fictional. Product and campaign themes are inspired by public Prudential Singapore and Prudential Hong Kong information, but no real Prudential customer, policy, agent, claim, response, or transaction data is used.

## Public Research Themes Used

The synthetic catalogue is customized around Singapore and Hong Kong insurance themes:

- Singapore protection and health themes such as PRUShield, PRUExtra, PRUActive Life, PRUActive Cash, PRULink, and health/protection campaign positioning.
- Singapore wellness and engagement themes inspired by Every Body Club and health-span messaging.
- Singapore distribution themes inspired by public hiring and Management Associate Programme messaging for financial representatives.
- Hong Kong health, VHIS, cancer, life, and wealth themes such as PRUCancer 360, PRUHealth VHIS, PRUHealth Guardian Critical Illness, PRULife Protector II, and multi-currency wealth planning.
- Hong Kong campaign and privilege themes inspired by PruNextGen, PruLivingHK, health/wellness promotions, maturity appreciation offers, and family/newcomer engagement.
- Rider attachment themes for medical riders, outpatient riders, hospital cash, critical illness multipay, premium waiver, accident, long-term care, and legacy riders. Riders are synthetic product components under base products, not standalone policy-header products.

Public source links used for theme research:

- Prudential Singapore PRUShield / PRUExtra health insurance: https://www.prudential.com.sg/products/health-insurance/medical/prushield
- Prudential Singapore health protection campaign page: https://www.prudential.com.sg/products/campaigns/health-protection
- Prudential Singapore Every Body Club: https://www.prudential.com.sg/wedo/wedohub/do-health/everybodyclub/
- Prudential Singapore PRUActive Cash: https://www.prudential.com.sg/others/pruactive-cash-ea
- Prudential Hong Kong PRUCancer 360: https://www.prudential.com.hk/en/products/health/critical-illness/prucancer-360
- Prudential Hong Kong PRUHealth VHIS VIP Plan: https://www.prudential.com.hk/en/products/health/medical/prudential-VHIS-series/pruhealth-vhis-vip-plan/
- Prudential Hong Kong PRULife Protector II: https://www.prudential.com.hk/en/products/life/life-protection/prulife-protector-ii/
- Prudential Hong Kong PruLivingHK: https://www.prudential.com.hk/en/about-us/promotion/prulivinghk
- Prudential / PruNextGen public campaign site: https://www.prunextgen.com/?lang=en

## Files

- `generate_synthetic_insurance_data.py` - deterministic CSV generator.
- `requirements.txt` - Python dependency list.
- `data/` - generated full-size CSV output.
- `data/_manifest.json` - generation parameters and row counts.
- `data_test/` - optional small dry-run output if retained locally.

## Generate Data

Use the bundled Codex Python runtime if your default `python` command is unavailable:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' generate_synthetic_insurance_data.py
```

Or with custom counts:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' generate_synthetic_insurance_data.py `
  --output-dir data `
  --customers 10000 `
  --policies 20000 `
  --agents 6000 `
  --campaigns 800 `
  --engagement-events 120000
```

By default, semantic document embeddings are left blank so you can populate them with your actual embedding model. To emit placeholder 1536-dimension vectors for testing pgvector load paths, add:

```powershell
--include-fake-embeddings
```

## Supabase Load Order

Run the DDL first:

```sql
\i 001_insurance_analytics_mvp_schema.sql
\i 004_product_riders_and_nbp_views.sql
```

Then load CSVs in this order:

1. `parties.csv`
2. `products.csv`
3. `customers.csv`
4. `addresses.csv`
5. `agents.csv`
6. `agent_movements.csv`
7. `campaigns.csv`
8. `leads.csv`
9. `opportunities.csv`
10. `policies.csv`
11. `policy_coverages.csv`
12. `premiums.csv`
13. `payments.csv`
14. `claims.csv`
15. `campaign_targets.csv`
16. `campaign_responses.csv`
17. `customer_engagement_events.csv`
18. `agent_mapa_metrics.csv`
19. `business_glossary.csv`
20. `semantic_documents.csv`
21. `query_audit_log.csv`

Example `psql` load command:

```sql
\copy public.parties from 'data/parties.csv' with (format csv, header true);
```

Repeat for each table in the load order above.

For Supabase dashboard imports, upload each CSV to the matching table in the same order.

## Data Volumes

Default generation creates:

- 10,000 customers
- 20,000 policies across three years
- 6,000 agents
- 800 campaigns
- 9 base products and 22 rider product components
- Campaign targets, responses, leads, opportunities, and conversions
- Monthly MAPA rows for every agent across 36 months
- Claims, premiums, payments, and engagement events
- Business glossary and semantic context documents

## Realism Features

The generator includes:

- Singapore and Hong Kong geography.
- Customer segments such as young professionals, family protection, affluent wealth, retirement planners, health-focused customers, and SME owners.
- Policy lifecycle statuses: active, issued, cancelled, expired, renewed, and lapsed.
- Rider-aware policies: base policies are stored in `policies.product_id`, attached riders are stored in `policy_coverages.product_id` with `is_rider = true` and `rider_tag`.
- Rider-tagged NBP: premium rows are allocated by base coverage and rider coverage, so `public.v_new_business_premium_by_rider` can report NBP by rider category, component product, base product, agent, or month.
- Seasonal demand patterns around common campaign and planning periods.
- Campaign attribution from campaigns to targets, responses, leads, opportunities, and policies.
- Agent performance variation through a lognormal performance factor.
- Agent movement history with appointments, territory changes, agency changes, and terminations.
- MAPA monthly metrics that partially reconcile with generated leads, opportunities, policies, premiums, and claims.
- Claims frequency and severity differences by product line.
- Payment statuses including paid, scheduled, failed, reversed, refunded, and past due.

## Intentional Data Quality Issues

The data includes mild, load-safe quality issues for realistic analytics testing:

- Some customers have missing email, phone, or tax ID suffix values.
- Some parties have stale secondary addresses that are still marked current.
- Some engagement events include metadata flags such as `late_arriving_event` or `duplicate_click_candidate`.
- Some campaigns have bounced, unsubscribed, suppressed, or excluded targets.
- Some failed or past-due payments exist against otherwise active customers.

These issues are designed not to violate primary keys, foreign keys, or check constraints.

## Notes

- The `claims` CSV intentionally omits `incurred_amount` because that column is generated by Postgres.
- The `query_audit_log.user_id` column is blank by default because it references `auth.users(id)` in Supabase.
- `semantic_documents.embedding` is blank by default. Populate it after load using your embedding pipeline, or regenerate with fake vectors for pgvector plumbing tests.
