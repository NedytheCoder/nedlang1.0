# Rules

**Status:** blueprint · **Created:** 2026-09-15

Every agent — Claude, Codex, or any other — working on this repository is
obligated to follow these rules. Read this file before your first edit in a
session. If a rule conflicts with something you were asked to do, say so and
STOP; do not resolve it silently.

---

## Rule 1 — Never over-engineer. Never overcomplicate.

**This is the most important rule in this file.** The previous version of this
project died of features, not of bugs.

Write the minimum code that solves the actual problem.

- No abstraction until there are **three** real uses. Two is a coincidence.
- No configuration option nobody asked for.
- No error handling for situations that cannot occur.
- No "we'll need this later." Later will ask for it later.
- No new dependency when 20 lines of standard library will do.
- No new database table, service, queue, cache, or background worker without a
  written reason in `record.md`.

**The tests, applied honestly:**

1. Would a senior engineer reading this diff say it's overcomplicated?
2. Could this be half the lines? If yes, make it half the lines.
3. Can I name every layer's purpose in one sentence each? If not, remove a layer.
4. Does every changed line trace directly back to what was asked?

If you write 200 lines and 50 would do, delete the 150. Do this before you
report the task complete, not after someone complains.

---

## Rule 2 — Build only what was asked

The requested scope is the deliverable.

- Do not widen it ("while I was in there…"). Do not narrow it either.
- Do not refactor adjacent code that is not broken.
- Do not "improve" formatting, comments, or naming you were not sent to change.
- If you notice a real problem outside scope: **mention it, don't fix it.** Put
  it in the `Noticed but not touched` field of your `record.md` entry.
- If something in `product.md` is listed under Could have / Nice add-ons /
  Non-goals, you may not build it. Not even a small version. Not even "to make
  the rest easier."

---

## Rule 3 — Verify before you claim

Never report work as done based on the fact that you wrote it.

- Ran it? Say what you ran and what it printed.
- Didn't run it? Say that plainly: "written, not executed."
- Tests failing? Show the output. Do not describe a failure as a success.
- Skipped part of the task? Say which part and why.

"It should work" is not a status. Hedged completion claims are worse than an
honest "I couldn't verify this."

---

## Rule 4 — Log every task to `record.md`

**Obligatory. After every task, before you report back, append an entry to
`blueprint/record.md`.** No exceptions for small tasks.

Each entry must contain:

| Field | What goes in it |
|---|---|
| **Date & time** | `YYYY-MM-DD HH:MM` + timezone. Get it from the system, don't guess. |
| **Agent** | Which model/tool did the work |
| **Prompt** | What the user actually asked, quoted or closely paraphrased |
| **Added** | Files and features created — with paths |
| **Changed** | Files modified and what changed, in plain language |
| **Deleted** | Anything removed, and why. Never leave this blank if you deleted something. |
| **Commands run** | What you executed and the outcome |
| **Verified / Not verified** | Honestly split. What was actually proven vs. only written. |
| **Decisions** | Any judgement call made, and the reason |
| **Noticed but not touched** | Out-of-scope problems spotted (Rule 2) |
| **Next** | The obvious next step, if there is one |

Append at the top (newest first). Never rewrite or delete an older entry — if
an earlier entry was wrong, add a new one that corrects it and say so.

The format and a worked example live in `record.md` itself.

---

## Rule 5 — Money rules (AI calls)

Every model call costs real money from a project with no revenue.

- **No AI endpoint is reachable without a logged-in user.** Ever. No exceptions
  for demos, previews, or landing pages.
- **Every AI call is logged** before it returns: model, feature, user id, tokens
  in/out, estimated cost, timestamp.
- **Daily allowance is enforced and fails CLOSED.** If the usage check errors,
  deny the request. A blocked user is recoverable; a drained budget is not.
- **One AI call per learner submission.** Not three for self-consistency. Not a
  retry loop. One.
- **Cache anything that isn't personal** — scenario text, audio, prompts.
  Generate it once, serve it to everyone.
- **Pin the model explicitly.** Never ship a routing alias that can silently
  switch models between requests.
- Changing a model, a prompt, or a cap gets its own `record.md` entry with the
  before/after cost reasoning.

---

## Rule 6 — Privacy rules (we are the data controller, in Ireland)

- Collect the minimum. If a field isn't used by a feature that exists today,
  don't create the column.
- **Never send an email address, real name, or account history to an AI
  provider.** Scenario + learner response + internal user id only.
- Raw audio is deleted immediately after successful transcription. Keep the
  transcript only if a feature reads it.
- Account **deletion and export must be reachable by a button in the UI.** A
  backend endpoint with no caller is not a feature — it's a compliance failure
  that looks like compliance.
- Any new data collected, or any new third party receiving data, requires the
  privacy policy to be updated **in the same task**. Not the next one.
- No analytics, tracking pixels, or third-party scripts without an explicit,
  recorded decision.

---

## Rule 7 — Authorization rules

- One entry point for identity. One function that answers "who is this
  request?" Do not add a second.
- Every query filters on the server-resolved user id. Never on anything the
  client sent.
- **Per-request traffic uses the least-privileged database connection.** The
  admin/superuser connection is for migrations and offline scripts only — never
  on a request path, not even for "just one small lookup."
- If you catch yourself reaching for the admin connection to make something
  work, that is a signal the permissions are wrong. Fix the permissions.

---

## Rule 8 — Ask when it actually matters

- Ambiguity that changes the work materially → ask before building.
- Ambiguity that doesn't → pick the simpler option, state your assumption, and
  record it in `record.md`.
- Never ask a question you could answer by reading the repository for 30
  seconds.
- Do not stop and wait when you could deliver everything that isn't blocked and
  flag the one thing that is.

---

## Rule 9 — Destructive actions need a human

Confirm with the user before: deleting files you did not create, dropping or
altering a table, running anything against production data, force-pushing,
rewriting history, or sending anything to an external service.

Look at what you are about to overwrite before you overwrite it.

---

## Rule 10 — Build in this order

Do not start a later step because an earlier one is boring.

```
1. Database + auth            → a user can exist
2. Scenario display           → read + listen works, no AI at request time
3. Written reply + feedback   → the loop closes (ONE AI call)
4. Save mistake + due-today   → a reason to return tomorrow
5. Deletion + export + policy → a real person may now sign up
6. Speaking                   → second input mode, same feedback path
7. Email reminder             → only once step 4 proves people return
```

Step 5 is not optional and does not move later. Until it ships, only you and
people who know it's a prototype may use the product.

---

## Rule 11 — Every page works on a phone, and in both colour schemes

Two things, checked on every page you add or touch. Neither is a polish pass at
the end; both are cheaper to do while the markup is being written than to
retrofit.

**Responsive.** It must be usable at 320px wide. Single column by default,
widening at breakpoints — not a desktop layout that gets scrollbars. Padding and
type scale up, they do not start large: a flat `px-16` is 64px of gutter on each
side, which is a quarter of a small phone's screen.

**Light and dark.** Every colour you set needs its counterpart. A `bg-white`
without a `dark:` is a white slab on a dark page. Utilities that are genuinely
mode-agnostic — white text on a saturated brand colour, or a token like
`bg-foreground` that already flips — need nothing, but that has to be true, not
assumed.

Dark mode has **two** sources, in this order: an explicit choice from the switch
in the header, and failing that, the operating system's `prefers-color-scheme`.
The choice lives in one place — `data-theme` on `<html>` — and it is resolved
once, by the inline script in `layout.tsx`, before the first paint. Nothing else
recomputes it; the toggle and the stylesheet both read the attribute.

Three things hold that together, and breaking any one of them breaks dark mode in
a way that is invisible in review:

- `globals.css` redefines Tailwind's `dark:` variant with `@custom-variant`, so
  it fires on `:root[data-theme='dark']` **and** on `prefers-color-scheme: dark`
  when no attribute is set. The colour variables below it repeat the same two
  conditions in the same order. Change one, change both, or half a page goes
  dark and half stays light.
- The inline script in `layout.tsx` must stay in `<head>` and stay inline. Moved,
  deferred, or turned into something that hydrates, it stops running before paint
  and every load flashes the wrong colour.
- `color-scheme` follows the attribute, not the OS. It is what extends the theme
  to the parts of the UI the browser draws — carets, scrollbars, autofill, native
  focus rings. Do not set it back to `light dark`: that hands the decision to the
  OS, which is exactly what a person just overrode. Do not remove it either.

With JavaScript off, no attribute is ever written and the media query alone
decides — which is what this project did before the switch existed.

**Verify it in a real browser. Use Playwright.** Reading the generated CSS proves
a class was emitted, not that a human can use the page. Seams, overlaps, text
that wraps into a heading, a spinner invisible against its own button — none of
those are in the stylesheet. Drive the page.

What that means in practice: run the dev server, open the route, set the viewport
to 320px and to a desktop width, and render it under both
`color_scheme="light"` and `color_scheme="dark"`. Screenshot each. **Then look at
the screenshots** — agents can read image files, so this is a real check, not a
file you generate and ignore. For anything interactive, drive it: fill the field,
click the button, watch the request leave. That is the difference between
"written" and "executed", and Rule 3 turns on it.

**Setup, honestly.** The browsers are already cached at `~/.cache/ms-playwright`,
but as of 2026-09-17 Playwright does not run here. Two things are missing, and
the first needs a password you do not have:

```
sudo apt install -y libnss3 libnspr4     # chrome-headless-shell won't start without these
```

...plus the driver package itself, which is installed in neither project. Ask for
these rather than assuming they are there — check first, every time, because the
answer changes.

**When it genuinely is not available**, fall back: build, then read the generated
CSS. Each `dark:` class you wrote should appear **twice** — once inside
`@media (prefers-color-scheme:dark)` qualified by `:root:not([data-theme])`, and
once under `:root[data-theme='dark']` with no media query at all. Only one of the
two means the variant has been broken back to a single source. Responsive
utilities belong inside their `@media (min-width:...)` block. This is the weaker
check. Say plainly that no browser was used and that the claim is about
generated CSS rather than pixels — never let the fallback pass for the real
thing.
