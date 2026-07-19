-- Adds role-based access control and the exception-based report review
-- workflow.
--
-- Run this once in the Supabase SQL editor (Project > SQL Editor > New
-- query), the same way every other migration in this folder was applied -
-- there is no migration-runner script in this repo.
--
-- ── Background ─────────────────────────────────────────────────────────────
-- Until now every authenticated user has been treated identically - no
-- concept of who someone is beyond their auth.users row, and nothing in
-- the app is gated by role. This migration introduces:
--   1. profiles - one row per user, storing their real job title (not a
--      generic "role" label - the certificate needs to show the specific
--      title of whoever approved it, e.g. "QM - Approved By").
--   2. role_change_requests - a Viewer's request to be granted a higher-
--      access title, reviewed by a full-edit-tier user.
--   3. Review columns on calibration_sessions - the exception-based report
--      approval workflow: most sessions never touch these (clean pass,
--      certificate generates immediately as before); a session only gets
--      flagged when a master-instrument validity check fails.
--
-- Permission tiers are NOT stored as a separate column - they're derived
-- from title in Python (see backend/auth.py's TITLE_PERMISSION_TIER dict),
-- since the mapping is small and keeping it in one place in code (rather
-- than duplicated in a DB CHECK constraint) makes it easier to change.
-- profiles.title still has a CHECK constraint listing the known titles, to
-- catch typos at the database level - update both places together if a
-- new title is ever added.

-- ── profiles ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name text,
  title text NOT NULL DEFAULT 'Viewer'
    CHECK (title IN ('QM', 'TM', 'MR', 'MD', 'Cal Tech', 'Engineer', 'Admin', 'Lab Staff', 'Viewer')),
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE profiles IS
  'One row per user (mirrors auth.users). Stores the real job title selected at sign-up, which both drives permission-tier checks in the backend (see auth.py) and is displayed verbatim on certificates (e.g. "Approved By: J. Smith, QM"). Created automatically by the handle_new_user trigger below, not by the application.';
COMMENT ON COLUMN profiles.title IS
  'The user''s actual job title, self-selected at sign-up for now (a safer admin-assigned model is deferred future work). Maps to a permission tier in backend/auth.py: QM/TM/MR/MD -> full edit access; Cal Tech/Engineer/Admin/Lab Staff -> certificate-creation access; Viewer -> read-only.';

-- Auto-create a profile row whenever someone signs up, reading the name/
-- title passed into Supabase Auth's signUp() call via options.data. This
-- runs as the table owner (SECURITY DEFINER via the trigger), so it works
-- regardless of what RLS is later configured on profiles - the alternative
-- (inserting the profile client-side right after signUp() succeeds) is
-- less reliable, since it can be left half-finished if the tab closes or
-- the request fails between the two steps.
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  requested_title text := NEW.raw_user_meta_data ->> 'title';
BEGIN
  INSERT INTO public.profiles (id, full_name, title)
  VALUES (
    NEW.id,
    NEW.raw_user_meta_data ->> 'full_name',
    CASE
      WHEN requested_title IN ('QM', 'TM', 'MR', 'MD', 'Cal Tech', 'Engineer', 'Admin', 'Lab Staff', 'Viewer')
        THEN requested_title
      ELSE 'Viewer'
    END
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ── role_change_requests ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS role_change_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  requested_title text NOT NULL
    CHECK (requested_title IN ('QM', 'TM', 'MR', 'MD', 'Cal Tech', 'Engineer', 'Admin', 'Lab Staff')),
  reason text,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied')),
  reviewed_by uuid REFERENCES auth.users(id),
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE role_change_requests IS
  'A user requesting a higher-access title (most commonly a Viewer requesting Cal Tech/Engineer/etc., but not restricted to that direction). Denied requests can be resubmitted - there is no unique constraint blocking a new pending request after a prior denial, only ever one pending request at a time is enforced in application code (see database.py), not here.';

-- ── Session review workflow ────────────────────────────────────────────────
-- Exception-based: the vast majority of sessions never touch these columns.
-- review_status defaults to 'clean', meaning certificate generation proceeds
-- immediately with no approval step, exactly like before this migration.
-- A session only moves to 'pending_review' when a master-instrument
-- validity check fails at calculation/report time (expired cal_due_date,
-- missing/TBA critical values, etc. - see validation.py). A full-edit-tier
-- user then approves or rejects it; review_note carries the reason either
-- way (why it was flagged, and/or why it was rejected) so the person who
-- ran the calibration knows exactly what to fix.

ALTER TABLE calibration_sessions
  ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'clean'
    CHECK (review_status IN ('clean', 'pending_review', 'approved', 'rejected')),
  ADD COLUMN IF NOT EXISTS review_note text,
  ADD COLUMN IF NOT EXISTS reviewed_by uuid REFERENCES auth.users(id),
  ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;

COMMENT ON COLUMN calibration_sessions.review_status IS
  '''clean'' (default): no issue found, certificate generates immediately, same as before this migration existed. ''pending_review'': a master-instrument validity check failed - certificate generation is held until a full-edit-tier user (QM/TM/MR/MD) approves or rejects. ''approved''/''rejected'': the outcome of that review; review_note explains why in either the pending or rejected state.';

-- ── RLS ──────────────────────────────────────────────────────────────────
-- NOTE: exactly like every other migration in this folder, these are a
-- reasonable starting point, NOT verified against the live project - this
-- project's own history (see the RLS section of the Phase 2 handover doc)
-- shows guessed RLS SQL has been wrong twice before until checked against
-- an actual screenshot of a working policy on a similar table. Check these
-- against the Supabase dashboard after applying, the same way.
--
-- Consistent with this app's established architecture ("all database
-- access goes through database.py"), writes to profiles and
-- role_change_requests are intended to go through the FastAPI backend
-- (using the service-role key, which bypasses RLS entirely) rather than
-- directly from the frontend - the frontend's Supabase client is only ever
-- used for auth (sign in/up/out), never direct table access. RLS here is
-- deliberately conservative (read-heavy, write-locked-down) as a backstop,
-- not the primary enforcement mechanism - auth.py's require_tier
-- dependency is.

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_change_requests ENABLE ROW LEVEL SECURITY;

-- Any authenticated user can read every profile - needed so a full-edit
-- user can see who's requesting access, and so the "carried out by /
-- approved by" fields can be resolved to a name+title anywhere in the app.
-- Matches the precedent already set for master_instruments (shared lab
-- assets, not gated per-user).
CREATE POLICY "profiles_select_all_authenticated" ON profiles
  FOR SELECT TO authenticated USING (true);

-- No direct INSERT/UPDATE/DELETE for regular authenticated users - profile
-- creation is the trigger's job (which runs as SECURITY DEFINER, bypassing
-- RLS), and profile edits (name changes, title changes via an approved
-- request) go through backend endpoints using the service-role key.

CREATE POLICY "role_change_requests_select_own_or_reviewer" ON role_change_requests
  FOR SELECT TO authenticated
  USING (
    user_id = auth.uid()
    OR EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND title IN ('QM', 'TM', 'MR', 'MD'))
  );

-- No direct INSERT/UPDATE for regular authenticated users - submitting a
-- request and approving/denying one both go through backend endpoints.
