<template>
  <LineCard class="space-y-4" padding="default">
    <!-- Header: Title, Authors, Badge, Confidence -->
    <div class="flex items-start justify-between gap-4">
      <div class="flex-1 min-w-0">
        <h3 class="text-title-semibold text-text dark:text-text-dark leading-snug line-clamp-2">
          {{ reference.title }}
        </h3>
        <!-- Venue & CCF Rank -->
        <div class="flex items-center gap-2 mt-1">
          <p v-if="reference.venue" class="text-small text-text-secondary dark:text-text-dark-secondary">
            {{ reference.venue }}
          </p>
          <span
            v-if="reference.ccf_rank"
            class="inline-flex items-center px-1.5 py-0.5 rounded text-caption font-semibold"
            :class="ccfRankClass"
          >
            CCF-{{ reference.ccf_rank }}
          </span>
        </div>
        <p class="text-small text-text-secondary dark:text-text-dark-secondary mt-1 line-clamp-1">
          {{ reference.authors.join(', ') }}
        </p>
      </div>
      <div class="flex flex-col items-end gap-2 flex-shrink-0">
        <HallucinationBadge :type="reference.hallucination_type" />
        <ConfidenceBar :score="reference.confidence" />
      </div>
    </div>

    <!-- Reasoning -->
    <div class="pt-4 border-t border-border dark:border-border-dark">
      <p class="text-small text-text-secondary dark:text-text-dark-secondary leading-relaxed">
        {{ reference.reasoning }}
      </p>
    </div>

    <!-- Evidence links -->
    <div v-if="reference.evidence?.length" class="pt-2">
      <div class="flex flex-wrap gap-x-4 gap-y-2">
        <a
          v-for="url in reference.evidence.slice(0, 3)"
          :key="url"
          :href="url"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-1.5 text-caption text-text-tertiary dark:text-text-dark-tertiary hover:text-text dark:hover:text-text-dark transition-colors"
        >
          <span class="i-lucide-link-2 w-3.5 h-3.5" />
          <span class="truncate max-w-[120px]">{{ formatUrl(url) }}</span>
        </a>
        <span v-if="reference.evidence.length > 3" class="text-caption text-text-muted dark:text-text-dark-muted">
          +{{ reference.evidence.length - 3 }} 更多
        </span>
      </div>
    </div>
  </LineCard>
</template>

<script setup lang="ts">
import type { ReferenceResult } from '~/types/api';
import { computed } from 'vue';

interface Props {
  reference: ReferenceResult;
}

const props = defineProps<Props>();

const ccfRankClass = computed(() => {
  switch (props.reference.ccf_rank) {
    case 'A':
      return 'bg-gradient-to-r from-amber-500/10 to-orange-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20 dark:border-amber-400/20';
    case 'B':
      return 'bg-gradient-to-r from-blue-500/10 to-indigo-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/20 dark:border-blue-400/20';
    case 'C':
      return 'bg-gradient-to-r from-emerald-500/10 to-teal-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 dark:border-emerald-400/20';
    default:
      return 'bg-surface-secondary dark:bg-surface-dark-secondary text-text-secondary dark:text-text-dark-secondary';
  }
});

function formatUrl(url: string): string {
  try {
    const urlObj = new URL(url);
    // Remove www. prefix for cleaner display
    return urlObj.hostname.replace(/^www\./, '');
  } catch {
    return url.slice(0, 25) + (url.length > 25 ? '…' : '');
  }
}
</script>
