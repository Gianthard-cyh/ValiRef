<template>
  <div class="space-y-3">
    <div
      v-for="group in groups"
      :key="group.type"
      class="border border-border dark:border-border-dark rounded-lg overflow-hidden bg-surface dark:bg-surface-dark"
    >
      <button
        class="w-full flex items-center justify-between p-4 bg-surface-secondary dark:bg-surface-dark-secondary hover:bg-surface-tertiary dark:hover:bg-surface-dark-tertiary transition-colors duration-200"
        @click="toggleGroup(group.type)"
      >
        <div class="flex items-center gap-3">
          <span :class="[typeIcons[group.originalType], 'w-4 h-4']" />
          <span class="text-small font-medium text-text dark:text-text-dark">{{ group.type }}</span>
          <span class="text-small text-text-secondary dark:text-text-dark-secondary">({{ group.refs.length }}条)</span>
        </div>
        <span
          class="i-lucide-chevron-down w-4 h-4 text-text-muted dark:text-text-dark-tertiary transition-transform duration-200"
          :class="expanded[group.type] ? 'rotate-180' : ''"
        />
      </button>

      <Transition
        enter-active-class="transition-all duration-300 ease-out"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition-all duration-200 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div
          v-show="expanded[group.type]"
          class="divide-y divide-border-subtle dark:divide-border-dark-subtle"
        >
          <ReferenceCard
            v-for="ref in group.refs"
            :key="ref.title"
            :reference="ref"
            class="border-0 rounded-none"
          />
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ReferenceResult } from '~/types/api';

interface Props {
  references: ReferenceResult[];
}

const props = defineProps<Props>();

const typeOrder = ['Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual', 'Unknown', 'Real'];
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
