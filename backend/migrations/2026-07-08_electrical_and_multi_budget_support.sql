-- Adds Electrical's data tables, and makes uncertainty_budgets support
-- MULTIPLE budgets per session (one per Temperature setpoint, one per
-- Electrical function-type/range tested) instead of assuming exactly one
-- budget per session_id.
--
-- Background: Temperature's calculation was previously hard-blocked to a
-- single setpoint per session (see formula_manager.py's old
-- _build_temperature_budget), and Electrical wasn't wired at all, both
-- for the same root reason - uncertainty_budgets had no way to
-- distinguish "the budget for setpoint A" from "the budget for setpoint
-- B" within one session. This migration fixes that at the schema level
-- so both categories can be built on the same foundation.
--
-- Run this once in the Supabase SQL editor, same as the other migration
-- files in this folder - there is no migration-runner script in this repo.

-- ── Electrical: one row per function-type-and-range tested ─────────────────
-- (e.g. a single DMM calibration session might test DCV at 6 different
-- ranges - each range is its own row here, the same way each Temperature
-- setpoint is its own row in temperature_repeatability_tests.)
CREATE TABLE IF NOT EXISTS electrical_tests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES calibration_sessions(id) ON DELETE CASCADE,
  function_type text NOT NULL,       -- 'DCV', 'ACV', 'DCA', 'ACA', 'Resistance',
                                      -- 'Frequency', 'Insulation Resistance',
                                      -- 'Temperature (R,S,B)', 'Temperature (K,J,N,E,T)',
                                      -- 'DCA (Coil)', 'ACA (Coil)' - must match
                                      -- formulas/electrical.json's function_types keys
  range_label text NOT NULL,          -- e.g. '20mV', '200mV', '50A' - human-readable range identifier
  nominal_value numeric,              -- the numeric nominal test point within this range
  unit text NOT NULL,
  cert_uncertainty_limit numeric,     -- Ub1 input: Uncertainty of Standard Calibrator
  calibrator_accuracy_limit numeric,  -- Ub2 input: Accuracy of Standard Calibrator
  resolution numeric,                 -- Ub3 (or Ub4 for Coil types) input: UUC resolution
  thermo_electric_limit numeric,      -- DCV only - nullable for every other function_type
  coil_accuracy_limit numeric,        -- DCA (Coil) / ACA (Coil) only - nullable otherwise
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS electrical_readings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  test_id uuid NOT NULL REFERENCES electrical_tests(id) ON DELETE CASCADE,
  reading_number int NOT NULL,
  reading_value numeric NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ── uncertainty_budgets: support multiple rows per session ──────────────────
-- Two separate nullable FKs (not one polymorphic column - Postgres FKs
-- don't do polymorphic references cleanly). Exactly one of these two is
-- set for a Temperature or Electrical budget row; both stay NULL for
-- Pressure/Weighing, which still get exactly one budget row per session.
ALTER TABLE uncertainty_budgets
  ADD COLUMN IF NOT EXISTS temperature_test_id uuid REFERENCES temperature_repeatability_tests(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS electrical_test_id uuid REFERENCES electrical_tests(id) ON DELETE CASCADE;

-- Electrical's own Type B component fields (u_b1-u_b4), distinct from
-- Pressure/Weighing/Temperature's differently-named component columns -
-- see models.py's UncertaintyBudgetCreate for why these are separate
-- rather than reusing e.g. u_std for u_b1 (Electrical's inputs don't map
-- 1:1 to any existing category's fields - see formulas/electrical.json's
-- anomalies_found for why this mapping is still unconfirmed).
ALTER TABLE uncertainty_budgets
  ADD COLUMN IF NOT EXISTS u_b1 numeric,
  ADD COLUMN IF NOT EXISTS u_b2 numeric,
  ADD COLUMN IF NOT EXISTS u_b3 numeric,
  ADD COLUMN IF NOT EXISTS u_b4 numeric;

-- ── IMPORTANT: check for a UNIQUE constraint on session_id ──────────────────
-- If uncertainty_budgets.session_id currently has a UNIQUE constraint
-- (from when the table assumed one budget per session), it MUST be
-- dropped, or every second budget insert for a multi-setpoint/multi-range
-- session will fail. Run this first to check:
--
--   SELECT conname FROM pg_constraint
--   WHERE conrelid = 'uncertainty_budgets'::regclass AND contype = 'u';
--
-- If that returns a row, drop it (replace CONSTRAINT_NAME with whatever
-- the query above returned):
--
--   ALTER TABLE uncertainty_budgets DROP CONSTRAINT CONSTRAINT_NAME;

-- ── RLS ──────────────────────────────────────────────────────────────────────
-- electrical_tests and electrical_readings need the same Row Level
-- Security policy pattern as weighing_repeatability_tests /
-- temperature_repeatability_tests (scoped to the owning session's
-- user_id). Copy the exact policy definitions from those two tables
-- rather than writing new ones from scratch here - this file doesn't
-- have visibility into your live Supabase policy text to reproduce it
-- exactly, and RLS policies have been applied manually via the SQL
-- editor throughout this project rather than tracked in this repo.
