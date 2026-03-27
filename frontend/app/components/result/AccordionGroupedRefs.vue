<template>
  <div class="result-panel h-full flex flex-col">
    <!-- Stats header -->
    <div class="flex-shrink-0 flex border-b border-border dark:border-border-dark">
      <div
        v-for="(stat, index) in stats"
        :key="stat.label"
        class="flex-1 flex flex-col items-center justify-center py-4"
        :class="[
          index !== stats.length - 1 ? 'border-r border-border dark:border-border-dark' : '',
          stat.highlight ? 'bg-surface-secondary dark:bg-surface-dark-secondary' : '',
        ]"
      >
        <span
          class="text-heading tabular-nums"
          :class="stat.colorClass || 'text-text dark:text-text-dark'"
        >
          {{ stat.value }}
        </span>
        <span class="text-caption text-text-secondary dark:text-text-dark-secondary mt-1">{{ stat.label }}</span>
      </div>
    </div>

    <!-- 手风琴内容区域 -->
    <div class="flex-1 min-h-0 flex flex-col overflow-hidden">
      <!-- Top headers (groups before active) -->
      <div v-if="topGroups.length > 0" class="flex-shrink-0">
        <div
          v-for="(group, index) in topGroups"
          :key="group.originalType"
          class="cursor-pointer border-b border-border dark:border-border-dark"
          :class="index === 0 ? '' : ''"
          @click="activeType = group.originalType"
        >
          <div class="flex items-center justify-between px-4 py-3 bg-surface-secondary dark:bg-surface-dark-secondary">
            <div class="flex items-center gap-3">
              <!-- Icon separate from text -->
              <span :class="[typeIcons[group.originalType], 'w-4 h-4']" />
              <span class="text-small font-medium text-text dark:text-text-dark">{{ group.type }}</span>
              <span class="text-small text-text-secondary dark:text-text-dark-secondary">({{ group.refs.length }}条)</span>
            </div>
            <span class="i-lucide-chevron-down w-4 h-4 text-text-muted dark:text-text-dark-tertiary" />
          </div>
        </div>
      </div>

      <!-- Active group content -->
      <div class="flex-1 min-h-0 flex flex-col overflow-hidden">
        <!-- Active group header -->
        <div class="flex-shrink-0 bg-surface-tertiary dark:bg-surface-dark-tertiary border-b border-border dark:border-border-dark">
          <div class="flex items-center justify-between px-4 py-3">
            <div class="flex items-center gap-3">
              <!-- Icon separate from text -->
              <span :class="[typeIcons[activeGroup.originalType], 'w-4 h-4']" />
              <span class="text-small font-medium text-text dark:text-text-dark">{{ activeGroup.type }}</span>
              <span class="text-small text-text-secondary dark:text-text-dark-secondary">({{ activeGroup.refs.length }}条)</span>
            </div>
            <span class="i-lucide-chevron-up w-4 h-4 text-text-muted dark:text-text-dark-tertiary" />
          </div>
        </div>

        <!-- Scrollable reference list -->
        <div class="flex-1 overflow-y-auto min-h-0 bg-surface dark:bg-surface-dark">
          <div class="divide-y divide-border-subtle dark:divide-border-dark-subtle">
            <ReferenceCard
              v-for="ref in activeGroup.refs"
              :key="ref.title"
              :reference="ref"
              class="border-0 rounded-none"
            />
          </div>
        </div>
      </div>

      <!-- Bottom headers (groups after active) -->
      <div v-if="bottomGroups.length > 0" class="flex-shrink-0">
        <div
          v-for="group in bottomGroups"
          :key="group.originalType"
          class="cursor-pointer border-t border-border dark:border-border-dark"
          @click="activeType = group.originalType"
        >
          <div class="flex items-center justify-between px-4 py-3 bg-surface-secondary dark:bg-surface-dark-secondary">
            <div class="flex items-center gap-3">
              <!-- Icon separate from text -->
              <span :class="[typeIcons[group.originalType], 'w-4 h-4']" />
              <span class="text-small font-medium text-text dark:text-text-dark">{{ group.type }}</span>
              <span class="text-small text-text-secondary dark:text-text-dark-secondary">({{ group.refs.length }}条)</span>
            </div>
            <span class="i-lucide-chevron-down w-4 h-4 text-text-muted dark:text-text-dark-tertiary" />
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

const typeOrder = ['Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual', 'Unknown', 'Real'];
const typeNames: Record<string, string> = {
  Real: '真实引用',
  Fabrication: '完全虚构',
  AttributionError: '作者错误',
  Irrelevance: '内容不符',
  Counterfactual: '结论相反',
  Unknown: '未知类型',
};

// Icons matching the homepage
const typeIcons: Record<string, string> = {
  'Real': 'i-lucide-check-circle text-emerald-500',
  'Fabrication': 'i-lucide-x-circle text-rose-500',
  'AttributionError': 'i-lucide-user-x text-amber-500',
  'Irrelevance': 'i-lucide-git-compare text-blue-500',
  'Counterfactual': 'i-lucide-arrow-left-right text-violet-500',
  'Unknown': 'i-lucide-help-circle text-text-muted dark:text-text-dark-tertiary',
  // Chinese type mapping
  '真实引用': 'i-lucide-check-circle text-emerald-500',
  '完全虚构': 'i-lucide-x-circle text-rose-500',
  '作者错误': 'i-lucide-user-x text-amber-500',
  '内容不符': 'i-lucide-git-compare text-blue-500',
  '结论相反': 'i-lucide-arrow-left-right text-violet-500',
  '未知类型': 'i-lucide-help-circle text-text-muted dark:text-text-dark-tertiary',
};

const stats = computed(() => [
  {
    label: '总引用数',
    value: props.result.total_references,
    highlight: false,
  },
  {
    label: '真实引用',
    value: props.result.real_count,
    colorClass: 'text-emerald-600 dark:text-emerald-400',
    highlight: false,
  },
  {
    label: '幻觉引用',
    value: props.result.hallucination_count,
    colorClass: props.result.hallucination_count > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-text dark:text-text-dark',
    highlight: false,
  },
  {
    label: '耗时(秒)',
    value: props.result.duration_seconds?.toFixed(1) || '-',
    highlight: false,
  },
]);

const activeType = ref<string>('');

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

const activeGroup = computed(() => {
  return groups.value.find(g => g.originalType === activeType.value) || groups.value[0];
});

const topGroups = computed(() => {
  const activeIndex = groups.value.findIndex(g => g.originalType === activeType.value);
  if (activeIndex <= 0) return [];
  return groups.value.slice(0, activeIndex);
});

const bottomGroups = computed(() => {
  const activeIndex = groups.value.findIndex(g => g.originalType === activeType.value);
  if (activeIndex === -1) return groups.value.slice(1);
  if (activeIndex === groups.value.length - 1) return [];
  return groups.value.slice(activeIndex + 1);
});

onMounted(() => {
  const firstNonReal = groups.value.find(g => g.originalType !== 'Real');
  activeType.value = firstNonReal?.originalType || groups.value[0]?.originalType || '';
});

watch(() => props.result.references, () => {
  const firstNonReal = groups.value.find(g => g.originalType !== 'Real');
  activeType.value = firstNonReal?.originalType || groups.value[0]?.originalType || '';
}, { deep: true });
</script>
