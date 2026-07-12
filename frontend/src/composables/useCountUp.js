import { ref, watch, onUnmounted, isRef, unref } from 'vue'

// Animate a numeric value from its previous value up/down to the target using
// requestAnimationFrame with an ease-out curve. Non-numeric values (e.g. a
// currency-formatted string KPI) pass straight through unchanged. Honors
// prefers-reduced-motion by rendering the final value instantly.
//
// Usage: const shown = useCountUp(() => props.value)
//        <span>{{ shown }}</span>
export function useCountUp(source, { duration = 600 } = {}) {
  const read = () => (typeof source === 'function' ? source() : unref(source))

  const initial = read()
  const display = ref(initial)

  let frame = 0
  let from = Number.isFinite(Number(initial)) ? Number(initial) : 0

  const reduced = () =>
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  const easeOut = (t) => 1 - Math.pow(1 - t, 3)

  const cancel = () => {
    if (frame) cancelAnimationFrame(frame)
    frame = 0
  }

  const run = (target) => {
    cancel()

    // Pass non-numeric values (strings like "฿4.2M") through verbatim.
    if (target == null || !Number.isFinite(Number(target))) {
      display.value = target
      return
    }

    const to = Number(target)

    if (reduced() || from === to) {
      display.value = to
      from = to
      return
    }

    const start = performance.now()
    const delta = to - from
    const origin = from

    const step = (now) => {
      const p = Math.min(1, (now - start) / duration)
      display.value = Math.round(origin + delta * easeOut(p))
      if (p < 1) {
        frame = requestAnimationFrame(step)
      } else {
        display.value = to
        from = to
        frame = 0
      }
    }
    frame = requestAnimationFrame(step)
  }

  // Kick off the initial count-up on mount, then react to changes.
  run(initial)

  const target =
    typeof source === 'function' ? source : isRef(source) ? source : () => source
  watch(target, (v) => run(v))

  onUnmounted(cancel)

  return display
}
