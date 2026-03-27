<template>
  <button
    :disabled="disabled || loading"
    :class="[
      // Base styles
      'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 ease-out',
      'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-surface dark:focus:ring-offset-surface-dark',
      'disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100',
      'active:scale-[0.98] active:duration-100',
      'hover:-translate-y-0.5 hover:shadow-sm',
      block ? 'w-full' : '',
      sizeClasses[size],
      variantClasses[variant],
    ]"
    v-bind="$attrs"
  >
    <!-- Loading spinner -->
    <span
      v-if="loading"
      class="i-lucide-loader-2 w-4 h-4 animate-spin"
      aria-hidden="true"
    />
    <!-- Leading icon -->
    <span
      v-else-if="leadingIcon"
      :class="[leadingIcon, 'w-4 h-4']"
      aria-hidden="true"
    />
    <slot />
    <!-- Trailing icon -->
    <span
      v-if="trailingIcon"
      :class="[trailingIcon, 'w-4 h-4']"
      aria-hidden="true"
    />
  </button>
</template>

<script setup lang="ts">
interface Props {
  variant?: 'default' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  block?: boolean;
  leadingIcon?: string;
  trailingIcon?: string;
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'md',
  disabled: false,
  loading: false,
  block: false,
});

const sizeClasses: Record<string, string> = {
  sm: 'px-3 py-1.5 text-caption',
  md: 'px-5 py-2.5 text-small',
  lg: 'px-6 py-3 text-body',
};

const variantClasses: Record<string, string> = {
  default: 'bg-text text-surface dark:bg-text-dark dark:text-surface-dark hover:opacity-90 focus:ring-text/20 dark:focus:ring-text-dark/20',
  outline: 'border border-border-strong dark:border-border-dark-strong text-text dark:text-text-dark hover:bg-surface-secondary dark:hover:bg-surface-dark-secondary focus:ring-text/10 dark:focus:ring-text-dark/10',
  ghost: 'text-text-secondary dark:text-text-dark-secondary hover:bg-surface-secondary dark:hover:bg-surface-dark-secondary hover:text-text dark:hover:text-text-dark focus:ring-text/10 dark:focus:ring-text-dark/10',
  danger: 'bg-rose-600 text-white hover:bg-rose-700 focus:ring-rose-500/20',
};
</script>
