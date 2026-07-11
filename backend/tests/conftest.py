"""tests/conftest.py

Sets dummy Supabase credentials before any test module imports database.py
or main.py, so `pytest` works out of the box with no manual environment
setup. Safe because database.py's supabase client is lazy (see
database._LazySupabaseClient) - these dummy values are never actually used
to make a real network call, since every test in this suite mocks the
relevant database.py/validation.py functions directly rather than hitting
a real Supabase instance.
"""

import os

os.environ.setdefault("SUPABASE_URL", "https://dummy-test-project.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "dummy-test-key-not-a-real-secret")
