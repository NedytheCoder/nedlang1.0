"""Who is this request?

Rule 7 asks for one entry point for identity. `current_user_id` is it. Nothing
else in the backend should read the Authorization header, and nothing else
should decide who a caller is.

It answers with this application's own `users.id` — never Clerk's. The two are
different strings and the difference matters: every policy in schema.sql
compares against `users.id`, so returning Clerk's `sub` here would match no rows
at all. The learner would sign in successfully and see an empty account, with
nothing in the logs. That is exactly the failure this project keeps finding.

What this module deliberately does NOT do: create a user. A verified token with
no row behind it means a deleted account or an unfinished signup, and the honest
answer to both is 401. Signup writes that row; authentication only reads it.
"""

from __future__ import annotations

import hmac
import os
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from dotenv import load_dotenv
from fastapi import HTTPException, Request

from app.db import cursor

load_dotenv()

# Test tokens carry this prefix so they can never be mistaken for a Clerk JWT,
# in either direction. A JWT starts "eyJ"; this does not.
_TEST_PREFIX = "nltest."


def _secret() -> str:
    """The Clerk secret key, resolved at call time so a missing variable fails
    on the first request rather than at import."""
    key = os.getenv("CLERK_SECRET_KEY")
    if not key:
        raise RuntimeError("Set CLERK_SECRET_KEY in .env")
    return key


def _development() -> bool:
    """Whether this process is talking to a Clerk development instance.

    Live keys carry the sk_live_ prefix, so this is a property of the
    credentials themselves, not of a DEBUG flag someone can leave switched on.
    """
    return _secret().startswith("sk_test_")


# ── the Clerk client ───────────────────────────────────────────────────────────
# Built once and kept, because it caches Clerk's signing keys; rebuilding it per
# request would refetch them. Built lazily rather than at import, so importing
# this module still touches no network — same rule as app/db.py.
_clerk: Clerk | None = None


def _clerk_client() -> Clerk:
    global _clerk
    if _clerk is None:
        _clerk = Clerk(bearer_auth=_secret())
    return _clerk


def _authorized_parties() -> list[str] | None:
    """Which origins may present a token to us.

    Without this, a token Clerk minted for some other site that shares our Clerk
    instance is accepted here too. None means "don't check" — acceptable while
    the only caller is localhost, and worth setting before deploy.
    """
    raw = os.getenv("ALLOWED_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip()] or None


# ── test tokens ────────────────────────────────────────────────────────────────

def mint_test_token(clerk_id: str) -> str:
    """A token that the verification path below accepts. Tests only.

    silent_tests.py mints these so the suite exercises the real verification
    path instead of monkeypatching past it. Clerk cannot issue a session token
    offline, so something local has to stand in.

    It is signed with CLERK_SECRET_KEY rather than a secret of its own. That is
    the point: anyone holding that key can already impersonate any learner
    through Clerk's API, so the ability to mint one of these grants nothing they
    did not already have — and there is no second secret to leak, rotate, or
    forget to set.
    """
    if not _development():
        raise RuntimeError("mint_test_token is for Clerk development instances only")
    body = urlsafe_b64encode(clerk_id.encode()).decode().rstrip("=")
    return f"{_TEST_PREFIX}{body}.{_sign(body)}"


def _sign(body: str) -> str:
    return hmac.new(_secret().encode(), body.encode(), sha256).hexdigest()


def _clerk_id_from_test_token(token: str) -> str | None:
    """The clerk_id inside a test token, or None if it isn't a valid one.

    Returns None rather than raising on a live instance, so the whole test-token
    path simply does not exist in production: an "nltest." token presented there
    is refused here and never reaches Clerk. Measured — minting raises, and a
    token minted on the development key gets a 401 once the key is a live one.
    """
    if not _development():
        return None
    try:
        body, signature = token[len(_TEST_PREFIX):].split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(body)):
        return None
    return urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()


# ── verification ───────────────────────────────────────────────────────────────

def _clerk_id(request: Request) -> str | None:
    """The Clerk user id behind this request, or None if there isn't a valid one.

    Every "no" is the same None: no header, wrong scheme, empty token, forged
    signature, expired session. The caller turns all of them into one 401,
    because telling an anonymous caller *which* part failed tells an attacker
    which part to fix.
    """
    header = request.headers.get("authorization", "")
    if header[:7].lower() != "bearer ":
        return None
    token = header[7:].strip()
    if not token:
        return None

    if token.startswith(_TEST_PREFIX):
        return _clerk_id_from_test_token(token)

    state = _clerk_client().authenticate_request(
        request,
        AuthenticateRequestOptions(authorized_parties=_authorized_parties()),
    )
    if not state.is_signed_in or not state.payload:
        return None
    return state.payload.get("sub")


def current_clerk_id(request: Request) -> str:
    """The verified Clerk id behind this request. Raises 401 if there isn't one.

    This is not a second entry point for identity. Rule 7 forbids that, and both
    this function and `current_user_id` below get their answer from the same
    `_clerk_id` — the one place that reads the header and checks the signature.
    What differs is only which of the two ids the caller is handed.

    Almost nothing should want this one. It exists for signup, where there is by
    definition no `users.id` yet, so asking for one would be asking the very
    question signup is there to answer. Every other route wants the function
    below.
    """
    clerk_id = _clerk_id(request)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return clerk_id


def clerk_email(clerk_id: str) -> str:
    """This learner's primary email address, read from Clerk.

    Asked of Clerk rather than believed from the browser. The difference is not
    theoretical: this is the address the reminder in product.md S2 gets sent to,
    so a client that could choose it could make us mail a stranger. Read once,
    when the row is created — never on a request path.
    """
    account = _clerk_client().users.get(user_id=clerk_id)
    for address in account.email_addresses or []:
        if address.id == account.primary_email_address_id:
            return address.email_address
    raise HTTPException(status_code=400, detail="This account has no email address.")


def current_user_id(request: Request) -> str:
    """This request's `users.id`. Raises 401 if there isn't one.

    Use it as a FastAPI dependency:

        @app.get("/today")
        def today(user_id: str = Depends(current_user_id)): ...

    The lookup goes through app_resolve_user() rather than a plain SELECT. It
    has to: users_self hides a row until you already know the id, which is the
    one thing this function does not yet know. See the note in schema.sql.
    """
    clerk_id = current_clerk_id(request)

    with cursor() as cur:
        cur.execute("SELECT app_resolve_user(%s)", (clerk_id,))
        row = cur.fetchone()

    user_id = row[0] if row else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user_id


# Next, once there is a route: the caller still has to announce this id to
# Postgres before any query, or every policy in schema.sql evaluates against
# NULL and returns nothing. The statement is
# `SELECT set_config('app.current_user_id', %s, true)` — not `SET LOCAL`, which
# cannot take a bound parameter under psycopg3. See the note in scripts.py.
# That belongs with the cursor, not here — app/db.py grows a variant that takes
# a user id when the first route needs one. Not built yet, nothing calls it (Rule 1).
