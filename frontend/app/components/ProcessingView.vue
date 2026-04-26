<template>
  <div class="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-6 py-12 bg-surface-tertiary dark:bg-surface-dark-tertiary">
    <div class="w-full max-w-md text-center">
      <div class="w-12 h-12 mx-auto mb-6 rounded-full bg-surface-secondary dark:bg-surface-dark-secondary border border-border dark:border-border-dark flex items-center justify-center">
        <span class="i-lucide-loader-2 w-5 h-5 text-text dark:text-text-dark animate-spin" />
      </div>

      <h2 class="text-title mb-1">正在验证</h2>
      <p class="text-small text-text-secondary dark:text-text-dark-secondary mb-8">{{ currentStatus?.filename }}</p>

      <!-- Two-Stage Progress -->
      <div class="w-full max-w-xs mx-auto mb-8">
        <!-- Two-Stage Progress Bar -->
        <div class="flex gap-2 h-2">
          <!-- Stage 1: Extraction (20% weight) -->
          <div class="relative flex-[1] bg-surface dark:bg-surface-dark border border-border-subtle dark:border-border-dark-subtle rounded-full overflow-hidden">
            <div
              class="absolute inset-y-0 left-0 bg-text dark:bg-text-dark rounded-full transition-all duration-500 ease-out"
              :style="{ width: `${extractionProgress}%` }"
            >
              <div v-if="extractionStage === 'active'" class="absolute inset-0 shimmer-overlay" />
            </div>
          </div>
          <!-- Stage 2: Validation (80% weight) -->
          <div class="relative flex-[4] bg-surface dark:bg-surface-dark border border-border-subtle dark:border-border-dark-subtle rounded-full overflow-hidden">
            <div
              class="absolute inset-y-0 left-0 bg-text dark:bg-text-dark rounded-full transition-all duration-500 ease-out"
              :style="{ width: `${validationProgress}%` }"
            >
              <div v-if="validationStage === 'active'" class="absolute inset-0 shimmer-overlay" />
            </div>
          </div>
        </div>

        <!-- Stage Labels -->
        <div class="flex gap-2 mt-3">
          <div class="flex-[1] flex justify-center">
            <div
              class="w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300"
              :class="extractionStage === 'pending' ? 'bg-surface-secondary dark:bg-surface-dark-secondary text-text-tertiary dark:text-text-dark-tertiary' : 'bg-text dark:bg-text-dark text-surface dark:text-surface-dark'"
              title="提取引用"
            >
              <span class="i-lucide-file-text w-3.5 h-3.5" />
            </div>
          </div>
          <div class="flex-[4] flex justify-center">
            <div
              class="w-6 h-6 rounded-full flex items-center justify-center transition-all duration-300"
              :class="validationStage === 'pending' ? 'bg-surface-secondary dark:bg-surface-dark-secondary text-text-tertiary dark:text-text-dark-tertiary' : validationStage === 'active' ? 'bg-text dark:bg-text-dark text-surface dark:text-surface-dark' : 'bg-text dark:bg-text-dark text-surface dark:text-surface-dark'"
              title="验证引用"
            >
              <span class="i-lucide-search w-3.5 h-3.5" />
            </div>
          </div>
        </div>
      </div>

      <!-- Current Title -->
      <p v-if="currentTitle" class="text-small text-text-secondary dark:text-text-dark-secondary truncate px-4 mb-4">
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

// Stage states
const extractionStage = computed(() => {
  if (stage.value === 'completed') return 'completed';
  if (stage.value === 'validation') return 'completed';
  return 'active';
});

const validationStage = computed(() => {
  if (stage.value === 'completed') return 'completed';
  if (stage.value === 'validation') return 'active';
  return 'pending';
});

// Progress calculations for two-stage bar
// Stage 1: Extraction is binary - either extracting (100% with shimmer) or completed (100% solid)
const extractionProgress = computed(() => {
  // Extraction is binary: pending (0%), active (100% with shimmer), completed (100% solid)
  if (extractionStage.value === 'pending') return 0;
  return 100; // Both active and completed show full bar
});

const validationProgress = computed(() => {
  if (validationStage.value === 'completed') return 100;
  if (validationStage.value === 'pending') return 0;
  // During validation, map overall progress (20-100%) to 0-100% of stage 2
  const stage2Progress = progress.value - 20;
  return Math.min(100, Math.max(0, (stage2Progress / 80) * 100));
});

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

<style scoped>
.shimmer-overlay {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.25) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite linear;
  border-radius: inherit;
}

.dark .shimmer-overlay {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.15) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
