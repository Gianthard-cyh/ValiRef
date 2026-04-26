<template>
  <div class="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-6 py-12 bg-surface-tertiary dark:bg-surface-dark-tertiary">
    <div class="w-full max-w-md text-center">
      <h2 class="text-title mb-1">正在验证</h2>
      <p class="text-small text-text-secondary dark:text-text-dark-secondary mb-8">{{ currentStatus?.filename }}</p>

      <!-- Two-Stage Progress -->
      <div class="w-full max-w-xs mx-auto mb-8">
        <!-- Progress Bars -->
        <div class="flex gap-2 h-1.5">
          <!-- Extraction Segment -->
          <div
            class="relative rounded-full overflow-hidden transition-[flex] duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
            :class="extractionStage === 'active' ? 'flex-[3]' : 'flex-[1]'"
          >
            <div class="absolute inset-0 bg-surface dark:bg-surface-dark border border-border-subtle dark:border-border-dark-subtle rounded-full" />
            <div
              class="absolute inset-0 bg-text dark:bg-text-dark rounded-full transition-all duration-500 ease-out"
              :style="{ width: `${extractionProgress}%` }"
            >
              <div v-if="extractionStage === 'active'" class="absolute inset-0 shimmer-overlay" />
            </div>
          </div>
          <!-- Validation Segment -->
          <div
            class="relative rounded-full overflow-hidden transition-[flex] duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
            :class="validationStage === 'active' ? 'flex-[3]' : 'flex-[1]'"
          >
            <div class="absolute inset-0 bg-surface dark:bg-surface-dark border border-border-subtle dark:border-border-dark-subtle rounded-full" />
            <div
              class="absolute inset-0 bg-text dark:bg-text-dark rounded-full transition-all duration-500 ease-out"
              :style="{ width: `${validationProgress}%` }"
            >
              <div v-if="validationStage === 'active'" class="absolute inset-0 shimmer-overlay" />
            </div>
          </div>
        </div>

        <!-- Stage Labels -->
        <div class="flex gap-2 mt-2">
          <!-- Extraction Label -->
          <div
            class="flex items-center justify-between transition-[flex] duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
            :class="extractionStage === 'active' ? 'flex-[3]' : 'flex-[1]'"
          >
            <div class="flex items-center gap-1.5">
              <span
                class="w-3.5 h-3.5 shrink-0"
                :class="extractionStage === 'completed' ? 'i-lucide-check text-text dark:text-text-dark' : extractionStage === 'active' ? 'i-lucide-file-text text-text dark:text-text-dark' : 'i-lucide-file-text text-text-tertiary dark:text-text-dark-tertiary'"
              />
              <span
                class="text-xs font-medium transition-colors duration-300"
                :class="extractionStage === 'pending' ? 'text-text-tertiary dark:text-text-dark-tertiary' : 'text-text dark:text-text-dark'"
              >
                提取
              </span>
            </div>
            <span
              v-if="extractionStage === 'active'"
              class="text-xs text-text-secondary dark:text-text-dark-secondary"
            >
              {{ extractedCount }} 引用
            </span>
          </div>
          <!-- Validation Label -->
          <div
            class="flex items-center justify-between transition-[flex] duration-700 ease-[cubic-bezier(0.4,0,0.2,1)]"
            :class="validationStage === 'active' ? 'flex-[3]' : 'flex-[1]'"
          >
            <div class="flex items-center gap-1.5">
              <span
                class="w-3.5 h-3.5 shrink-0"
                :class="validationStage === 'completed' ? 'i-lucide-check text-text dark:text-text-dark' : validationStage === 'active' ? 'i-lucide-search text-text dark:text-text-dark' : 'i-lucide-search text-text-tertiary dark:text-text-dark-tertiary'"
              />
              <span
                class="text-xs font-medium transition-colors duration-300"
                :class="validationStage === 'pending' ? 'text-text-tertiary dark:text-text-dark-tertiary' : 'text-text dark:text-text-dark'"
              >
                验证
              </span>
            </div>
            <span
              v-if="validationStage === 'active'"
              class="text-xs text-text-secondary dark:text-text-dark-secondary"
            >
              {{ currentStatus?.progress?.processed || 0 }}/{{ currentStatus?.progress?.total || 0 }}
            </span>
          </div>
        </div>
      </div>

      <!-- Current Reference -->
      <div v-if="currentTitle" class="h-8 flex items-center justify-center">
        <p
          :key="currentTitle"
          class="text-small text-text-secondary dark:text-text-dark-secondary truncate px-4 title-fade-in"
        >
          {{ currentTitle }}
        </p>
      </div>
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
  // During validation, calculate based on processed/total
  const status = currentStatus.value;
  if (!status?.progress || status.progress.total === 0) return 0;
  return Math.min(100, Math.max(0, (status.progress.processed / status.progress.total) * 100));
});

// Current title being validated
const currentTitle = computed(() => currentStatus.value?.current_title);

// Extracted reference count (shown during extraction phase)
const extractedCount = computed(() => {
  const status = currentStatus.value;
  if (!status) return 0;
  // During extraction, show total references found so far
  // During validation, show total references
  return status.progress?.total || 0;
});
</script>

<style scoped>
.shimmer-overlay {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.4) 50%,
    rgba(255, 255, 255, 0) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite ease-in-out;
  border-radius: inherit;
}

.dark .shimmer-overlay {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.25) 50%,
    rgba(255, 255, 255, 0) 100%
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

.title-fade-in {
  animation: titleFadeIn 0.4s ease-out;
}

@keyframes titleFadeIn {
  0% {
    opacity: 0;
    transform: translateY(4px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  .shimmer-overlay {
    animation: none;
    background: rgba(255, 255, 255, 0.15);
  }
  .dark .shimmer-overlay {
    background: rgba(255, 255, 255, 0.1);
  }
  .title-fade-in {
    animation: none;
  }
}
</style>
