<template>
  <NuxtPage />
</template>

<script setup lang="ts">
useHead({
  script: [
    {
      defer: true,
      src: 'https://static.cloudflareinsights.com/beacon.min.js',
      'data-cf-beacon': '{"token": "849aa3ca00b64b6cab72ef455297fbc6"}'
    }
  ]
})
</script>
