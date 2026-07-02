# Calibration Uncertainty Calculator

A Progressive Web App for GUM-compliant calibration uncertainty calculation, validation, and PDF/Excel certificate generation. Built for Instruworks LLC FZ, Dubai. Complies with ISO/IEC 17025:2017.

## What It Does

- Registers instruments under calibration with full reference details
- Manages master/reference instrument traceability records
- Records ascending and descending calibration readings with live mean error and hysteresis calculation
- Calculates measurement uncertainty per GUM JCGM 100:2008
- Validates compliance against acceptance limits
- Generates PDF calibration certificates and Excel uncertainty budget sheets
- Runs on any device without installation (PWA)

## Instrument Categories

Pressure, Temperature, Electrical, Weighing, Mass

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React (JavaScript) |
| Backend | Python FastAPI |
| Database | Supabase (PostgreSQL) |
| Authentication | Supabase Auth with JWT |
| PDF generation | ReportLab |
| Excel generation | openpyxl |
| Frontend hosting | Vercel |
| Backend hosting | Railway |

## Project Structure

```
calibration-pwa/
├── frontend/               React PWA
│   ├── public/             Static assets (logo, manifest, service worker)
│   └── src/
│       ├── api.js          All backend fetch functions (single source of truth)
│       ├── auth.js         Supabase auth helpers
│       ├── index.css       Global design system and CSS variables
│       ├── hooks/          Custom React hooks
│       ├── components/     Reusable UI components
│       └── pages/          One file per route
└── backend/                FastAPI application
    ├── main.py             All API endpoints (CORS configured here only)
    ├── config.py           Environment variable loading
    ├── database.py         All database query functions (no raw SQL elsewhere)
    ├── auth.py             JWT verification
    ├── models.py           Pydantic request validation models
    ├── modules/
    │   ├── calculation_engine.py   GUM uncertainty calculations
    │   ├── formula_manager.py      Excel formula file parser
    │   ├── validation.py           Compliance validation
    │   └── reporting.py            PDF and Excel certificate generation
    ├── formulas/           Uncertainty formula files (xlsx + json fallback)
    └── assets/             Logo and static assets for PDF generation
```

## Local Setup

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- A Supabase project with the schema from `docs/schema.sql`

### Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install fastapi uvicorn numpy scipy reportlab openpyxl psycopg2-binary supabase python-dotenv pydantic python-jose
```

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Run the development server:

```bash
uvicorn main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Auto-generated API docs are at `http://127.0.0.1:8000/docs`.

### Frontend

```bash
cd frontend
npm install
```

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Run the development server:

```bash
npm start
```

The app runs at `http://localhost:3000`.

## Environment Variables

### Backend (backend/.env)

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (not the anon key) |
| `SUPABASE_JWT_SECRET` | Supabase JWT secret from Project Settings > JWT Settings |

### Frontend (frontend/.env)

| Variable | Description |
|---|---|
| `REACT_APP_SUPABASE_URL` | Your Supabase project URL |
| `REACT_APP_SUPABASE_ANON_KEY` | Supabase anon/public key |

Never commit `.env` files. They are in `.gitignore`.

## Database

All tables are created in Supabase. Row Level Security is enabled on all eight tables. Users can only access their own records. The `acceptance_limits` table is readable by all authenticated users.

Tables: `instruments`, `calibration_sessions`, `calibration_reference`, `readings`, `master_instruments`, `uncertainty_budgets`, `acceptance_limits`, `audit_log`

## Formula Files

The uncertainty calculation engine reads from Excel files in `backend/formulas/`. Each instrument category has its own file:

- `pressure.xlsx`
- `temperature.xlsx`
- `electrical.xlsx`
- `weighing.xlsx`
- `mass.xlsx`

If an Excel file is missing or returns non-numeric cell values, the engine falls back to the corresponding JSON file in the same directory. The JSON files must be kept in sync with the Excel files.

## API

All endpoints require a valid Supabase JWT in the `Authorization: Bearer <token>` header except `GET /health`.

Full interactive API documentation is available at `http://127.0.0.1:8000/docs` when the backend is running.

## Deployment

### Frontend (Vercel)

1. Connect the GitHub repository to Vercel
2. Set the root directory to `frontend`
3. Add environment variables in the Vercel dashboard
4. Deploy

### Backend (Railway)

1. Connect the GitHub repository to Railway
2. Set the root directory to `backend`
3. Add environment variables in the Railway dashboard
4. Set the start command to `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Deploy

After deploying the backend, add the Vercel production URL to the `origins` list in `backend/main.py` and redeploy.

## Important Rules for Developers

- All database access goes through functions in `database.py`. No raw SQL anywhere else.
- All API calls from the frontend go through `api.js`. No fetch calls inside components.
- CORS is configured in `main.py` only.
- Authentication uses Supabase Auth and JWT verification in `auth.py` only.
- All sensitive values come from environment variables via `config.py`. Nothing hardcoded.
- Every Python function must have a Google-style docstring with Args, Returns, and Raises.
- Every React component must have a JSDoc comment.

## License

Private. All rights reserved. Instruworks LLC FZ.
