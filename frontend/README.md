# ResearchMind Frontend

This is the Next.js 15 frontend application for ResearchMind, providing a powerful, accessible, and performant dashboard and corpus management interface for scientific paper analysis.

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4
- **Components**: shadcn/ui (Radix UI primitives)
- **State Management**: Zustand
- **Data Fetching**: TanStack Query v5
- **Testing**: Vitest + React Testing Library

## Getting Started

First, install the dependencies:

```bash
npm install
```

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Architecture

The frontend follows a feature-based architecture to maintain high cohesion and low coupling.
See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architectural decisions and guidelines.

## Testing

Run the test suite using Vitest:

```bash
npm test
```

## Mock Data Strategy

Currently, the application uses deterministic mock data generated on the client side (`services/mock-data.ts`) to simulate the ResearchMind API schema (RUO and SRO models). This allows the frontend to be developed and tested completely independently of the Python backend.

- No `Math.random()`, UUID generation, or `Date.now()` are used in mock generation to ensure deterministic test results and snapshot consistency.
