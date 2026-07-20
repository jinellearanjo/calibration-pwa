-- Extends profiles (added in 2026-07-19_roles_and_review_workflow.sql)
-- with additional sign-up fields and account deactivation.
--
-- Run this once in the Supabase SQL editor, after the roles migration.
--
-- ── Background ─────────────────────────────────────────────────────────────
-- "Role" (a broad grouping like Management/Technician/Viewer) is
-- deliberately NOT a new column here - it's purely a frontend UX device
-- to narrow down the 9-option title picker into two shorter steps
-- (Role, then Job Title). The value actually stored and used everywhere
-- (permissions, certificate display) is still profiles.title, unchanged
-- from the previous migration.
--
-- "Delete account" is implemented as deactivation, not a real DELETE.
-- A true delete of the auth.users row was deliberately avoided: this
-- app's instruments/calibration_sessions/master_instruments tables (and
-- others) were mostly hand-created in the Supabase dashboard before this
-- repo's migrations folder existed, so their user_id foreign keys' delete
-- behavior (cascade vs restrict vs no constraint at all) can't be
-- confirmed from code - check the live schema before ever attempting a
-- real delete. Deactivation avoids that risk entirely: historical
-- calibration data and the profile itself stay intact and attributable,
-- only the ability to log in and act is revoked.

ALTER TABLE profiles
  ADD COLUMN IF NOT EXISTS employee_id text,
  ADD COLUMN IF NOT EXISTS site_location text,
  ADD COLUMN IF NOT EXISTS department text,
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN profiles.employee_id IS 'Employee ID / payroll number, free text, display-only - not used in any permission or business logic.';
COMMENT ON COLUMN profiles.site_location IS 'Site/facility location, free text, display-only.';
COMMENT ON COLUMN profiles.department IS 'Assigned lab/department, free text, display-only.';
COMMENT ON COLUMN profiles.is_active IS
  'false means the account is deactivated - auth.get_current_user_id rejects every request from a deactivated user with a 403, regardless of which endpoint. Historical data (sessions, instruments, certificates) they created is completely unaffected; only their own ability to act is revoked. Reactivating flips this back to true - nothing else needs to change.';

-- Extend the sign-up trigger to also capture the new fields from
-- Supabase Auth's signUp() options.data. CREATE OR REPLACE is safe to
-- re-run - this fully replaces the function body from the previous
-- migration, it doesn't need dropping first.
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  requested_title text := NEW.raw_user_meta_data ->> 'title';
BEGIN
  INSERT INTO public.profiles (id, full_name, title, employee_id, site_location, department)
  VALUES (
    NEW.id,
    NEW.raw_user_meta_data ->> 'full_name',
    CASE
      WHEN requested_title IN ('QM', 'TM', 'MR', 'MD', 'Cal Tech', 'Engineer', 'Admin', 'Lab Staff', 'Viewer')
        THEN requested_title
      ELSE 'Viewer'
    END,
    NEW.raw_user_meta_data ->> 'employee_id',
    NEW.raw_user_meta_data ->> 'site_location',
    NEW.raw_user_meta_data ->> 'department'
  );
  RETURN NEW;
END;
$$;
-- Trigger itself (on_auth_user_created) already exists from the previous
-- migration and doesn't need recreating - it points at this function by
-- name, and CREATE OR REPLACE FUNCTION updates the body in place.
