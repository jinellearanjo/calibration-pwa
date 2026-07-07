-- Adds the master instrument's OWN calibration certificate number.
--
-- Previously master_instruments had no column for this, so the "Certificate
-- No." row in the Reference / Master Instrument section of every generated
-- certificate rendered blank rather than a fabricated value (documented as
-- a known gap in the handover doc, Section 4). This migration closes that
-- gap; nullable so existing rows and any master instrument without a known
-- certificate number stay valid.
--
-- Run this once in the Supabase SQL editor (Project > SQL Editor > New query),
-- the same way the weighing_* / temperature_* tables were added earlier in
-- this project - there is no migration-runner script in this repo, these
-- are tracked here for reference and applied manually.

ALTER TABLE master_instruments
  ADD COLUMN IF NOT EXISTS master_certificate_number text;

COMMENT ON COLUMN master_instruments.master_certificate_number IS
  'The master instrument''s own calibration certificate number, as issued by whichever lab calibrated it (e.g. PROCAL). Distinct from calibration_reference.certificate_number, which is this app''s own certificate for the instrument under test.';
