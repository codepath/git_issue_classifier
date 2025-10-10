# PR Explorer Frontend

React + TypeScript web UI for browsing and exploring classified GitHub/GitLab PRs.

## Features

- **Browse PRs**: Paginated list of classified PRs with filters
- **Detailed View**: View PR metadata, changed files, diffs, linked issues, and comments
- **Classification Insights**: See LLM classifications (difficulty, suitability, concepts taught)
- **LLM Prompt Inspector**: View the exact prompt sent to the LLM for debugging
- **Favorites**: Mark PRs as favorites for learning exercises
- **Multi-Platform**: Supports both GitHub PRs and GitLab MRs

## Tech Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui
- **HTTP Client**: Fetch API
- **Testing**: Vitest + React Testing Library

## Prerequisites

- Node.js 18+ and npm
- Backend API server running (see root README.md)

## Installation

```bash
cd frontend
npm install
```

## Development

Start the development server with hot reload:

```bash
npm run dev
```

The frontend will be available at http://localhost:5173

**Note:** Make sure the backend API server is running on http://localhost:8000 before starting the frontend.

## Available Scripts

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run tests
npm run test

# Run tests with UI
npm run test:ui

# Run linter
npm run lint
```

## Project Structure

```
frontend/
├── src/
│   ├── components/       # React components
│   │   ├── ui/          # shadcn/ui base components
│   │   ├── PRList.tsx   # PR list view
│   │   ├── PRDetail.tsx # PR detail view
│   │   └── ...
│   ├── lib/
│   │   ├── api.ts       # API client for backend
│   │   └── utils.ts     # Utility functions
│   ├── types/
│   │   └── pr.ts        # TypeScript type definitions
│   ├── App.tsx          # Main app component
│   └── main.tsx         # Entry point
├── dist/                # Production build output
└── public/              # Static assets
```

## API Integration

The frontend communicates with the FastAPI backend at `http://localhost:8000`.

Key API endpoints used:
- `GET /api/prs` - List PRs with pagination and filters
- `GET /api/prs/{repo}/{pr_number}` - Get PR details
- `GET /api/prs/{repo}/{pr_number}/llm_payload` - Get LLM prompt
- `POST /api/prs/{repo}/{pr_number}/favorite` - Toggle favorite status
- `GET /api/repos` - List all repositories

See `src/lib/api.ts` for the complete API client implementation.

## Building for Production

```bash
npm run build
```

This will create an optimized production build in the `dist/` directory.

To preview the production build locally:

```bash
npm run preview
```

## Testing

The project uses Vitest for unit testing:

```bash
# Run tests
npm run test

# Run tests with coverage
npm run test -- --coverage

# Run tests in watch mode
npm run test -- --watch

# Run tests with UI
npm run test:ui
```

Test files are located next to their corresponding components with the `.test.tsx` suffix.

## Styling

The project uses:
- **Tailwind CSS** for utility-first styling
- **shadcn/ui** for pre-built, accessible components
- **CSS variables** for theming (see `src/index.css`)

### Adding New UI Components

This project uses shadcn/ui. To add new components:

```bash
npx shadcn@latest add <component-name>
```

Example:
```bash
npx shadcn@latest add button
npx shadcn@latest add card
```

Components will be added to `src/components/ui/`.

## Environment Configuration

The frontend expects the backend API to be available at `http://localhost:8000` by default.

To change this, update the `API_BASE_URL` in `src/lib/api.ts`:

```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

You can also create a `.env.local` file:

```bash
VITE_API_URL=http://your-backend-url:8000
```

## Troubleshooting

### CORS Errors

If you see CORS errors in the browser console:

1. Make sure the backend is running
2. Check that the backend's CORS configuration includes your frontend URL
3. Backend CORS is configured in `backend/app.py` - default allows `http://localhost:5173`

### API Connection Failed

If the frontend can't connect to the backend:

1. Verify the backend is running: http://localhost:8000/docs
2. Check the `API_BASE_URL` in `src/lib/api.ts`
3. Check browser console for error messages

### Build Errors

If you encounter TypeScript errors during build:

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Check TypeScript configuration
npx tsc --noEmit
```

## Contributing

When adding new features:

1. Create components in `src/components/`
2. Add types to `src/types/`
3. Update API client in `src/lib/api.ts` if needed
4. Write tests alongside components (`.test.tsx`)
5. Update this README if adding significant features

## License

Part of the Git Issue Classifier project. See root LICENSE file.
