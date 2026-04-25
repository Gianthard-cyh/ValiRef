<template>
  <div class="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-6 py-12 bg-surface-tertiary dark:bg-surface-dark-tertiary">
    <div class="w-full max-w-md text-center">
      <div class="w-12 h-12 mx-auto mb-6 rounded-full bg-surface-secondary dark:bg-surface-dark-secondary border border-border dark:border-border-dark flex items-center justify-center">
        <span class="i-lucide-loader-2 w-5 h-5 text-text dark:text-text-dark animate-spin" />
      </div>

      <h2 class="text-title mb-1">正在验证</h2>
      <p class="text-small text-text-secondary dark:text-text-dark-secondary mb-6">{{ currentStatus?.filename }}</p>

      <!-- Stage Indicator -->
      <div class="flex items-center justify-center gap-2 mb-6">
        <div class="flex items-center gap-2">
          <div
            class="w-6 h-6 rounded-full flex items-center justify-center text-caption"
            :class="stageClasses.extraction"
          >
            <span v-if="stage === 'extraction' || stage === 'validation' || stage === 'completed'" class="i-lucide-check w-3.5 h-3.5" />
            <span v-else class="i-lucide-file-text w-3.5 h-3.5" />
          </div>
          <span class="text-caption" :class="stage === 'extraction' ? 'text-text font-medium' : 'text-text-tertiary'">
            提取引用
          </span>
        </div>

        <span class="text-text-tertiary">→</span>

        <div class="flex items-center gap-2">
          <div
            class="w-6 h-6 rounded-full flex items-center justify-center text-caption"
            :class="stageClasses.validation"
          >
            <span v-if="stage === 'validation'" class="i-lucide-loader-2 w-3.5 h-3.5 animate-spin" />
            <span v-else-if="stage === 'completed'" class="i-lucide-check w-3.5 h-3.5" />
            <span v-else class="i-lucide-search w-3.5 h-3.5" />
          </div>
          <span class="text-caption" :class="stage === 'validation' ? 'text-text font-medium' : 'text-text-tertiary'">
            验证引用
          </span>
        </div>
      </div>

      <LineProgress
        :percentage="progress"
        size="md"
        class="max-w-xs mx-auto"
      />

      <!-- Current Title -->
      <p v-if="currentTitle" class="mt-4 text-small text-text-secondary dark:text-text-dark-secondary truncate px-4">
        <span class="text-text-tertiary">正在验证:</span> {{ currentTitle }}
      </p>

      <!-- Stats -->
      <p class="mt-4 text-caption text-text-muted dark:text-text-dark-tertiary">
        <template v-if="currentStatus?.progress">
          {{ currentStatus.progress.processed }} / {{ currentStatus.progress.total }} 个引用
          <span v-if="speed > 0" class="ml-2">| {{ speed }} 个/分钟</span>
        </template>
        <template v-else>准备中...</template>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const taskStore = useTaskStore();
const { currentStatus, progress } = storeToRefs(taskStore);

// Stage computed from status
const stage = computed(() => currentStatus.value?.stage || 'extraction');

// Stage indicator classes
const stageClasses = computed(() => ({
  extraction: stage.value === 'extraction'
    ? 'bg-primary text-white'
    : 'bg-success text-white',
  validation: stage.value === 'validation'
    ? 'bg-primary text-white'
    : stage.value === 'completed'
      ? 'bg-success text-white'
      : 'bg-surface-secondary dark:bg-surface-dark-secondary text-text-tertiary',
}));

// Current title being validated
const currentTitle = computed(() => currentStatus.value?.current_title);

// Calculate validation speed (references per minute)
const speed = computed(() => {
  const status = currentStatus.value;
  if (!status?.progress || status.progress.processed < 5) return 0;

  const processed = status.progress.processed;
  const total = status.progress.total;
  const progressRatio = processed / total;

  // Estimate based on progress ratio and typical processing time
  // Extraction takes ~20% of time, validation ~80%
  const elapsedMinutes = (Date.now() - new Date(status.created_at).getTime()) / 60000;
  if (elapsedMinutes < 0.5) return 0;

  // Only show speed during validation stage
  if (status.stage !== 'validation') return 0;

  const refsPerMinute = Math.round(processed / elapsedMinutes);
  return refsPerMinute > 0 ? refsPerMinute : 0;
});
</script>
