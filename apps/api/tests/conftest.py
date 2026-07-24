# Env must be set before app.config's cached Settings is first constructed.
import os

os.environ.setdefault("INTERNAL_HMAC_SECRET", "test-secret")
os.environ.setdefault("CLERK_AUTH_DISABLED", "1")
os.environ.setdefault("DATABASE_URL", "")  # unit tests never touch a DB
