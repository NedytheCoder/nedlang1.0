# Product

**Status:** blueprint · **Created:** 2026-09-15 · **Owner:** Nedy

---

## The one sentence

> **NedLang gives English-speaking adults who freeze in everyday French one 10-minute conversation a day, and turns the mistakes they actually make into tomorrow's practice.**

If a feature does not serve that sentence, it does not ship in v1.

---

## Who this is for

**Yes:** adults, 16+, who already know some French but seize up in real situations — ordering, small talk with a colleague, a doctor's appointment, dealing with a landlord. They can read a menu. They cannot hold the conversation.

**No (for now):** absolute beginners, children, exam candidates, other language pairs, anyone needing a certificate.

Saying no here is the product decision. Everything below depends on it.

---

## The core value: one loop

The entire product is one loop. Not four features that happen to share a login.

```
  1. A real situation      "You're at the boulangerie. The baker asks what you want."
           ↓
  2. READ                  Short French dialogue on screen, English hint available
           ↓
  3. LISTEN                Same dialogue as audio (pre-generated, cached)
           ↓
  4. WRITE or SPEAK        Type a reply. Or record one when ready.
           ↓
  5. ONE correction        Not a report card. One fix, one reason, one retry prompt.
           ↓
  6. RETRY                 Say it again, correctly. This is where learning happens.
           ↓
  7. SAVED                 The mistake gets a next_review_at date.
           ↓
  8. TOMORROW              "3 phrases due today" — same mistake, new context.
```

Reading, listening, writing and speaking all live inside this one loop. That is
how we cover four skills without building four systems.

---

## Must have

Nothing ships to a real user until all of these exist.

| # | Item | Why it's a must |
|---|---|---|
| M1 | Sign up / sign in | Gate every AI call behind an account. Anonymous AI = unbounded spend. |
| M2 | Two onboarding questions: *what do you want to do in French?* and *how comfortable are you?* | Start learning in under 60 seconds. No placement test. |
| M3 | Today's scenario — read + listen | The entry point. Pre-generated text + cached audio. |
| M4 | Written reply | The safe way in. Lower friction than speaking on day one. |
| M5 | One structured correction: **fix / why / retry** | The differentiator. Not a grade — a next action. |
| M6 | Retry the corrected phrase | Without this it's feedback, not practice. |
| M7 | Mistake saved with `next_review_at` | The reason to come back tomorrow. |
| M8 | Home screen shows "N due today" | This *is* the notification system for v1. |
| M9 | Hard daily allowance per user, **fails closed** | One session + one retry per day. No cap = no business. |
| M10 | Graceful degradation when AI is unavailable | Show a pre-written correction, never a crash. |
| M11 | Privacy policy + terms, Irish/GDPR, naming real processors | Legally required before a real user signs up. |
| M12 | **Self-service account deletion and export, with a working button** | GDPR Art. 17/15. Learned the hard way — see `architecture.md` → Inherited lessons. |
| M13 | Per-request AI usage log: model, tokens, feature, user, estimated cost | You cannot control a cost you cannot see. |

---

## Should have

Ships soon after v1, once the loop is proven to bring people back.

- **S1 — Speaking.** Record a short reply → transcribe → same correction path. Not real-time. Not pronunciation *scoring*.
- **S2 — Opt-in daily email reminder.** One message, only when reviews are actually due. Off by default.
- **S3 — Choose your situation.** A small library (café, work, travel, doctor, admin) instead of one assigned scenario.
- **S4 — Simple progress view.** Phrases mastered, days practised. Honest numbers only.
- **S5 — Delete a single saved mistake.** Learner control over their own data, at the row level.

---

## Could have

Only after retention is real. Each of these is a *maybe*, not a plan.

- **C1 — Pricing page and a paid tier.** Free: 1 session/day. Paid: unlimited + speaking.
- **C2 — Quiet streaks.** Counted, shown once, never nagged about.
- **C3 — Pronunciation hints** (not scoring): "the *r* here is in your throat."
- **C4 — Scenario suggestions from the learner's own goal text.**
- **C5 — Weekly summary email.** Opt-in, separate consent from S2.

---

## Nice add-ons

Genuinely later. Written down so they stop occupying head-space now.

- **N1 — Other languages.** The old project has 41 seeded curricula (Spanish, German, Chinese, Japanese, Korean, English). That is a real asset — but it is a *later* asset.
- **N2 — Placement test.** Only once someone asks "what level am I?" more than once.
- **N3 — Real-time voice call.** The single most expensive feature imaginable. Needs a paying customer first.
- **N4 — Structured curriculum path** (modules, progression). Reuse from the old project when the daily loop earns it.
- **N5 — Certification / exams.** Requires calibration evidence we do not have and cannot fake.
- **N6 — Mobile push notifications.**

---

## Non-goals (v1)

State these plainly so no agent "helpfully" adds them:

- ❌ Open-ended AI chat box — feels flexible, teaches nothing measurable
- ❌ Placement or certification exams
- ❌ Real-time voice / WebSockets
- ❌ Multiple languages or frameworks (HSK / JLPT / TOPIK)
- ❌ Admin dashboard
- ❌ Gamification beyond a plain day count
- ❌ Grading every sentence like an examiner — correct selectively, or it feels punishing

---

## What we reuse from the old project

Port the **data and the hard-won lessons**, not the platform.

| Reuse | Skip |
|---|---|
| French A1–B1 curriculum seed data (topics, objectives) as scenario source material | The other 38 curricula (keep on disk, do not wire up) |
| Privacy policy / terms structure and wording | Consent versioning + reconsent gating machinery |
| The GDPR export + purge approach (ordered deletes, derived table list) | Soft-delete + 30-day restore flow — too much for v1 |
| Per-request cost logging idea (`request_log`) | Tiered cap tables, admin dashboards |
| Scenario/prompt-building patterns | Realtime voice, WebSocket auth, four grading pipelines |

---

## How we know it works

Six numbers. If these are flat, no new feature fixes it.

1. Visitor → first completed session
2. First session → second session (does anyone come back at all?)
3. Day-7 and day-30 return rate
4. Reviews completed ÷ reviews due
5. **AI cost per active user per day** — the number that decides if a business exists
6. Later: free → paid conversion

---

## The honest risk

The loop above is a bet: that *one correction you actually retry* beats *twenty corrections you skim*. It is not proven. v1 exists to find out cheaply — which is exactly why it must stay small.
