<template>
  <span
    :class="[
      'inline-flex items-center gap-1 px-2 py-1 rounded-md text-caption font-medium border transition-colors',
      statusClasses[status] || statusClasses.pending,
    ]"
  >
    <span
      v-if="status === 'processing' || status === 'retrying'"
      class="w-1.5 h-1.5 rounded-full bg-current animate-pulse"
    />
    {{ statusLabels[status] || statusLabels.pending }}
  </span>
</template>

<script setup lang="ts">
import type { TaskStatus } from '~/types/api';

interface Props {
  status: TaskStatus;
}

const props = defineProps<Props>();

const statusClasses: Record<string, string> = {
  pending: 'bg-surface-secondary dark:bg-surface-dark-secondary text-text-secondary dark:text-text-dark-secondary border-border dark:border-border-dark',
  processing: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
  retrying: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
  completed: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
  failed: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
  failed_permanently: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
};

const statusLabels: Record<string, string> = {
  pending: '等待中',
  processing: '处理中',
  retrying: '重试中',
  completed: '已完成',
  failed: '失败',
  failed_permanently: '失败',
};
</script>
