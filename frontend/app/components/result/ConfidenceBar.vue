<template>
  <div class="flex items-center gap-2.5">
    <!-- Progress bar -->
    <div class="w-20 h-1.5 bg-surface-tertiary dark:bg-surface-dark-tertiary rounded-full overflow-hidden">
      <div
        class="h-full rounded-full transition-all duration-500 ease-out"
        :class="scoreClass"
        :style="{ width: `${score * 100}%` }"
      />
    </div>
    <!-- Score label -->
    <span class="text-caption font-medium text-text-secondary dark:text-text-dark-secondary tabular-nums">
      {{ (score * 100).toFixed(0) }}%
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  score: number;
}

const props = defineProps<Props>();

const scoreClass = computed(() => {
  if (props.score >= 0.9) return 'bg-emerald-500';
  if (props.score >= 0.7) return 'bg-emerald-400';
  if (props.score >= 0.5) return 'bg-amber-500';
  if (props.score >= 0.3) return 'bg-amber-400';
  return 'bg-rose-500';
});
</script>
