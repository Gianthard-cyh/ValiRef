<template>
  <div class="flex items-center gap-2">
    <div class="w-16 h-1 bg-gray-200 rounded overflow-hidden">
      <div
        class="h-full rounded transition-all duration-300"
        :class="scoreClass"
        :style="{ width: `${score * 100}%` }"
      />
    </div>
    <span class="text-xs text-gray-500">{{ (score * 100).toFixed(0) }}%</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  score: number;
}

const props = defineProps<Props>();

const scoreClass = computed(() => {
  if (props.score >= 0.8) return 'bg-emerald-500';
  if (props.score >= 0.6) return 'bg-blue-500';
  if (props.score >= 0.4) return 'bg-amber-500';
  return 'bg-rose-500';
});
</script>
