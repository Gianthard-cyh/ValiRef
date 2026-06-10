<template>
  <div class="h-[calc(100vh-3.5rem)] flex flex-col bg-surface dark:bg-surface-dark">
    <!-- Top Bar -->
    <div class="flex-shrink-0 px-6 py-4 border-b border-border dark:border-border-dark flex items-center justify-between">
      <div>
        <h2 class="text-title-semibold">验证结果</h2>
        <p class="text-caption text-text-secondary dark:text-text-dark-secondary">{{ result.filename }}</p>
      </div>
      <LineButton variant="outline" size="sm" @click="reset">
        <span class="i-lucide-rotate-ccw w-4 h-4" />
        新文件
      </LineButton>
    </div>

    <!-- Content -->
    <div class="flex-1 min-h-0 flex flex-col lg:flex-row">
      <!-- PDF -->
      <div class="flex-1 min-h-0 border-r border-border dark:border-border-dark flex flex-col">
        <div class="flex-shrink-0 px-4 py-2 border-b border-border-subtle dark:border-border-dark-subtle flex items-center justify-between bg-surface-secondary dark:bg-surface-dark-secondary">
          <span class="text-small text-text-secondary dark:text-text-dark-secondary">输入文件</span>
          <a v-if="pdfUrl" :href="pdfUrl" target="_blank" class="text-small text-text-tertiary dark:text-text-dark-tertiary hover:text-text dark:hover:text-text-dark transition-colors flex items-center gap-1">
            打开
            <span class="i-lucide-external-link w-3 h-3" />
          </a>
        </div>
        <div class="flex-1 min-h-0 bg-surface-secondary dark:bg-surface-dark-secondary">
          <iframe v-if="pdfUrl" :src="pdfUrl" class="w-full h-full bg-surface dark:bg-surface-dark border border-border dark:border-border-dark" />
          <div v-else class="w-full h-full flex flex-col items-center justify-center text-text-muted dark:text-text-dark-tertiary gap-2">
            <span class="i-lucide-file-x w-6 h-6" />
            <span class="text-sm">PDF 无法预览</span>
          </div>
        </div>
      </div>

      <!-- Results -->
      <div class="flex-1 min-h-0 lg:w-96 flex flex-col">
        <AccordionGroupedRefs :result="result" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ValidationResult } from '~/types/api';

interface Props {
  result: ValidationResult;
  pdfUrl: string;
}

const props = defineProps<Props>();

const taskStore = useTaskStore();
const { reset } = taskStore;
</script>
