<template>
  <section class="simulation-practice" aria-label="仿真操作">
    <TheorySimulationConsole practice />
  </section>
</template>

<script setup>
import TheorySimulationConsole from '@/features/simulationConsole/TheorySimulationConsole.vue'
</script>

<style scoped>
.simulation-practice { width: 100%; min-width: 0; }
</style>
