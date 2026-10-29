<template><section class="pending-feature"><h1>{{ title }}</h1><p>null</p><p>待后续步骤实现（{{ stage }}）</p></section></template>
<script setup>defineProps({ title: String, stage: String })</script>
<style scoped>.pending-feature{background:white;border:1px solid #dce7f0;border-radius:10px;padding:30px}.pending-feature p{color:#586f82}</style>
