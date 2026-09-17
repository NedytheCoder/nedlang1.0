/**
 * The loading spinner. A ring with a gap, rotating.
 *
 * Ported from the original project, which drew exactly this with border
 * utilities — but drew it about twenty times, in nine slightly different
 * variants, because it was never a component. That is the whole reason this file
 * exists: one spinner, so the second place that needs one cannot quietly
 * disagree with the first.
 *
 * `border-current` is what keeps it to one component instead of a colour prop.
 * The ring inherits whatever text colour it lands in — white inside the purple
 * submit button, foreground on a plain surface — so it is correct in light and
 * dark mode without a single `dark:` class (Rule 11). `border-t-transparent` is
 * the gap that makes the rotation visible.
 *
 * Size comes from the caller via className, because the two sizes the original
 * actually used (inline in a button, and alone on a page) differ by more than a
 * number — `size-4` next to text, `size-8` standing by itself.
 */
export default function Spinner({ className = 'size-4' }: { className?: string }) {
  return (
    <span
      // A spinner is pure decoration to a screen reader unless it says what it
      // means. role="status" puts it in the live region so the label is
      // announced when it appears, rather than silence while the form submits.
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
    />
  )
}
