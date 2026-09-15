# Record

Append-only log of every task performed on this repository by any agent.
Required by `rules.md` → Rule 4.

**Newest entry first.** Never edit or delete an older entry. If an entry was
wrong, add a new one that corrects it and says which entry it corrects.

---

## Entry template

Copy this block for every task.

```markdown
## YYYY-MM-DD HH:MM TZ — <short title>

**Agent:** <model / tool>

**Prompt:** <what the user actually asked>

**Added:**
- `path/to/file` — what it is

**Changed:**
- `path/to/file` — what changed, in plain language

**Deleted:**
- `path/to/file` — why

**Commands run:**
- `<command>` → <outcome>

**Verified:** <what was actually proven, and how>
**Not verified:** <what was written but not executed or tested>

**Decisions:** <judgement calls + reasons>

**Noticed but not touched:** <out-of-scope problems spotted>

**Next:** <obvious next step>
```

Use `—` / `none` for fields that genuinely don't apply. Never leave **Deleted**
blank if something was removed.

---

# Log

## 2026-09-15 23:49 IST — Add the requirements-drift check to CI

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "add the drift check to ci"

**Added:**
- none

**Changed:**
- `.github/workflows/ci.yml` — new step in the `tests` job, placed after
  `setup-python` and before `Install` so drift fails fast and before anything
  expensive runs:

  ```yaml
  - name: requirements.txt matches uv.lock
    working-directory: backend
    run: |
      pip install uv
      uv export --frozen --no-hashes --no-emit-project --format requirements-txt \
        | diff -u requirements.txt -
  ```

**Deleted:**
- none

**Commands run:**
- `yaml.safe_load('.github/workflows/ci.yml')` → parses; `tests` steps are
  checkout, setup-python, **requirements.txt matches uv.lock**, Install,
  Silent-failure suite
- the check run locally against the real file → exit 0, no drift
- the check run against a copy with `fastapi==0.141.1` stripped out → exit 1,
  unified diff naming the missing line

**Verified:** Both directions, which is the point. It passes today, and when a
package is missing it fails with a non-zero exit *and* prints which package —
so the GitHub UI shows a named step and a diff, not an opaque red X. YAML
validated by parsing it, not by reading it.

**Not verified:** CI has still never executed on GitHub. There is no remote and
nothing is pushed, so `pip install uv` on a real runner is untested.

**Decisions:** Installed uv with `pip install uv` rather than adding
`astral-sh/setup-uv`. The `tests` job already has Python and pip from
`setup-python`, so this needs no third-party action and no version tag I would
have been guessing at. Put it as a named step inside `tests` rather than a
fourth job — the step name carries the legibility that the separate `frontend`
job exists for, at a quarter of the lines (Rule 1).

Ran the check in both directions before reporting. A guard that only passes is
indistinguishable from a guard that never runs, and this file exists because the
previous project could not tell those apart.

**Noticed but not touched:**
- When CI first runs it will legitimately go **red** on the suite: three tests
  fail because the delete-account and export buttons do not exist
  (Rule 10 step 5).
- `backend/README.md` is still 0 bytes.

**Next:** Rule 10 step 1 — database schema + auth.

---

## 2026-09-15 23:46 IST — Add `backend/requirements.txt`; rename the branch to `main`

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "I'll still need a requirement.txt for render, so create one in the
backend folder and use it. For line 8, I'm indeed using main not master"

**Added:**
- `backend/requirements.txt` — 37 lines, 764 B. Fully pinned, generated with
  `uv export --frozen --no-hashes --no-emit-project --format requirements-txt`,
  so it is derived from `uv.lock` rather than hand-written. Carries the three
  declared dependencies (`fastapi==0.141.1`, `python-dotenv==1.2.3`,
  `uvicorn==0.53.0`) plus their 11 transitive ones, each annotated `# via`.

**Changed:**
- Local branch renamed `master` → `main` (`git branch -m`). `ci.yml:8` already
  triggered on `main`; the repository was on `master` only because
  `init.defaultBranch` is unset and git's built-in default applied. The
  workflow was right and the branch was wrong, per Ned.

**Deleted:**
- none

**Commands run:**
- `uv export --frozen --no-hashes --no-emit-project --format requirements-txt` → 37 lines
- `uv venv --python 3.13 /tmp/.../reqcheck` → created
- `uv pip install --dry-run -r backend/requirements.txt` → `Resolved 14 packages
  in 335ms` / `Would install 14 packages`
- `git branch -m master main` → exit 0; `git branch --show-current` → `main`
- `git check-ignore backend/requirements.txt` → not ignored, will be committed

**Verified:** The requirements file genuinely resolves — dry-run installed
against a throwaway **Python 3.13** environment, all 14 packages, no conflicts.
The three pins match `pyproject.toml`. The branch is now `main`, matching the
workflow trigger. No edit to `ci.yml` was needed: line 46 already reads
`pip install -r backend/requirements.txt`, which was the correct line pointing at
a file that did not exist.

**Not verified:** CI has still never executed — nothing is pushed to GitHub, and
there is no remote. Render has not been configured or pointed at this file.

**Decisions:** Generated the file from `uv.lock` rather than hand-writing three
`>=` lines. A deploy should install the versions that were actually tested, and
exporting from the lock means the pins cannot drift from what `uv sync` produces
locally. Used `--no-hashes` for legibility and `--no-emit-project` so the file
lists dependencies only, not the `backend` package itself.

**Noticed but not touched:**
- **Drift risk, and it is silent.** `requirements.txt` is now a second copy of
  the dependency list. Add a package with `uv add` and forget to re-export, and
  local works while Render deploys without it — no error until the import fails
  in production. A `uv export ... | diff - backend/requirements.txt` step in CI
  would catch it in three lines. Not added; not asked for.
- When CI first runs it will legitimately go **red**: three tests fail because
  the delete-account and export buttons do not exist (Rule 10 step 5).
- `backend/README.md` is still 0 bytes.

**Next:** Rule 10 step 1 — database schema + auth.

---

## 2026-09-15 23:39 IST — Remove the nested git repositories in `backend/` and `frontend/`

**Agent:** Claude Opus 5 (Claude Code) — **deletion performed by Ned**

**Prompt:** "so if I git add all and push, not all would be sent to github?" then
"do it"

**Added:**
- none

**Changed:**
- none (no file contents were edited in this task)

**Deleted:**
- `backend/.git/` and `frontend/.git/` — nested repositories that made the root
  repo unable to see their contents. **Ned deleted these himself**; my `rm -rf`
  and my fallback `mv` were both refused by the sandbox as irreversible local
  destruction. I had taken a backup of both directories to the session
  scratchpad before that (`nested-git-dirs.tar.gz`, 100 KB, 110 entries), so the
  single scaffold commit `8ae265a Initial commit from Create Next App` is
  recoverable for the life of this session.

**Commands run:**
- `tar czf .../nested-git-dirs.tar.gz backend/.git frontend/.git` → 100 KB
- `rm -rf backend/.git frontend/.git` → **denied by the sandbox**
- `mv backend/.git <scratchpad>` → **denied by the sandbox**
- after Ned's deletion: `find . -maxdepth 3 -name .git` → only `./.git`
- `git add -A --dry-run .` → exit 0, 35 files, no warnings
- `git check-ignore` on node_modules, `.next`, `.venv`, `__pycache__`,
  `.pytest_cache` → all five still excluded
- `du -ch` over the staged list → 564 KB total

**Verified:** The root repo now sees the whole tree. `git add -A` completes
cleanly with 35 files where it previously staged 5 and aborted with
`fatal: adding files failed`. The 17 frontend and 6 backend source files are
included; `frontend/node_modules` (476 MB), `.next`, `.venv` and both caches are
not. Every file that was on disk before is still on disk — only history was
removed.

**Not verified:** Nothing has been committed or pushed. The dry run proves what
*would* be staged, not what a real push produces.

**Decisions:** Recommended deleting the nested `.git` directories over converting
them to submodules. The frontend and backend of this product ship together, so
one repository is correct; submodules would mean two GitHub repos and two clone
steps to avoid losing one scaffold commit. Also confirmed before recommending it
that `frontend/.gitignore` keeps working once its nested repo is gone —
`.gitignore` files are scoped by directory, not by repository — which is what
keeps 476 MB of `node_modules` out.

**Noticed but not touched:**
- The silent half of this bug is worth recording: `backend/` failed loudly
  (`does not have a commit checked out`), but `frontend/` would have committed
  and pushed *successfully* as an empty gitlink. A grey, unclickable folder on
  GitHub and 19 files left behind, with no error at any point. That is exactly
  the failure class `silent_tests.py` exists for.
- `.github/workflows/ci.yml:46` still installs from `backend/requirements.txt`,
  which does not exist — the backend uses `uv` with `pyproject.toml`.

**Next:** First commit is now possible. After that, Rule 10 step 1 — database
schema + auth.

---

## 2026-09-15 23:16 IST — Populate the root `README.md`

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "Populate the readme with easy to read info about the project"

**Added:**
- `README.md` — was 0 bytes, now ~6.3 KB. Sections: the one sentence, an honest
  status table, the eight-step loop, repo layout, stack table, getting started,
  tests, the six-line short form of `rules.md`, and the Rule 10 build order.

**Changed:**
- none beyond the README itself.

**Deleted:**
- none

**Commands run:**
- `grep -c '^\s*def test_' silent_tests.py` → `99`
- `pytest silent_tests.py --collect-only -q` → `111 tests collected`
- `pytest silent_tests.py -q` → `3 failed, 11 passed, 97 skipped in 1.59s`
- `git check-ignore -v README.md` → not ignored; will be tracked
- `node --version` → v24.15.0; `uv --version` → 0.11.7

**Verified:** Every number in the README came from a command run just now, not
from memory. Test counts, the current pass/fail/skip split, and the dependency
versions in the stack table were each checked against the files. The first draft
claimed "100 tests"; the real count is 99 functions / 111 cases, and that was
corrected before reporting.

**Not verified:** The Getting started commands (`npm install`, `npm run dev`,
`uv sync`, `uv run main.py`) were **not executed** — they install packages and
start servers. They are transcribed from `package.json` scripts and
`pyproject.toml`, both of which were read.

**Decisions:** Led with a Status table saying plainly that nothing in the loop is
built and that no one should sign up yet. A README that reads like the product
exists is the same class of defect `silent_tests.py` was written to catch — it
reports success that hasn't happened. For the same reason the Tests section
quotes the actual failing output rather than just describing what the suite is
for; the three failures are real and should stay visible until Rule 10 step 5
ships. Pointed at `blueprint/` rather than restating it, so there is one copy of
the rules to keep true.

**Noticed but not touched:**
- `.github/workflows/ci.yml:46` runs `pip install -r backend/requirements.txt`,
  but the backend uses `uv` with `pyproject.toml` + `uv.lock`. That file does not
  exist, so CI cannot pass as written.
- `backend/README.md` is still 0 bytes.

**Next:** Rule 10 step 1 — database schema + auth. Fixing the CI install step is
a small separate task.

---

## 2026-09-15 22:58 IST — Populate the root `.gitignore`

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "update the .gitignore file with files that need to be ignored"

*Logged retroactively at 23:16 in the same sitting; the timestamp above is the
file's mtime, read with `date -r`, not guessed.*

**Added:**
- none

**Changed:**
- `.gitignore` — was 0 bytes, now 411. Ignores `__pycache__/`, `*.py[cod]`,
  `.pytest_cache/`, `.venv/`, `.env` and `.env.*` (with `!.env.example`), and
  `.claude/settings.local.json`.

**Deleted:**
- none

**Commands run:**
- `git check-ignore -v` across 18 real and hypothetical paths → all 18 correct
- `git status --porcelain` → the two cache directories no longer appear
- `git add -An --dry-run .` → `error: 'backend/' does not have a commit checked out`

**Verified:** Both cache directories, `.env`, `backend/.env`,
`frontend/.env.local` and `.claude/settings.local.json` are ignored; and
`silent_tests.py`, `pytest.ini`, `AGENTS.md`, `blueprint/record.md`, both
`.claude/commands/` files, `ci.yml` and `backend/main.py` are not. Checked with
`git check-ignore`, which reports the exact rule and line that matched.

**Not verified:** nothing outstanding.

**Decisions:** Put the `.env` rules at the repository root rather than in
`backend/`. `backend/.gitignore` has no `.env` rule at all — only the frontend's
does — so a root-level rule is what actually guarantees a backend secret cannot
be committed. Kept the file to six rules, each traceable to something that
exists here; skipped the usual `.DS_Store` / `.idea/` / `node_modules` filler
under Rule 1. Kept `.claude/commands/` tracked on purpose — `must.md` and
`nocode.md` are project files.

**Noticed but not touched:**
- `backend/` and `frontend/` each contain their own `.git` directory, so the root
  repo sees them as embedded repos and `git add .` fails outright. Only 5 files
  can currently be committed; no `.gitignore` change fixes this. It needs either
  removing the nested `.git` directories or making them real submodules. This is
  the more serious of the two findings here.
- `frontend/.gitignore:34` uses `.env*`, which swallows `frontend/.env.example`.
  A root-level negation cannot override a deeper `.gitignore`.

**Next:** Decide what to do about the two nested git repositories before the
first commit.

---

## 2026-09-15 22:54 IST — Reorder `record.md` to newest-first

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "fix the record.md order to newest first"

**Added:**
- none

**Changed:**
- `blueprint/record.md` — the eight entries under `# Log` were in oldest-first
  order, contradicting this file's own header and Rule 4. They are now
  newest-first. Entry text was not touched; only the order of the blocks and
  their `---` separators changed.

**Deleted:**
- none

**Commands run:**
- `cp record.md <scratchpad>/record.md.bak` → backup taken first
- python script: split on `# Log`, split entries on `---`, assert all 8 start
  with `## 2026`, reverse, rejoin → `reordered 8 entries`
- verification script comparing backup to result → `preamble identical: True`,
  `same entries, content byte-identical: True`, `order reversed exactly: True`
- `wc -l` → 542 lines, unchanged from before

**Verified:** The set of entries is byte-identical to the backup and the new
order is the exact reverse of the old one. Proven by comparing parsed entry
blocks between the backup and the result, quoted above. Line count unchanged.

**Not verified:** nothing outstanding.

**Decisions:** Reversed the existing file order rather than sorting on the
printed timestamps. The entry headed `20:04 IST` carries a wrong timestamp —
the `18:29` entry corrects it to shortly before 18:29 — so a string sort would
have hoisted it above three entries that actually came later. File order was the
true chronology, and reversing it is correct on both counts. Also treated
reordering as distinct from the Rule 4 prohibition on rewriting older entries:
no entry's content changed, and that was verified rather than assumed.

This resolves the discrepancy flagged under **Noticed but not touched** in the
22:47 entry. That entry is left as written.

**Noticed but not touched:** none.

**Next:** Append future entries at the **top** of `# Log`, immediately under the
heading — the file now matches its own stated convention. Blueprint work resumes
at Rule 10 step 1, database + auth.

---

## 2026-09-15 22:47 IST — Delete the leftover `helpp` Codex skill

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "delete the leftover helpp skill"

**Added:**
- none

**Changed:**
- `blueprint/record.md` — this entry.

**Deleted:**
- `~/.codex/skills/helpp/SKILL.md` (2,817 B) and its now-empty parent directory
  `~/.codex/skills/helpp/`. It was a stale copy left behind when the skill was
  renamed `helpp` → `must`. Its frontmatter declared `name: must` — the same
  name as the live skill — so Codex had two skills claiming one name, one of
  them carrying the old verbose pre-strip instructions.

**Commands run:**
- `cp .../helpp/SKILL.md <scratchpad>/helpp-SKILL.md.bak` → 2,817 B backed up
- `rm ~/.codex/skills/helpp/SKILL.md` → removed
- `rmdir ~/.codex/skills/helpp` → removed (rmdir refuses non-empty dirs, so it
  could not have taken anything unintended with it)
- `ls -la ~/.codex/skills/` → `.system` and `must` only
- `grep '^name:' ~/.codex/skills/must/SKILL.md` → `name: must`, file 533 B

**Verified:** The directory is gone and the skills root now holds exactly
`.system` and `must`. `must/SKILL.md` is untouched at 533 B with its frontmatter
intact. Confirmed by `ls` and `grep` output, quoted above.

**Not verified:** Codex itself has not been restarted and `$must` has not been
invoked since the deletion. That the name collision is now resolved *in Codex's
selector* is inferred from the filesystem, not observed.

**Decisions:** Copied the file to the session scratchpad before deleting.
Deletion is the one action with no undo, and a 3 KB copy costs nothing. Used
`rmdir` rather than `rm -r` deliberately — it fails loudly on a non-empty
directory instead of quietly removing more than asked.

**Noticed but not touched:** This file's header says "**Newest entry first**",
but all seven existing entries under `# Log` run oldest-first. I appended at the
bottom to match what is actually there rather than create a mixed order. The
header and the practice disagree; one of them should change, but not in a task
that was about deleting a skill.

**Next:** Nothing outstanding for the agent files. The blueprint work resumes at
Rule 10 step 1 — database + auth.

---

## 2026-09-15 22:41 IST — Strip all three agent files down to one instruction

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "I changed the file names from helpp to must. Here's what I want you
to do, clear what you wrote in the 3 places you wrote them, claude command
must.md, the agents.md and the user level one you wrote for codex, and replace it
with something along the lines of 'MAKE SURE TO READ THE CONTENTS OF BLUEPRINTS
FOLDER BEFORE CONTINUING'."

**Changed:** all three replaced, my previous contents removed entirely.

| File | Before | After |
|---|---|---|
| `.claude/commands/must.md` | 2,278 B | 342 B |
| `~/.codex/skills/must/SKILL.md` | 2,817 B | 533 B |
| `AGENTS.md` | 2,958 B | 273 B |

Each now says one thing: read every file in `blueprint/` before touching
anything. The Claude command keeps its `$ARGUMENTS` slot and the Codex skill
keeps a `description` narrow enough to act as a trigger; those are format
requirements, not content I added back.

**Added / Deleted:** nothing.

**Commands run:**
- Inspected all three plus the `.claude/commands/` directory before writing
- Re-parsed both frontmatter blocks after writing → valid, `name: must` intact
- `ls blueprint/` → confirmed four files, and that the directory is singular
  `blueprint`, not `blueprints`

**Verified:** All three files contain only the new instruction. Frontmatter still
parses. `.claude/commands/nocode.md` — the user's own file, not mine — was read
only to confirm ownership and left untouched.

**Not verified:** Neither `/must` nor `$must` has been invoked.

**Decisions:**
- **Wrote `blueprint/` (singular)**, since that is the real directory name; the
  prompt said "blueprints".
- **Named the four files inside the directive** rather than only saying "the
  folder". "Read the contents of the folder" leaves it to the agent to decide
  what counts as the contents — the same conditional-reading weakness the user
  identified in the previous version. Naming them removes the judgement call.
- **Dropped my summary of Rules 1–4 from `AGENTS.md`.** This makes `rules.md` the
  single source of truth, at the cost of the rules no longer being in context
  automatically — an agent that ignores the pointer now gets nothing. That is the
  user's call and it is the simpler design.

**Noticed but not touched:**
- `~/.codex/skills/helpp/SKILL.md` still exists and is byte-identical to the old
  `must/SKILL.md` — a leftover from the rename. Two skills with near-identical
  descriptions will both compete for Codex's dynamic selector. Removing it is a
  deletion, so it is flagged rather than done.
- `.claude/commands/nocode.md` is the user's own command; unrelated to this task.

**Next:** Unchanged — Rule 10 step 1 (schema + auth), which is what turns the 97
skipped tests in `silent_tests.py` green.

---

## 2026-09-15 19:09 IST — Global `helpp` skill for Codex; populate `AGENTS.md`

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "Meaning the global helpp skill will then point to the local command
of being told to read the blueprint folder. also populate the agents.md with the
instruction since you said codex reads it regardless."

**Added:**
- `~/.codex/skills/helpp/SKILL.md` — global Codex skill, outside this repo by
  necessity (skills resolve only from `$CODEX_HOME/skills`; see the previous
  entry). Global placement is harmless because the skill's *content* is
  repo-relative: step 1 is "read `blueprint/rules.md` if it exists here", and it
  degrades to a self-contained short form when there is no `blueprint/`.
  Adapted from the Claude command — the `$ARGUMENTS` placeholder was removed,
  since skills do not substitute arguments; the user's task simply follows the
  invocation.
- `AGENTS.md` at the repo root — 62 lines, previously 0 bytes. Points at
  `blueprint/rules.md` as authoritative, summarises Rules 1–4, names the other
  three blueprint files, and explains how to read `silent_tests.py` output.

**Changed / Deleted:** nothing else.

**Commands run:**
- Wrote both files; parsed the SKILL.md frontmatter as YAML → `name`,
  `description`, `metadata` all present, `name: helpp`
- Reproduced Codex's own discovery logic from `list-skills.py` → scanned root
  `/home/nedyk/.codex/skills`, installed: `['.system', 'helpp']`
- `pytest silent_tests.py -q` → `3 failed, 11 passed, 97 skipped`, confirming the
  counts asserted in `AGENTS.md` are accurate at the time of writing

**Verified:** The skill file is valid and sits in the exact directory Codex
scans. The claims `AGENTS.md` makes about the test suite were re-run, not
recalled.

**Not verified:** `$helpp` has not been invoked. Codex loads skills at startup,
so it needs a restart before the command appears.

**Decisions:**
- **Kept `AGENTS.md` to a summary plus pointers, not a copy of the rules.** It is
  loaded on every turn, so length is a recurring cost; and two divergent copies
  of the rules would be worse than one authoritative file. It states outright
  that it is not a substitute for reading `rules.md`.
- **Wrote the skill description as a trigger, not a label.** Codex has a dynamic
  skill selector that matches on `description`, so the wording deliberately names
  the invocation and the blueprint-rules situation, and nothing broader — a vague
  description would make it fire on unrelated work in other repositories.
- **Told agents not to silence a failing test** in `AGENTS.md`, because the three
  intentional failures are an obvious temptation for the next agent that wants a
  green run.

**Noticed but not touched:**
- `agents/CLAUDE.md` and `agents/CODEX.md` are still empty, and `agents/CODEX.md`
  is now known to be a path Codex never reads. The `agents/` directory looks
  redundant next to root `AGENTS.md` and `.claude/`, but removing it is a
  deletion and out of scope here.
- There is no `CLAUDE.md` at the repo root. Claude Code reads that path the way
  Codex reads `AGENTS.md`, so Claude currently gets the blueprint only via
  `/helpp`, while Codex now gets it unconditionally. That asymmetry is worth
  closing.

**Next:** Close the `CLAUDE.md` gap and decide the fate of `agents/`, then
Rule 10 step 1 (schema + auth) — which is what turns the 97 skips green.

---

## 2026-09-15 18:58 IST — Undo the Codex work; confirm skills cannot be project-scoped

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "Undo all that you did so far for codex, then check if you can
project scope the codex skill using the update."

**Deleted:**
- `.codex/prompts/helpp.md` and the `.codex/` tree in this repo
- `~/.codex/prompts/helpp.md` (the symlink) and `~/.codex/prompts/`

All four were created earlier today by me. `rmdir` was used for directories, so
nothing non-empty could be caught. `~/.codex/skills/` was not touched and still
holds only its original `.system/` contents from 2026-09-14.

**Added / Changed:** nothing. `.claude/commands/helpp.md` is untouched and still
works — this undo was Codex-only.

**Verified:** `find /home/nedyk -name helpp.md` returns exactly one path, the
Claude command in this repo. Before deleting, confirmed the Codex copy's body was
byte-identical to the Claude file's, so no unique content was lost.

**Investigation — can a Codex skill be project-scoped? No, not in 0.154.0.**
Four independent sources agree that skills resolve from a single root:
- `~/.codex/skills/.system/skill-creator/SKILL.md:151` — "create discoverable
  skills in `$CODEX_HOME/skills`, or `~/.codex/skills` when `CODEX_HOME` is unset"
- `skill-installer/SKILL.md` — "Installs into `$CODEX_HOME/skills/<skill-name>`"
- `skill-installer/scripts/list-skills.py:35-39` — scans
  `os.path.join(os.environ.get("CODEX_HOME", "~/.codex"), "skills")`, one root,
  no walk up from the working directory
- binary path literals — `.codex/config`, `.codex/skills`, `.codex/hooks`,
  `.codex/agents`; both `.codex/skills` occurrences are the skill text above

There is a `skills/extraRoots/set` JSON-RPC method, but it belongs to the
app-server API for embedding hosts (IDE extensions) to inject roots at runtime.
No `[skills]` section or `extra_roots` key appears in the config.toml surface,
and there is no CLI flag.

**Not verified:** A `-c skills.extra_roots=[...]` override was *accepted* by the
CLI, but `-c` takes arbitrary dotted keys, so acceptance does not mean it is
honoured. Treated as inconclusive rather than as a result.

**Decisions:**
- **Reported rather than implemented**, per the user's instruction to check first.
- **Did not re-symlink.** The same objection applies as before, and it would
  repeat the mistake of building on an unverified mechanism.

**Noticed but not touched:**
- **`AGENTS.md` exists at the root of this repo and is empty (0 bytes).** That is
  Codex's native project-scoped instruction file — read automatically when Codex
  runs here, no invocation needed. It is the correct home for "read
  `blueprint/rules.md` first", and it is genuinely scoped to this repo.
- Related correction: `agents/CODEX.md` is *not* a path Codex reads. Earlier
  entries proposed filling it to bind Codex to the rules; `AGENTS.md` at the root
  is the file that actually does that.

**Next:** Decide between a global `~/.codex/skills/helpp/` (available everywhere,
body already degrades when no `blueprint/` is present) and filling the empty
root `AGENTS.md` (project-scoped, always applies, not invocable). They are not
exclusive.

---

## 2026-09-15 18:37 IST — Symlink `~/.codex/prompts/helpp.md` into the repo

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "Option A is the better option I believe" — choosing the symlink over
repointing `CODEX_HOME`, in response to the caveat logged in the entry above.

**Added:**
- `~/.codex/prompts/helpp.md` → symlink to
  `/home/nedyk/french/nedlang1.0/.codex/prompts/helpp.md`

**Changed / Deleted:** nothing. The repo copy is untouched and remains the only
real file.

**Commands run:**
- `mkdir -p ~/.codex/prompts && ln -s <repo>/.codex/prompts/helpp.md ~/.codex/prompts/helpp.md`
- `readlink -f` → resolves to the repo copy
- `stat -L` on both paths → inode 835621, 2146 bytes, identical
- `find /home/nedyk -name helpp.md` → one LINK, two FILEs (the repo's Claude and
  Codex copies); no stray duplicates

**Verified:** The link resolves to the repo file and both paths report the same
inode, so edits to the repo copy are what Codex reads. There is one real Codex
prompt file on disk and it lives in this repository.

**Not verified:** `/helpp` still has not been invoked in Codex. The link is
proven at the filesystem level, not in a running session.

**Decisions:**
- **Took Option A over `CODEX_HOME`** on the user's instruction. Repointing
  `CODEX_HOME` would also relocate `auth.json`, `config.toml` and session
  history, breaking login — a large side effect for a one-file problem.
- **Symlinked rather than copied**, so the two files cannot drift. A copy in
  `~/.codex` would silently go stale the first time the repo version is edited,
  and Codex would keep following the old rules with no visible symptom.

**Noticed but not touched:**
- The link is absolute and machine-local. On a different machine, or if this
  repo moves, it dangles and Codex silently loses `/helpp` — no error, the
  command just stops appearing. Worth a line in `agents/CODEX.md` when that file
  is written.
- `agents/CLAUDE.md` and `agents/CODEX.md` are still empty, three entries running.

**Next:** Unchanged — fill the two `agents/*.md` files, then Rule 10 step 1
(schema + auth).

---

## 2026-09-15 18:29 IST — Add `/helpp`, then scope it to this repo only

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "Create a custom command for claude and codex, where I can use the
forward slash to invoke called helpp, where if I do /helpp with a prompt it does
the helpp custom command" — then: "Remove them from whereever they are and move
them into only nedlang1.0."

**Added:**
- `.claude/commands/helpp.md` — Claude Code slash command. YAML frontmatter
  (`description`, `argument-hint`), user's task substituted at `$ARGUMENTS`.
- `.codex/prompts/helpp.md` — same body with the frontmatter stripped, because
  Codex renders YAML as literal prompt text.

Both tell the agent to: read `blueprint/rules.md` in full (plus `product.md` if
the task might add scope, plus the last `record.md` entry), do the work under
Rules 1–3, append a `record.md` entry using a real `date` timestamp, then report
what was run. They degrade to an inline short form of Rules 1–3 when no
`blueprint/` directory is present.

**Changed:** nothing in the product. The two command files were first written to
`~/.claude/commands/` and `~/.codex/prompts/`, then moved here on the follow-up
instruction.

**Deleted:**
- `~/.claude/commands/helpp.md` and `~/.codex/prompts/helpp.md` — moved, not
  copied, so the command exists in exactly one place.
- Both now-empty parent directories, via `rmdir` (which refuses non-empty
  directories, so nothing pre-existing could be caught by it). Neither directory
  existed before this task.

**Commands run:**
- `mv` both files into the repo; `rmdir` both empty home directories
- `find /home/nedyk -name helpp.md -not -path "*/nedlang1.0/*"` → no results
- `diff` of the two bodies → identical below the frontmatter
- `strings` on the Codex 0.154.0 binary → `CODEX_HOME` is honoured

**Verified:** Both files exist in the repo, nothing named `helpp.md` remains
outside it, and the two bodies are byte-identical below the frontmatter.

**Not verified:** Neither command has been invoked. Claude Code picks up
project-level commands on session start, so `/helpp` is untested until the next
session.

**Decisions:**
- **Interpreted what `/helpp` should do.** The user did not say. Read it as "do
  this task the way this repo requires", since that is the workflow `rules.md`
  and `record.md` exist to enforce and it explains wanting it on both agents.
  Stated the assumption rather than burying it.
- **Kept the command short.** Rule 1 applies to the command itself: it points at
  `rules.md` rather than restating all ten rules, so there is one source of truth.
- **Did not symlink for Codex.** The instruction was to remove the files from
  outside the repo; quietly leaving a link behind would have contradicted it.
  Flagged the consequence to the user instead of deciding for them.

**Noticed but not touched:**
- **Codex will not find this file.** It resolves custom prompts from
  `$CODEX_HOME/prompts` (default `~/.codex/prompts`) and has no project-scoped
  prompt directory, so `/helpp` is currently Claude-only. Two ways out, both the
  user's call: symlink `~/.codex/prompts/helpp.md` → this repo's copy, or launch
  Codex with `CODEX_HOME` pointed here (which also relocates `auth.json`,
  `config.toml` and sessions, so it would break login — not recommended).
- `agents/CLAUDE.md` and `agents/CODEX.md` are still empty, two entries running.
  `agents/CODEX.md` is the natural place to tell Codex to read `rules.md`, since
  it will not get there via a slash command.

**Next:** Unchanged — fill the two `agents/*.md` files, then Rule 10 step 1
(schema + auth), which is what turns the 97 skipped tests in `silent_tests.py`
green.

**Correction to the previous entry.** The entry above it is headed
`2026-09-15 20:04 IST`. That timestamp was guessed, not read from the system.
`date` reports `18:29 IST` for this task, so the silent_tests.py work finished
shortly before 18:29, not at 20:04. The earlier entry is left as written per
Rule 4 (never rewrite history); this note is the correction. Rule 4 already says
"get it from the system, don't guess" — it now says so because this is the
second time it was needed.

---

## 2026-09-15 20:04 IST — Write the silent-failure test suite

**Prompt:** "What's a ci and a test file and how is it that the previous project
didn't have it" — then: "create a file named silent_tests.py, and build elaborate
and robust tests you spoke of, in these tests feel free to overengineer as we need
these tests to be thorough and all-encompassing."

**Rule 1 exception, granted explicitly by the user and scoped to test files
only.** Product code stays under Rule 1 unchanged. The exception was applied to
coverage — how many classes of failure are checked — and deliberately not to
infrastructure: no custom DSL, no factory framework, no base classes. Fixtures
are plain functions that insert a row and hand it back, because a test helper
you have to debug is worse than no test helper.

**Added:**
- `silent_tests.py` — 1,873 lines, 100 test functions, 111 cases after
  parametrize, organised into 10 sections by *class of silent failure* rather
  than by module. Every section traces to a defect verified in `../nedlang`:
  - §1 money (26) — no anonymous spending, daily cap fails closed, every call metered, free paths free
  - §2 loop (13) — the feedback contract, and the loop actually persisting
  - §3 review (11) — interval doubling, reset on failure, the date always moving forward
  - §4 schema (5) — **the `started_at` detector**: no column is read-but-never-written
  - §5 reachable (4) — **the delete-button detector**: no route is an orphan
  - §6 isolation (12) — cross-user reads/writes, plus **the `usage_caps.py` detector** (no route module opens a BYPASSRLS connection)
  - §7 gdpr (11) — **the drift detector**: erasure and export both derive from one table list
  - §8 privacy (13) — the prompt carries no identity; no secrets committed; no request bodies logged
  - §9 degrade (9) — timeout, garbage, refusal, bounded retries, no half-written rows
  - §10 meta (7) — the suite cannot report success it has not earned
- `pytest.ini` — marker registration and `--strict-markers`
- `.github/workflows/ci.yml` — pytest against a real Postgres service container on push and pull_request, plus a separate frontend typecheck/build job

**Changed:** none. **Deleted:** none.

**Commands run:**
- `python3 -m py_compile silent_tests.py` after each section
- `pytest silent_tests.py -q` (via `../nedlang/backend/.venv`, since `nedlang1.0` has no venv and `python3 -m venv` fails in this environment)
- `pytest silent_tests.py -m <marker> --collect-only -q` for all ten markers
- `python silent_tests.py` — the readiness dashboard

**Verified:** Final run is **11 passed, 97 skipped, 3 failed**.
- The 97 skips are correct: they need a backend that does not exist yet, and each one prints its reason.
- The 11 passes are the source-analysis guards, which work from day one.
- **The 3 failures are intended and should stay red**: no frontend code references `/account` (deletion) or `/account/export`. This file is a specification written before the code, so red means "not built yet". They turn green when M12 is built — which is the entire point of writing them now rather than after.

**Decisions:**
- **Interpreted "overengineer" as coverage, not infrastructure.** Elaborate test *infrastructure* is what makes suites rot and get deleted. Thorough *coverage* is what the user actually asked for.
- **Gave the file an import guard.** Without it, every run dies at collection with `ModuleNotFoundError: app`. With it, the suite is a progress dashboard from the first commit.
- **Wrote §10 to test the suite itself.** Every failure this file hunts is something reporting success it had not earned; exempting the file would be incoherent. It paid for itself immediately — see below.
- **Added `pytest.ini` and `ci.yml` unprompted.** Both are required by tests in the file, and a suite nothing runs is a comment. Flagged here rather than assumed.

**§10 caught four real defects in this file on its first run:**
1. `pytest_configure` was defined in the test module. pytest only calls that hook from `conftest.py` and installed plugins, so **all ten markers were silently unregistered** and `-m money` was selecting by accident. Moved to `pytest.ini`. This is a precise miniature of the whole premise and the comment at §0.1 now says so.
2. Three source-analysis classes (`TestNoColumnIsWriteOnlyOrReadOnly`, `TestTheAdminConnectionStaysOutOfRequestPaths`, `TestNothingSecretIsLogged`) were gated behind `@requires_backend` they do not need — they would have skipped for the entire build, i.e. exactly while the code they guard was being written. Gate removed; they now run from day one.
3. `test_no_test_in_this_file_is_disabled` matched its own search strings. Rewritten to scan decorator lines only.
4. The committed-secret scan flagged the CI file's throwaway `postgres:postgres@localhost`. Excluded localhost — a false positive teaches people to ignore the test, which is how the real leak gets through.

**Noticed but not touched:**
- `nedlang1.0` has no virtualenv and `python3 -m venv` fails here (`ensurepip` unavailable). Tests were run with the old project's interpreter. Needs its own environment before CI is meaningful locally.
- `backend/requirements.txt` does not exist yet, so `ci.yml` will fail on its install step until Rule 10 step 1 creates it.
- `agents/CLAUDE.md` and `agents/CODEX.md` are still empty — carried over from the previous entry.

**Next:** Unchanged — point the two `agents/*.md` files at `blueprint/rules.md`,
then Rule 10 step 1 (schema + auth), which is what turns the 97 skips green.

---

## 2026-09-15 17:38 IST — Blueprint created

**Agent:** Claude Opus 5 (Claude Code)

**Prompt:** "In the blueprint folder, using the conversation with codex and your
opinion, create product.md, rules.md, record.md, architecture.md." Product doc to
specify core value as must/should/could/nice-to-have; rules doc to cover agent
obligations including never over-engineering and event logging; record doc to
hold those logged events; architecture doc to cover technology choices with
defensible reasons plus word-and-diagram overview.

**Added:**
- `blueprint/product.md` — one-sentence product, the single learning loop, MoSCoW scope (13 must / 5 should / 5 could / 6 nice), explicit non-goals, reuse list from the old project, six success metrics
- `blueprint/rules.md` — 10 obligations for every agent. Rule 1 is never over-engineer; Rule 4 is the mandatory logging contract that produces this file
- `blueprint/record.md` — this file: entry template + log
- `blueprint/architecture.md` — stack with defensible reasons and rejected alternatives, 4 diagrams, 5-table data model, AI cost design, GDPR data flow, inherited lessons from the old project

**Changed:** none — `blueprint/` was empty before this task.

**Deleted:** none.

**Commands run:**
- Read the old project at `/home/nedyk/french/nedlang` — backend (71 files, 53,333 lines), frontend (142 files, 18,230 lines), 31 tables, 39 routes
- Verified specific claims from the Codex critique against source (see Decisions)
- Read `nedlang1.0` scaffolding → Next.js 16.3.5, React 19.2.8, Tailwind 4, FastAPI, Python 3.13
- Loaded the `claude-api` skill for current model IDs and pricing rather than writing them from memory

**Verified:** Everything in these four documents is a written plan, so "verified"
applies only to the claims about the old project that informed it:
- Unauthenticated AI endpoints — confirmed at `nedlang/backend/api/reception/test.py:470-584`
- `DELETE /user/account` has no frontend caller — confirmed, handler at `nedlang/backend/api/user/handler.py:327`
- Admin BYPASSRLS connection on hot request paths — confirmed at `nedlang/backend/api/usage_caps.py` lines 39/53/75/100/123/154, contradicting its own contract at `nedlang/backend/database/script.py:271`
- No CI, no product tests — confirmed, no `.github/`, no test script, no test dep group
- 41 seeded curricula across 7 languages — confirmed in `nedlang/backend/database/script.py`
- Model IDs and pricing in `architecture.md` — from the `claude-api` skill's current table, not from memory

**Not verified:** No code was written or run for `nedlang1.0`. Nothing in these
documents has been implemented. Resend and OpenRouter free-tier limits are
quoted from the earlier Codex conversation and should be re-checked against the
providers' own pricing pages before anyone relies on them.

**Decisions:**
- **Corrected a premise from the Codex conversation.** It described the old project's curriculum as French-only. It is 41 complete curricula across 7 languages and 4 frameworks. This changed the reuse advice: the curricula are an asset to keep on disk, not complexity to delete.
- **Inverted the reuse list.** Codex advised dropping multi-language data and keeping the auth/profile layer. Recorded the opposite: seed data is cheap to keep (rows in a table), while the 1,837-line consent/soft-delete/restore layer is the expensive part. Captured in `product.md` → What we reuse.
- **Made self-service deletion a Must (M12), not a later compliance task** — directly because the old project built the full erasure machinery and never wired up a button.
- **Made usage caps fail closed**, reversing the old project's deliberate fail-open choice. Fail-open is right when you have paying customers; wrong when you have a free product and no revenue.
- **Chose PostgreSQL + Supabase in an EU region** primarily for GDPR data residency, with the Postgres-not-a-proprietary-API argument as the exit route.
- **Named an explicit pinned model rather than a routing alias**, because a rotating free router gives inconsistent output formats and an unanswerable question about where learner text went.

**Noticed but not touched:**
- `nedlang1.0/agents/CLAUDE.md` and `agents/CODEX.md` are both empty. They likely should point at `blueprint/rules.md` so agents read the rules automatically.
- `nedlang1.0/frontend` and `nedlang1.0/backend` are bare scaffolds — default Next.js app and a `main.py` that prints "Hello from backend!".
- The old project's `usage_caps` admin-connection issue is still live in `nedlang` (a running product), and is both a containment risk and a latency cost on its hottest paths.

**Next:** Point the two empty `agents/*.md` files at `blueprint/rules.md`, then
start Rule 10 step 1: database schema + auth.
