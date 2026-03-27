<template>
  <span
    :class="[
      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
      statusClasses[status] || statusClasses.pending,
    ]"
  >
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
  pending: 'bg-gray-100 text-gray-600',
  processing: 'bg-blue-100 text-blue-600',
  retrying: 'bg-amber-100 text-amber-600',
  completed: 'bg-emerald-100 text-emerald-600',
  failed: 'bg-rose-100 text-rose-600',
  failed_permanently: 'bg-rose-100 text-rose-600',
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
