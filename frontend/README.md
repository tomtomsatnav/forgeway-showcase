# Forgeway web

The React front end for Forgeway: a map of tracks and exercises, and a workspace where the
learner reads a brief, edits code and runs automated checks.

Stack: Vite, React 18, TypeScript (strict), Tailwind CSS on semantic design tokens, TanStack Router
and Query, `openapi-fetch` with types generated from `openapi.json`, CodeMirror 6, Motion.
The design system is specified in [`../DESIGN.md`](../DESIGN.md).

## Develop

```sh
docker compose up -d --wait api worker   # from the repository root
npm ci
npm run dev                              # http://localhost:5173
```

The dev server proxies `/api`, `/healthz` and `/readyz` to `http://localhost:8000`, so the session
cookie is same-origin and needs no CORS configuration.

## Scripts

| Script              | Purpose                                              |
| ------------------- | ---------------------------------------------------- |
| `npm run dev`       | Dev server with hot reload                           |
| `npm run build`     | Type-check, then production build into `dist/`       |
| `npm run preview`   | Serve the production build                           |
| `npm run gen:api`   | Regenerate `src/api/schema.d.ts` from `openapi.json` |
| `npm run lint`      | ESLint (typescript-eslint, strict type-checked)      |
| `npm run typecheck` | `tsc` without emitting                               |
| `npm test`          | Vitest and Testing Library                           |
| `npm run e2e`       | Playwright against the compose stack (see below)     |
| `npm run format`    | Prettier                                             |

## End-to-end tests

`e2e/` holds Playwright tests (journey, axe accessibility, keyboard, 375px layout). They run against
a live stack, by default http://localhost:8080 (override with `E2E_BASE_URL`):

```sh
docker compose up -d --build --wait api worker web   # from the repository root
npx playwright install chromium                      # once
npm run e2e
```

## Layout

- `src/theme/` mode and colour-scheme provider, per-mode lexicon, and the layout slots
  (`BranchOverview`, `CompletionMoment`, `PageHeader`) with one renderer per mode.
- `src/api/` the typed client (CSRF header on mutations, problem+json errors) and query hooks.
- `src/components/` shared, token-driven components.
- `src/features/` the auth, map and workspace screens.

## Production image

`Dockerfile` builds the SPA and serves it from nginx, with a history fallback and `/api`
proxied to the `api` service. `docker compose up --build web` serves it on
http://localhost:8080.
