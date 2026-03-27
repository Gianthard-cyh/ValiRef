<template>
  <div class="space-y-4">
    <div
      v-for="group in groups"
      :key="group.type"
      class="border border-gray-200 rounded overflow-hidden"
    >
      <button
        class="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
        @click="toggleGroup(group.type)"
      >
        <div class="flex items-center gap-3">
          <HallucinationBadge :type="group.originalType" />
          <span class="text-sm text-gray-500">({{ group.refs.length }}条)</span>
        </div>
        <span
          class="text-gray-400 transition-transform"
          :class="expanded[group.type] ? 'rotate-180' : ''"
        >
          ▼
        </span>
      </button>

      <div
        v-show="expanded[group.type]"
        class="divide-y divide-gray-100"
      >
        <ReferenceCard
          v-for="ref in group.refs"
          :key="ref.title"
          :reference="ref"
          class="border-0 rounded-none"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ReferenceResult } from '~/types/api';

interface Props {
  references: ReferenceResult[];
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

const groups = computed(() => {
  const grouped = new Map<string, ReferenceResult[]>();

  for (const ref of props.references) {
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

const expanded = reactive<Record<string, boolean>>({});

defineExpose({ groups, expanded });

onMounted(() => {
  for (const group of groups.value) {
    expanded[group.type] = group.originalType !== 'Real';
  }
});

function toggleGroup(type: string) {
  expanded[type] = !expanded[type];
}
</script>
