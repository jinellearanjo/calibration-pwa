# Contributing

This document explains how the codebase is organised and what the rules are for making changes. Read this before touching any file.

## File Ownership

Each person owns specific files. Do not modify files outside your list without talking to the architecture lead (P1) first.

| Person | Role | Files |
|---|---|---|
| P1 | Architecture Lead | `backend/main.py`, `backend/config.py`, `backend/database.py`, `backend/auth.py`, `backend/models.py`, `frontend/src/App.js`, `frontend/src/index.js`, `frontend/src/api.js`, `frontend/src/auth.js`, `frontend/src/components/Navbar.jsx`, `frontend/src/components/ProtectedRoute.jsx`, `frontend/src/pages/Login.jsx`, `frontend/src/pages/Dashboard.jsx` |
| P2 | Data Entry | `frontend/src/pages/InstrumentForm.jsx`, `frontend/src/pages/SessionForm.jsx`, `frontend/src/pages/ReadingsForm.jsx`, `frontend/src/pages/MasterForm.jsx` |
| P3 | Calculation Engine | `backend/modules/calculation_engine.py`, `backend/modules/formula_manager.py`, `frontend/src/pages/CalculationView.jsx`, `backend/formulas/*.json` |
| P4 | Validation | `backend/modules/validation.py`, `frontend/src/pages/ResultsView.jsx`, `frontend/src/components/StatusBadge.jsx` |
| P5 | Reporting | `backend/modules/reporting.py`, `frontend/src/pages/ReportPage.jsx` |

## Non-Negotiable Rules

**Database access**
All database queries go through functions in `database.py`. No raw SQL or direct Supabase calls anywhere else in the codebase. If you need a new query, add a function to `database.py` and ask P1 to review it.

**API calls from frontend**
All fetch calls go through `api.js`. No inline fetch calls inside components. If you need a new API call, write the function in `api.js` and import it in your component.

**FastAPI endpoints**
All endpoints live in `main.py`. If your module needs an endpoint, write it as a clearly labelled snippet and pass it to P1 to add to `main.py`. Do not write endpoints anywhere else.

**CORS**
Configured in `main.py` only. Do not add CORS headers anywhere else.

**Authentication**
Uses Supabase Auth and JWT verification in `auth.py` only. Do not build a custom login system or add auth logic elsewhere.

**Environment variables**
All sensitive values come from environment variables via `config.py`. Never hardcode API keys, URLs, or secrets anywhere in the code.

**Pydantic models**
All request body validation models live in `models.py`. Do not define Pydantic models inside endpoint functions.

## Code Standards

**Python**
Every function must have a Google-style docstring:

```python
def my_function(arg1: str, arg2: float) -> dict:
    """One line summary.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2.

    Returns:
        dict: Description of return value.

    Raises:
        ValueError: When arg1 is empty.
    """
```

Inline comments must explain why, not what. No single-letter variable names outside loop indices. No hardcoded values.

**React**
Every component must have a JSDoc comment:

```javascript
/**
 * MyComponent description.
 *
 * @param {Object} props
 * @param {string} props.value - Description.
 */
function MyComponent({ value }) {
```

Inline comments must explain why, not what. No single-letter variable names outside loop indices. No fetch calls inside components.

**Calculation engine specifically**
Every line of uncertainty mathematics must have an inline comment citing the GUM equation number or section. Example:

```python
u_res = resolution / (2 * math.sqrt(3))  # GUM section 4.3.7, rectangular distribution
```

## What To Do When You Need Something From Another Person

If your module needs a database function that does not exist yet, describe what you need and ask P1 to add it to `database.py`.

If your module needs a FastAPI endpoint, write the full endpoint function as a snippet with a comment identifying it, and pass it to P1 to add to `main.py`.

If your frontend component needs a new API call, write the fetch function as a snippet and pass it to P1 to add to `api.js`.

Do not add these yourself to files you do not own.

## Git Workflow

Always pull before you start working:

```bash
git pull origin main
```

Commit messages should be descriptive:

```bash
git commit -m "add calculate_u_res function to calculation_engine.py"
```

Push to main directly for now (no branches). If you get a rejected push it means someone else pushed while you were working. Run `git pull origin main` first then push again.

Never commit `.env` files. They are in `.gitignore` for a reason.

## Validation Status Values

The only permitted status values are exactly: `ACCEPTED`, `REVIEW REQUIRED`, `REJECTED`. No other values. These are used in `validation.py`, `StatusBadge.jsx`, `ResultsView.jsx`, and `ReportPage.jsx`. Do not change or add status values without updating all four files.

## Report Generation Rules

Report generation is blocked for sessions with status `REJECTED`. This check happens in `gather_report_data` in `reporting.py` and must not be bypassed. Report files are never stored on the server — they are generated, streamed to the client, and deleted immediately.

## Formula Files

The `backend/formulas/` directory contains Excel files (provided by the supervisor) and JSON fallback files. The JSON files are used when an Excel file is missing or returns non-numeric values. When Excel files are updated, the corresponding JSON fallback files must also be updated to match.

Do not commit the Excel files if they contain confidential calibration data. Check with the architecture lead first.