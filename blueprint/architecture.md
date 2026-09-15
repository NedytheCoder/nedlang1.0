# Architecture

**Status:** blueprint · **Created:** 2026-09-15

This document is written for both humans and models. Read `product.md` first —
it says *what* we are building. This says *how*, and *why each tool was chosen
over the alternatives*.

---

## Overview, in words

NedLang is a small web app with three moving parts and one job: run the daily
loop from `product.md` reliably and cheaply.

A learner opens the site and signs in. The home screen shows either **today's
scenario** or **the phrases due for review**. A scenario is a short French
situation — text plus audio — that was generated and cached ahead of time, so
opening one costs nothing but a database read. The learner types (or later,
records) a reply. That reply is the *only* thing that triggers a live AI call:
one request, one structured answer containing one fix, one reason, and one
retry prompt. The learner retries. The mistake is saved with a date to bring it
back. Tomorrow, it comes back.

Three deliberate architectural consequences:

1. **AI cost scales with active users, not page views.** Reading and listening
   are free; only submitting a reply costs money. One call per submission, hard
   daily cap, fails closed.
2. **The database is small enough to hold in your head.** Five tables plus one
   usage log. If a feature needs a sixth table, that feature needs a written
   justification first.
3. **Personal data stays in the EU and out of prompts.** We are the data
   controller, based in Ireland. The AI provider receives a scenario, a reply,
   and an anonymous id — never an email, a name, or an account history.

---

## Diagram 1 — What the learner experiences

```
     ┌──────────────────────────────────────────────────┐
     │                  HOME SCREEN                      │
     │                                                   │
     │   "3 phrases due today"   or   "Start today's     │
     │                                 conversation"     │
     └───────────────────────┬──────────────────────────┘
                             │
                             ▼
     ┌──────────────────────────────────────────────────┐
     │  SCENARIO       "You're at the boulangerie..."    │
     │                                                   │
     │   READ  📖  French text  +  English hint           │
     │   LISTEN 🔊  cached audio, same text               │
     └───────────────────────┬──────────────────────────┘
                             │
                             ▼
     ┌──────────────────────────────────────────────────┐
     │  YOUR REPLY                                       │
     │   ⌨  type it        (v1)                          │
     │   🎙  or record it   (v1.5)                        │
     └───────────────────────┬──────────────────────────┘
                             │  ◄── the only live AI call
                             ▼
     ┌──────────────────────────────────────────────────┐
     │  ONE CORRECTION                                   │
     │   ✗  "je voudrais un pain"                        │
     │   ✓  "je voudrais une baguette"                   │
     │   💡  why: "un pain" is a loaf, not a baguette     │
     │   ↻  now try: ask for two of them                 │
     └───────────────────────┬──────────────────────────┘
                             │
                             ▼
     ┌──────────────────────────────────────────────────┐
     │  RETRY  →  saved for review  →  back tomorrow      │
     └──────────────────────────────────────────────────┘
```

---

## Diagram 2 — System shape

```
   ┌──────────────┐
   │   LEARNER    │  browser
   └──────┬───────┘
          │ HTTPS
          ▼
   ┌─────────────────────────┐        ┌──────────────────┐
   │      FRONTEND           │───────►│  CLERK           │
   │      Next.js 16         │  auth  │  sign-in, JWT    │
   │      Vercel (EU)        │◄───────│                  │
   └──────┬──────────────────┘        └──────────────────┘
          │ REST + Bearer JWT
          ▼
   ┌─────────────────────────┐
   │      BACKEND            │        ┌──────────────────┐
   │      FastAPI / Python   │───────►│  AI PROVIDER     │
   │      Render (EU)        │  1 call│  pinned model    │
   │                         │◄───────│  text in/out     │
   │   · verifies the JWT    │        └──────────────────┘
   │   · enforces daily cap  │
   │   · logs every AI call  │        ┌──────────────────┐
   │   · owns all SQL        │───────►│  RESEND          │
   └──────┬──────────────────┘  opt-in│  1 daily email   │
          │                     only  └──────────────────┘
          ▼
   ┌─────────────────────────┐
   │   POSTGRES (Supabase)   │
   │   EU region             │
   │   5 tables + usage log  │
   └─────────────────────────┘
```

The frontend never talks to the AI provider or the database. Everything goes
through the backend, because that is where the cap, the log, and the identity
check live.

---

## Diagram 3 — One session, step by step

```
LEARNER        FRONTEND          BACKEND           DATABASE      AI PROVIDER
   │               │                 │                 │              │
   │─ open app ───►│                 │                 │              │
   │               │─ GET /today ───►│                 │              │
   │               │                 │─ due reviews? ─►│              │
   │               │                 │◄─── 3 due ──────│              │
   │               │◄─ scenario ─────│                 │              │
   │◄─ read+listen─│                 │                 │   no AI call
   │               │                 │                 │   no cost
   │               │                 │                 │              │
   │─ type reply ─►│                 │                 │              │
   │               │─ POST /reply ──►│                 │              │
   │               │                 │─ under cap? ───►│              │
   │               │                 │◄──── yes ───────│              │
   │               │                 │──── scenario + reply + user# ─►│
   │               │                 │◄─── {fix, why, retry} ─────────│
   │               │                 │─ log cost ─────►│              │
   │               │                 │─ save mistake ─►│              │
   │               │◄─ correction ───│  next_review_at │              │
   │◄─ one fix ────│                 │  = tomorrow     │              │
   │─ retry ──────►│                 │                 │   no AI call
   │               │                 │                 │              │
```

**If the cap is hit or the AI provider fails**, the backend returns a
pre-written correction from the scenario's own answer key. The learner sees a
working product, never an error page. (Rule 5, `product.md` M10.)

---

## Diagram 4 — How a mistake comes back

```
  Day 1   mistake made ────────► next_review_at = Day 2
            │
  Day 2   shown in new context
            ├─ got it right ───► next_review_at = Day 4    (interval doubles)
            └─ got it wrong ───► next_review_at = Day 3    (interval resets)
            │
  Day 4   got it right ────────► next_review_at = Day 8
  Day 8   got it right ────────► next_review_at = Day 16
  Day 16  got it right ────────► mastered, stops appearing
```

Doubling intervals, reset on failure. That is the entire algorithm — one
integer column and a date. **Do not replace this with SM-2, FSRS, or any other
scheduling library** until there is evidence this is the thing holding
retention back. (Rule 1.)

---

## Data model

Five tables and one log. Every column below exists because a feature in
`product.md` reads or writes it.

```
┌─────────────────────┐
│ users               │
├─────────────────────┤
│ id            PK    │
│ clerk_id      uniq  │  ← identity lives in Clerk, not here
│ email               │  ← for the reminder only; never sent to AI
│ goal          text  │  ← "order food on holiday"  (onboarding Q1)
│ comfort       text  │  ← "I freeze up"            (onboarding Q2)
│ email_reminders bool│  ← opt-in, default FALSE
│ created_at          │
└──────────┬──────────┘
           │ 1
           │
           │ many          ┌─────────────────────┐
┌──────────▼──────────┐    │ scenarios           │
│ sessions            │    ├─────────────────────┤
├─────────────────────┤    │ id            PK    │
│ id            PK    │    │ situation     text  │ "at the boulangerie"
│ user_id       FK ───┼───►│ text_fr       text  │ pre-generated
│ scenario_id   FK ───┼───►│ text_en       text  │ the hint
│ reply         text  │    │ audio_url     text  │ generated once, cached
│ feedback      jsonb │    │ answer_key    text  │ the graceful fallback
│ created_at          │    │ level         text  │ A2 / B1
└──────────┬──────────┘    └─────────────────────┘
           │ 1                    shared by all users — no personal data
           │
           │ many
┌──────────▼──────────┐
│ mistakes            │
├─────────────────────┤
│ id            PK    │
│ user_id       FK    │
│ session_id    FK    │
│ wrong         text  │  "je voudrais un pain"
│ right         text  │  "je voudrais une baguette"
│ why           text  │  the one-line explanation
│ next_review_at date │  ◄── the whole retention mechanic
│ interval_days int   │  ◄── doubles on success, resets on failure
│ mastered      bool  │
└─────────────────────┘

┌─────────────────────┐
│ ai_usage            │   append-only. Never deleted, never joined on.
├─────────────────────┤
│ id, user_id         │
│ feature             │  "feedback" | "tts"
│ model               │  the exact pinned id
│ tokens_in/out       │
│ estimated_cost      │  computed and stored at request time
│ created_at          │
└─────────────────────┘
```

**Why so few tables:** the old project had 31 and nobody could hold it in their
head. Every table is a join, a migration, an RLS policy, and a line in the GDPR
export. Five is enough to run the loop.

---

## Technology choices

Each row states what was chosen, the honest reason, and what was rejected. A
choice without a defensible reason is a choice that gets churned later.

### Frontend

| | |
|---|---|
| **Chosen** | **Next.js 16 + React 19** |
| **Why** | Already scaffolded. Server components keep the JS bundle small on the pages that matter (home, scenario), and the file-based router means 6 pages = 6 files. The previous project used it in production, so the failure modes are known. |
| **Rejected** | **SvelteKit / Remix** — likely nicer, but switching costs a rewrite for no user-visible gain. **Plain React + Vite** — then we hand-build routing, SSR and metadata. **Astro** — optimised for content sites; this is an app behind a login. |

| | |
|---|---|
| **Chosen** | **Tailwind CSS 4** |
| **Why** | Already scaffolded. Styles live next to markup, so there is no second file to keep in sync and no dead-CSS problem. For an app with ~8 screens, a design system would be overhead. |
| **Rejected** | **CSS Modules** — more files, more naming. **shadcn/ui or MUI** — a component library is the right call at 50 screens, not 8; at this size it's more API to learn than code it saves. **styled-components** — runtime cost, and the ecosystem has moved on. |

### Backend

| | |
|---|---|
| **Chosen** | **FastAPI on Python 3.13** |
| **Why** | Already scaffolded. Pydantic models give request validation *and* the schema for structured AI output from the same type definition — that is the single most useful thing in this product. Async-native, which matters when one request waits on an AI call. Every AI SDK ships Python first. |
| **Rejected** | **Next.js API routes only** — tempting (one language, one deploy) but puts the AI key, the spend cap and the database in the same process as the UI, and serverless timeouts fight long AI calls. The separation is the point. **Django** — an ORM, admin, migrations and auth we would immediately disable. **Express/Node** — fine, but loses Pydantic and the Python AI ecosystem. **Go** — faster than we need; slower to write. |

### Database

| | |
|---|---|
| **Chosen** | **PostgreSQL** |
| **Why** | `next_review_at <= today` is a date query over a relational join — exactly what Postgres is for. Row-Level Security lets the database enforce "users see only their own rows", so an application bug can't leak across accounts. JSONB stores AI feedback without a migration per field change. |
| **Rejected** | **SQLite** — genuinely fine for v1, rejected because migrating a live product with real user data later is a worse day than setting up Postgres now. **MongoDB** — this data is relational; we would rebuild joins by hand. **A vector database** — nothing here does semantic search. |

| | |
|---|---|
| **Chosen** | **Supabase (EU region) as the Postgres host** |
| **Why** | Managed Postgres with backups, pooling and an EU region — which is a **GDPR requirement**, not a preference (see the data-flow diagram below). Known from the previous project. Critically: it is *just Postgres*, so leaving means changing a connection string, not rewriting the app. |
| **Rejected** | **Neon** — comparable and good; Supabase wins only on prior operational familiarity. **AWS RDS** — more control, more ops work than a solo project should carry. **Self-hosted Postgres** — we would own backups, patching and uptime. |
| **Not using** | Supabase Auth, Storage, Realtime or the JS client. Postgres only. Using the whole platform is how you end up unable to leave. |

### Authentication

| | |
|---|---|
| **Chosen** | **Clerk** |
| **Why** | Email + Google sign-in, sessions, password reset and the "forgot password" flow are solved, hosted, and not our security surface. Known from the previous project, including the Next.js integration. Passwords never touch our database — which removes an entire category of breach from the privacy policy. |
| **Rejected** | **NextAuth/Auth.js** — free, but we own session handling, verification emails and reset flows; that is real weeks. **Supabase Auth** — would deepen the lock-in we just avoided. **Roll our own** — never, for a product handling personal data in the EU. |
| **Watch** | Clerk is a US company: confirm its DPA, sub-processors and EU data handling before real users. Note it in the privacy policy by name. |

### AI

| | |
|---|---|
| **Chosen** | **One pinned model for the feedback call, reached through a provider-agnostic client** |
| **Why** | The feedback call is small and bounded: short scenario + short reply in, strict JSON out. It does not need a frontier model, and the cost difference compounds across every submission from every user. Pinning means the output format is stable and we can always answer "where did this learner's text go?" |
| **Candidates** | `claude-haiku-4-5` — $1/$5 per million tokens in/out, the cheap default for a bounded task. `claude-sonnet-5` — $2/$10, if the corrections need more judgement. `claude-opus-5` — $5/$25, reserve for offline scenario authoring where quality matters and volume is ~zero. |
| **Decision** | Start on Haiku 4.5. Before launch, run ~20 real learner replies through Haiku and Sonnet side by side and read the corrections. If Haiku's corrections are wrong or unhelpful, move up — a cheap wrong answer is worth nothing. This check is a task, not an opinion. |
| **Rejected** | **A routing alias or `:free` model** — picks a different model per request, so the JSON shape and the teaching quality vary invisibly, and provider data-handling policies differ underneath. Fine for local development with fake data; **not** for real learner writing. **Self-hosted open model** — a GPU bill and an ops job to avoid a small API bill. |
| **Rule** | The model id lives in one environment variable, read in one module. Never hardcoded at a call site. The previous project's defaults silently aged two years because they were scattered. |

| | |
|---|---|
| **Chosen** | **Pre-generated, cached audio for listening** |
| **Why** | Scenario audio is identical for every learner. Generate each file once at authoring time, store it, serve it forever. This turns listening — a per-play cost in the naive design — into a static file. |
| **Rejected** | **Browser SpeechSynthesis** — free, but the voice varies by device and can be unusable for French on some platforms. **TTS at request time** — pays repeatedly for identical audio. |

### Email

| | |
|---|---|
| **Chosen** | **Resend** |
| **Why** | We send exactly one kind of message: "your French review is ready." Resend's free tier (~3,000/month, 100/day — **re-verify before relying on it**) covers a beta at one email per opted-in learner per day. Domain verification with SPF/DKIM is well documented, which is what actually determines whether the mail arrives. |
| **Rejected** | **SendGrid / Mailgun** — built for marketing volume; more product than we need. **AWS SES** — cheapest at scale, worst setup experience, and scale is not our problem. **Postmark** — excellent deliverability, no meaningful free tier. |
| **Rule** | Service reminders only. The moment an email says "upgrade" or "invite a friend" it is marketing, and Irish law needs separate affirmative consent for that. |

### Hosting

| | |
|---|---|
| **Chosen** | **Vercel (frontend) + Render (backend), both EU regions** |
| **Why** | Vercel is the reference host for Next.js — zero config, preview deploys per branch. Render runs a plain long-lived Python process, which suits an endpoint that waits on an AI call and a nightly job that scans for due reviews. Both have EU regions; the backend must be near the database. |
| **Rejected** | **Everything on Vercel** — serverless function timeouts and cold starts fight both AI calls and the reminder job. **Fly.io** — a strong alternative; Render wins on simplicity for one web service plus one cron. **A VPS** — we would own the OS, TLS, deploys and uptime. |

### Error monitoring

| | |
|---|---|
| **Chosen** | **Sentry — but not in week one** |
| **Why later** | Real value, but it is a third-party processor receiving data that may include learner content, so it needs a privacy-policy entry and a scrubbing config. Add it at Rule 10 step 5, alongside the policy work, not before. |
| **Until then** | Structured logs to stdout, read through the host's log viewer. |

### Deliberately absent

No Redis, no Celery, no message queue, no Docker Compose, no microservices, no
feature-flag service, no analytics platform, no CI matrix. Every one of these
is a correct choice for a product with traffic. None is a correct choice for a
product with zero users. (Rule 1.)

**One exception, and it is not optional:** a test file and a CI workflow that
runs it exist from the first feature. The previous project has 71,000 lines
and no CI, so nobody can change anything with confidence. Two tests running on
every push is not over-engineering — it is the thing that makes Rule 1
survivable.

---

## Where personal data goes

```
  LEARNER INPUT
       │
       ├─ email, name ──────────────► CLERK (US) ────► never leaves
       │                                              never sent to AI
       │
       ├─ goal, comfort ────────────► POSTGRES (EU)
       │
       ├─ written reply ────────────► POSTGRES (EU)
       │         │
       │         └──── scenario + reply + anonymous user id ──► AI PROVIDER
       │                (no email, no name, no history)
       │
       ├─ voice recording (v1.5) ───► transcribe ──► DELETE THE AUDIO
       │                                  │          immediately
       │                                  └─► transcript ──► POSTGRES (EU)
       │
       └─ email address ────────────► RESEND ────► only if reminders opted in
```

**Rules this diagram encodes:**

- The AI provider never receives an identifier that maps to a person outside our database.
- Raw audio is transient. It is transcribed and deleted in the same request.
- Every box in this diagram is a named processor in the privacy policy — no "trusted partners."
- Adding a box means updating the policy **in the same task** (Rule 6).
- Deletion must remove the learner's rows from every EU box, on a button they can find.

---

## Inherited lessons

Six things the previous project (`/home/nedyk/french/nedlang`) got wrong or
right, verified in its source, encoded as constraints here.

| Lesson | What happened there | What we do here |
|---|---|---|
| **Wire the delete button** | `DELETE /user/account` was fully built — soft delete, grace period, restore, ordered purge — and no page in the app ever called it. GDPR erasure existed and was unreachable. | Deletion is `product.md` M12 and Rule 10 step 5. A button, tested by a human clicking it. |
| **Never expose AI without a login** | Placement generation and grading were reachable with no account, rate-limited by IP only — and grading ran the model 3× per request. Rotating IPs draw straight from the budget. | Rule 5, absolute. Every AI path requires a logged-in user. One call per submission. |
| **Fail closed on caps** | Usage caps failed *open* by design — a telemetry hiccup silently removed all per-user spend limits at once. | Fail closed. A blocked user is recoverable; a drained budget is not. |
| **Least-privileged connection, always** | The module enforcing spend caps opened the admin BYPASSRLS connection on every expensive path — contradicting its own documented contract, unpooled, on the hottest routes. | Rule 7. Admin connection for migrations only. If you need it on a request path, the permissions are wrong. |
| **Pin models in one place** | Model defaults were scattered across call sites and quietly aged ~2 years. Pricing constants were marked "approximate — verify." | One env var, one module. Model or price change = a `record.md` entry. |
| **Keep the curriculum** | 41 complete curricula across 7 languages — French A1–C2, Spanish, German, English, Chinese HSK, Japanese JLPT, Korean TOPIK — roughly 19,500 lines of structured module/lesson data. The most valuable thing in that repository. | Port the French A1–B1 portion as scenario source material. Keep the rest on disk. It is not complexity — it is rows in a table, and it is expensive to recreate. |
