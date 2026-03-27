<template>
  <div class="w-full" :class="{ 'space-y-2': showLabel || $slots.label }">
    <!-- Label -->
    <div
      v-if="showLabel || $slots.label"
      class="flex items-center justify-between text-small"
    >
      <span class="text-text-secondary dark:text-text-dark-secondary">
        <slot name="label">进度</slot>
      </span>
      <span class="font-medium text-text dark:text-text-dark">
        {{ Math.round(percentage) }}%
      </span>
    </div>

    <!-- Progress bar -->
    <div
      class="relative overflow-hidden rounded-full bg-surface-tertiary dark:bg-surface-dark-tertiary"
      :class="sizeClasses[size]"
      role="progressbar"
      :aria-valuenow="percentage"
      :aria-valuemin="0"
      :aria-valuemax="100"
    >
      <!-- Background track with pattern for indeterminate state -->
      <div
        v-if="indeterminate"
        class="absolute inset-0 animate-pulse bg-surface-secondary dark:bg-surface-dark-secondary"
      />

      <!-- Progress fill -->
      <div
        class="h-full rounded-full transition-all duration-300 ease-out"
        :class="[
          variantClasses[variant],
          indeterminate ? 'animate-indeterminate w-1/3' : '',
        ]"
        :style="indeterminate ? {} : { width: `${percentage}%` }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  percentage?: number;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'success' | 'error' | 'warning';
  showLabel?: boolean;
  indeterminate?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  percentage: 0,
  size: 'md',
  variant: 'default',
  showLabel: false,
  indeterminate: false,
});

const sizeClasses: Record<string, string> = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-3',
};

const variantClasses: Record<string, string> = {
  default: 'bg-text dark:bg-text-dark',
  success: 'bg-emerald-500',
  error: 'bg-rose-500',
  warning: 'bg-amber-500',
};
</script>

<style scoped>
@keyframes indeterminate {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(300%);
  }
}

.animate-indeterminate {
  animation: indeterminate 1.5s ease-in-out infinite;
}
</style>
