# AI Agency Frontend

Next.js 14+ frontend for the AI Agency multi-agent system.

## Tech Stack

- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript 5+
- **Styling**: Tailwind CSS 3+
- **State Management**: Zustand
- **Real-time**: WebSocket
- **Build Tool**: Turbopack (Next.js native)

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Open browser to http://localhost:3000
```

### Development

```bash
# Start dev server with Turbopack
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Run linter
npm run lint

# Type check
npm run type-check
```

## Project Structure

```
src/
├── app/                  # Next.js App Router
│   ├── layout.tsx       # Root layout
│   ├── page.tsx         # Home page
│   └── globals.css      # Global styles
├── components/          # React components
│   └── WorkspaceClient.tsx
├── lib/                 # Utilities and hooks
│   ├── stores/          # Zustand stores
│   └── utils/           # Helper functions
└── types/               # TypeScript types
    └── brief.ts         # Project Brief types
```

## Features

- ✓ Next.js 14+ with App Router
- ✓ TypeScript 5+ for type safety
- ✓ Tailwind CSS 3+ for styling
- ✓ Zustand for state management
- ✓ Dark mode theme
- ✓ Responsive layout

## Next Steps

- Implement WebSocket connection for Gemini Live
- Create audio capture and playback components
- Build Project Brief Panel with real-time updates
- Add conversation transcript display
- Implement persistent microphone component
- Create asset display components (images, video, audio, code)
