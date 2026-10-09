// "Fill either" helper for schema fields that share an `exclusive` group (the BOM
// discount pair: discountBath / discountPct). The backend trigger derives the
// field the user did not fill, so the form must send ONLY the one they typed in:
//   - sending the untouched counterpart too would resend a stale value, and
//   - sending it as `null` would tell the trigger "clear the discount".
// Nothing here computes a value — it only decides which keys go over the wire.
import { reactive } from 'vue'

export function useExclusiveFields(fields, form) {
  const exclusive = fields.filter((f) => f.exclusive)
  const keysByGroup = {}
  for (const f of exclusive) (keysByGroup[f.exclusive] ??= []).push(f.key)
  const groupOf = Object.fromEntries(exclusive.map((f) => [f.key, f.exclusive]))

  // group -> key the user last typed in (absent = group untouched).
  const touched = reactive({})

  // Call from the input's @input handler. Blank the counterpart(s) so the form
  // reads as "this one drives, the other is computed on save".
  function onTyped(key) {
    const g = groupOf[key]
    if (!g) return
    touched[g] = key
    for (const other of keysByGroup[g]) if (other !== key) form[other] = ''
  }

  // True while another member of the group is the one being typed in.
  function isAuto(key) {
    const g = groupOf[key]
    return !!g && !!touched[g] && touched[g] !== key
  }

  // Strip the untouched members from a payload. A touched member left empty is
  // sent as null (= remove the discount); an untouched group sends nothing, so
  // editing qty / unit price never resends stale discount values.
  function prune(out) {
    for (const [g, keys] of Object.entries(keysByGroup)) {
      for (const k of keys) {
        if (touched[g] !== k) delete out[k]
        else if (out[k] === '' || out[k] === undefined) out[k] = null
      }
    }
    return out
  }

  return { onTyped, isAuto, prune }
}
