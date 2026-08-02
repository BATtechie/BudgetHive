# BudgetHive Frontend Build Log

## Design System (CSS — Phase 2 Dark Theme)
**What:** Complete dark theme design system. Color palette: bg #0D0B0A, card #1A1714, primary amber #D4940A, accent green #0F9D6E, danger #D44333. Typography: Playfair Display (serif display), Inter (sans body), JetBrains Mono (data). Extensive component classes for hero, ticker, problem grid, agent grid, demo section, verdict results, pipeline flow, invocation table, scoring grid, weight bars, screen previews, callout boxes, verdict badges, buttons, inputs, alerts, spinner. Responsive breakpoints at 1024px, 768px, 480px.
**Files:** `frontend/src/styles.css`

## Auth Context
**What:** React Context + useReducer for auth state management. Handles login/signup/logout, JWT persistence in localStorage, auto-fetch user on mount via `/users/me`.
**Files:** `frontend/src/context/AuthContext.jsx`

## Error Boundary
**What:** Class-based error boundary to catch render errors and show a recovery UI instead of blanking the app.
**Files:** `frontend/src/components/ErrorBoundary.jsx`

## Protected Route
**What:** Route guard component that redirects to `/login` when no JWT token is present, shows spinner during auth loading.
**Files:** `frontend/src/components/ProtectedRoute.jsx`

## Navbar
**What:** Sticky nav with hexagonal hive logo SVG, brand name, conditional auth buttons (login/signup when logged out, user name + logout when logged in), dashboard link.
**Files:** `frontend/src/components/Navbar.jsx`

## Footer
**What:** Minimal footer with copyright year and nav links (Home, Dashboard).
**Files:** `frontend/src/components/Footer.jsx`

## Main Layout
**What:** Layout wrapper using react-router-dom's Outlet — renders Navbar, ErrorBoundary-wrapped main content, and Footer.
**Files:** `frontend/src/layouts/MainLayout.jsx`

## Landing Page (Phase 2 — Dark Theme Redesign)
**What:** Complete redesign with 5 reference-matched sections:
1. **Hero + Problem** — Serif headline (Playfair Display), animated ticker bar, 3 problem cards with icons and dashed-border callouts.
2. **Agent Showcase Grid** — 6 cards (A1–A5 agents + A6 Final Judge presentational). Each card shows real orchestrator weight badge, description, and monospace example snippet in a dashed callout. Weights match `_BASE_WEIGHTS`: A1=25%, A2=25%, A3=20%, A4=15%, A5=15%.
3. **Live Product Demo** — Functional evaluate form wired to `POST /api/v1/verdict/evaluate`. Auth-gated: shows login prompt with demo credentials when logged out, shows form + live verdict results when logged in. All scores, labels, reasoning strings come from the real API — zero hardcoded data.
4. **How It Works Flow** — 4-step numbered process cards + Selective Invocation table showing which agents fire per input scenario. Rules match real `_decide_agents()` logic.
5. **Scoring Breakdown** — BUY/MAYBE/SKIP threshold items (≥70, 40–69, <40), Signal Weights bars with real percentages, weight redistribution callout, and "Five screens" app preview (Onboarding, Watchlist marked "Coming Soon", Decision Log).

Design language: dark bg (#0D0B0A), card (#1A1714), primary amber (#D4940A), accent green (#0F9D6E), serif display font (Playfair Display) + sans body (Inter) + mono data (JetBrains Mono), uppercase tracked section labels, dashed-border callout boxes.
**Files:** `frontend/src/pages/Landing.jsx`, `frontend/src/styles.css`

## Login Page
**What:** Email + password form, calls `/auth/login` via api.js, shows real API error messages, redirects to `/dashboard` on success, link to signup.
**Files:** `frontend/src/pages/Login.jsx`

## Signup Page
**What:** Full onboarding form matching UserCreate schema exactly — name, email, password (8-72 chars), monthly_income, monthly_savings_target, active_emis (optional), recurring_bills (optional). Calls `/auth/signup`, auto-logs in on success.
**Files:** `frontend/src/pages/Signup.jsx`

## Dashboard
**What:** Purchase evaluation form (product name, price, category select with all 15 backend categories, optional URL/budget/use case). Calls `/api/v1/verdict/evaluate`. Displays verdict result with BUY/MAYBE/SKIP badge, composite score bar, confidence %, per-agent breakdowns with scores and reasoning, skipped agents marked.
**Files:** `frontend/src/pages/Dashboard.jsx`

## API Client Update
**What:** Added `verdictEvaluate` method for `POST /api/v1/verdict/evaluate` (the orchestrator endpoint).
**Files:** `frontend/src/api.js`

## App Router
**What:** BrowserRouter setup with react-router-dom. Routes: `/` (Landing), `/login`, `/signup`, `/dashboard` (protected). AuthProvider wraps all routes.
**Files:** `frontend/src/App.jsx`, `frontend/src/main.jsx`
