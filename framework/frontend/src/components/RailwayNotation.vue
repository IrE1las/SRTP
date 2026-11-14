<template><span class="railway-notation"><template v-for="(part, i) in parts" :key="i"><sub v-if="part.align === 'subscript'">{{ part.text }}</sub><sup v-else-if="part.align === 'superscript'">{{ part.text }}</sup><template v-else>{{ part.text }}</template></template></span></template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ text: { type: [String, Number], default: '' }, runs: { type: Array, default: () => [] } })
const parts = computed(() => {
  if (props.runs.length) return props.runs.map(r => ({ text: r.text, align: r.vertical_align }))
  const value = String(props.text ?? ''), result = []
  // Only signal indices are typographic subscripts; switch/section numbers keep their baseline.
  const re = /\b(D(\d+)|(S)(III|II|I|[45])|(X)(D))(?=A|D|L|[^A-Za-z0-9]|$)/g
  let index = 0
  for (const match of value.matchAll(re)) {
    result.push({ text: value.slice(index, match.index), align: 'baseline' })
    result.push({ text: match[0][0], align: 'baseline' })
    result.push({ text: match[0].slice(1), align: 'subscript' })
    index = match.index + match[0].length
  }
  result.push({ text: value.slice(index), align: 'baseline' })
  return result
})
</script>
<style scoped>
.railway-notation { white-space: pre-wrap; overflow-wrap: anywhere; }sub, sup { font-size: .72em; line-height: 0; }sub { vertical-align: sub; }sup { vertical-align: super; }
</style>
