# Frontend Architecture

This document details the architectural guidelines and decisions for the ResearchMind frontend.

## 1. Core Principles

- **Feature-first organization**: Code is organized by feature rather than type (e.g., `features/dashboard` instead of grouping all components together).
- **Server and Client Components**: Utilize Next.js App Router carefully. Keep components Server Components by default. Add `"use client"` only when interactivity, hooks, or client-side state are required.
- **Strict Data Contracts**: The frontend must strictly adhere to the `RUO` (Raw Unstructured Object) and `SRO` (Structured Research Object) schemas defined in the backend. These are modeled in `types/document.ts`.

## 2. Directory Structure

```text
frontend/
├── app/                  # Next.js App Router pages and layouts
├── components/           # Shared, dumb UI components
│   ├── layout/           # AppShell, Sidebar, Header
│   ├── shared/           # Error states, Empty states, Status badges
│   └── ui/               # shadcn/ui components
├── features/             # Feature-specific modules
│   ├── dashboard/        # Dashboard page components and hooks
│   └── corpus/           # Corpus manager page components and hooks
├── hooks/                # Global shared hooks (useDebounce, useMediaQuery)
├── lib/                  # Utilities (Tailwind cn, API client)
├── providers/            # React context providers (Query, Theme, Auth)
├── services/             # API calls and Mock Data generators
├── stores/               # Global state (Zustand)
├── styles/               # Additional global styles if needed
├── tests/                # Vitest test files matching source structure
└── types/                # TypeScript interfaces and enums (RUO/SRO schemas)
```

## 3. State Management

We use a layered state management approach:

1. **Server State**: Managed by `@tanstack/react-query`. Used for all data fetched from the API (currently mocked). Handles caching, revalidation, and loading states.
2. **Global Client State**: Managed by `zustand`. Used for cross-cutting UI state like sidebar collapse status and selected rows in the corpus manager.
3. **Local Component State**: Managed by `useState` / `useReducer` for ephemeral UI state (e.g., input field values before debouncing).

## 4. Styling and Theming

- **Tailwind v4**: We use CSS-first configuration via `app/globals.css`.
- **shadcn/ui**: Components are copy-pasted into `components/ui` and customized as needed.
- **Dark Mode**: Fully supported via `next-themes` and CSS variables.
- **Accessibility**: All interactive elements use Radix UI primitives ensuring WCAG 2.1 AA compliance.
