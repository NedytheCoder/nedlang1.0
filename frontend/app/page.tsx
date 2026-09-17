import Link from 'next/link'
import { Show, SignInButton, SignUpButton } from '@clerk/nextjs'

// The palette is the French school exercise book — le cahier Seyès — whose
// ruling is lilac, which is also where this app's existing purple button comes
// from. Ink is violet-black rather than grey-black so the two agree.
//
// Every value below is written with its dark counterpart at the call site
// (Rule 11). They are string constants rather than theme tokens because this is
// one page: globals.css gets them when a second page needs them, not before
// (Rule 1).
const QUIET = 'text-[#615C7A] dark:text-[#A09BB8]'
const RULE = 'bg-[#C9BFEA] dark:bg-[#3A2F63]'

// White on purple is mode-agnostic, but purple-700 sits too close to the dark
// page colour to read as a raised control, so the button lightens a step there.
const ACTION =
  'inline-flex h-12 items-center justify-center rounded-full bg-purple-700 px-7 text-base font-medium text-white transition-colors hover:bg-purple-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-700 cursor-pointer dark:bg-purple-600 dark:hover:bg-purple-500 dark:focus-visible:outline-purple-400'

// The same decision in both CTA positions, so it is written once. Signed out,
// the page's job is an account; signed in, the only thing built past the account
// is onboarding's two questions, so that is where it points — saying that
// plainly rather than promising a conversation that does not exist yet.
function Start() {
  return (
    <>
      <Show when="signed-out">
        <SignUpButton>
          <button className={ACTION}>Create your account</button>
        </SignUpButton>
      </Show>
      <Show when="signed-in">
        <Link href="/onboarding" className={ACTION}>
          Answer your two questions
        </Link>
      </Show>
    </>
  )
}

// One mark on the review scale. Five of them, and the rails between carry the
// interval: the gap doubles because the interval doubles.
function Mark({ label, mastered = false }: { label: string; mastered?: boolean }) {
  return (
    <div className="flex shrink-0 flex-col items-center gap-2">
      <span
        className={`h-3 w-3 rounded-full ${
          mastered
            ? 'border border-[#C9BFEA] dark:border-[#3A2F63]'
            : 'bg-purple-700 dark:bg-purple-400'
        }`}
      />
      <span className={`text-[13px] font-medium ${QUIET}`}>{label}</span>
    </div>
  )
}

function Rail({ className }: { className: string }) {
  // mt-1.5 puts the 1px rail on the centre line of the 12px marks.
  return <span className={`mt-1.5 h-px ${RULE} ${className}`} aria-hidden="true" />
}

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      {/* Hero. The page opens in French, mid-situation, because that is the
          thing the product is about — not a claim about the product. The line
          under it is empty on purpose. */}
      <section className="mx-auto w-full max-w-[52rem] px-6 pt-8 pb-14 sm:px-10 sm:pt-12 sm:pb-20">
        <div className="md:grid md:grid-cols-[minmax(0,1fr)_11rem] md:gap-x-10">
          <p
            lang="fr"
            className="text-[2.75rem] font-semibold leading-[0.95] tracking-[-0.04em] sm:text-6xl lg:text-7xl"
          >
            {'Vous désirez ?'}
          </p>
          <p className={`mt-5 max-w-[26rem] text-sm leading-6 md:mt-2 ${QUIET}`}>
            What would you like? The baker says it fast, and there are three people
            behind you.
          </p>

          {/* The writing line, and a caret waiting on it. The one piece of motion
              on this page, and the only thing it says is: your turn, and nothing
              is coming. */}
          <div
            className={`mt-7 border-b border-[#C9BFEA] pb-3 md:col-span-2 md:mt-10 dark:border-[#3A2F63]`}
          >
            <span
              aria-hidden="true"
              className="inline-block h-9 w-[3px] animate-pulse bg-purple-700 motion-reduce:animate-none sm:h-11 dark:bg-purple-400"
            />
          </div>
        </div>

        <div className="mt-10 max-w-[34rem] sm:mt-12">
          <h1 className="text-2xl font-semibold leading-tight tracking-[-0.02em] sm:text-[2rem]">
            You know the words. They arrive ten seconds too late.
          </h1>
          <p className={`mt-5 text-[1.0625rem] leading-7 ${QUIET}`}>
            NedLang gives you one ten-minute French conversation a day. Read it,
            hear it, answer it in your own words. What comes back is a single fix.
            Tomorrow, that mistake returns in a new situation.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-4">
            <Start />
            <Show when="signed-out">
              <SignInButton>
                <button
                  className={`cursor-pointer text-sm underline underline-offset-4 decoration-[#C9BFEA] hover:decoration-purple-700 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-purple-700 ${QUIET} dark:decoration-[#3A2F63] dark:hover:decoration-purple-400`}
                >
                  I already have an account
                </button>
              </SignInButton>
            </Show>
          </div>
          <p className={`mt-4 text-sm ${QUIET}`}>
            Two questions to set up. There is no test.
          </p>
        </div>
      </section>

      {/* The correction. Shown as the artefact itself rather than described:
          four lines, which is the whole of what a submission returns. */}
      <section className="mx-auto w-full max-w-[52rem] px-6 py-12 sm:px-10 sm:py-16">
        <h2 className="max-w-[34rem] text-2xl font-semibold tracking-[-0.02em] sm:text-3xl">
          What comes back is one fix.
        </h2>

        <dl className="mt-10 max-w-[44rem] space-y-6">
          <div className="grid gap-1 sm:grid-cols-[7rem_minmax(0,1fr)] sm:items-baseline sm:gap-x-8">
            <dt className={`text-sm ${QUIET}`}>you wrote</dt>
            <dd
              lang="fr"
              className={`text-lg line-through decoration-1 decoration-[#C9BFEA] sm:text-xl ${QUIET} dark:decoration-[#3A2F63]`}
            >
              Je voudrais un pain.
            </dd>
          </div>
          <div className="grid gap-1 sm:grid-cols-[7rem_minmax(0,1fr)] sm:items-baseline sm:gap-x-8">
            <dt className={`text-sm ${QUIET}`}>say instead</dt>
            <dd lang="fr" className="text-lg font-medium sm:text-xl">
              Je voudrais une baguette.
            </dd>
          </div>
          <div className="grid gap-1 sm:grid-cols-[7rem_minmax(0,1fr)] sm:items-baseline sm:gap-x-8">
            <dt className={`text-sm ${QUIET}`}>because</dt>
            <dd className="max-w-[30rem] leading-7">
              <span lang="fr" className="font-medium">un pain</span> is a loaf. The long thin
              one you meant is <span lang="fr" className="font-medium">une baguette</span>.
            </dd>
          </div>
          <div className="grid gap-1 sm:grid-cols-[7rem_minmax(0,1fr)] sm:items-baseline sm:gap-x-8">
            <dt className={`text-sm ${QUIET}`}>now try</dt>
            <dd className="leading-7">Ask for two of them.</dd>
          </div>
        </dl>

        <p className={`mt-10 max-w-[34rem] text-[1.0625rem] leading-7 ${QUIET}`}>
          Then you say it yourself. The retry is the part that sticks, which is why
          it is not optional and why nothing here is graded.
        </p>
      </section>

      {/* The review schedule — the only genuine sequence on the page, so it is
          the only thing given marks and an order. The rails double in width
          because the interval doubles. */}
      <section className="mx-auto w-full max-w-[52rem] px-6 py-12 sm:px-10 sm:py-16">
        <h2 className="max-w-[34rem] text-2xl font-semibold tracking-[-0.02em] sm:text-3xl">
          Tomorrow it comes back. Then it stops.
        </h2>

        <div className="mt-12 flex max-w-[40rem] items-start">
          <Mark label="today" />
          <Rail className="grow-[1]" />
          <Mark label="2" />
          <Rail className="grow-[2]" />
          <Mark label="4" />
          <Rail className="grow-[4]" />
          <Mark label="8" />
          <Rail className="grow-[8]" />
          <Mark label="16" mastered />
        </div>
        <p className={`mt-6 max-w-[34rem] text-sm leading-6 ${QUIET}`}>
          Days after the mistake, if you get it right each time. Get it wrong and it
          resets to tomorrow. After the last one it stops appearing.
        </p>

        <p className={`mt-8 max-w-[34rem] text-[1.0625rem] leading-7 ${QUIET}`}>
          Your home screen opens with one line:{' '}
          <span className="font-medium text-foreground">3 phrases due today</span>. That is
          the whole of the reminder system.
        </p>
      </section>

      {/* The non-goals, said out loud. They are the reason the product is small,
          and for this audience they answer the real hesitation. */}
      <section className="mx-auto w-full max-w-[52rem] px-6 py-12 sm:px-10 sm:py-16">
        <h2 className="max-w-[34rem] text-2xl font-semibold tracking-[-0.02em] sm:text-3xl">
          What it does not do.
        </h2>
        <ul className={`mt-8 max-w-[34rem] space-y-4 text-[1.0625rem] leading-7 ${QUIET}`}>
          <li>There is no streak to protect. Miss a day and you lose nothing.</li>
          <li>There is no placement test. You answer two questions and start.</li>
          <li>There is no chat box. A real situation, your reply, one fix.</li>
          <li>There is one conversation a day. Ten minutes is the whole ask.</li>
        </ul>

        <div className="mt-12">
          <Start />
        </div>
      </section>

      <footer className={`mx-auto w-full max-w-[52rem] px-6 pb-12 sm:px-10 ${QUIET}`}>
        <p className="text-sm">Built in Ireland. French only, for now.</p>
      </footer>
    </div>
  )
}
