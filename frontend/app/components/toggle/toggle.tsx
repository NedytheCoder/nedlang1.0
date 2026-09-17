import './toggle.css'

// The day/night switch from Uiverse (RiccardoRapelli), converted from the
// toggle.html and toggle.css sitting beside this file.
//
// The stylesheet is imported unchanged rather than rewritten into Tailwind or a
// CSS module: it is 340 lines of absolute positions and keyframes that only
// make sense together, and leaving it byte-identical to what was pasted in
// keeps the next upstream update a paste rather than a translation.
//
// No state, and no 'use client'. The original is a native checkbox and every
// bit of the animation hangs off `:checked` in CSS, so there is nothing here
// for JavaScript to do — rendered from a server component it ships none. Pass
// `defaultChecked` to let the DOM hold the state, or `checked` with `onChange`
// to hold it yourself.
//
// Two things the caller has to know. There is no visible text, so pass an
// `aria-label`. And one of these per page: the stylesheet selects on `#input`
// and on sixteen further ids, which a second instance would duplicate.

// The ornaments inside the sun/moon are all the same circle; the id is the only
// difference, because the id is what the stylesheet sizes and positions. Order
// is the source file's order.
const SUN_MOON = [
  ['moon-dot-1', 'moon-dot'],
  ['moon-dot-2', 'moon-dot'],
  ['moon-dot-3', 'moon-dot'],
  ['light-ray-1', 'light-ray'],
  ['light-ray-2', 'light-ray'],
  ['light-ray-3', 'light-ray'],
  ['cloud-1', 'cloud-dark'],
  ['cloud-2', 'cloud-dark'],
  ['cloud-3', 'cloud-dark'],
  ['cloud-4', 'cloud-light'],
  ['cloud-5', 'cloud-light'],
  ['cloud-6', 'cloud-light'],
]

const STARS = ['star-1', 'star-2', 'star-3', 'star-4']

// One four-pointed star, drawn once and used by all four.
const STAR =
  'M 0 10 C 10 10,10 10 ,0 10 C 10 10 , 10 10 , 10 20 C 10 10 , 10 10 , 20 10 C 10 10 , 10 10 , 10 0 C 10 10,10 10 ,0 10 Z'

export default function Toggle(props: React.ComponentProps<'input'>) {
  return (
    <label className="switch">
      {/* type and id come after the spread so a caller cannot replace them:
          `#input:checked + .slider` is the entire mechanism. */}
      <input {...props} type="checkbox" id="input" />
      <div className="slider round">
        <div className="sun-moon">
          {SUN_MOON.map(([id, className]) => (
            <svg key={id} id={id} className={className} viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="50" />
            </svg>
          ))}
        </div>
        <div className="stars">
          {STARS.map((id) => (
            <svg key={id} id={id} className="star" viewBox="0 0 20 20">
              <path d={STAR} />
            </svg>
          ))}
        </div>
      </div>
    </label>
  )
}
