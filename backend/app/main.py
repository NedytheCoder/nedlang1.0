"""The FastAPI application instance.

This module exists so `app.main:app` resolves — it is what uvicorn serves in
production and what `silent_tests.py` imports. Routes arrive with the features
that need them, in the order set by rules.md Rule 10, and are registered here so
there is one place that lists everything the app answers.

Importing this module must not touch the network. Connections live in
`app/db.py` and are opened when a query needs one.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import user

# Loaded here as well as in app/db.py and app/auth.py. Those imports happen
# first, so this is already a no-op today — but _origins() below reads an
# environment variable at module level, and relying on another module's import
# to have populated it is the kind of ordering that breaks when someone sorts
# the imports.
load_dotenv()

app = FastAPI(
    title="NedLang",
    description="One 10-minute French conversation a day.",
    version="0.1.0",
)


def _origins() -> list[str]:
    """Which sites a browser may let talk to this API.

    The frontend runs on a different origin from the backend — a different port
    in development, a different domain in production — so every call it makes is
    cross-origin, and the browser asks our permission before sending one. This
    list is that permission.

    Falls back to the Next dev server. That address means nothing to anyone who
    is not sitting at this machine, so the default grants no stranger anything;
    and a deploy that forgets the variable fails visibly, with the real frontend
    blocked, rather than quietly accepting every origin on the internet.

    Same variable as the one `auth.py` reads for Clerk's authorized_parties,
    because it is the same question — which sites may talk to us — and two
    lists that are supposed to match will not stay matched.
    """
    raw = os.getenv("ALLOWED_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip()] or ["http://localhost:3000"]


# The origin list is the control here; methods and headers deliberately are not.
# Once only our own frontend is allowed to make the request at all, restricting
# which verbs or headers it may use protects nothing further — it only sets a
# trap for the day a GET route ships and fails with an opaque console error.
#
# allow_credentials stays False: this API is authenticated by an Authorization
# header the frontend attaches on purpose, never by a cookie the browser sends
# on its own. Turning it on would ask browsers to do exactly the automatic thing
# we do not want.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
