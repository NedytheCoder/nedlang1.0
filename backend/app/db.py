"""The one place that opens a database connection.

Nothing else in the backend calls `psycopg.connect` directly. That is the point:
the connection URL, the timeout, and the choice of role are decided once, here.

Connections are opened when a caller asks for one, never at import. Importing a
module must not require a network.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv

# Read here, not only in main.py — tests import app.db on its own.
# load_dotenv does not override variables that are already set, so on Render
# (where there is no .env) this is a no-op and the dashboard values win.
load_dotenv()


def _url() -> str:
    """The connection URL, resolved at call time so a missing variable fails
    on the first query rather than at import.

    APP_DATABASE_URL only, by Rule 7: per-request traffic uses the
    least-privileged role. There is deliberately no fallback to DATABASE_URL —
    that role has rolbypassrls, so falling back would keep the app working
    while silently switching every policy in schema.sql off. Missing config
    should break loudly, not quietly remove the isolation.
    """
    url = os.getenv("APP_DATABASE_URL")
    if not url:
        raise RuntimeError("Set APP_DATABASE_URL in .env (app_runtime, not the admin role)")
    return url


def connect():
    """Open a fresh connection. The caller must close it — prefer `cursor()`.

    connect_timeout bounds the handshake. Without it a network that silently
    drops packets parks the caller until the OS gives up, which on Linux is
    over two minutes.

    No row_factory, so rows come back as plain tuples and are read by position.
    That is what silent_tests.py expects — its `conn` fixture calls this
    function directly and then reads `row[0]`, `row[1]`. A dict_row factory
    here would break every one of those assertions.
    """
    return psycopg.connect(_url(), connect_timeout=15)


@contextmanager
def cursor():
    """One unit of work: commits on success, rolls back on any exception, and
    always closes.

    In psycopg3 `with conn` does all three by itself — unlike psycopg2, where
    it ended the transaction but left the connection open for the caller to
    close. Nothing is pooling connections yet, so closing is what we want.
    """
    with connect() as conn, conn.cursor() as cur:
        yield cur


# Next, once there are request paths: a psycopg_pool.ConnectionPool in front of
# connect(). nedlang measured a 0.8-1.3s TCP+TLS+auth handshake per request to a
# remote region without one. It is a separate package (psycopg-pool), so it is
# not installed yet — nothing calls this on a request path (Rule 1). Note that
# `cursor()` closes its connection today; against a pool it would return it.
