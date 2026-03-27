<template>
  <div class="flex border border-border dark:border-border-dark rounded-lg overflow-hidden bg-surface dark:bg-surface-dark">
    <div
      v-for="(stat, index) in stats"
      :key="stat.label"
      class="flex-1 flex items-center justify-between px-4 py-3"
      :class="[
        index !== stats.length - 1 ? 'border-r border-border dark:border-border-dark' : '',
        stat.highlight ? 'bg-surface-secondary dark:bg-surface-dark-secondary' : '',
      ]"
    >
      <span class="text-small text-text-secondary dark:text-text-dark-secondary">{{ stat.label }}</span>
      <span
        class="text-heading tabular-nums"
        :class="stat.colorClass || 'text-text dark:text-text-dark'"
      >
        {{ stat.value }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PDFValidationResult } from '~/types/api';

interface Props {
  result: PDFValidationResult;
}

const props = defineProps<Props>();

const stats = computed(() => [
  {
    label: '总引用数',
    value: props.result.total_references,
    highlight: false,
  },
  {
    label: '真实引用',
    value: props.result.real_count,
    colorClass: 'text-emerald-600 dark:text-emerald-400',
    highlight: true,
  },
  {
    label: '幻觉引用',
    value: props.result.hallucination_count,
    colorClass: props.result.hallucination_count > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-text dark:text-text-dark',
    highlight: props.result.hallucination_count > 0,
  },
  {
    label: '耗时(秒)',
    value: props.result.duration_seconds?.toFixed(1) || '-',
    highlight: false,
  },
]);
</script>
