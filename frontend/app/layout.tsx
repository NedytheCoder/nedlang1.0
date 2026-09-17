import type { Metadata } from 'next'
import { ClerkProvider, Show, SignInButton, SignUpButton, UserButton } from '@clerk/nextjs'
import { Poppins } from 'next/font/google'
import ThemeToggle from './components/theme-toggle'
import './globals.css'

// The only font in the project. Poppins is not a variable font, so next/font
// requires the weights to be named up front and downloads one file per weight —
// these are the three the app actually uses: 400 for body text, 500 for
// `font-medium`, 600 for `font-semibold`. Adding one later is a one-line change;
// shipping a weight nothing renders is a download every visitor pays for.
const poppins = Poppins({
  variable: '--font-poppins',
  weight: ['400', '500', '600'],
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'NedLang',
  description: 'One 10-minute French conversation a day.',
}

// ClerkProvider wraps <html> rather than sitting inside <body>: that is Clerk's
// documented App Router placement, and it is what lets the provider contribute
// to <head> during the server render instead of only after hydration.
//
// It is in the root layout, so every route ships and boots the Clerk SDK. The
// previous project scoped it to an /auth segment instead, to keep the ~1.3MB
// widget off public pages like the landing page and the privacy policy. That is
// a real saving, but it is an optimisation for pages that do not exist yet —
// revisit it at Rule 10 step 5, when the policy pages arrive.
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <ClerkProvider>
      {/* suppressHydrationWarning because the script below writes an attribute
          onto this element that the server never rendered. It is scoped to
          <html>'s own attributes, not to anything inside it. */}
      <html lang="en" suppressHydrationWarning className={`${poppins.variable} h-full antialiased`}>
        <head>
          {/* Runs while the head is still being parsed, so a stored choice is
              on <html> before the first paint rather than after hydration —
              otherwise someone who picked dark gets a white page for a few
              hundred milliseconds on every single load. Next's recipe from
              `preventing-flash-before-hydration`, with the operating system
              added as the fallback so that an untouched switch behaves the way
              this app behaved before it had one.

              Resolving here and writing it down means nothing else has to work
              the preference out a second time — the toggle and the stylesheet
              both just read the attribute. If this script never runs, there is
              no attribute, and globals.css falls back to the media query. */}
          <script
            dangerouslySetInnerHTML={{
              __html: `(function(){try{var t=localStorage.getItem("theme")||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`,
            }}
          />
        </head>
        <body className="min-h-full flex flex-col">
          <header className="flex justify-end items-center p-4 gap-4 h-16">
            <ThemeToggle />
            <Show when="signed-out">
              <SignInButton />
              <SignUpButton>
                <button className="bg-purple-700 text-white rounded-full font-medium text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5 cursor-pointer">
                  Sign Up
                </button>
              </SignUpButton>
            </Show>
            <Show when="signed-in">
              <UserButton />
            </Show>
          </header>
          {children}
        </body>
      </html>
    </ClerkProvider>
  )
}
