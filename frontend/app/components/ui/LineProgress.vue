<template>
  <div class="w-full">
    <div class="flex justify-between mb-2 text-sm text-gray-600">
      <span>{{ label }}</span>
      <span>{{ percentage }}%</span>
    </div>
    <div class="h-1 w-full bg-gray-100 rounded overflow-hidden">
      <div
        class="h-full bg-gray-900 transition-all duration-300 ease-out"
        :style="{ width: `${percentage}%` }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  percentage: number;
  label?: string;
}

withDefaults(defineProps<Props>(), {
  label: '进度',
});
</script>
