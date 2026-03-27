<template>
  <div class="result-panel h-full flex flex-col">
    <!-- 固定顶部：统计摘要 -->
    <div class="panel-header flex-shrink-0">
      <ResultSummary :result="result" />
    </div>

    <!-- 手风琴容器 -->
    <div class="accordion-container flex-1 min-h-0 flex flex-col overflow-hidden border border-gray-200 rounded mt-4">
      <!-- 顶部 Headers（展开分组之前的分组） -->
      <div v-if="topGroups.length > 0" class="top-headers flex-shrink-0">
        <div
          v-for="group in topGroups"
          :key="group.originalType"
          class="group-header cursor-pointer hover:bg-gray-100 transition-colors border-b border-gray-200"
          @click="activeType = group.originalType"
        >
          <div class="flex items-center justify-between p-3 bg-gray-50">
            <div class="flex items-center gap-3">
              <HallucinationBadge :type="group.originalType" />
              <span class="text-sm text-gray-500">({{ group.refs.length }}条)</span>
            </div>
            <span class="text-gray-400">▼</span>
          </div>
        </div>
      </div>

      <!-- 中间 Content 区域 -->
      <div class="content-wrapper flex-1 min-h-0 flex flex-col overflow-hidden">
        <!-- 当前激活分组的 Header（固定） -->
        <div class="active-header flex-shrink-0 bg-gray-100 border-b border-gray-200">
          <div class="flex items-center justify-between p-3">
            <div class="flex items-center gap-3">
              <HallucinationBadge :type="activeGroup.originalType" />
              <span class="text-sm text-gray-500">({{ activeGroup.refs.length }}条)</span>
            </div>
            <span class="text-gray-400">▲</span>
          </div>
        </div>

        <!-- 引用列表（可滚动） -->
        <div class="content-area flex-1 overflow-y-auto min-h-0 bg-white">
          <div class="divide-y divide-gray-100">
            <ReferenceCard
              v-for="ref in activeGroup.refs"
              :key="ref.title"
              :reference="ref"
              class="border-0 rounded-none"
            />
          </div>
        </div>
      </div>

      <!-- 底部 Headers（展开分组之后的分组） -->
      <div v-if="bottomGroups.length > 0" class="bottom-headers flex-shrink-0">
        <div
          v-for="group in bottomGroups"
          :key="group.originalType"
          class="group-header cursor-pointer hover:bg-gray-100 transition-colors border-t border-gray-200"
          @click="activeType = group.originalType"
        >
          <div class="flex items-center justify-between p-3 bg-gray-50">
            <div class="flex items-center gap-3">
              <HallucinationBadge :type="group.originalType" />
              <span class="text-sm text-gray-500">({{ group.refs.length }}条)</span>
            </div>
            <span class="text-gray-400">▼</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PDFValidationResult, ReferenceResult } from '~/types/api';

interface Group {
  type: string;
  originalType: string;
  refs: ReferenceResult[];
}

interface Props {
  result: PDFValidationResult;
}

const props = defineProps<Props>();

const typeOrder = ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual', 'Unknown'];
const typeNames: Record<string, string> = {
  Real: '真实引用',
  Fabrication: '完全虚构',
  AttributionError: '作者错误',
  Irrelevance: '内容不符',
  Counterfactual: '结论相反',
  Unknown: '未知类型',
};

// 当前激活的分组类型
const activeType = ref<string>('');

// 计算分组数据
const groups = computed<Group[]>(() => {
  const grouped = new Map<string, ReferenceResult[]>();

  for (const ref of props.result.references) {
    const type = ref.hallucination_type || 'Unknown';
    if (!grouped.has(type)) {
      grouped.set(type, []);
    }
    grouped.get(type)!.push(ref);
  }

  return typeOrder
    .filter(type => grouped.has(type))
    .map(type => ({
      type: typeNames[type] || type,
      originalType: type,
      refs: grouped.get(type) || [],
    }));
});

// 当前激活的分组
const activeGroup = computed(() => {
  return groups.value.find(g => g.originalType === activeType.value) || groups.value[0];
});

// 顶部 Headers（激活分组之前的分组）
const topGroups = computed(() => {
  const activeIndex = groups.value.findIndex(g => g.originalType === activeType.value);
  if (activeIndex <= 0) return [];
  return groups.value.slice(0, activeIndex);
});

// 底部 Headers（激活分组之后的分组）
const bottomGroups = computed(() => {
  const activeIndex = groups.value.findIndex(g => g.originalType === activeType.value);
  if (activeIndex === -1) return groups.value.slice(1);
  if (activeIndex === groups.value.length - 1) return [];
  return groups.value.slice(activeIndex + 1);
});

// 初始化：默认激活第一个非 Real 的分组
onMounted(() => {
  const firstNonReal = groups.value.find(g => g.originalType !== 'Real');
  activeType.value = firstNonReal?.originalType || groups.value[0]?.originalType || '';
});

// 当结果变化时重新初始化
watch(() => props.result.references, () => {
  const firstNonReal = groups.value.find(g => g.originalType !== 'Real');
  activeType.value = firstNonReal?.originalType || groups.value[0]?.originalType || '';
}, { deep: true });
</script>
