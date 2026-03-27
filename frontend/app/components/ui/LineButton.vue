<template>
  <button
    :disabled="disabled"
    :class="[
      disabled ? 'line-btn-disabled' : variant === 'outline' ? 'line-btn-outline' : 'line-btn',
      block ? 'w-full' : '',
    ]"
    v-bind="$attrs"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
interface Props {
  variant?: 'default' | 'outline';
  disabled?: boolean;
  block?: boolean;
}

withDefaults(defineProps<Props>(), {
  variant: 'default',
  disabled: false,
  block: false,
});
</script>
