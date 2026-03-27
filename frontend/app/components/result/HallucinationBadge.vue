<template>
  <span
    :class="[
      'inline-flex items-center px-2 py-0.5 rounded text-caption font-medium border',
      typeClasses[type || 'Unknown'],
    ]"
  >
    {{ typeLabels[type || 'Unknown'] }}
  </span>
</template>

<script setup lang="ts">
import type { HallucinationType } from '~/types/api';

interface Props {
  type?: HallucinationType;
}

const props = defineProps<Props>();

const typeClasses: Record<string, string> = {
  'Real': 'border-emerald-500/20 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10',
  'Fabrication': 'border-rose-500/20 text-rose-700 dark:text-rose-400 bg-rose-500/10',
  'AttributionError': 'border-amber-500/20 text-amber-700 dark:text-amber-400 bg-amber-500/10',
  'Irrelevance': 'border-blue-500/20 text-blue-700 dark:text-blue-400 bg-blue-500/10',
  'Counterfactual': 'border-violet-500/20 text-violet-700 dark:text-violet-400 bg-violet-500/10',
  'Unknown': 'border-border dark:border-border-dark text-text-secondary dark:text-text-dark-secondary bg-surface-secondary dark:bg-surface-dark-secondary',
  // Chinese type mapping
  '真实引用': 'border-emerald-500/20 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10',
  '完全虚构': 'border-rose-500/20 text-rose-700 dark:text-rose-400 bg-rose-500/10',
  '作者错误': 'border-amber-500/20 text-amber-700 dark:text-amber-400 bg-amber-500/10',
  '内容不符': 'border-blue-500/20 text-blue-700 dark:text-blue-400 bg-blue-500/10',
  '结论相反': 'border-violet-500/20 text-violet-700 dark:text-violet-400 bg-violet-500/10',
  '未知类型': 'border-border dark:border-border-dark text-text-secondary dark:text-text-dark-secondary bg-surface-secondary dark:bg-surface-dark-secondary',
};

const typeLabels: Record<string, string> = {
  'Real': '真实',
  'Fabrication': '虚构',
  'AttributionError': '作者错误',
  'Irrelevance': '不相关',
  'Counterfactual': '反事实',
  'Unknown': '未知',
  // Chinese type mapping
  '真实引用': '真实',
  '完全虚构': '虚构',
  '内容不符': '不相关',
  '结论相反': '反事实',
  '未知类型': '未知',
};
</script>
