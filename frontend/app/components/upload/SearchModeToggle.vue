<template>
  <div class="flex items-center gap-4">
    <span class="text-small text-text-secondary dark:text-text-dark-secondary">搜索模式：</span>
    <div class="flex gap-2">
      <button
        v-for="mode in modes"
        :key="mode.value"
        :class="[
          'px-4 py-2 border rounded-lg text-small font-medium transition-all duration-200',
          modelValue === mode.value
            ? 'border-text dark:border-text-dark bg-text dark:bg-text-dark text-surface dark:text-surface-dark'
            : 'border-border dark:border-border-dark text-text-secondary dark:text-text-dark-secondary hover:border-border-strong dark:hover:border-border-dark-strong hover:text-text dark:hover:text-text-dark',
        ]"
        @click="modelValue = mode.value"
      >
        {{ mode.label }}
      </button>
    </div>
    <span class="text-caption text-text-muted dark:text-text-dark-tertiary">{{ currentDescription }}</span>
  </div>
</template>

<script setup lang="ts">
const modelValue = defineModel<'local' | 'online'>('modelValue', { default: 'local' });

const modes = [
  { value: 'local' as const, label: 'Local', description: '使用本地数据库搜索' },
  { value: 'online' as const, label: 'Online', description: '使用在线API搜索' },
];

const currentDescription = computed(() => {
  return modes.find(m => m.value === modelValue.value)?.description;
});
</script>
