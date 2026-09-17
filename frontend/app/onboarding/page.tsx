'use client'

import { useState } from 'react'
import { Show, SignInButton, useAuth } from '@clerk/nextjs'

// Where the FastAPI backend lives. NEXT_PUBLIC_ because this fetch runs in the
// browser — the token is a Clerk session token the user already holds, so there
// is nothing secret in this call and nothing secret in this address.
//
// The fallback is the uvicorn default. Set NEXT_PUBLIC_API_URL in deployment;
// whatever origin the frontend is served from must also appear in the backend's
// ALLOWED_ORIGINS, or the browser blocks this call before it is ever sent.
const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// The second onboarding question, answerable in one tap.
//
// These are sentences, not levels, and what gets stored is the sentence itself —
// `users.comfort` is free text and stays that way. Deliberate twice over:
// product.md N2 rules out a placement test, and a learner who picks "A2" has
// told us nothing we can build a scenario from, whereas "they reply too fast" is
// a description of the actual problem.
//
// Tappable rather than free text because M2's entire justification is "start
// learning in under 60 seconds". Asking someone to compose a paragraph about
// their own competence, before they have seen a single thing the app does, is
// the friction we are trying to remove.
const COMFORT_OPTIONS = [
  'I freeze up the moment someone speaks to me.',
  'I manage simple things, but I lose it when they reply fast.',
  'I get by, but I hesitate and I sound stiff.',
  'I am fairly comfortable — I just keep making the same mistakes.',
]

const CARD =
  'w-full max-w-lg rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl shadow-zinc-200/50 sm:p-8 dark:border-white/10 dark:bg-zinc-900 dark:shadow-black/40'

export default function OnboardingPage() {
  // Only getToken. The signed-in question is asked below with <Show>, matching
  // the root layout's header.
  //
  // Be aware that neither <Show> nor useAuth().isLoaded resolves during the
  // server render *from inside a client component* — measured on this route, the
  // SSR HTML is the wrapper div and nothing inside it, so both cards appear only
  // after hydration. (The same <Show> in layout.tsx does server-render, because
  // that layout is a server component.) <ClerkProvider dynamic> in the root
  // layout is what would fix it, at the cost of making every route dynamic —
  // a root-layout decision, not this page's to make.
  const { getToken } = useAuth()
  const [goal, setGoal] = useState('')
  const [comfort, setComfort] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    setError('')
    try {
      const res = await fetch(`${API}/api/user`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await getToken()}`,
        },
        // Only the two answers. email_reminders is left off on purpose — the
        // backend defaults it to false, and the reminder itself is product.md
        // S2, which has not been built. A checkbox here would be an opt-in to
        // nothing.
        body: JSON.stringify({ goal, comfort }),
      })
      if (!res.ok) {
        setError("We couldn't save that. Please try again.")
        return
      }
      setSaved(true)
    } catch {
      setError("We couldn't reach the server. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  if (saved) {
    return (
      <div className="flex flex-1 items-center justify-center px-4 py-10">
        <div className={CARD}>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-white">You&apos;re set.</h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Saved. Your first conversation isn&apos;t built yet — this is where it will start.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-10">
      {/* POST /api/user takes identity from the token and nowhere else, so with
          no signed-in user this form can do nothing but collect a 401. Saying so
          up front is cheaper than letting someone type two answers and lose
          them. */}
      <Show when="signed-out">
        <div className={CARD}>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-white">Sign in first</h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            These answers are saved to your account, so we need to know whose they are.
          </p>
          <SignInButton>
            <button className="mt-6 h-11 rounded-full bg-purple-700 px-5 text-sm font-medium text-white">
              Sign in
            </button>
          </SignInButton>
        </div>
      </Show>

      <Show when="signed-in">
        <form onSubmit={save} className={CARD}>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-white">
            Two questions.
          </h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Then you&apos;re done. There is no test.
          </p>

          <div className="mt-8">
            <label
              htmlFor="goal"
              className="block text-sm font-medium text-zinc-900 dark:text-zinc-200"
            >
              What do you want to be able to do in French?
            </label>
            <textarea
              id="goal"
              rows={3}
              value={goal}
              // Matches the backend's Field(max_length=500), so an over-long
              // answer is stopped here instead of coming back as a 422 that says
              // nothing the learner can act on.
              maxLength={500}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Order lunch without switching to English. Talk to my landlord."
              className="mt-2 w-full resize-none rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 focus:outline-none dark:border-white/10 dark:bg-zinc-800 dark:text-white dark:placeholder-zinc-500"
            />
          </div>

          <fieldset className="mt-6">
            <legend className="text-sm font-medium text-zinc-900 dark:text-zinc-200">
              How comfortable are you right now?
            </legend>
            <div className="mt-2 space-y-2">
              {COMFORT_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setComfort(option)}
                  aria-pressed={comfort === option}
                  className={`w-full rounded-xl border px-4 py-3 text-left text-sm transition-colors ${
                    comfort === option
                      ? 'border-purple-600 bg-purple-50 text-purple-900 dark:bg-purple-500/10 dark:text-purple-200'
                      : 'border-zinc-200 bg-zinc-50 text-zinc-700 hover:border-zinc-300 dark:border-white/10 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:border-white/20'
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
          </fieldset>

          {error && <p className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

          {/* Both answers are required by the backend. Disabling the button is
              the whole of the client-side validation: there is no error message
              to write if the button that would produce it cannot be pressed. */}
          <button
            type="submit"
            disabled={saving || !goal.trim() || !comfort}
            className="mt-8 h-11 w-full rounded-full bg-purple-700 text-sm font-medium text-white transition-colors hover:bg-purple-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? 'Saving…' : 'Start'}
          </button>
        </form>
      </Show>
    </div>
  )
}
