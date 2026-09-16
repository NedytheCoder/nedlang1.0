"""Operational commands. Run by hand; never imported by the application.

    python scripts.py status      what is actually on the database right now
    python scripts.py migrate     apply schema.sql — idempotent, safe to re-run
    python scripts.py isolation   prove RLS still keeps two learners apart
    python scripts.py freeze      re-export requirements.txt from uv.lock

The database commands use DATABASE_URL — the admin role — because migrations and
inspection are exactly what Rule 7 reserves it for. `app.db` deliberately cannot
do any of this: it connects as app_runtime, which has no CREATE privilege.

app_runtime was created once, by hand. If another project ever needs one:

    CREATE ROLE app_runtime LOGIN NOBYPASSRLS PASSWORD '<token_urlsafe(24)>';

then set APP_DATABASE_URL to DATABASE_URL with the username swapped to
"app_runtime.<project_ref>". The ".<project_ref>" suffix is not optional —
Supabase's pooler routes by tenant and rejects a bare role name with EAUTHQUERY.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env")

TABLES = ("users", "scenarios", "sessions", "mistakes", "ai_usage")


def admin():
    """The admin connection. Migrations and offline scripts only (Rule 7)."""
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    return psycopg.connect(url, connect_timeout=15, autocommit=True)


def status() -> None:
    """Read-only. The first thing to run when something looks wrong."""
    with admin() as conn, conn.cursor() as cur:
        cur.execute("select current_user, current_database(), version()")
        user, dbname, version = cur.fetchone()
        print(f"{version.split(',')[0]}\nconnected as {user.split('.')[0]} to {dbname}\n")

        cur.execute("""select c.relname, c.relrowsecurity, c.relforcerowsecurity
                       from pg_class c join pg_namespace n on n.oid = c.relnamespace
                       where n.nspname = 'public' and c.relkind = 'r'
                       order by c.relname""")
        tables = cur.fetchall()
        if not tables:
            print("no tables — run `python scripts.py migrate`")
            return
        print(f"{'table':12s} {'rls':6s} {'force':6s} rows")
        for name, rls, force in tables:
            cur.execute(f"select count(*) from {name}")
            print(f"{name:12s} {str(rls):6s} {str(force):6s} {cur.fetchone()[0]}")

        cur.execute("select policyname from pg_policies where schemaname='public' order by 1")
        print("\npolicies:", ", ".join(r[0] for r in cur.fetchall()) or "none")
        cur.execute("select 1 from pg_roles where rolname='app_runtime'")
        print("app_runtime role:", "present" if cur.fetchone() else "MISSING")


def migrate() -> None:
    """Apply schema.sql. It is idempotent, so re-running is a no-op — which is
    why the object counts before and after are worth printing: an unchanged
    count is the expected result, not a failure to do anything."""
    sql = (HERE / "schema.sql").read_text()

    def counts(cur):
        cur.execute("""select
            (select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
             where n.nspname='public' and c.relkind='r'),
            (select count(*) from pg_indexes where schemaname='public'),
            (select count(*) from pg_policies where schemaname='public')""")
        return cur.fetchone()

    conn = admin()
    conn.autocommit = False          # all of it, or none of it
    try:
        with conn.cursor() as cur:
            before = counts(cur)
            cur.execute(sql)
            after = counts(cur)
        conn.commit()
        labels = ("tables", "indexes", "policies")
        print("applied schema.sql")
        for label, b, a in zip(labels, before, after):
            print(f"  {label:9s} {b} -> {a}" + ("  (unchanged)" if b == a else ""))
    except Exception as exc:
        conn.rollback()
        sys.exit(f"rolled back, nothing applied: {type(exc).__name__}: {exc}")
    finally:
        conn.close()


def isolation() -> None:
    """Seed two learners, then read them back over the app_runtime connection
    to confirm neither can see the other. Worth re-running after any change to
    schema.sql — a policy can be dropped by accident and nothing else notices."""
    app_url = os.getenv("APP_DATABASE_URL")
    if not app_url:
        sys.exit("APP_DATABASE_URL is not set — this check needs the app_runtime role")

    conn, app = admin(), psycopg.connect(app_url, connect_timeout=15)
    ids = ("_rlscheck_a", "_rlscheck_b")
    try:
        with conn.cursor() as cur:
            for uid in ids:
                cur.execute("insert into users (id, clerk_id, email) values (%s,%s,%s)",
                            (uid, "clerk" + uid, uid + "@example.invalid"))
        ok = True
        for me in ids:
            with app.cursor() as cur:
                # set_config(name, value, is_local=true) is SET LOCAL as a
                # function call. It is not a stylistic choice: psycopg3 binds
                # parameters server-side, and SET does not accept a bound
                # parameter — `SET LOCAL x = %s` fails with a syntax error on
                # $1. set_config takes the value as an argument, so it does.
                cur.execute("SELECT set_config('app.current_user_id', %s, true)", (me,))
                cur.execute("select id from users where id = any(%s) order by id", (list(ids),))
                seen = [r[0] for r in cur.fetchall()]
            app.rollback()           # ends the transaction; the local setting dies with it
            ok &= seen == [me]
            print(f"  as {me}: sees {seen}")
        with app.cursor() as cur:
            cur.execute("select count(*) from users")
            unset = cur.fetchone()[0]
        app.rollback()
        print(f"  identity unset: {unset} rows visible")
        print("\nPASS" if ok and unset == 0 else "\nFAIL — learners can see each other")
        sys.exit(0 if ok and unset == 0 else 1)
    finally:
        with conn.cursor() as cur:
            cur.execute("delete from users where id = any(%s)", (list(ids),))
        conn.close()
        app.close()


def freeze() -> None:
    """Regenerate requirements.txt from uv.lock. Run this whenever a dependency
    changes: Render installs from requirements.txt and has never heard of uv,
    so the two drifting apart is a deploy that silently ships without a package.
    CI checks the same thing.

    --no-dev keeps the dev group out. It is not cosmetic: `uv export` includes
    dev dependencies by default, so without this flag pytest and its
    dependencies land in the file Render installs from, and the production
    server builds a test framework it will never run. Measured 2026-09-16 —
    pytest, pluggy and iniconfig all appeared in the export until this was
    added."""
    out = subprocess.run(
        ["uv", "export", "--frozen", "--no-hashes", "--no-emit-project",
         "--no-dev", "--format", "requirements-txt"],
        cwd=HERE, capture_output=True, text=True,
    )
    if out.returncode:
        sys.exit(out.stderr.strip())
    target = HERE / "requirements.txt"
    old = target.read_text() if target.exists() else ""
    target.write_text(out.stdout)
    print("requirements.txt unchanged" if old == out.stdout else "requirements.txt updated")


COMMANDS = {"status": status, "migrate": migrate, "isolation": isolation, "freeze": freeze}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(f"usage: python scripts.py [{' | '.join(COMMANDS)}]")
    COMMANDS[sys.argv[1]]()
