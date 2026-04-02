# Jenkins Log Analyzer Frontend

Professional HPE-themed frontend built with Next.js 16, Tailwind CSS, shadcn/ui, and Zod validation.

## Stack

- Next.js 16 (App Router)
- TypeScript
- Tailwind CSS v4
- shadcn/ui components
- react-hook-form + zod validation
- Sonner toasts

## Prerequisites

- Node.js 20+
- Backend Flask API running (default expected at http://localhost:5005)

## Environment Setup

1. Create local env file from example:

```bash
cp .env.local.example .env.local
```

2. Update API base URL if needed:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:5005
```

## Run Locally

Always run commands from this folder:

Jenkings-Log-Analyser/chatbot-frontend

```bash
npm install
npm run dev
```

Open http://localhost:3000

## Quality Checks

```bash
npm run lint
npm run build
```

## Available Scripts

- `npm run dev` — start development server
- `npm run build` — production build
- `npm run start` — run production server
- `npm run lint` — run ESLint

## Troubleshooting

### `npm run dev` fails with exit code 254

You are likely running from the wrong directory. Ensure current folder is:

Jenkings-Log-Analyser/chatbot-frontend

Then run:

```bash
npm run dev
```

### API calls fail

- Confirm Flask backend is running on port 5005.
- Check `.env.local` has the correct `NEXT_PUBLIC_API_BASE_URL`.
- Verify backend health endpoint: `GET /api/health`.

## Feature Areas

- Analyze Jenkins Build (validated form + API response panel)
- Schedule Email Report (validated form + immediate/scheduled send)
- Reusable loading/empty states + toast notifications
- Dark mode + professional HPE-themed layout
- Confidence % metric with click-to-open speech-bubble breakdown
- Backtrack similarity % across the last 1-3 session results

## Result Metrics UX

### Confidence %

- Displayed on the analysis result card after a successful analysis.
- Click the badge to open a detailed breakdown bubble.
- Breakdown includes:
	- Quality dimensions (evidence coverage, specificity, structure, certainty)
	- Positive signals and risk signals
	- "Why this is not 100%" list (when score is below 100)

### Backtrack %

- Displayed on the analysis result card after there is at least one previous result in the same browser session.
- Click the badge to open a detailed comparison bubble.
- Breakdown includes:
	- 100% exact result matches
	- Top exact shared terms
	- Synonymous match groups
	- Per-result comparison percentages against recent history

## Developer Notes (Metrics)

- API metric type: `src/lib/api.ts` (`ConfidenceMetrics`)
- Session comparison engine: `src/lib/result-history.ts`
- Metric badge + speech-bubble UI: `src/components/common/analysis-result-card.tsx`
- Analyze flow wiring: `src/components/forms/analyze-jenkins-form.tsx`
