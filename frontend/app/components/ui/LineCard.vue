<template>
  <div
    class="rounded-lg border transition-all duration-200"
    :class="[
      elevated ? 'shadow-sm hover:shadow-md' : '',
      interactive ? 'cursor-pointer hover:border-border-strong dark:hover:border-border-dark-strong' : '',
      padding === 'none' ? '' : padding === 'small' ? 'p-4' : padding === 'large' ? 'p-8' : 'p-6',
      variant === 'secondary' ? 'bg-surface-secondary dark:bg-surface-dark-secondary border-border-subtle dark:border-border-dark-subtle' :
      variant === 'ghost' ? 'bg-transparent border-transparent' :
      'bg-surface dark:bg-surface-dark border-border dark:border-border-dark',
    ]"
    v-bind="$attrs"
  >
    <slot />
  </div>
</template>

<script setup lang="ts">
interface Props {
  variant?: 'default' | 'secondary' | 'ghost';
  padding?: 'none' | 'small' | 'default' | 'large';
  elevated?: boolean;
  interactive?: boolean;
}

withDefaults(defineProps<Props>(), {
  variant: 'default',
  padding: 'default',
  elevated: false,
  interactive: false,
});
</script>
