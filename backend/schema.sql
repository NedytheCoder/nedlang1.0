-- NedLang schema
--
-- Five tables and one usage log, per blueprint/architecture.md → Data model.
-- Every column here is read or written by something in product.md. A sixth
-- table needs a written justification in record.md first (Rule 1).
--
-- Ids are TEXT rather than serial: they are minted by the application
-- ("u_3f9a...", "s_1b2c..."), so a row can be referenced before it is
-- inserted and nothing leaks a count of our users.
--
-- This file is safe to run twice. Tables and indexes use IF NOT EXISTS;
-- policies are dropped before being created, because PostgreSQL has no
-- CREATE POLICY IF NOT EXISTS; GRANT and ALTER ... ROW LEVEL SECURITY are
-- already repeatable. All four verified against PostgreSQL 17.6.
--
-- What that does NOT give you: IF NOT EXISTS skips a table that already
-- exists with a DIFFERENT shape, silently. Re-running this file will never
-- add a column you added above, and never tell you it didn't. The day the
-- schema needs to change, it needs a migration, not a second run of this.


-- ── users ──────────────────────────────────────────────────────────────────
-- Identity lives in Clerk. This table holds only what a feature reads:
-- the two onboarding answers and the reminder opt-in. No password, ever.
CREATE TABLE IF NOT EXISTS users (
    id               text        PRIMARY KEY,
    clerk_id         text        NOT NULL UNIQUE,
    email            text        NOT NULL,       -- reminders only; never sent to AI
    goal             text,                       -- onboarding Q1: "order food on holiday"
    comfort          text,                       -- onboarding Q2: "I freeze up"
    email_reminders  boolean     NOT NULL DEFAULT false,   -- opt-in, Rule 6
    created_at       timestamptz NOT NULL DEFAULT now()
);


-- ── scenarios ──────────────────────────────────────────────────────────────
-- Shared by every learner. No personal data, so no RLS below.
-- Written at authoring time, read on every page view, never written at
-- request time — which is what makes reading and listening free.
CREATE TABLE IF NOT EXISTS scenarios (
    id          text PRIMARY KEY,
    situation   text NOT NULL,              -- "at the boulangerie"
    text_fr     text NOT NULL,
    text_en     text NOT NULL,              -- the hint
    audio_url   text,                       -- NULL until the audio is generated once
    answer_key  text NOT NULL,              -- the graceful fallback when AI is down (M10)
    level       text NOT NULL               -- A2 / B1
);


-- ── sessions ───────────────────────────────────────────────────────────────
-- One attempt at one scenario. `reply` and `feedback` are the content;
-- `completed_at` stays NULL for a session that was started and abandoned,
-- which is the only way to tell those apart.
CREATE TABLE IF NOT EXISTS sessions (
    id           text        PRIMARY KEY,
    user_id      text        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_id  text        NOT NULL REFERENCES scenarios(id),
    reply        text,                      -- the learner's own words
    feedback     jsonb,                     -- {fix, why, retry} — jsonb so the
                                            -- shape can change without a migration
    started_at   timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,               -- NULL = started, never finished
    turns        integer     NOT NULL DEFAULT 0
);


-- ── mistakes ───────────────────────────────────────────────────────────────
-- The retention mechanic. `next_review_at <= today` is the query the whole
-- product turns on.
--
-- `correct` was called "right" until 2026-09-16. RIGHT is a reserved word in
-- PostgreSQL (RIGHT JOIN), so the old name had to be double-quoted in every
-- query that ever touched it — and one forgotten pair of quotes is a syntax
-- error that only shows up when that code path runs. Renaming costs nothing
-- and removes the trap permanently. Nothing needs quoting now.
CREATE TABLE IF NOT EXISTS mistakes (
    id             text    PRIMARY KEY,
    user_id        text    NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id     text    REFERENCES sessions(id) ON DELETE SET NULL,
    wrong          text    NOT NULL,        -- "je voudrais un pain"
    correct        text    NOT NULL,        -- "je voudrais une baguette"
    why            text    NOT NULL,        -- the one-line explanation
    next_review_at date    NOT NULL,
    interval_days  integer NOT NULL DEFAULT 1,   -- doubles on success, resets on failure
    mastered       boolean NOT NULL DEFAULT false
);


-- ── ai_usage ───────────────────────────────────────────────────────────────
-- Rule 5: every model call is logged before it returns. You cannot control a
-- cost you cannot see. `estimated_cost` is computed and stored at request
-- time, because the price of a model changes and the history should not.
--
-- NOT NULL on every column is deliberate: a usage row with a NULL model or a
-- NULL cost is worse than no row, because it makes the total look smaller
-- than it is.
CREATE TABLE IF NOT EXISTS ai_usage (
    id              text          PRIMARY KEY,
    user_id         text          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feature         text          NOT NULL,    -- "feedback" | "tts"
    model           text          NOT NULL,    -- the exact pinned id, never an alias
    tokens_in       integer       NOT NULL,
    tokens_out      integer       NOT NULL,
    estimated_cost  numeric(10,6) NOT NULL,
    created_at      timestamptz   NOT NULL DEFAULT now()
);


-- ── indexes ────────────────────────────────────────────────────────────────
-- Three, one per query that runs on every request. No speculative indexes:
-- each one costs write time, and nothing here has enough rows to guess with.

-- "what is due today?" — the home screen, every visit
CREATE INDEX IF NOT EXISTS mistakes_due ON mistakes (user_id, next_review_at)
    WHERE NOT mastered;

-- "how much has this user spent today?" — the cap check, before every AI call
CREATE INDEX IF NOT EXISTS ai_usage_daily ON ai_usage (user_id, created_at);

-- "has this user already submitted today?" — the daily submission cap
CREATE INDEX IF NOT EXISTS sessions_by_user ON sessions (user_id, started_at);


-- ── row-level security ─────────────────────────────────────────────────────
-- Rule 7: per-request traffic uses a least-privileged connection, and the
-- database — not the application — enforces "you see only your own rows".
-- In ../nedlang the module enforcing spend caps opened an admin BYPASSRLS
-- connection on its hottest path, contradicting its own documented contract.
-- The defence against that is making the ordinary connection incapable of
-- crossing accounts.
--
-- The role's password is set outside this file and never committed.
-- FORCE is what stops the table owner from quietly bypassing its own policy.

-- The role is created once, by hand, before this file is first run — the
-- GRANTs below need it to exist. PostgreSQL has no CREATE ROLE IF NOT EXISTS,
-- so a repeatable version needs a DO block that checks pg_roles first.
-- Left commented either way: the password must never enter the repository.
--
-- CREATE ROLE app_runtime LOGIN PASSWORD :'app_runtime_password';

-- GRANT and ALTER ... ROW LEVEL SECURITY are repeatable as written.
GRANT USAGE ON SCHEMA public TO app_runtime;
GRANT SELECT ON scenarios TO app_runtime;   -- shared, read-only at request time
GRANT SELECT, INSERT, UPDATE, DELETE ON users, sessions, mistakes TO app_runtime;
GRANT SELECT, INSERT, DELETE ON ai_usage TO app_runtime;   -- never UPDATE: append-only

ALTER TABLE users    ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mistakes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_usage ENABLE ROW LEVEL SECURITY;

ALTER TABLE users    FORCE ROW LEVEL SECURITY;
ALTER TABLE sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE mistakes FORCE ROW LEVEL SECURITY;
ALTER TABLE ai_usage FORCE ROW LEVEL SECURITY;

-- The application sets app.current_user_id once, when it resolves the Clerk
-- token. Nothing the client sends reaches these policies.
DROP POLICY IF EXISTS users_self ON users;
CREATE POLICY users_self ON users
    USING      (id = current_setting('app.current_user_id', true))
    WITH CHECK (id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS sessions_owner ON sessions;
CREATE POLICY sessions_owner ON sessions
    USING      (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS mistakes_owner ON mistakes;
CREATE POLICY mistakes_owner ON mistakes
    USING      (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS ai_usage_owner ON ai_usage;
CREATE POLICY ai_usage_owner ON ai_usage
    USING      (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

-- scenarios carries no personal data, so it gets no policy and no RLS.
-- A permissive policy that always evaluates true is a comment pretending to
-- be a control.
--
-- DISABLE is not redundant here. Supabase turns RLS on automatically for every
-- new table in the public schema, so scenarios arrived with RLS enabled and no
-- policy — which is default-deny. Measured: app_runtime read 0 of 1 rows, with
-- no error. Reading a scenario is step 2 of Rule 10, so this would have shipped
-- as "the page is blank" with nothing in the logs.
ALTER TABLE scenarios DISABLE ROW LEVEL SECURITY;


-- ── identity resolution ────────────────────────────────────────────────────
-- Clerk knows a learner by their Clerk id. Every policy above compares against
-- users.id, which this application mints. Something has to translate between
-- the two, and app_runtime cannot: users_self hides the row until you already
-- know the id you are looking for. Measured 2026-09-16 — the plain query
-- `select id from users where clerk_id = ...` returns 0 rows over the app
-- connection, with no error.
--
-- SECURITY DEFINER runs the body as the function's owner (postgres), which is
-- exempt from the policy. That exemption is the entire privileged surface here:
-- one clerk_id in, one users.id out. It cannot list learners, read an email, or
-- return anybody else's row. Measured: with EXECUTE granted, app_runtime still
-- reads 0 rows from `select count(*) from users`. This is not a way around RLS,
-- it is the one hole RLS requires, cut to the shape of the question.
--
-- SET search_path is not optional. A SECURITY DEFINER function without it can
-- be pointed at a `users` table the caller controls, and then it returns
-- whatever that caller wants it to.
CREATE OR REPLACE FUNCTION app_resolve_user(p_clerk_id text)
    RETURNS text
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = public
AS $$ SELECT id FROM users WHERE clerk_id = p_clerk_id $$;

-- CREATE FUNCTION grants EXECUTE to PUBLIC by default, and Supabase's default
-- privileges additionally grant it to anon / authenticated / service_role — the
-- roles behind its REST API. Measured 2026-09-16: all three were granted EXECUTE
-- the moment this function was created. We do not use that API (architecture.md
-- "Not using Supabase Auth, Storage, Realtime or the JS client"), and anon is
-- reachable without any credential, so it is revoked here rather than left to
-- the assumption that the API stays switched off.
--
-- Naming the three Supabase roles makes this line Supabase-specific. The
-- portable version is a DO block looping over pg_roles; it is eight lines
-- instead of one, and if this project ever leaves Supabase the line fails loudly
-- with "role does not exist" at a moment when connection strings are being
-- rewritten anyway. One line, deliberately (Rule 1).
REVOKE ALL ON FUNCTION app_resolve_user(text) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION app_resolve_user(text) TO app_runtime;


-- ── open decisions ─────────────────────────────────────────────────────────
-- Recorded here because the next person to touch this file needs them.
--
-- 1. ai_usage rows are deleted with the user (ON DELETE CASCADE), because
--    GDPR erasure must clear every user-owned table. architecture.md calls
--    this log "append-only, never deleted". Erasure wins; the alternative is
--    keeping the cost row and dropping the user link, which is a real option
--    but needs a decision, not a default.
--
-- Settled on 2026-09-16. Both were disagreements with silent_tests.py, and
-- both were settled by fixing the side that was actually wrong:
--   - "right" -> correct, so nothing ever needs quoting again. The live
--     database was renamed in place; the table held 0 rows, so nothing moved.
--   - ai_usage keeps feature / tokens_in / tokens_out. architecture.md,
--     Rule 5 and silent_tests.py:445 all already agreed with this file; only
--     the seeder at silent_tests.py:1133 disagreed, and it was the stale one.
