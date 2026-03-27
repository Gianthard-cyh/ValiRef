<template>
  <span
    :class="[
      'inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium border',
      variantClasses[variant],
    ]"
  >
    <slot />
  </span>
</template>

<script setup lang="ts">
interface Props {
  variant?: 'default' | 'success' | 'error' | 'warning' | 'info';
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
});

const variantClasses: Record<string, string> = {
  default: 'border-gray-200 text-gray-700 bg-gray-50',
  success: 'border-emerald-200 text-emerald-700 bg-emerald-50',
  error: 'border-rose-200 text-rose-700 bg-rose-50',
  warning: 'border-amber-200 text-amber-700 bg-amber-50',
  info: 'border-blue-200 text-blue-700 bg-blue-50',
};
</script>
