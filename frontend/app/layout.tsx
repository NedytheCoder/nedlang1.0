import type { Metadata } from 'next'
import { ClerkProvider, Show, SignInButton, SignUpButton, UserButton } from '@clerk/nextjs'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
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
      <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
        <body className="min-h-full flex flex-col">
          <header className="flex justify-end items-center p-4 gap-4 h-16">
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
