<template>
  <div class="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-6 py-12 bg-surface-tertiary dark:bg-surface-dark-tertiary">
    <div class="w-full max-w-sm text-center">
      <div class="w-12 h-12 mx-auto mb-6 rounded-full bg-surface-secondary dark:bg-surface-dark-secondary border border-border dark:border-border-dark flex items-center justify-center">
        <span class="i-lucide-loader-2 w-5 h-5 text-text dark:text-text-dark" />
      </div>

      <h2 class="text-title mb-1">正在验证</h2>
      <p class="text-small text-text-secondary dark:text-text-dark-secondary mb-8">{{ currentStatus?.filename }}</p>

      <LineProgress
        :percentage="progress"
        size="md"
        class="max-w-xs mx-auto"
      />

      <p class="mt-6 text-caption text-text-muted dark:text-text-dark-tertiary">
        <span v-if="currentStatus?.progress">
          {{ currentStatus.progress.processed }} / {{ currentStatus.progress.total }} 个引用
        </span>
        <span v-else>准备中...</span>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const taskStore = useTaskStore();
const { currentStatus, progress } = storeToRefs(taskStore);
</script>
