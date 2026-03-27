<template>
  <LineCard class="space-y-4">
    <div class="flex items-start justify-between gap-4">
      <div class="flex-1 min-w-0">
        <h3 class="font-semibold text-gray-900 leading-tight">
          {{ reference.title }}
        </h3>
        <p class="text-sm text-gray-500 mt-1">
          {{ reference.authors.join(', ') }}
        </p>
      </div>
      <div class="flex flex-col items-end gap-2">
        <HallucinationBadge :type="reference.hallucination_type" />
        <ConfidenceBar :score="reference.confidence" />
      </div>
    </div>

    <div class="pt-4 border-t border-gray-200">
      <p class="text-sm text-gray-600 leading-relaxed">
        {{ reference.reasoning }}
      </p>
    </div>

    <div v-if="reference.evidence?.length" class="pt-2">
      <div class="flex flex-wrap gap-2">
        <a
          v-for="url in reference.evidence.slice(0, 3)"
          :key="url"
          :href="url"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 transition-colors"
        >
          <span class="i-lucide-link w-3 h-3" />
          {{ formatUrl(url) }}
        </a>
        <span v-if="reference.evidence.length > 3" class="text-xs text-gray-400">
          +{{ reference.evidence.length - 3 }} 更多
        </span>
      </div>
    </div>
  </LineCard>
</template>

<script setup lang="ts">
import type { ReferenceResult } from '~/types/api';

interface Props {
  reference: ReferenceResult;
}

defineProps<Props>();

function formatUrl(url: string): string {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname;
  } catch {
    return url.slice(0, 30) + (url.length > 30 ? '...' : '');
  }
}
</script>
