<template>
  <span
    class="inline-flex items-center gap-1 rounded-full text-caption font-medium transition-colors"
    :class="[
      sizeClasses[size],
      variantClasses[variant],
    ]"
  >
    <span
      v-if="dot"
      class="w-1.5 h-1.5 rounded-full"
      :class="dotClasses[variant]"
      aria-hidden="true"
    />
    <slot />
  </span>
</template>

<script setup lang="ts">
interface Props {
  variant?: 'default' | 'success' | 'error' | 'warning' | 'info' | 'neutral';
  size?: 'sm' | 'md';
  dot?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'md',
  dot: false,
});

const sizeClasses: Record<string, string> = {
  sm: 'px-2 py-0.5',
  md: 'px-2.5 py-1',
};

const variantClasses: Record<string, string> = {
  default: 'bg-surface-secondary dark:bg-surface-dark-secondary text-text-secondary dark:text-text-dark-secondary border border-border dark:border-border-dark',
  success: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20',
  error: 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border border-rose-500/20',
  warning: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20',
  info: 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-500/20',
  neutral: 'bg-text/10 dark:bg-text-dark/10 text-text dark:text-text-dark',
};

const dotClasses: Record<string, string> = {
  default: 'bg-text-secondary dark:bg-text-dark-secondary',
  success: 'bg-emerald-500',
  error: 'bg-rose-500',
  warning: 'bg-amber-500',
  info: 'bg-blue-500',
  neutral: 'bg-text dark:bg-text-dark',
};
</script>
