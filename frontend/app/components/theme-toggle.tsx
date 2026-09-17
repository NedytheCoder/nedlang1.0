'use client'

import { useLayoutEffect, useState } from 'react'
import Toggle from './toggle/toggle'

// The switch in the header.
//
// `data-theme` on <html> is the single source of truth, and it is resolved once
// by the inline script in layout.tsx before the first paint — a stored choice if
// there is one, the operating system's preference if there is not. Everything
// here reads that attribute rather than working it out again, so there is no
// second copy of the rule to drift.
//
// localStorage rather than a cookie: the choice never needs to reach the server,
// and reading a cookie in the root layout would opt the whole app out of static
// prerendering (Next's guide, `preventing-flash-before-hydration`).

// Sets the checkbox to match the theme while the header is still being parsed,
// so the switch is in the right position in the HTML React hydrates against.
// Without it a dark-mode visitor gets the sun on every load, and watches it
// slide to the moon once hydration catches up. `#input` is the toggle's own id,
// fixed in toggle.tsx because its stylesheet selects on it.
const SYNC = `(function(){try{var i=document.getElementById("input");if(i)i.checked=document.documentElement.dataset.theme==="dark"}catch(e){}})()`

export default function ThemeToggle() {
  // Light on the server, which has no attribute to read. On the client the
  // attribute is already there, so hydration starts from the right answer.
  const [dark, setDark] = useState(
    () => typeof document !== 'undefined' && document.documentElement.dataset.theme === 'dark'
  )

  // Puts the switch's state back onto <html>, which is the one place the rest of
  // the app looks. It repeats the inline script's work on first render, and that
  // is deliberate: in development React's Strict Mode remounts once and resets
  // <html> to the attributes JSX manages, wiping what the script set.
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  }, [dark])

  function choose(next: boolean) {
    setDark(next)
    try {
      localStorage.setItem('theme', next ? 'dark' : 'light')
    } catch {
      // Storage blocked, or Safari in private mode. The switch still works for
      // the rest of the visit; it just will not be remembered.
    }
  }

  return (
    <>
      <Toggle aria-label="Dark mode" checked={dark} onChange={(e) => choose(e.target.checked)} />
      <script dangerouslySetInnerHTML={{ __html: SYNC }} />
    </>
  )
}
