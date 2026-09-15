# NedLang

> **NedLang gives English-speaking adults who freeze in everyday French one
> 10-minute conversation a day, and turns the mistakes they actually make into
> tomorrow's practice.**

If a feature doesn't serve that sentence, it doesn't ship. This is a deliberate
ground-up rebuild of an earlier version that died of features, not of bugs.

---

## Status: scaffold, not a product

**Nothing in the loop below is built yet.** Honest state as of 2026-09-15:

| Part | State |
|---|---|
| `blueprint/` | Complete. This is the real content of the repo today. |
| `frontend/` | Next.js 16 starter, untouched |
| `backend/` | FastAPI + uvicorn declared as deps; `main.py` still prints `Hello from backend!` |
| Database | Not created |
| Auth, AI, the daily loop | Not started |
| `silent_tests.py` | 99 tests (111 cases) written; most skip until there's a backend to import |
| `.github/workflows/ci.yml` | Written, never run green |

No one should sign up for this yet. Account deletion and export don't exist, and
that's a hard gate — see step 5 of the build order.

---

## The loop

The whole product is one loop, not four features sharing a login.

```
1. A real situation   "You're at the boulangerie. The baker asks what you want."
        ↓
2. READ               Short French dialogue, English hint available
        ↓
3. LISTEN             Same dialogue as audio — pre-generated, cached, free to replay
        ↓
4. WRITE or SPEAK     Type a reply. Or record one, later.
        ↓
5. ONE correction     Not a report card. One fix, one reason, one retry prompt.
        ↓
6. RETRY              Say it again, correctly. This is where learning happens.
        ↓
7. SAVED              The mistake gets a next_review_at date.
        ↓
8. TOMORROW           "3 phrases due today" — same mistake, new context.
```

Reading, listening, writing and speaking all live inside this one loop. That's
how four skills get covered without building four systems.

**The bet:** that *one correction you actually retry* beats *twenty corrections
you skim*. It isn't proven. v1 exists to find out cheaply.

---

## Repo layout

```
blueprint/          The governing docs. Read these before changing anything.
  product.md        The one sentence, the loop, MoSCoW scope, non-goals
  rules.md          What every agent working here must do. Rule 1: never over-engineer.
  architecture.md   Stack choices with the rejected alternatives written down
  record.md         Append-only log of every task performed here, newest first
frontend/           Next.js 16, React 19, Tailwind 4, TypeScript
backend/            FastAPI on Python 3.13, managed with uv
silent_tests.py     Tests for failures that don't announce themselves
pytest.ini          Marker registry — the markers do nothing without it
AGENTS.md           Read by Codex every turn
.claude/commands/   Slash commands for Claude Code
```

---

## Stack

| Layer | Choice | In one clause |
|---|---|---|
| Frontend | Next.js 16 + React 19 + Tailwind 4 | Already scaffolded; 6 pages = 6 files |
| Backend | FastAPI, Python 3.13, `uv` | Async by default, typed request bodies |
| Database | PostgreSQL on Supabase, **EU region** | Postgres only — no Auth, Storage or Realtime, to stay portable |
| Auth | Clerk | Sessions, verification and reset flows we'd otherwise own |
| AI | One pinned model, one env var, one module | A routing alias that silently switches models is a budget leak |
| Audio | Pre-generated and cached | Identical for every learner; generate once, serve forever |
| Email | Resend | Service reminders only — never marketing |
| Hosting | Vercel (frontend) + Render (backend), EU regions | |

Deliberately absent: Redis, Celery, Docker, a message queue, an admin dashboard,
WebSockets. The reasons are in `blueprint/architecture.md`.

---

## Getting started

**Prerequisites:** Node 20+, `uv`, and access to a Postgres instance.

```bash
# frontend
cd frontend
npm install
npm run dev          # http://localhost:3000

# backend
cd backend
uv sync
uv run main.py       # currently just prints "Hello from backend!"
```

There's no `.env` yet because there's nothing to configure. When there is, it's
git-ignored — secrets never enter this repo.

---

## Tests

```bash
python -m pytest silent_tests.py
```

`silent_tests.py` targets one specific enemy: **failures that report success.**
A column written but never read. An endpoint with no button. An export that
misses a table. A cap that fails open when the usage check errors.

Most tests skip today because there's no backend to import — that's intended.
The skip count is the progress bar. Run it now and it tells you what's missing,
rather than that everything's fine.

As of 2026-09-15 it reports **3 failed, 11 passed, 97 skipped**. The three
failures are real, not flakes: there is no delete-account button and no export
button in the frontend. That's Rule 10 step 5, and the suite is supposed to keep
failing until it's built.

---

## Rules for anyone working here — human or agent

`blueprint/rules.md` is binding. The short version:

1. **Never over-engineer.** If 200 lines are written and 50 would do, delete 150.
2. **Build only what was asked.** Spot a problem outside scope? Mention it, don't fix it.
3. **Verify before you claim.** "It should work" is not a status.
4. **Log every task to `record.md`.** No exceptions for small tasks.
5. **Money:** no AI call without a logged-in user; every call metered; the daily
   cap fails *closed*.
6. **Privacy:** we're the data controller, in Ireland. Never send an email
   address or real name to an AI provider.

---

## Build order

Do not start a later step because an earlier one is boring.

```
1. Database + auth            → a user can exist          ← next
2. Scenario display           → read + listen, no AI at request time
3. Written reply + feedback   → the loop closes (ONE AI call)
4. Save mistake + due-today   → a reason to return tomorrow
5. Deletion + export + policy → a real person may now sign up
6. Speaking                   → second input mode, same feedback path
7. Email reminder             → only once step 4 proves people return
```

**Step 5 does not move later.** Until it ships, only people who know this is a
prototype may use it.
