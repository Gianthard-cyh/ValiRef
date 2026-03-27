<template>
  <div class="flex items-center gap-4">
    <span class="text-sm text-gray-600">搜索模式：</span>
    <div class="flex gap-2">
      <button
        v-for="mode in modes"
        :key="mode.value"
        :class="[
          'px-4 py-2 border rounded text-sm font-medium transition-all',
          modelValue === mode.value
            ? 'border-gray-900 bg-gray-900 text-white'
            : 'border-gray-200 text-gray-700 hover:border-gray-400',
        ]"
        @click="modelValue = mode.value"
      >
        {{ mode.label }}
      </button>
    </div>
    <span class="text-xs text-gray-400">{{ currentDescription }}</span>
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
