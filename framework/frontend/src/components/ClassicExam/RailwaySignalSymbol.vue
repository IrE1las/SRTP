<template>
  <!-- This is a transcription of the monochrome symbols in 原始图.jpg, not a
       live signal-aspect display. Answer state must never change these lamp marks. -->
  <g class="railway-signal-symbol" :data-symbol="variant">
    <defs>
      <pattern :id="hatchId" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
        <rect width="4" height="4" class="paper" /><path d="M0 0V4" class="hatch-stroke" />
      </pattern>
    </defs>
    <!-- Align the post, or the center of the photographed rectangular bracket,
         with the parent signal's track-insulation coordinate. -->
    <g :transform="`scale(${direction === 2 ? -1 : 1} 1) translate(${recipe.bracket ? 5 : 0} 0)`">
      <path :d="recipe.post" class="outline" />
      <!-- Only the photographed S5/SIII/S4 pattern has this narrow bracket. -->
      <g v-if="recipe.bracket">
        <rect x="-10" y="-18" width="10" height="36" class="outline paper" />
        <circle cx="-5" cy="-12" r="2.4" class="outline paper" />
      </g>
      <g v-for="(lamp, index) in recipe.lamps" :key="index" class="lamp-mark" :data-lamp-mark="lamp.mark" :transform="`translate(${lamp.x}, ${lamp.y || 0})`">
        <circle r="8" class="outline" :style="{ fill: lamp.mark === 'hatched' || lamp.mark === 'hatched-steady' ? `url(#${hatchId})` : lamp.mark === 'filled' ? 'currentColor' : 'var(--signal-paper, #111e2b)' }" />
        <circle v-if="lamp.mark === 'ring'" r="4.1" class="outline paper" />
        <circle v-if="lamp.mark === 'dot'" r="4.5" class="ink" />
        <path v-if="lamp.mark === 'cross'" d="M-5.6 -5.6L5.6 5.6M-5.6 5.6L5.6 -5.6" class="outline" />
        <path v-if="lamp.mark === 'filled' || lamp.mark === 'hatched-steady'" d="M-6 -6L-10 -10M6 -6L10 -10M-6 6L-10 10M6 6L10 10" class="outline" />
      </g>
    </g>
  </g>
</template>

<script setup>
import { computed, useId } from 'vue'
const props = defineProps({ variant: { type: String, required: true }, direction: { type: Number, default: 1 } })
const hatchId = `signal-hatch-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
// Select the photographed device pattern directly, without high/dwarf type styling.
// D signals have a short vertical stroke and two circles, with no added filled base.
// XD has a crossed-out fourth lamp; X has an open one.
const recipes = {
  X: { post: 'M0 -11V11M0 0H19M35 0H46', lamps: [{ x: 27, mark: 'ring' }, { x: 54, mark: 'hatched' }, { x: 70, mark: 'filled' }, { x: 86, mark: 'open' }, { x: 102, mark: 'hatched' }] },
  XD: { post: 'M0 -11V11M0 0H19M35 0H46', lamps: [{ x: 27, mark: 'ring' }, { x: 54, mark: 'hatched' }, { x: 70, mark: 'filled' }, { x: 86, mark: 'cross' }, { x: 102, mark: 'hatched' }] },
  SII: { post: 'M0 -11V11M0 0H19', lamps: [{ x: 27, mark: 'ring' }, { x: 43, mark: 'hatched' }, { x: 59, mark: 'filled' }, { x: 75, mark: 'open' }] },
  YXD: { post: 'M0 -11V11M0 0H17', lamps: [{ x: 25, mark: 'hatched-steady' }, { x: 41, mark: 'open' }] },
  D: { post: 'M0 -11V11', lamps: [{ x: 8, mark: 'dot' }, { x: 24, mark: 'ring' }] },
  S5: { post: 'M0 -18V18', bracket: true, lamps: [{ x: 9, y: -8, mark: 'filled' }, { x: 27, y: -8, mark: 'ring' }, { x: 9, y: 8, mark: 'hatched' }, { x: 27, y: 8, mark: 'cross' }, { x: 45, y: 8, mark: 'open' }] },
}
const recipe = computed(() => recipes[props.variant] || { post: '', lamps: [] })
</script>

<style scoped>
.railway-signal-symbol { color: var(--signal-ink, #e2ebf2); pointer-events: none; }
.outline { stroke: currentColor; stroke-width: 1.7; stroke-linecap: square; fill: none; }
.paper { fill: var(--signal-paper, #111e2b); }.ink { fill: currentColor; }
.hatch-stroke { stroke: currentColor; stroke-width: 1.4; }
</style>
