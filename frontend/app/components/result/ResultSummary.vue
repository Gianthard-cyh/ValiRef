<template>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
    <LineCard v-for="stat in stats" :key="stat.label" class="text-center">
      <div class="text-2xl font-bold text-gray-900">{{ stat.value }}</div>
      <div class="text-sm text-gray-500 mt-1">{{ stat.label }}</div>
    </LineCard>
  </div>
</template>

<script setup lang="ts">
import type { PDFValidationResult } from '~/types/api';

interface Props {
  result: PDFValidationResult;
}

const props = defineProps<Props>();

const stats = computed(() => [
  { label: '总引用数', value: props.result.total_references },
  { label: '真实引用', value: props.result.real_count },
  { label: '幻觉引用', value: props.result.hallucination_count },
  { label: '耗时(秒)', value: props.result.duration_seconds?.toFixed(1) || '-' },
]);
</script>
