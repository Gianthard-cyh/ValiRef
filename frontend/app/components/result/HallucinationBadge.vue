<template>
  <span
    :class="[
      'inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium border',
      typeClasses[type || 'Unknown'],
    ]"
  >
    {{ typeLabels[type || 'Unknown'] }}
  </span>
</template>

<script setup lang="ts">
import type { HallucinationType } from '~/types/api';

interface Props {
  type?: HallucinationType;
}

const props = defineProps<Props>();

const typeClasses: Record<string, string> = {
  'Real': 'border-emerald-200 text-emerald-700 bg-emerald-50',
  'Fabrication': 'border-rose-200 text-rose-700 bg-rose-50',
  'AttributionError': 'border-amber-200 text-amber-700 bg-amber-50',
  'Irrelevance': 'border-blue-200 text-blue-700 bg-blue-50',
  'Counterfactual': 'border-violet-200 text-violet-700 bg-violet-50',
  'Unknown': 'border-gray-200 text-gray-700 bg-gray-50',
  // 中文类型映射
  '真实引用': 'border-emerald-200 text-emerald-700 bg-emerald-50',
  '完全虚构': 'border-rose-200 text-rose-700 bg-rose-50',
  '作者错误': 'border-amber-200 text-amber-700 bg-amber-50',
  '内容不符': 'border-blue-200 text-blue-700 bg-blue-50',
  '结论相反': 'border-violet-200 text-violet-700 bg-violet-50',
  '未知类型': 'border-gray-200 text-gray-700 bg-gray-50',
};

const typeLabels: Record<string, string> = {
  'Real': '真实',
  'Fabrication': '虚构',
  'AttributionError': '作者错误',
  'Irrelevance': '不相关',
  'Counterfactual': '反事实',
  'Unknown': '未知',
  // 中文类型映射
  '真实引用': '真实',
  '完全虚构': '虚构',
  '内容不符': '不相关',
  '结论相反': '反事实',
  '未知类型': '未知',
};
</script>
