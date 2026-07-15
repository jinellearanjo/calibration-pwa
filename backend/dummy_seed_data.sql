-- ─────────────────────────────────────────────────────────────────────────────
-- Dummy seed data for local testing
-- Run in Supabase SQL Editor
-- Replace <ANY_REAL_USER_ID> with any one real Supabase auth user's UUID
-- Find one: Supabase dashboard → Authentication → Users → copy any UUID
-- ─────────────────────────────────────────────────────────────────────────────
-- master_instruments.user_id has a genuine FOREIGN KEY constraint to
-- auth.users(id) - confirmed the hard way: a fixed sentinel UUID like
-- 00000000-0000-0000-0000-000000000001 fails with
-- "insert or update on table master_instruments violates foreign key
-- constraint master_instruments_user_id_fkey" because that UUID isn't a
-- real row in auth.users. So this MUST be a real user's UUID, not a
-- made-up placeholder value.
--
-- The good news: it can be ANY real user's UUID, not specifically yours,
-- and not one-per-team-member either. master_instruments.user_id no
-- longer gates visibility - GET /api/master-instruments doesn't filter
-- by it (see main.py's list_master_instruments), and the table's RLS
-- SELECT policy ("Authenticated users can read masters") checks
-- auth.role() = 'authenticated', not auth.uid() = user_id. So pick any
-- one real user (e.g. yours), paste that single UUID below, and every
-- authenticated user - including everyone else on the team - will see
-- these seeded rows regardless of whose UUID ended up recorded here.
--
-- user_id is still recorded purely as an audit trail of who's associated
-- with each row's creation (see create_master_instrument's docstring) -
-- it's fine for that trail to point at whichever real user ran this
-- seed script, even for rows meant to represent shared lab assets.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Master Instruments ────────────────────────────────────────────────────────
INSERT INTO master_instruments (
  user_id, name, make, model, serial_number, asset_number,
  traceability_chain, uncertainty_u, accuracy, resolution,
  cal_due_date, claimed_cmc, instrument_type, master_certificate_number
) VALUES
-- Pressure
(
  '514b9812-7e5b-4c42-950f-17a7013f3c89',
  'WIKA CPH6000 Pressure Controller',
  'WIKA', 'CPH6000', 'WK-2021-4471', 'MI-P-001',
  'WIKA Germany → PTB → BIPM',
  0.005, 0.01, 0.001,
  '2027-01-01', 0.012,
  'Pressure', 'WIKA-CERT-2026-0042'
),
-- Weighing
(
  '514b9812-7e5b-4c42-950f-17a7013f3c89',
  'Mettler Toledo Standard Weights Set',
  'Mettler Toledo', 'OIML Class E2', 'MT-E2-2019-0088', 'MI-W-001',
  'Mettler Toledo → SASO → BIPM',
  0.002, 0.005, 0.001,
  '2027-01-01', 0.008,
  'Weighing', 'MT-CERT-2026-0017'
),
-- Temperature
(
  '514b9812-7e5b-4c42-950f-17a7013f3c89',
  'Fluke 1523 Reference Thermometer',
  'Fluke', '1523', 'FL-1523-2020-0334', 'MI-T-001',
  'Fluke USA → NIST → BIPM',
  0.015, 0.02, 0.001,
  '2027-01-01', 0.05,
  'Temperature', 'FLUKE-CERT-2026-0091'
),
-- Electrical
(
  '514b9812-7e5b-4c42-950f-17a7013f3c89',
  'Fluke 5522A Multi-Product Calibrator',
  'Fluke', '5522A', 'FL-5522-2019-0771', 'MI-E-001',
  'Fluke USA → NIST → BIPM',
  0.003, 0.005, 0.001,
  '2027-01-01', 0.01,
  'Electrical', 'FLUKE-CERT-2026-0055'
);

-- ── CMC Bands ─────────────────────────────────────────────────────────────────
-- Pressure and Weighing use range-dependent CMC lookup.
-- Temperature and Electrical use claimed_cmc from master_instruments directly.
INSERT INTO cmc_bands (
  instrument_type, min_value, max_value, unit, cmc_value, cmc_unit, standard_ref
) VALUES
-- Pressure bands (bar) — three ranges covering 0–10 bar
-- Values are plausible dummies; replace with real Instruworks CMC data when available
('Pressure', 0,    2,    'bar', 0.006,  'bar', 'DUMMY-DO-NOT-CERTIFY'),
('Pressure', 2,    6,    'bar', 0.010,  'bar', 'DUMMY-DO-NOT-CERTIFY'),
('Pressure', 6,    10,   'bar', 0.015,  'bar', 'DUMMY-DO-NOT-CERTIFY'),
-- Weighing bands (g) — three ranges covering 0–3100g
-- Values are plausible dummies; replace with real Instruworks CMC data when available
('Weighing', 0,    100,  'g',   0.005,  'g',   'DUMMY-DO-NOT-CERTIFY'),
('Weighing', 100,  1550, 'g',   0.008,  'g',   'DUMMY-DO-NOT-CERTIFY'),
('Weighing', 1550, 3100, 'g',   0.012,  'g',   'DUMMY-DO-NOT-CERTIFY');

-- ── Acceptance Limits ─────────────────────────────────────────────────────────
-- Used by validation.py to assign ACCEPTED / REVIEW REQUIRED / REJECTED.
-- These are plausible dummies — confirm real limits with Eng. Charkha.
INSERT INTO acceptance_limits (
  instrument_type, parameter, limit_value
) VALUES
('Pressure',    'accuracy', 0.1),
('Weighing',    'accuracy', 0.05),
('Temperature', 'accuracy', 0.2),
('Electrical',  'accuracy', 0.1);