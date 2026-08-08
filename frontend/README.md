# Insurance Decision Intelligence Platform

Client-presentable React and Tailwind frontend for an insurance decision intelligence product.

## Experience

- Prudential-inspired red, white, and dark grey enterprise theme
- Responsive sidebar and top header
- Role selector and mock user profile
- Executive Home dashboard
- Know Your Customer workspace
- Know Your Agent workspace
- Campaign Effectiveness workspace
- Agent Performance Tracking workspace
- Policy Lapse Risk workspace
- AI Intelligence workspace
- Model Insights workspace
- Reusable KPI cards, chart cards, recommendation cards, lineage panels, confidence badges, loading states, and error states

The app uses mock data so the insurance intelligence platform remains usable while APIs evolve. The AI Intelligence panel is API-ready and calls the existing backend ask route when the FastAPI gateway is available. If the API is unavailable, it falls back to a platform sample response.

## Setup

```powershell
cd C:\Users\Nitin\Documents\Codex\2026-05-29\act-as-an-enterprise-insurance-data\frontend
npm install
```

Set the gateway URL in `.env.local`:

```text
NEXT_PUBLIC_INTELLIGENCE_API_URL=http://127.0.0.1:8071
```

Start the backend gateway from the repository root:

```powershell
cd C:\Users\Nitin\Documents\Codex\2026-05-29\act-as-an-enterprise-insurance-data
python -m uvicorn <backend_gateway_module>.api:app --host 127.0.0.1 --port 8071
```

Start the frontend:

```powershell
cd C:\Users\Nitin\Documents\Codex\2026-05-29\act-as-an-enterprise-insurance-data\frontend
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

## Build

```powershell
npm run build
```

## API Connection Points

The current UI is designed to connect these sections later:

- AI Intelligence: backend ask route
- Role selector: `GET /roles`
- Role dashboards: `GET /roles/{role}/dashboard`
- Customer profile: `GET /customers/{id}/360`
- Agent profile: `GET /agents/{id}/360`
- Campaign profile: `GET /campaigns/{id}/360`
- Claims profile: `GET /claims/{id}/360`
- Recommendations: `GET /recommendations/{entity_id}`
- Lineage: `GET /lineage/{insight_id}`

## Notes

- The visual layer is intentionally executive-friendly and avoids exposing technical detail by default.
- Generated SQL is available only inside the AI Intelligence answer details.
- Mock data keeps the platform usable while backend APIs evolve.
