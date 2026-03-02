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
