# RAG SQL Validation Regression Report

- Total tests: 35
- Pass: 30
- Partial: 1
- Blocked unsupported: 4
- Fail: 0
- Generated at: 2026-06-01 23:11:47

| Status | Role | Question | Rows | Validation | Key Data Points |
|---|---|---|---:|---|---|
| PASS | Insurance Agent | Which customers should I contact first this week? | 25 | PASS | Recommended action: service_recovery; Priority score: 98.7%; Confidence score: 0.0% |
| PASS | Insurance Agent | Which customers are likely to lapse in the next 90 days? | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| BLOCKED | Insurance Agent | Which product should I cross-sell to my high propensity customers? | 6 | FAIL | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| BLOCKED | Insurance Agent | Which customers have high CLV and high churn risk? | 6 | FAIL | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Insurance Agent | Which renewal customers need a retention conversation? | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Agency Manager | Which agents need coaching this month? | 25 | PASS | Agent needing coaching: Kyle McCarthy; Recent MAPA activity: 0; MAPA activity change: -13; Recent new business premium: S$0 |
| PASS | Agency Manager | Which agents have the highest premium at risk? | 25 | PASS | Agent: Sandra Price; Premium at risk: S$778.9K; Average lapse score: 22.0% |
| PASS | Agency Manager | Which branch has the highest lapse exposure? | 20 | PASS | Lapse rate: 5.5%; Lapsed policies: 56; Total policies: 1,013 |
| PASS | Agency Manager | Which agents changed territories and improved sales? | 25 | PASS | Agent with movement: Peter Hayes; Premium lift: S$302.1K; Policies after move: 4 |
| PASS | Agency Manager | Which agents show declining productivity? | 25 | PASS | Agent needing coaching: Kyle McCarthy; Recent MAPA activity: 0; MAPA activity change: -13; Recent new business premium: S$0 |
| PASS | Campaign Manager | Which campaign generated the highest policy conversion? | 25 | PASS | Top campaign: VHIS medical upgrade 2023 Wave 2; Converted premium: S$1.01M; Policy conversions: 38; Policy conversion rate: 9.2% |
| PASS | Campaign Manager | Which customer segments responded best to recent campaigns? | 25 | PASS | Top campaign: VHIS medical upgrade 2023 Wave 2; Converted premium: S$1.01M; Policy conversions: 38; Policy conversion rate: 9.2% |
| PASS | Campaign Manager | Which campaign has engagement but poor conversion? | 25 | PASS | Weakest campaign: Paid-up maturity appreciation 2025 Wave 1; Converted premium: S$0; Policy conversions: 0; Policy conversion rate: 0.0%; Response rate: 87.9% |
| PASS | Campaign Manager | What is campaign conversion rate by channel? | 8 | PASS | Top campaign channel: agent_call; Policy conversion rate: 8.0%; Response rate: 91.4%; Converted premium: S$17.35M |
| PASS | Campaign Manager | What are the bad campaigns? | 25 | PASS | Weakest campaign: Paid-up maturity appreciation 2025 Wave 1; Converted premium: S$0; Policy conversions: 0; Policy conversion rate: 0.0%; Response rate: 87.9% |
| PASS | Claims Manager | Which products have the highest claims ratio? | 9 | PASS | Product: PRUHealth VHIS VIP Plan (HK synthetic); Claims ratio: 33.9%; Incurred amount: S$17.82M |
| PASS | Claims Manager | Which claims have high fraud risk? | 12 | PASS | Claim for review: CLM-HK-00000699; Fraud indicator score: 29.5%; Incurred amount: S$145.8K |
| PASS | Claims Manager | Which regions show unusual claims growth? | 25 | PASS | Branch or territory: HK-TM; Claim count: 3; Incurred amount: S$1.51M |
| PASS | Claims Manager | Which claims need manual fraud review? | 12 | PASS | Claim for review: CLM-HK-00000699; Fraud indicator score: 29.5%; Incurred amount: S$145.8K |
| PASS | Claims Manager | What is claims exposure by product? | 9 | PASS | Product: PRUHealth VHIS VIP Plan (HK synthetic); Claims ratio: 33.9%; Incurred amount: S$17.82M |
| PASS | Sales Director | Which products are declining in new sales? | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| BLOCKED | Sales Director | Where is the largest cross-sell opportunity? | 6 | FAIL | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Sales Director | Which regions are underperforming against target? | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PARTIAL | Sales Director | Which products are declining in the market? | 6 | PARTIAL | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Sales Director | What product line has the largest premium concentration? | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Executive Leadership | What are the top risks to revenue this month? | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Executive Leadership | What hidden trends should leadership focus on? | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Executive Leadership | What are the top three growth opportunities? | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Executive Leadership | What is our current lapse rate? | 1 | PASS | Lapse rate: 5.3%; Lapsed policies: 1,053; Total policies: 20,000 |
| PASS | Executive Leadership | Which business area needs immediate management attention? | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Data Analyst | Show SQL for lapse risk by product. | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Data Analyst | Show campaign conversion rate by channel. | 8 | PASS | Top campaign channel: agent_call; Policy conversion rate: 8.0%; Response rate: 91.4%; Converted premium: S$17.35M |
| BLOCKED | Data Analyst | Show customers with high CLV and high churn risk. | 6 | FAIL | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
| PASS | Data Analyst | Show policies sold in Singapore. | 25 | PASS | Previewed policies: 10; Previewed annual premium: S$54.6K; First product: PRULink InvestGrowth (SG synthetic) |
| PASS | Data Analyst | Show internal premium by line of business. | 6 | PASS | Top line of business: wealth; Policy count: 1,943; Annual premium: S$108.65M |
