<template>
  <router-view :key="$route.meta.examStandalone ? $route.path : undefined" />
</template>
