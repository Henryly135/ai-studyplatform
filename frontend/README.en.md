# Frontend

中文版本: [README.md](README.md)

## Stack

- React
- TypeScript
- Vite
- React Router

## Run Locally

```bash
cd frontend
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

When running through the full Docker Compose stack, the frontend should use:

```env
VITE_API_BASE_URL=/api
```

## Current Route Shape

- `/`: public home page.
- `/login`: login.
- `/register/:role`: role-based registration.
- `/home`: authenticated workspace home.
- `/home/*`: workspace child pages.
- `/ai-demo`: AI demo page.

## Current Auth Behavior

- Login success redirects to `/home`.
- Accessing `/home` or `/ai-demo` without a valid token returns to the public entry.
- Logout clears frontend local session state from `localStorage`.

## Home Workspace

The protected `/home` area includes:

- Left sidebar navigation.
- Topbar with profile and logout.
- `/home` overview page.
- `/home/*` child pages for each function area.

Function-area visibility is configured in:

- `src/pages/Home/homeConfig.ts`
