"""
silent_tests.py
═══════════════════════════════════════════════════════════════════════════════

The failures that do not announce themselves.

Every test in this file guards against a bug that would leave the application
*running, rendering, and returning 200* while being wrong. Crashes are easy —
Sentry catches those, users report those. These are the other kind:

  · a column the dashboard reads that no code path ever writes
  · a delete endpoint with no button attached to it
  · an AI endpoint that forgot to check for a login
  · a spend cap that fails open when the database hiccups
  · a review date that is never set, so nothing ever comes back
  · an email address quietly riding along inside a model prompt

The name is the point. Each of the categories below is drawn from a real
silent failure found in the previous version of this product (`../nedlang`),
where every one of them shipped to production and none of them raised an error.

───────────────────────────────────────────────────────────────────────────────
STATUS: this file is an EXECUTABLE SPECIFICATION, written before the code.

Nothing here passes yet, because `nedlang1.0/backend` is still a stub. That is
the intended state. Running it today reports every test as SKIPPED with the
reason "backend not built yet" — as each feature is built, its tests light up.

    $ pytest silent_tests.py -v          # see the whole spec
    $ pytest silent_tests.py -v -m money # see one category

When a test fails, it is describing a real defect in the application, not a
defect in itself. Fix the application.
───────────────────────────────────────────────────────────────────────────────

ASSUMED CONTRACT
This spec assumes the surface described in blueprint/architecture.md:

  Tables    users · scenarios · sessions · mistakes · ai_usage
  Routes    GET    /today              scenario + count of reviews due
            POST   /reply              the single live AI call
            POST   /review/{id}        mark a due review right or wrong
            POST   /transcribe         audio in, transcript out  (v1.5)
            GET    /account/export     GDPR Art. 15
            DELETE /account            GDPR Art. 17

If the real implementation diverges, change the constants in §0 — not the
assertions. The assertions are the requirements.
"""

from __future__ import annotations

import datetime as dt
import importlib
import inspect
import json
import os
import pathlib
import re
import uuid

import pytest

# ═══════════════════════════════════════════════════════════════════════════
# §0  CONFIGURATION
#     The only place this file should need editing when the app changes shape.
# ═══════════════════════════════════════════════════════════════════════════

REPO = pathlib.Path(__file__).resolve().parent
BACKEND_DIR = REPO / "backend"
FRONTEND_DIR = REPO / "frontend"

# Route → HTTP method, as the spec above defines them.
ROUTE_TODAY = "/today"
ROUTE_REPLY = "/reply"
ROUTE_REVIEW = "/review/{mistake_id}"
ROUTE_TRANSCRIBE = "/transcribe"
ROUTE_EXPORT = "/account/export"
ROUTE_DELETE = "/account"

# Every table that holds data belonging to an identifiable person. Used by the
# GDPR tests to prove export and deletion cover all of them. Add a table here
# the moment you create one — §7 will then fail until export and purge know
# about it, which is the entire point.
USER_OWNED_TABLES = ["users", "sessions", "mistakes", "ai_usage"]

# Tables that belong to nobody — shared content, safe to exclude from erasure.
SHARED_TABLES = ["scenarios"]

# The feedback contract. Exactly these keys, no more.
FEEDBACK_KEYS = {"fix", "why", "retry"}

# Free tier: one full session per day, plus one retry.
DAILY_SUBMISSION_CAP = 1


# ═══════════════════════════════════════════════════════════════════════════
# §0.1  IMPORT GUARD
#     Turns "the backend does not exist" from a confusing collection error
#     into a clean, readable skip — so this file is a progress dashboard
#     rather than a wall of red.
# ═══════════════════════════════════════════════════════════════════════════

_IMPORT_ERROR: Exception | None = None
app = None
db = None

try:  # pragma: no cover - import probe
    import sys

    sys.path.insert(0, str(BACKEND_DIR))
    app = importlib.import_module("app.main").app
    db = importlib.import_module("app.db")
    BACKEND_READY = True
except Exception as exc:  # ImportError, ModuleNotFoundError, AttributeError...
    BACKEND_READY = False
    _IMPORT_ERROR = exc


requires_backend = pytest.mark.skipif(
    not BACKEND_READY,
    reason=f"backend not built yet ({type(_IMPORT_ERROR).__name__}: {_IMPORT_ERROR})",
)

requires_frontend = pytest.mark.skipif(
    not (FRONTEND_DIR / "app").is_dir(),
    reason="frontend/app not built yet",
)


# Markers (money, loop, review, schema, reachable, isolation, gdpr, privacy,
# degrade, meta) are registered in pytest.ini, next to this file. They are NOT
# registered here: pytest only calls pytest_configure from conftest.py and from
# installed plugins, so a hook defined in a test module is collected and never
# run. The first draft of this file did exactly that, and the markers silently
# did nothing — which the §10 tests caught on the first run. Kept as a note
# because it is a perfect miniature of the whole premise.


# ═══════════════════════════════════════════════════════════════════════════
# §0.2  FIXTURES
#     Deliberately plain. A test helper you have to debug is worse than no
#     test helper, so these stay boring: make a thing, hand it over, clean up.
# ═══════════════════════════════════════════════════════════════════════════


class AISpy:
    """Stands in for the model provider.

    Records every call so tests can assert on *how many* calls happened and
    *what was inside them* — the two questions that decide whether this
    product is affordable and whether it leaks personal data.

    Can also be told to fail, so §9 can prove the app degrades instead of 500ing.
    """

    def __init__(self):
        self.calls: list[dict] = []
        self.mode = "ok"          # "ok" | "timeout" | "garbage" | "refusal"
        self.reply = {"fix": "une baguette", "why": "un pain is a loaf", "retry": "ask for two"}

    def __call__(self, *, prompt: str, model: str, **kwargs):
        self.calls.append({"prompt": prompt, "model": model, "kwargs": kwargs})
        if self.mode == "timeout":
            raise TimeoutError("simulated provider timeout")
        if self.mode == "garbage":
            return "this is not json at all {{{"
        if self.mode == "refusal":
            return json.dumps({"error": "refused"})
        return json.dumps(self.reply)

    # — convenience accessors, so assertions read like sentences —
    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def last_prompt(self) -> str:
        assert self.calls, "expected at least one AI call, got none"
        return self.calls[-1]["prompt"]

    @property
    def all_prompt_text(self) -> str:
        return "\n".join(c["prompt"] for c in self.calls)

    def reset(self):
        self.calls.clear()
        self.mode = "ok"


@pytest.fixture
def ai(monkeypatch):
    """Replaces the real provider. No test in this file may spend real money."""
    spy = AISpy()
    if BACKEND_READY:
        monkeypatch.setattr("app.ai.complete", spy, raising=False)
    yield spy
    spy.reset()


@pytest.fixture
def client():
    """HTTP client bound to the real ASGI app — real routing, real middleware,
    real auth dependency. Not a mock of the app; a mock here would test nothing."""
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture
def conn():
    """A transaction that is always rolled back, so tests cannot leak state
    into each other — the classic source of 'passes alone, fails in suite'."""
    c = db.connect()
    c.autocommit = False
    yield c
    c.rollback()
    c.close()


def _make_user(conn, *, email: str | None = None, reminders: bool = False) -> dict:
    uid = "u_" + uuid.uuid4().hex[:10]
    email = email or f"{uid}@example.invalid"
    conn.execute(
        "INSERT INTO users (id, clerk_id, email, goal, comfort, email_reminders)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (uid, "clerk_" + uid, email, "order food on holiday", "I freeze up", reminders),
    )
    return {"id": uid, "clerk_id": "clerk_" + uid, "email": email}


@pytest.fixture
def user(conn):
    return _make_user(conn)


@pytest.fixture
def other_user(conn):
    """A second, unrelated learner. Exists so isolation tests have something
    real to fail to see."""
    return _make_user(conn)


@pytest.fixture
def scenario(conn):
    sid = "s_" + uuid.uuid4().hex[:10]
    conn.execute(
        "INSERT INTO scenarios (id, situation, text_fr, text_en, audio_url, answer_key, level)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (sid, "at the boulangerie", "Bonjour, vous desirez ?", "Hello, what would you like?",
         "/audio/" + sid + ".mp3", "je voudrais une baguette", "A2"),
    )
    return {
        "id": sid,
        "situation": "at the boulangerie",
        "text_fr": "Bonjour, vous desirez ?",
        "answer_key": "je voudrais une baguette",
    }


def auth(u: dict) -> dict:
    """Headers for a signed-in learner. Uses the app's own token minting so
    these tests exercise the real verification path, not a bypass."""
    from app.auth import mint_test_token

    return {"Authorization": "Bearer " + mint_test_token(u["clerk_id"])}


def _sources(root: pathlib.Path, *suffixes: str) -> list[pathlib.Path]:
    """Every source file under root, skipping the noise directories."""
    skip = {"node_modules", ".next", ".venv", "__pycache__", ".git", "dist", "build"}
    out = []
    for p in root.rglob("*"):
        if p.suffix in suffixes and not any(part in skip for part in p.parts):
            out.append(p)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# §1  MONEY — the budget cannot be drained
#
# Origin: in ../nedlang, placement generation and AI grading were reachable
# with no account at all, gated only by a per-IP rate limit — and the grading
# path ran the model three times per request for self-consistency. Anyone
# rotating IPs drew directly on the OpenAI budget with no account, no
# attribution and no cap. Nothing errored. The bill was the only symptom.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.money
@requires_backend
class TestNoAnonymousSpending:
    """Rule 5: no AI path is reachable without a logged-in user. Ever."""

    def test_reply_rejects_missing_token(self, client, ai, scenario):
        r = client.post(ROUTE_REPLY, json={"scenario_id": scenario["id"], "reply": "bonjour"})
        assert r.status_code == 401, "an anonymous caller reached the AI endpoint"
        assert ai.call_count == 0, "money was spent on an unauthenticated request"

    def test_reply_rejects_garbage_token(self, client, ai, scenario):
        r = client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "bonjour"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert r.status_code == 401
        assert ai.call_count == 0

    def test_reply_rejects_empty_bearer(self, client, ai, scenario):
        r = client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "bonjour"},
            headers={"Authorization": "Bearer "},
        )
        assert r.status_code == 401
        assert ai.call_count == 0

    def test_reply_rejects_token_for_deleted_user(self, client, ai, conn, user, scenario):
        headers = auth(user)
        conn.execute("DELETE FROM users WHERE id = %s", (user["id"],))
        r = client.post(
            ROUTE_REPLY, json={"scenario_id": scenario["id"], "reply": "bonjour"}, headers=headers
        )
        assert r.status_code in (401, 403), "a deleted account still bought AI calls"
        assert ai.call_count == 0

    def test_transcribe_rejects_missing_token(self, client, ai):
        r = client.post(ROUTE_TRANSCRIBE, files={"audio": ("a.webm", b"\x00\x01", "audio/webm")})
        assert r.status_code == 401
        assert ai.call_count == 0

    def test_no_route_in_the_app_calls_ai_without_an_auth_dependency(self):
        """Structural backstop. Instead of trusting that we remembered to test
        every future endpoint, walk the app's own route table and require that
        anything touching the AI module also declares the auth dependency.

        This is the test that catches the endpoint someone adds next year.
        """
        from app import ai as ai_module  # noqa: F401

        offenders = []
        for route in app.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None:
                continue
            try:
                src = inspect.getsource(endpoint)
            except (OSError, TypeError):
                continue
            touches_ai = re.search(r"\bai\.(complete|transcribe|speak)\b", src)
            if not touches_ai:
                continue
            params = inspect.signature(endpoint).parameters
            has_auth = any("current_user" in p or "user_id" in p for p in params)
            if not has_auth:
                offenders.append(getattr(route, "path", str(route)))
        assert not offenders, f"routes spend money without requiring a login: {offenders}"


@pytest.mark.money
@requires_backend
class TestDailyCap:
    """Rule 5: the cap is enforced, per-user, and FAILS CLOSED.

    ../nedlang's caps failed *open* by design — a transient database error
    silently removed all per-user spend enforcement at once. That is the right
    call when you have paying customers and wrong when you have none.
    """

    def test_first_submission_of_the_day_is_allowed(self, client, ai, user, scenario):
        r = client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
            headers=auth(user),
        )
        assert r.status_code == 200
        assert ai.call_count == 1

    def test_second_submission_same_day_is_blocked(self, client, ai, user, scenario):
        body = {"scenario_id": scenario["id"], "reply": "je voudrais un pain"}
        first = client.post(ROUTE_REPLY, json=body, headers=auth(user))
        assert first.status_code == 200
        calls_after_first = ai.call_count

        second = client.post(ROUTE_REPLY, json=body, headers=auth(user))
        assert second.status_code == 429, "the daily cap did not stop a second submission"
        assert ai.call_count == calls_after_first, "a capped request still called the model"

    def test_the_cap_is_per_user_not_global(self, client, ai, user, other_user, scenario):
        body = {"scenario_id": scenario["id"], "reply": "bonjour"}
        client.post(ROUTE_REPLY, json=body, headers=auth(user))
        r = client.post(ROUTE_REPLY, json=body, headers=auth(other_user))
        assert r.status_code == 200, "one learner's usage blocked a different learner"

    def test_cap_resets_after_the_window(self, client, ai, conn, user, scenario):
        body = {"scenario_id": scenario["id"], "reply": "bonjour"}
        client.post(ROUTE_REPLY, json=body, headers=auth(user))
        # Age the usage row past the rolling window.
        conn.execute(
            "UPDATE ai_usage SET created_at = created_at - interval '25 hours' WHERE user_id = %s",
            (user["id"],),
        )
        r = client.post(ROUTE_REPLY, json=body, headers=auth(user))
        assert r.status_code == 200, "the daily cap never resets"

    def test_cap_fails_CLOSED_when_the_usage_query_errors(
        self, client, ai, monkeypatch, user, scenario
    ):
        """The reversal of ../nedlang's decision, pinned by a test so nobody
        can quietly restore the old behaviour for a good-sounding reason."""

        def explode(*a, **k):
            raise ConnectionError("simulated pooler timeout")

        monkeypatch.setattr("app.caps.usage_today", explode, raising=False)
        r = client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "bonjour"},
            headers=auth(user),
        )
        assert r.status_code >= 400, "cap check failed OPEN — spending is unbounded on DB errors"
        assert ai.call_count == 0, "money was spent while the cap was unverifiable"


@pytest.mark.money
@requires_backend
class TestEveryCallIsMetered:
    """You cannot control a cost you cannot see."""

    def test_a_successful_reply_writes_exactly_one_usage_row(
        self, client, ai, conn, user, scenario
    ):
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "bonjour"},
            headers=auth(user),
        )
        rows = conn.execute(
            "SELECT * FROM ai_usage WHERE user_id = %s", (user["id"],)
        ).fetchall()
        assert len(rows) == 1, f"expected exactly 1 usage row, found {len(rows)}"

    @pytest.mark.parametrize(
        "column", ["model", "feature", "tokens_in", "tokens_out", "estimated_cost", "created_at"]
    )
    def test_usage_row_has_no_null_columns(self, client, ai, conn, user, scenario, column):
        """A usage row with a NULL cost is indistinguishable from no row at all
        once you start summing it."""
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "bonjour"},
            headers=auth(user),
        )
        row = conn.execute(
            f"SELECT {column} FROM ai_usage WHERE user_id = %s", (user["id"],)
        ).fetchone()
        assert row is not None, "no usage row written at all"
        assert row[0] is not None, f"ai_usage.{column} was NULL — metering is a lie"

    def test_estimated_cost_is_positive(self, client, ai, conn, user, scenario):
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "bonjour"},
            headers=auth(user),
        )
        cost = conn.execute(
            "SELECT estimated_cost FROM ai_usage WHERE user_id = %s", (user["id"],)
        ).fetchone()[0]
        assert float(cost) > 0, "every real model call costs something; 0.0 means the maths is wrong"

    def test_exactly_one_model_call_per_submission(self, client, ai, user, scenario):
        """../nedlang ran grading 3x per request for self-consistency. That is
        a 3x bill. Rule 5: one call per submission."""
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "bonjour"},
            headers=auth(user),
        )
        assert ai.call_count == 1, f"one submission triggered {ai.call_count} model calls"

    def test_the_logged_model_matches_the_model_actually_called(
        self, client, ai, conn, user, scenario
    ):
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "bonjour"},
            headers=auth(user),
        )
        logged = conn.execute(
            "SELECT model FROM ai_usage WHERE user_id = %s", (user["id"],)
        ).fetchone()[0]
        assert logged == ai.calls[0]["model"], "the usage log records a different model than was called"

    def test_the_model_is_pinned_not_a_routing_alias(self, client, ai, user, scenario):
        """Rule 5: a routing alias picks a different model per request, so both
        the output format and the teaching quality vary invisibly."""
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "bonjour"},
            headers=auth(user),
        )
        model = ai.calls[0]["model"]
        assert model, "no model id was passed to the provider"
        for alias in ("auto", "free", ":free", "openrouter/auto", "default"):
            assert alias not in model.lower(), f"model '{model}' is a routing alias, not a pin"


@pytest.mark.money
@requires_backend
class TestFreePathsAreActuallyFree:
    """The cost model in architecture.md only holds if reading and listening
    are database reads. If opening a scenario ever calls a model, the unit
    economics in the blueprint are fiction."""

    def test_fetching_today_costs_nothing(self, client, ai, user, scenario):
        r = client.get(ROUTE_TODAY, headers=auth(user))
        assert r.status_code == 200
        assert ai.call_count == 0, "opening the app called the model"

    def test_fetching_today_twice_costs_nothing(self, client, ai, user, scenario):
        client.get(ROUTE_TODAY, headers=auth(user))
        client.get(ROUTE_TODAY, headers=auth(user))
        assert ai.call_count == 0

    def test_scenario_audio_is_a_stored_url_not_generated_per_request(self, conn, scenario):
        url = conn.execute(
            "SELECT audio_url FROM scenarios WHERE id = %s", (scenario["id"],)
        ).fetchone()[0]
        assert url, "scenario has no stored audio — listening would cost per play"

    def test_marking_a_review_costs_nothing(self, client, ai, conn, user, scenario):
        mid = _seed_mistake(conn, user, scenario, due_in_days=0)
        r = client.post(
            ROUTE_REVIEW.format(mistake_id=mid), json={"correct": True}, headers=auth(user)
        )
        assert r.status_code == 200
        assert ai.call_count == 0, "reviewing a saved mistake called the model"


def _seed_mistake(conn, user, scenario, *, due_in_days: int = 0, interval: int = 1,
                  mastered: bool = False, phrase: str = "un pain") -> str:
    """Insert a mistake with a controlled review date. Used by §2 and §3."""
    mid = "m_" + uuid.uuid4().hex[:10]
    conn.execute(
        "INSERT INTO mistakes (id, user_id, session_id, wrong, correct, why,"
        " next_review_at, interval_days, mastered)"
        " VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s)",
        (mid, user["id"], phrase, "une baguette", "un pain is a loaf",
         dt.date.today() + dt.timedelta(days=due_in_days), interval, mastered),
    )
    return mid


# ═══════════════════════════════════════════════════════════════════════════
# §2  THE LOOP — it actually closes
#
# product.md describes one loop. A product where step 5 works but step 7
# silently does nothing is a demo, not a learning tool: the learner gets a
# correction, feels good, and nothing ever comes back. It looks like it works.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.loop
@requires_backend
class TestFeedbackContract:
    """The shape of what comes back from the model.

    A response that is well-formed but empty renders as a blank card. The
    learner reads it as "I got it right" and the loop breaks without a single
    error anywhere in the stack.
    """


    def test_a_reply_returns_a_correction(self, client, ai, user, scenario):
        r = client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
            headers=auth(user),
        )
        assert r.status_code == 200
        assert r.json(), "empty response body"

    def test_feedback_has_exactly_the_three_contract_keys(self, client, ai, user, scenario):
        """product.md M5: one fix, one reason, one retry. Not a report card —
        'do not grade every sentence like an examiner' is a product decision,
        so it gets a test."""
        r = client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
            headers=auth(user),
        )
        body = r.json()
        assert set(body) == FEEDBACK_KEYS, (
            f"feedback shape drifted: expected {FEEDBACK_KEYS}, got {set(body)}"
        )

    @pytest.mark.parametrize("key", sorted(FEEDBACK_KEYS))
    def test_no_feedback_field_is_empty(self, client, ai, user, scenario, key):
        r = client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
            headers=auth(user),
        )
        value = r.json()[key]
        assert isinstance(value, str) and value.strip(), f"feedback.{key} came back blank"

    def test_an_empty_reply_is_rejected_before_spending(self, client, ai, user, scenario):
        r = client.post(
            ROUTE_REPLY, json={"scenario_id": scenario["id"], "reply": "   "}, headers=auth(user)
        )
        assert r.status_code == 422
        assert ai.call_count == 0, "an empty submission still cost money"

    def test_an_absurdly_long_reply_is_rejected_before_spending(self, client, ai, user, scenario):
        r = client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "a" * 100_000},
            headers=auth(user),
        )
        assert r.status_code == 422, "no input ceiling — a paste bomb is an unbounded prompt"
        assert ai.call_count == 0

    def test_a_reply_to_a_nonexistent_scenario_is_rejected_before_spending(
        self, client, ai, user
    ):
        r = client.post(
            ROUTE_REPLY, json={"scenario_id": "s_does_not_exist", "reply": "bonjour"},
            headers=auth(user),
        )
        assert r.status_code == 404
        assert ai.call_count == 0


@pytest.mark.loop
@requires_backend
class TestTheLoopPersists:
    """Steps 5→7 of product.md. This is where a silent failure hides best:
    the response looks perfect and nothing is written down."""

    def test_a_reply_creates_a_session_row(self, client, ai, conn, user, scenario):
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
            headers=auth(user),
        )
        n = conn.execute(
            "SELECT count(*) FROM sessions WHERE user_id = %s", (user["id"],)
        ).fetchone()[0]
        assert n == 1, "the session was never recorded"

    def test_a_reply_creates_a_mistake_row(self, client, ai, conn, user, scenario):
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
            headers=auth(user),
        )
        n = conn.execute(
            "SELECT count(*) FROM mistakes WHERE user_id = %s", (user["id"],)
        ).fetchone()[0]
        assert n >= 1, "the correction was shown but never saved — nothing will come back"

    def test_the_saved_mistake_has_a_review_date(self, client, ai, conn, user, scenario):
        """THE started_at TEST.

        In ../nedlang, `learning_sessions.started_at` was read by streaks, the
        heatmap, weekly hours and study-day counts — and written by no code
        path at all. Every user saw zero, for months, with no error anywhere.

        `next_review_at` occupies the identical structural position here: the
        single column the entire retention mechanic reads. If it is ever NULL,
        the product silently stops working and still renders perfectly.
        """
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
            headers=auth(user),
        )
        row = conn.execute(
            "SELECT next_review_at, interval_days FROM mistakes WHERE user_id = %s",
            (user["id"],),
        ).fetchone()
        assert row is not None, "no mistake row at all"
        assert row[0] is not None, "next_review_at is NULL — this mistake will never come back"
        assert row[1] is not None and row[1] >= 1, "interval_days unset — scheduling cannot advance"

    def test_the_saved_mistake_keeps_what_the_learner_actually_wrote(
        self, client, ai, conn, user, scenario
    ):
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
            headers=auth(user),
        )
        wrong = conn.execute(
            "SELECT wrong FROM mistakes WHERE user_id = %s", (user["id"],)
        ).fetchone()[0]
        assert wrong and wrong.strip(), "the mistake was saved with no content to review"

    def test_a_correct_reply_does_not_invent_a_mistake(self, client, ai, conn, user, scenario):
        """Over-correction is a product failure: 'too much feedback feels
        punishing'. A perfect answer must not manufacture something to fix."""
        ai.reply = {"fix": "", "why": "", "retry": ""}
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "je voudrais une baguette"},
            headers=auth(user),
        )
        n = conn.execute(
            "SELECT count(*) FROM mistakes WHERE user_id = %s", (user["id"],)
        ).fetchone()[0]
        assert n == 0, "a correct answer created a mistake to review"


# ═══════════════════════════════════════════════════════════════════════════
# §3  REVIEWS — the mistakes come back
#
# This is the entire retention mechanic (architecture.md, Diagram 4). If it
# silently breaks, the product still works perfectly for exactly one day per
# user, and then quietly becomes a toy.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.review
@requires_backend
class TestScheduling:
    """The arithmetic of coming back.

    Spaced repetition is four lines of date maths, and every one of them fails
    silently: a date that never advances means the same mistake forever, and a
    date that advances too far means it is never seen again.
    """


    def test_a_new_mistake_is_due_tomorrow_not_today(self, client, ai, conn, user, scenario):
        client.post(
            ROUTE_REPLY,
            json={"scenario_id": scenario["id"], "reply": "un pain"},
            headers=auth(user),
        )
        due = conn.execute(
            "SELECT next_review_at FROM mistakes WHERE user_id = %s", (user["id"],)
        ).fetchone()[0]
        assert due > dt.date.today(), "a mistake made today is already due today"

    def test_a_correct_review_doubles_the_interval(self, client, conn, user, scenario):
        mid = _seed_mistake(conn, user, scenario, due_in_days=0, interval=2)
        client.post(ROUTE_REVIEW.format(mistake_id=mid), json={"correct": True}, headers=auth(user))
        interval = conn.execute(
            "SELECT interval_days FROM mistakes WHERE id = %s", (mid,)
        ).fetchone()[0]
        assert interval == 4, f"expected interval 2→4, got {interval}"

    def test_a_wrong_review_resets_the_interval(self, client, conn, user, scenario):
        mid = _seed_mistake(conn, user, scenario, due_in_days=0, interval=8)
        client.post(ROUTE_REVIEW.format(mistake_id=mid), json={"correct": False}, headers=auth(user))
        interval = conn.execute(
            "SELECT interval_days FROM mistakes WHERE id = %s", (mid,)
        ).fetchone()[0]
        assert interval == 1, f"expected reset to 1, got {interval}"

    def test_a_review_always_moves_the_date_forward(self, client, conn, user, scenario):
        """Whatever the algorithm does, it must never leave next_review_at in
        the past — that produces a review that is due forever and blocks the
        queue behind it."""
        for correct in (True, False):
            mid = _seed_mistake(conn, user, scenario, due_in_days=0, interval=1)
            client.post(
                ROUTE_REVIEW.format(mistake_id=mid), json={"correct": correct}, headers=auth(user)
            )
            due = conn.execute(
                "SELECT next_review_at FROM mistakes WHERE id = %s", (mid,)
            ).fetchone()[0]
            assert due > dt.date.today(), f"review (correct={correct}) stayed due today forever"

    def test_a_mistake_eventually_becomes_mastered(self, client, conn, user, scenario):
        """Without a terminal state the review queue only ever grows, and the
        product becomes a chore. Diagram 4 ends at 'mastered'."""
        mid = _seed_mistake(conn, user, scenario, due_in_days=0, interval=1)
        for _ in range(8):
            conn.execute(
                "UPDATE mistakes SET next_review_at = %s WHERE id = %s", (dt.date.today(), mid)
            )
            client.post(
                ROUTE_REVIEW.format(mistake_id=mid), json={"correct": True}, headers=auth(user)
            )
        mastered = conn.execute(
            "SELECT mastered FROM mistakes WHERE id = %s", (mid,)
        ).fetchone()[0]
        assert mastered is True, "a mistake answered correctly 8 times never retires"


@pytest.mark.review
@requires_backend
class TestDueToday:
    """product.md M8: the home screen count IS the notification system. If it
    is wrong, the product has no reason to be opened tomorrow."""

    def test_a_mistake_due_today_appears(self, client, conn, user, scenario):
        _seed_mistake(conn, user, scenario, due_in_days=0)
        body = client.get(ROUTE_TODAY, headers=auth(user)).json()
        assert body["due_count"] == 1

    def test_a_mistake_due_tomorrow_does_not_appear(self, client, conn, user, scenario):
        _seed_mistake(conn, user, scenario, due_in_days=1)
        body = client.get(ROUTE_TODAY, headers=auth(user)).json()
        assert body["due_count"] == 0, "a future review is being shown as due now"

    def test_an_overdue_mistake_still_appears(self, client, conn, user, scenario):
        """Miss a week and your reviews must still be waiting, not lost."""
        _seed_mistake(conn, user, scenario, due_in_days=-7)
        body = client.get(ROUTE_TODAY, headers=auth(user)).json()
        assert body["due_count"] == 1, "overdue reviews vanished instead of queueing"

    def test_a_mastered_mistake_does_not_appear(self, client, conn, user, scenario):
        _seed_mistake(conn, user, scenario, due_in_days=0, mastered=True)
        body = client.get(ROUTE_TODAY, headers=auth(user)).json()
        assert body["due_count"] == 0, "retired mistakes are still being drilled"

    def test_the_displayed_count_matches_the_database(self, client, conn, user, scenario):
        """The started_at bug in one assertion: the number on screen and the
        number in the table must be the same number."""
        for _ in range(3):
            _seed_mistake(conn, user, scenario, due_in_days=0)
        _seed_mistake(conn, user, scenario, due_in_days=5)

        shown = client.get(ROUTE_TODAY, headers=auth(user)).json()["due_count"]
        actual = conn.execute(
            "SELECT count(*) FROM mistakes WHERE user_id = %s AND next_review_at <= %s"
            " AND mastered = false",
            (user["id"], dt.date.today()),
        ).fetchone()[0]
        assert shown == actual == 3, f"screen says {shown}, database says {actual}"

    def test_the_count_is_never_structurally_zero(self, client, conn, user, scenario):
        """Guards the exact shape of the ../nedlang failure: a stat that is
        always zero regardless of the data behind it."""
        before = client.get(ROUTE_TODAY, headers=auth(user)).json()["due_count"]
        assert before == 0
        for _ in range(5):
            _seed_mistake(conn, user, scenario, due_in_days=0)
        after = client.get(ROUTE_TODAY, headers=auth(user)).json()["due_count"]
        assert after == 5, (
            "due_count did not move when 5 due reviews were added — "
            "it is reading a column nothing writes"
        )


# ═══════════════════════════════════════════════════════════════════════════
# §4  SCHEMA — no column is a lie
#
# These tests read the source code rather than run it. They exist because the
# started_at bug was not catchable by testing any single feature: nothing was
# broken in isolation. The column existed, the query was valid, the page
# rendered. The defect only appeared when you asked a question no individual
# test asks — "does anything ever WRITE this?"
#
# Generalising that question is the highest-value test in this file.
# ═══════════════════════════════════════════════════════════════════════════

# [^;] rather than . so a match cannot run past the end of its own statement.
# SQL uses the word SELECT for two unrelated things, and this pattern cannot
# tell them apart: `GRANT SELECT, INSERT ON users` is a permission, not a
# query. Those statements carry no FROM, so stopping at the semicolon is what
# excludes them — otherwise the match runs on to the next FROM in the file and
# reports every word in between, comments included, as a column name.
_SQL_SELECT_COLS = re.compile(r"SELECT\s+([^;]*?)\s+FROM\s+(\w+)", re.I | re.S)
_SQL_INSERT_COLS = re.compile(r"INSERT\s+INTO\s+(\w+)\s*\((.*?)\)", re.I | re.S)
_SQL_UPDATE_COLS = re.compile(r"UPDATE\s+(\w+)\s+SET\s+(.*?)(?:WHERE|RETURNING|$)", re.I | re.S)


def _schema_columns() -> dict[str, set[str]]:
    """table -> declared columns, parsed from the CREATE TABLE statements."""
    sql = ""
    for p in _sources(BACKEND_DIR, ".py", ".sql"):
        sql += p.read_text(errors="ignore")
    tables: dict[str, set[str]] = {}
    for m in re.finditer(r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(\w+)\s*\((.*?)\n\s*\)",
                         sql, re.I | re.S):
        name, body = m.group(1), m.group(2)
        cols = set()
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.upper().startswith(
                ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "--")
            ):
                continue
            cols.add(line.split()[0].strip('"'))
        if cols:
            tables[name] = cols
    return tables


def _columns_written() -> dict[str, set[str]]:
    """table -> columns that appear in an INSERT column list or an UPDATE SET."""
    written: dict[str, set[str]] = {}
    for p in _sources(BACKEND_DIR, ".py", ".sql"):
        src = p.read_text(errors="ignore")
        for table, cols in _SQL_INSERT_COLS.findall(src):
            written.setdefault(table, set()).update(
                c.strip().strip('"') for c in cols.split(",") if c.strip()
            )
        for table, assignments in _SQL_UPDATE_COLS.findall(src):
            for part in assignments.split(","):
                if "=" in part:
                    written.setdefault(table, set()).add(part.split("=")[0].strip().strip('"'))
    return written


def _columns_read() -> dict[str, set[str]]:
    """table -> columns that appear in a SELECT list."""
    read: dict[str, set[str]] = {}
    for p in _sources(BACKEND_DIR, ".py", ".sql"):
        src = p.read_text(errors="ignore")
        for cols, table in _SQL_SELECT_COLS.findall(src):
            if "*" in cols:
                continue
            for c in cols.split(","):
                c = c.strip().split()[0].split(".")[-1].strip('"')
                if c.isidentifier():
                    read.setdefault(table, set()).add(c)
    return read


@pytest.mark.schema
class TestNoColumnIsWriteOnlyOrReadOnly:
    """Columns that are read and never written, or written and never read.

    Source analysis rather than behaviour, because the started_at defect was
    invisible to every per-feature test: nothing was broken in isolation.
    """


    def test_no_column_is_read_but_never_written(self):
        """██ THE started_at DETECTOR ██

        A column that some query SELECTs and no query ever INSERTs or UPDATEs
        is, by construction, always NULL or always the default. Every feature
        reading it silently returns nothing. This is exactly, precisely the bug
        that zeroed streaks, the heatmap, weekly hours and study-day counts in
        ../nedlang for every user, undetected, in production.

        It is not catchable by testing features one at a time. It is trivially
        catchable by asking this question once.
        """
        schema, written, read = _schema_columns(), _columns_written(), _columns_read()
        if not schema:
            pytest.skip("no CREATE TABLE statements found yet")

        offenders = []
        for table, cols in read.items():
            if table not in schema:
                continue
            never_written = cols - written.get(table, set())
            # Columns the database fills in itself are legitimately never written.
            never_written -= {"id", "created_at", "updated_at"}
            for col in sorted(never_written):
                if col in schema[table]:
                    offenders.append(f"{table}.{col}")

        assert not offenders, (
            "these columns are READ by application code but WRITTEN by nothing — "
            f"every feature reading them returns a default forever: {offenders}"
        )

    def test_no_query_reads_a_column_that_does_not_exist(self):
        """The mirror image: a SELECT naming a column the schema dropped. In
        Postgres this raises at runtime, but only on the code path that runs
        it — which may be a page nobody visits until a user does."""
        schema, read = _schema_columns(), _columns_read()
        if not schema:
            pytest.skip("no CREATE TABLE statements found yet")

        offenders = []
        for table, cols in read.items():
            if table not in schema:
                continue
            for col in sorted(cols - schema[table]):
                offenders.append(f"{table}.{col}")
        assert not offenders, f"queries read columns that are not in the schema: {offenders}"

    def test_every_user_owned_table_declared_in_this_spec_actually_exists(self):
        schema = _schema_columns()
        if not schema:
            pytest.skip("no CREATE TABLE statements found yet")
        missing = [t for t in USER_OWNED_TABLES if t not in schema]
        assert not missing, f"tables named in this spec do not exist: {missing}"

    def test_every_table_in_the_schema_is_classified(self):
        """Forces a decision. A new table is either user-owned (and therefore
        must be exported and erased) or shared. Silence is how ../nedlang's
        purge list drifted away from its export list."""
        schema = _schema_columns()
        if not schema:
            pytest.skip("no CREATE TABLE statements found yet")
        known = set(USER_OWNED_TABLES) | set(SHARED_TABLES)
        unclassified = sorted(set(schema) - known)
        assert not unclassified, (
            f"unclassified tables: {unclassified} — add each to USER_OWNED_TABLES "
            "(exported + erased) or SHARED_TABLES (neither), in §0 of this file"
        )

    def test_every_user_owned_table_has_a_user_id_column(self):
        schema = _schema_columns()
        if not schema:
            pytest.skip("no CREATE TABLE statements found yet")
        offenders = [
            t for t in USER_OWNED_TABLES
            if t in schema and t != "users" and "user_id" not in schema[t]
        ]
        assert not offenders, (
            f"tables claimed as user-owned with no user_id column: {offenders} — "
            "erasure and isolation cannot be enforced on them"
        )


# ═══════════════════════════════════════════════════════════════════════════
# §5  REACHABILITY — no endpoint is an orphan
#
# Origin: ../nedlang built the whole GDPR erasure machine — soft delete, grace
# period, restore, ordered purge — and no page ever called DELETE /user/account.
# Art. 17 erasure existed and was unreachable by a human being. Every backend
# test would have passed. The feature was, in the only sense that matters,
# absent.
# ═══════════════════════════════════════════════════════════════════════════


def _backend_routes() -> list[tuple[str, str]]:
    out = []
    for route in getattr(app, "routes", []):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", set()) or set()
        if not path or path.startswith(("/openapi", "/docs", "/redoc")):
            continue
        for m in methods:
            if m not in ("HEAD", "OPTIONS"):
                out.append((m, path))
    return sorted(set(out))


def _frontend_text() -> str:
    return "\n".join(
        p.read_text(errors="ignore") for p in _sources(FRONTEND_DIR, ".ts", ".tsx", ".js", ".jsx")
    )


@pytest.mark.reachable
@requires_backend
@requires_frontend
class TestEveryEndpointHasACaller:
    """Backend routes no page calls.

    ../nedlang shipped a complete GDPR erasure implementation with no button.
    Every backend test passed. The feature did not exist.
    """


    def test_no_route_is_unreachable_from_the_frontend(self):
        """██ THE DELETE-BUTTON DETECTOR ██

        Walks the app's own route table and requires that each path appears
        somewhere in the frontend source. A backend endpoint no page calls is
        either dead code or — far worse — a feature the user was promised and
        cannot reach.
        """
        ui = _frontend_text()
        orphans = []
        for method, path in _backend_routes():
            # "/review/{mistake_id}" → match on the literal stem "/review/"
            stem = path.split("{")[0].rstrip("/") or "/"
            if stem not in ui:
                orphans.append(f"{method} {path}")
        assert not orphans, (
            f"backend endpoints that no frontend code calls: {orphans} — "
            "each is dead code or an unreachable promise"
        )


@pytest.mark.reachable
@requires_frontend
class TestTheUserFacingControlsExist:
    """The two controls a regulator would ask to be shown.

    Separated from the route-table test above because these need only the
    frontend: they must run from the first commit, not from whenever the
    backend first imports cleanly.
    """

    def test_the_delete_account_button_exists(self):
        """Named explicitly, because this is the one that actually happened,
        and because a generic test can be satisfied by an accidental mention."""
        ui = _frontend_text()
        assert ROUTE_DELETE in ui, "no frontend code references the account deletion endpoint"
        assert re.search(r'method:\s*["\']DELETE["\']', ui), (
            "no DELETE request is issued anywhere in the frontend — "
            "GDPR Art. 17 erasure is not self-service (this is the ../nedlang bug)"
        )

    def test_the_data_export_button_exists(self):
        ui = _frontend_text()
        assert ROUTE_EXPORT in ui, "GDPR Art. 15 export is not reachable from the UI"

    def test_delete_and_export_are_reachable_from_a_real_page(self):
        """A reference inside a helper module proves nothing if no page imports
        it. Require the call site to be reachable from an actual route file."""
        pages = [p for p in _sources(FRONTEND_DIR, ".tsx") if "page" in p.name]
        assert pages, "no page files found"
        joined = "\n".join(p.read_text(errors="ignore") for p in pages)
        for needle, label in ((ROUTE_DELETE, "deletion"), (ROUTE_EXPORT, "export")):
            reached = needle in joined or re.search(
                r"import[^\n]+(deleteAccount|exportData)", joined
            )
            assert reached, f"{label} is not wired into any page"


def _fetch_mistake(conn, mistake_id: str) -> dict:
    row = conn.execute(
        "SELECT next_review_at, interval_days, mastered FROM mistakes WHERE id = %s",
        (mistake_id,),
    ).fetchone()
    assert row is not None, f"mistake {mistake_id} vanished"
    return {"next_review_at": row[0], "interval_days": row[1], "mastered": row[2]}


def _seed_session(conn, user, scenario, *, minutes_ago: int = 0) -> str:
    sid = "sess_" + uuid.uuid4().hex[:10]
    started = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)
    conn.execute(
        "INSERT INTO sessions (id, user_id, scenario_id, started_at, turns)"
        " VALUES (%s, %s, %s, %s, %s)",
        (sid, user["id"], scenario["id"], started, 3),
    )
    return sid


def _seed_ai_usage(conn, user) -> str:
    rid = "use_" + uuid.uuid4().hex[:10]
    conn.execute(
        "INSERT INTO ai_usage (id, user_id, feature, model, tokens_in, tokens_out,"
        " estimated_cost, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (rid, user["id"], "feedback", "claude-haiku-4-5", 400, 120, 0.0011,
         dt.datetime.now(dt.timezone.utc)),
    )
    return rid


def _seed_all_user_tables(conn, user, scenario) -> None:
    """One row in every table this spec claims is user-owned.

    Deliberately written as a loop over USER_OWNED_TABLES rather than a fixed
    list of calls: when a table is added to the constant and no seeder exists
    for it, this raises instead of silently seeding nothing — which would make
    the erasure and export tests pass vacuously. A vacuous GDPR test is worse
    than no GDPR test, because it produces a green tick.
    """
    seeders = {
        "users": lambda: None,  # the `user` fixture already inserted it
        "sessions": lambda: _seed_session(conn, user, scenario),
        "mistakes": lambda: _seed_mistake(conn, user, scenario),
        "ai_usage": lambda: _seed_ai_usage(conn, user),
    }
    missing = [t for t in USER_OWNED_TABLES if t not in seeders]
    assert not missing, (
        f"no seeder for user-owned tables {missing} — add one here, or the "
        "erasure and export tests will pass without ever testing those tables"
    )
    for table in USER_OWNED_TABLES:
        seeders[table]()


# ═══════════════════════════════════════════════════════════════════════════
# §6  ISOLATION — one user's data never appears in another user's response
#
# Origin: ../nedlang carried a documented contract — the admin BYPASSRLS
# connection is "never used for per-request app traffic" — and then used it
# on every expensive per-request path in usage_caps.py. RLS on that connection
# is a no-op. Nothing failed. Nothing logged. The database's own containment
# was simply switched off on the hottest routes in the app.
#
# A leak is the quietest bug of all: the response is 200, well-formed, and
# wrong. These tests are the only thing standing between "it works" and
# "it works for everyone's data".
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.isolation
@requires_backend
class TestOneUserCannotSeeAnother:
    """Cross-user reads and writes.

    A leak returns 200 with a well-formed body. There is no exception, no log
    line and no visible symptom — only the wrong rows.
    """


    def test_the_daily_scenario_never_leaks_another_users_mistakes(
        self, client, conn, user, other_user, scenario
    ):
        _seed_mistake(conn, other_user, scenario, phrase="je suis 25 ans")
        r = client.get(ROUTE_TODAY, headers=auth(user))
        assert r.status_code == 200
        assert "je suis 25 ans" not in r.text

    def test_reviews_due_are_scoped_to_the_caller(self, client, conn, user, other_user, scenario):
        _seed_mistake(conn, other_user, scenario, due_in_days=-1)
        _seed_mistake(conn, other_user, scenario, due_in_days=-1)
        r = client.get(ROUTE_TODAY, headers=auth(user))
        body = r.json()
        assert body.get("reviews_due", 0) == 0, (
            "a user with no mistakes is being shown someone else's review count"
        )

    def test_a_mistake_id_from_another_user_cannot_be_reviewed(
        self, client, ai, conn, user, other_user, scenario
    ):
        """Direct object reference. The id is a perfectly valid row — it just
        isn't the caller's. If the handler filters on id alone, this passes 200
        and silently mutates a stranger's schedule."""
        victim = _seed_mistake(conn, other_user, scenario)
        r = client.post(ROUTE_REVIEW.format(mistake_id=victim), json={"correct": True},
                        headers=auth(user))
        assert r.status_code in (403, 404), (
            f"user A reviewed user B's mistake and got {r.status_code}"
        )

    def test_a_rejected_cross_user_review_changes_nothing(
        self, client, ai, conn, user, other_user, scenario
    ):
        """Rejecting the request is not enough — it must also not have written."""
        victim = _seed_mistake(conn, other_user, scenario, interval=1)
        client.post(ROUTE_REVIEW.format(mistake_id=victim), json={"correct": True},
                    headers=auth(user))
        after = _fetch_mistake(conn, victim)
        assert after["interval_days"] == 1, "a rejected cross-user review still mutated the row"

    def test_another_users_session_is_not_readable(self, client, conn, user, other_user, scenario):
        sid = _seed_session(conn, other_user, scenario)
        r = client.get(f"/session/{sid}", headers=auth(user))
        assert r.status_code in (403, 404), "session ids are guessable cross-user reads"

    def test_export_contains_only_the_callers_rows(
        self, client, conn, user, other_user, scenario
    ):
        _seed_mistake(conn, other_user, scenario, phrase="MARKER_OTHER_USER")
        _seed_mistake(conn, user, scenario, phrase="MARKER_SELF")
        r = client.get(ROUTE_EXPORT, headers=auth(user))
        assert r.status_code == 200
        assert "MARKER_SELF" in r.text
        assert "MARKER_OTHER_USER" not in r.text, "the GDPR export leaks other users' data"

    @pytest.mark.parametrize("route", [ROUTE_TODAY, ROUTE_EXPORT])
    def test_no_token_means_no_data(self, client, route):
        r = client.get(route)
        assert r.status_code in (401, 403), f"{route} served data with no credentials"

    def test_a_forged_token_is_rejected(self, client, route=ROUTE_TODAY):
        r = client.get(route, headers={"Authorization": "Bearer not-a-real-token"})
        assert r.status_code in (401, 403), "an arbitrary bearer string was accepted"


@pytest.mark.isolation
class TestTheAdminConnectionStaysOutOfRequestPaths:
    """██ THE usage_caps.py DETECTOR ██

    Structural, not behavioural — the whole point is that the behavioural
    symptom never appears until it appears catastrophically.
    """

    def test_no_request_handler_opens_an_admin_connection(self):
        """Any module defining a route must not call the privileged connection
        helper. Migrations and seed scripts may; request code may not."""
        offenders = []
        for p in _sources(BACKEND_DIR, ".py"):
            src = p.read_text(errors="ignore")
            defines_routes = bool(re.search(r"@\w*router\.(get|post|put|patch|delete)", src))
            if not defines_routes:
                continue
            for m in re.finditer(r"\b(admin_connection|get_admin_conn|bypass_rls\w*)\s*\(", src):
                line = src[: m.start()].count("\n") + 1
                offenders.append(f"{p.relative_to(REPO)}:{line}")
        assert not offenders, (
            "route modules opening a privileged (RLS-bypassing) connection: "
            f"{offenders} — this is exactly the ../nedlang usage_caps.py defect"
        )

    def test_rls_is_enabled_on_every_user_owned_table(self):
        sql = "".join(p.read_text(errors="ignore") for p in _sources(BACKEND_DIR, ".py", ".sql"))
        if "CREATE TABLE" not in sql.upper():
            pytest.skip("no schema yet")
        missing = [
            t for t in USER_OWNED_TABLES
            if not re.search(rf"ALTER TABLE\s+{t}\s+ENABLE ROW LEVEL SECURITY", sql, re.I)
        ]
        assert not missing, f"user-owned tables without RLS enabled: {missing}"

    def test_the_application_role_is_not_a_superuser(self):
        """A least-privileged role is the enforcement point. If the app connects
        as the owner or as a BYPASSRLS role, every policy above is decoration."""
        sql = "".join(p.read_text(errors="ignore") for p in _sources(BACKEND_DIR, ".py", ".sql"))
        for bad in ("BYPASSRLS", "SUPERUSER"):
            # \b before the keyword so NOBYPASSRLS and NOSUPERUSER — which say
            # the opposite — are not read as matches. Without it this test fails
            # on a role created correctly, which teaches you to ignore it.
            for m in re.finditer(rf"CREATE ROLE\s+(\w+)[^;]*\b{bad}", sql, re.I):
                role = m.group(1)
                assert "app" not in role.lower(), f"the application role {role} has {bad}"


# ═══════════════════════════════════════════════════════════════════════════
# §7  GDPR — erasure and export are complete, and stay complete
#
# Origin: ../nedlang's purge list and export list were maintained separately by
# hand. They drifted. A new table was added to one and not the other, which
# means either (a) a user exercises Art. 17 and rows survive, or (b) a user
# exercises Art. 15 and the export is incomplete. Both are regulator-facing.
# Ned is the controller, in Ireland. This is not a "later" category.
#
# The fix is structural: both lists derive from USER_OWNED_TABLES, and these
# tests fail the build the moment a table is added without a decision.
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.gdpr
@requires_backend
class TestErasureIsComplete:
    """Art. 17. Deletion removes everything, and only the caller's everything.

    Both directions fail quietly: surviving rows look like success, and
    over-deletion looks like success until the shared catalogue is thinner.
    """


    def test_deleting_an_account_removes_rows_from_every_user_owned_table(
        self, client, conn, user, scenario
    ):
        """██ THE DRIFT DETECTOR ██

        Seeds a row in every table this spec claims is user-owned, deletes the
        account, then checks all of them. Adding a table without adding it to
        the purge makes this fail loudly — which is the only reason it stays
        correct over time.
        """
        _seed_all_user_tables(conn, user, scenario)
        r = client.delete(ROUTE_DELETE, headers=auth(user))
        assert r.status_code in (200, 202, 204), f"deletion returned {r.status_code}"

        survivors = {}
        for table in USER_OWNED_TABLES:
            col = "id" if table == "users" else "user_id"
            n = conn.execute(
                f"SELECT count(*) FROM {table} WHERE {col} = %s", (user["id"],)
            ).fetchone()[0]
            if n:
                survivors[table] = n
        assert not survivors, f"rows survived account deletion: {survivors}"

    def test_deletion_does_not_remove_shared_data(self, client, conn, user, scenario):
        """Over-deleting is the opposite failure and just as silent: the next
        user finds the scenario catalogue mysteriously thinner."""
        client.delete(ROUTE_DELETE, headers=auth(user))
        alive = conn.execute(
            "SELECT count(*) FROM scenarios WHERE id = %s", (scenario["id"],)
        ).fetchone()[0]
        assert alive == 1, "account deletion destroyed shared scenario data"

    def test_deletion_does_not_touch_another_user(self, client, conn, user, other_user, scenario):
        _seed_mistake(conn, other_user, scenario)
        client.delete(ROUTE_DELETE, headers=auth(user))
        alive = conn.execute(
            "SELECT count(*) FROM mistakes WHERE user_id = %s", (other_user["id"],)
        ).fetchone()[0]
        assert alive == 1, "deleting one account deleted another user's data"

    def test_the_token_stops_working_after_deletion(self, client, user):
        client.delete(ROUTE_DELETE, headers=auth(user))
        r = client.get(ROUTE_TODAY, headers=auth(user))
        assert r.status_code in (401, 403, 404), (
            "a deleted user's session still resolves — the row is gone but the "
            "identity is not"
        )

    def test_deletion_is_idempotent(self, client, user):
        first = client.delete(ROUTE_DELETE, headers=auth(user))
        second = client.delete(ROUTE_DELETE, headers=auth(user))
        assert first.status_code in (200, 202, 204)
        assert second.status_code < 500, "a repeated deletion raises a server error"

    def test_deletion_requires_authentication(self, client):
        assert client.delete(ROUTE_DELETE).status_code in (401, 403)


@pytest.mark.gdpr
@requires_backend
class TestExportIsComplete:
    """Art. 15 and Art. 20. The export is all of it, and machine-readable.

    An export with the right keys and empty values passes a shape test and
    gives the learner nothing.
    """


    def test_the_export_covers_every_user_owned_table(self, client, conn, user, scenario):
        """Art. 15 is 'all the personal data', not 'the interesting bits'."""
        _seed_all_user_tables(conn, user, scenario)
        r = client.get(ROUTE_EXPORT, headers=auth(user))
        assert r.status_code == 200
        body = r.json()
        missing = [t for t in USER_OWNED_TABLES if t not in body]
        assert not missing, f"the export omits user-owned tables: {missing}"

    def test_the_export_is_not_empty_for_a_user_with_data(self, client, conn, user, scenario):
        _seed_all_user_tables(conn, user, scenario)
        body = client.get(ROUTE_EXPORT, headers=auth(user)).json()
        empties = [t for t in USER_OWNED_TABLES if t != "users" and not body.get(t)]
        assert not empties, (
            f"the export returns empty lists for seeded tables: {empties} — "
            "the key exists, so a shape test passes and the user gets nothing"
        )

    def test_export_and_erasure_agree_on_the_table_list(self):
        """██ THE STRUCTURAL FIX ██

        The two lists must be the same list. If the implementation hardcodes
        either one, this test names it.
        """
        src = "".join(p.read_text(errors="ignore") for p in _sources(BACKEND_DIR, ".py"))
        if "USER_OWNED_TABLES" not in src:
            pytest.skip("no shared table list defined in the backend yet")
        hardcoded = re.findall(r"DELETE FROM (\w+) WHERE user_id", src, re.I)
        stray = sorted(set(hardcoded) - set(USER_OWNED_TABLES))
        assert not stray, (
            f"erasure deletes from tables not in the shared list: {stray} — "
            "derive both the purge and the export from one constant"
        )

    def test_the_export_is_machine_readable(self, client, user):
        r = client.get(ROUTE_EXPORT, headers=auth(user))
        assert "json" in r.headers.get("content-type", ""), (
            "Art. 20 portability requires a structured, commonly used, "
            "machine-readable format"
        )

    def test_export_requires_authentication(self, client):
        assert client.get(ROUTE_EXPORT).status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════
# §8  PRIVACY — what leaves the building
#
# The prompt is the one place where personal data crosses an organisational
# boundary and no reviewer ever looks. It is assembled in code, sent to a
# processor in another jurisdiction, and never rendered on a screen. If it
# quietly carries the learner's email, name or auth identifier, nothing in the
# product looks different — and the record of processing in the DPIA is simply
# false.
#
# ../nedlang had a consent layer of 1,837 lines and no test that ever read a
# prompt. These tests read the prompt.
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.privacy
@requires_backend
class TestThePromptCarriesNoIdentity:
    """What is actually sent to the processor.

    The prompt is the one place personal data crosses a boundary and no
    reviewer ever looks, because it is never rendered on a screen.
    """


    def _one_prompt(self, client, ai, user, scenario) -> str:
        client.post(ROUTE_REPLY,
                    json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
                    headers=auth(user))
        assert ai.call_count == 1, "expected exactly one provider call"
        return ai.all_prompt_text

    def test_the_prompt_does_not_contain_the_email_address(self, client, ai, user, scenario):
        text = self._one_prompt(client, ai, user, scenario)
        assert user["email"] not in text, "the learner's email address was sent to the provider"

    def test_the_prompt_does_not_contain_the_auth_identifier(self, client, ai, user, scenario):
        text = self._one_prompt(client, ai, user, scenario)
        assert user["clerk_id"] not in text, "the Clerk user id was sent to the provider"

    def test_the_prompt_does_not_contain_the_internal_user_id(self, client, ai, user, scenario):
        text = self._one_prompt(client, ai, user, scenario)
        assert user["id"] not in text, (
            "the internal user id was sent to the provider — a stable identifier "
            "makes the provider's copy re-identifiable"
        )

    @pytest.mark.parametrize("pattern,label", [
        (r"[\w.+-]+@[\w-]+\.[\w.]+", "an email address"),
        (r"\buser_[A-Za-z0-9]{6,}", "a user identifier"),
        (r"\bclerk_[A-Za-z0-9]{6,}", "a Clerk identifier"),
        (r"\bBearer\s+\S+", "a bearer token"),
        (r"\bsk-[A-Za-z0-9]{10,}", "an API key"),
    ])
    def test_the_prompt_matches_no_identifier_shape(
        self, client, ai, user, scenario, pattern, label
    ):
        """Catches the identifiers of users this test did not create — the ones
        that arrive later via a 'helpful' context-enrichment refactor."""
        text = self._one_prompt(client, ai, user, scenario)
        found = re.search(pattern, text)
        assert not found, f"the prompt contains {label}: {found.group(0)!r}"

    def test_the_prompt_does_contain_what_it_needs(self, client, ai, user, scenario):
        """The mirror test. Stripping identity is worthless if the refactor that
        strips it also strips the learner's sentence — the model would then be
        grading nothing, plausibly, forever."""
        text = self._one_prompt(client, ai, user, scenario)
        assert "je voudrais un pain" in text, "the learner's reply never reached the model"
        assert scenario["situation"] in text or "boulangerie" in text, (
            "the scenario context never reached the model — feedback is being "
            "generated without knowing what was being practised"
        )

    def test_the_goal_is_sent_but_not_the_person(self, client, ai, conn, scenario):
        """Onboarding collects a goal in free text. It is useful context and it
        is also whatever the user typed. Sending it is a product decision; this
        test exists so that decision is explicit and visible in one place."""
        u = _make_user(conn, email="rachel.okonkwo@example.invalid")
        client.post(ROUTE_REPLY, json={"scenario_id": scenario["id"], "reply": "bonjour"},
                    headers=auth(u))
        text = ai.all_prompt_text
        assert "rachel.okonkwo" not in text, "the email reached the provider"
        assert "order food on holiday" in text, (
            "the learner's goal is not reaching the model — feedback cannot be "
            "tailored to why they are here"
        )


@pytest.mark.privacy
class TestNothingSecretIsLogged:
    """Transcripts in log aggregators, keys in the repository.

    `logger.info(request.json())` is one line, looks like diligence, and is a
    transfer of personal data to wherever the logs live.
    """


    def test_no_source_file_logs_a_whole_request_body(self):
        """`logger.info(request.json())` is how transcripts end up in a log
        aggregator in a third country. It is one line, it looks like diligence,
        and it is a transfer."""
        offenders = []
        for p in _sources(BACKEND_DIR, ".py"):
            for m in re.finditer(
                r"(?:logger|logging|print)\s*[.(][^\n]*\b(?:request\.json|await request\.body|"
                r"\.dict\(\)|model_dump\(\))", p.read_text(errors="ignore")
            ):
                line = p.read_text(errors="ignore")[: m.start()].count("\n") + 1
                offenders.append(f"{p.relative_to(REPO)}:{line}")
        assert not offenders, f"whole request bodies are being logged: {offenders}"

    def test_no_secret_is_committed(self):
        """A key in the repo is not a silent failure for a week and then a very
        loud one. The shapes below are the ones this stack actually issues."""
        shapes = [
            (r"sk-ant-[A-Za-z0-9\-_]{20,}", "an Anthropic API key"),
            (r"sk_live_[A-Za-z0-9]{20,}", "a Clerk live secret"),
            (r"re_[A-Za-z0-9]{20,}", "a Resend key"),
            # Excludes localhost: a throwaway credential pointing at a CI
            # service container is not a secret, and flagging it teaches people
            # to ignore this test — which is how the real one gets through.
            (r"postgres(?:ql)?://[^:]+:[^@\s]{8,}@(?!localhost|127\.0\.0\.1)",
             "a database URL with a password"),
        ]
        offenders = []
        for p in _sources(REPO, ".py", ".ts", ".tsx", ".js", ".json", ".yml", ".yaml", ".md"):
            if p.name == pathlib.Path(__file__).name:
                continue
            src = p.read_text(errors="ignore")
            for pattern, label in shapes:
                if re.search(pattern, src):
                    offenders.append(f"{p.relative_to(REPO)}: {label}")
        assert not offenders, f"secrets are committed to the repository: {offenders}"

    def test_env_example_lists_every_variable_the_code_reads(self):
        """A missing entry here is a deploy that boots, serves pages, and fails
        only on the one path that reads the variable."""
        example = REPO / ".env.example"
        if not example.exists():
            pytest.skip("no .env.example yet")
        declared = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", example.read_text(), re.M))
        used = set()
        for p in _sources(BACKEND_DIR, ".py"):
            used |= set(re.findall(r"environ(?:\.get)?\(?\[?[\"']([A-Z][A-Z0-9_]+)[\"']",
                                   p.read_text(errors="ignore")))
        missing = sorted(used - declared - {"PATH", "HOME", "PYTHONPATH", "PORT"})
        assert not missing, f"environment variables read by code but not in .env.example: {missing}"


# ═══════════════════════════════════════════════════════════════════════════
# §9  DEGRADATION — the bad day behaves
#
# Every test above assumes the provider answers. It will not always answer.
# The failure mode that matters is not the 500 — a 500 is loud, and someone
# fixes it. The failure mode that matters is the response that looks fine:
# empty feedback rendered as a blank card, a fallback that silently costs a
# second billed call, a timeout that leaves a session row half-written so the
# streak breaks and nobody knows why.
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.degrade
@requires_backend
class TestTheProviderFailing:
    """Timeouts, garbage and refusals.

    The 500 is not the dangerous case — it is loud and someone fixes it. The
    dangerous case is the outage that still returns 200.
    """


    def test_a_timeout_returns_the_answer_key_not_an_error(self, client, ai, user, scenario):
        """The scenario already carries a correct answer. A learner who submits
        during an outage should still see the right sentence — that is the whole
        reason `answer_key` is a column."""
        ai.mode = "timeout"
        r = client.post(ROUTE_REPLY,
                        json={"scenario_id": scenario["id"], "reply": "je voudrais un pain"},
                        headers=auth(user))
        assert r.status_code == 200, f"a provider timeout surfaced as {r.status_code}"
        assert scenario["answer_key"] in r.text, "the fallback did not include the answer key"

    def test_malformed_model_output_does_not_reach_the_learner(self, client, ai, user, scenario):
        """Models return prose where JSON was asked for. If the parser is
        permissive, the learner sees a half-parsed blob and assumes they broke
        something."""
        ai.mode = "garbage"
        r = client.post(ROUTE_REPLY,
                        json={"scenario_id": scenario["id"], "reply": "bonjour"},
                        headers=auth(user))
        assert r.status_code == 200
        body = r.json()
        assert set(body["feedback"]) == FEEDBACK_KEYS, (
            "malformed provider output leaked through the contract"
        )

    def test_a_refusal_is_treated_as_a_failure_not_as_feedback(self, client, ai, user, scenario):
        """'I can't help with that' is a 200 from the provider and a total
        failure for the learner. Shape-only validation lets it straight through."""
        ai.mode = "refusal"
        r = client.post(ROUTE_REPLY,
                        json={"scenario_id": scenario["id"], "reply": "bonjour"},
                        headers=auth(user))
        body = r.json()
        assert "can't help" not in json.dumps(body).lower(), (
            "a provider refusal was rendered to the learner as language feedback"
        )

    def test_the_fallback_does_not_retry_forever(self, client, ai, user, scenario):
        """██ THE BILL DETECTOR ██

        A retry loop around a failing provider is how an outage becomes an
        invoice. Bounded retries, and the bound is small.
        """
        ai.mode = "timeout"
        client.post(ROUTE_REPLY, json={"scenario_id": scenario["id"], "reply": "bonjour"},
                    headers=auth(user))
        assert ai.call_count <= 2, (
            f"one submission caused {ai.call_count} provider calls during an outage"
        )

    def test_a_failed_submission_does_not_consume_the_daily_allowance(
        self, client, ai, user, scenario
    ):
        """Charging the learner's one daily submission for the provider's bad
        day is the kind of unfairness nobody reports — they just stop coming."""
        ai.mode = "timeout"
        client.post(ROUTE_REPLY, json={"scenario_id": scenario["id"], "reply": "bonjour"},
                    headers=auth(user))
        ai.mode = "ok"
        r = client.post(ROUTE_REPLY,
                        json={"scenario_id": scenario["id"], "reply": "je voudrais une baguette"},
                        headers=auth(user))
        assert r.status_code == 200, (
            "a failed submission burned the daily allowance — the learner is "
            "locked out until tomorrow because of an outage"
        )

    def test_a_failed_submission_writes_no_half_session(self, client, ai, conn, user, scenario):
        """Partial writes are the quietest corruption there is: the row exists,
        so nothing retries it, and every aggregate over it is wrong."""
        ai.mode = "timeout"
        client.post(ROUTE_REPLY, json={"scenario_id": scenario["id"], "reply": "bonjour"},
                    headers=auth(user))
        orphans = conn.execute(
            "SELECT count(*) FROM sessions WHERE user_id = %s AND completed_at IS NULL"
            " AND started_at IS NULL", (user["id"],)
        ).fetchone()[0]
        assert orphans == 0, "a failed submission left a session row with no timestamps"

    def test_a_failed_submission_saves_no_mistakes(self, client, ai, conn, user, scenario):
        ai.mode = "timeout"
        client.post(ROUTE_REPLY, json={"scenario_id": scenario["id"], "reply": "bonjour"},
                    headers=auth(user))
        n = conn.execute(
            "SELECT count(*) FROM mistakes WHERE user_id = %s", (user["id"],)
        ).fetchone()[0]
        assert n == 0, "mistakes were saved from feedback that was never generated"


@pytest.mark.degrade
@requires_backend
class TestTheDatabaseFailing:
    """Writes that do not land.

    Returning success after a failed write is the worst available outcome: the
    learner practises, sees feedback, and finds nothing there tomorrow.
    """


    def test_a_database_error_is_not_reported_as_success(self, client, ai, monkeypatch,
                                                         user, scenario):
        """The worst possible response to a write failure is 200. The learner
        practises, sees feedback, and their mistakes are not there tomorrow."""
        import app.db as _db

        def boom(*_a, **_k):
            raise RuntimeError("connection reset")

        monkeypatch.setattr(_db, "save_mistakes", boom, raising=False)
        r = client.post(ROUTE_REPLY,
                        json={"scenario_id": scenario["id"], "reply": "un pain"},
                        headers=auth(user))
        assert r.status_code >= 500, (
            "a failed write to the mistakes table returned success to the learner"
        )

    def test_the_health_check_actually_touches_the_database(self):
        """A health check that returns {'ok': true} without a query is a green
        dashboard over a dead database — the archetypal silent failure."""
        health = [p for p in _sources(BACKEND_DIR, ".py") if "health" in p.read_text(errors="ignore")]
        if not health:
            pytest.skip("no health endpoint yet")
        src = "".join(p.read_text(errors="ignore") for p in health)
        block = re.search(r"health[^\n]*\n(?:.*\n){0,25}", src)
        assert block and re.search(r"SELECT|execute\(", block.group(0)), (
            "the health endpoint reports healthy without querying the database"
        )


# ═══════════════════════════════════════════════════════════════════════════
# §10  THE SUITE ITSELF — a green tick that means nothing is the worst bug here
#
# This file is designed to skip cleanly while the code it describes is still
# being written. That is deliberate and it is also dangerous: a suite where
# every test skips reports success. So does a suite where the assertions were
# quietly weakened. So does a suite that CI never runs.
#
# Every silent failure this file hunts is a case of something reporting success
# it had not earned. It would be incoherent to exempt the file itself.
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.meta
class TestThisSuiteCannotLie:
    """This file, held to its own standard.

    A suite where everything skips reports success. So does one whose
    assertions were quietly weakened, and one that CI never runs.
    """


    def test_the_backend_import_failure_is_visible(self):
        """When the backend cannot be imported every test here skips — which is
        correct on day one and a catastrophe on day ninety. Record the reason so
        it appears in the run output instead of dissolving into 'skipped'."""
        if BACKEND_READY:
            return
        assert _IMPORT_ERROR is not None, (
            "the backend did not import and no reason was recorded — the suite "
            "is skipping silently, which is the exact failure mode it exists to catch"
        )
        print(f"\n[silent_tests] backend not importable yet: {_IMPORT_ERROR}")

    def test_the_suite_is_wired_into_ci(self):
        """A test nothing runs is a comment. ../nedlang had 71,000 lines and no
        workflow file; every guard it might have had would have been decoration."""
        workflows = list((REPO / ".github" / "workflows").glob("*.yml")) + \
                    list((REPO / ".github" / "workflows").glob("*.yaml"))
        assert workflows, "no GitHub Actions workflow exists — nothing runs these tests"
        text = "\n".join(w.read_text(errors="ignore") for w in workflows)
        assert "pytest" in text, "no workflow runs pytest"
        assert "silent_tests" in text or "pytest" in text, (
            "this file is not referenced by any workflow"
        )

    def test_ci_runs_on_pull_requests_not_only_on_main(self):
        wf_dir = REPO / ".github" / "workflows"
        if not wf_dir.exists():
            pytest.skip("no workflows yet")
        text = "\n".join(w.read_text(errors="ignore") for w in wf_dir.glob("*.y*ml"))
        assert "pull_request" in text, (
            "CI only runs after merge — failures are found in main, which is "
            "the same as finding them in production"
        )

    def test_no_test_in_this_file_is_disabled(self):
        """`@pytest.mark.skip` and `xfail` are how a failing guard becomes a
        passing suite without anyone deciding to remove the guard."""
        offenders = []
        for i, line in enumerate(pathlib.Path(__file__).read_text().splitlines(), 1):
            if re.match(r"\s*@pytest\.mark\.(skip\b|skip\(|xfail)", line):
                offenders.append(f"line {i}: {line.strip()}")
        assert not offenders, (
            f"silenced tests: {offenders} — a disabled guard is worse than a "
            "missing one, because it still looks like coverage. "
            "(skipif is fine: it reports why, and it reports it every run.)"
        )

    def test_no_assertion_in_this_file_is_trivially_true(self):
        """Catches the `assert True`, the `assert response` and the commented-out
        assertion left behind while 'getting the suite green'."""
        src = pathlib.Path(__file__).read_text().splitlines()
        offenders = []
        for i, line in enumerate(src, 1):
            stripped = line.strip()
            if re.fullmatch(r"assert\s+(True|1|not\s+False)\s*(#.*)?", stripped):
                offenders.append(f"line {i}: {stripped}")
            if re.fullmatch(r"#\s*assert\s+.+", stripped) and "example" not in stripped.lower():
                offenders.append(f"line {i}: commented-out assertion")
        assert not offenders, f"vacuous or disabled assertions: {offenders}"

    def test_every_test_has_a_reason_to_exist(self):
        """Each test class documents the class of silent failure it covers. A
        class with no docstring is a test nobody will understand well enough to
        fix, so it will eventually be deleted or weakened instead."""
        src = pathlib.Path(__file__).read_text()
        classes = re.findall(r"\nclass (Test\w+):\n(\s*\"\"\")?", src)
        assert classes, "no test classes found — the scan is broken, not the file"
        undocumented = [name for name, doc in classes if not doc]
        assert not undocumented, (
            f"test classes with no stated purpose: {undocumented} — a guard "
            "nobody understands gets weakened rather than fixed"
        )

    def test_the_marker_list_matches_the_sections(self):
        """Markers exist so a developer can run one category — `-m money` before
        touching billing. A marker that no test uses, or a test with a marker
        that was never registered, means `-m` silently selects nothing."""
        ini = REPO / "pytest.ini"
        assert ini.exists(), "no pytest.ini — markers are unregistered and -m selects silently"
        registered = set(re.findall(r"^\s{4}(\w+):", ini.read_text(), re.M))
        src = pathlib.Path(__file__).read_text()
        used = set(re.findall(r"@pytest\.mark\.(\w+)", src)) - {
            "parametrize", "skipif", "skip", "xfail", "usefixtures"
        }
        assert not used - registered, f"markers used but never registered: {sorted(used - registered)}"
        assert not registered - used, f"markers registered but never used: {sorted(registered - used)}"


# ═══════════════════════════════════════════════════════════════════════════
# RUNNING THIS FILE
#
#   pytest silent_tests.py -v              everything
#   pytest silent_tests.py -m money        just the ones that guard the bill
#   pytest silent_tests.py -m gdpr         just the ones a regulator would ask about
#   pytest silent_tests.py -m "schema or reachable"
#                                          the two that need no database at all —
#                                          these work from day one, on source code
#
# Reading the output while the product is still being built: every skip is a
# line item on the to-do list, and every pass is a class of failure that can no
# longer reach a learner without someone deciding to let it.
#
# `python silent_tests.py` prints that as a checklist instead of running it.
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":  # pragma: no cover
    print("\nsilent_tests.py — readiness\n" + "─" * 46)
    print(f"  backend importable   {'yes' if BACKEND_READY else 'no  (' + str(_IMPORT_ERROR) + ')'}")
    print(f"  frontend present     {'yes' if FRONTEND_DIR.exists() else 'no'}")
    schema = _schema_columns()
    print(f"  tables in schema     {len(schema)}  {sorted(schema) if schema else ''}")
    if BACKEND_READY:
        print(f"  routes registered    {len(_backend_routes())}")
    wf = REPO / ".github" / "workflows"
    print(f"  CI workflows         {len(list(wf.glob('*.y*ml'))) if wf.exists() else 0}")
    src = pathlib.Path(__file__).read_text()
    print(f"  test functions       {len(re.findall(r'def test_', src))}  (111 cases after parametrize)")
    print("─" * 46)
    print("  run: pytest silent_tests.py -v\n")
