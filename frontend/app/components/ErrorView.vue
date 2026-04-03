<template>
  <div class="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-6 py-12 bg-surface-tertiary dark:bg-surface-dark-tertiary relative">
    <div class="w-full max-w-md">
      <!-- Error Icon -->
      <div class="w-16 h-16 mx-auto mb-6 rounded-full bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800 flex items-center justify-center">
        <span class="i-lucide-circle-x w-8 h-8 text-red-500 dark:text-red-400" />
      </div>

      <!-- Title -->
      <h2 class="text-title text-center mb-2">处理失败</h2>
      <p class="text-small text-text-secondary dark:text-text-dark-secondary text-center mb-8">
        {{ errorConfig.title }}
      </p>

      <!-- Error Details Card -->
      <div class="bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-xl p-6 mb-6">
        <div class="flex items-start gap-4">
          <div class="flex-shrink-0 w-10 h-10 rounded-lg bg-surface-secondary dark:bg-surface-dark-secondary flex items-center justify-center">
            <span :class="errorConfig.icon" class="w-5 h-5 text-text-secondary dark:text-text-dark-secondary" />
          </div>
          <div class="flex-1 min-w-0">
            <h3 class="text-small-semibold text-text dark:text-text-dark mb-1">
              {{ errorConfig.heading }}
            </h3>
            <p class="text-caption text-text-secondary dark:text-text-dark-secondary">
              {{ errorConfig.description }}
            </p>
          </div>
        </div>

        <!-- Technical Details (collapsible) -->
        <div v-if="errorMessage" class="mt-4 pt-4 border-t border-border-subtle dark:border-border-dark-subtle">
          <button
            @click="showDetails = !showDetails"
            class="flex items-center gap-2 text-caption text-text-tertiary dark:text-text-dark-tertiary hover:text-text-secondary dark:hover:text-text-dark-secondary transition-colors"
          >
            <span class="i-lucide-terminal w-4 h-4" />
            技术详情
            <span :class="showDetails ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'" class="w-4 h-4" />
          </button>
          <div v-if="showDetails" class="mt-3 p-3 bg-surface-secondary dark:bg-surface-dark-secondary rounded-lg">
            <code class="text-xs text-text-secondary dark:text-text-dark-secondary font-mono break-all">
              {{ errorMessage }}
            </code>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex flex-col gap-3">
        <LineButton variant="primary" size="lg" @click="reset" class="w-full">
          <span class="i-lucide-upload w-5 h-5" />
          上传新文件
        </LineButton>

        <LineButton
          v-if="errorConfig.showRetry"
          variant="outline"
          size="lg"
          @click="retryTask"
          :disabled="isRetrying"
          class="w-full"
        >
          <span v-if="isRetrying" class="i-lucide-loader-2 w-5 h-5 animate-spin" />
          <span v-else class="i-lucide-rotate-ccw w-5 h-5" />
          {{ isRetrying ? '重试中...' : '重新处理' }}
        </LineButton>
      </div>

      <!-- Error Code (for support) -->
      <p v-if="errorCode" class="mt-6 text-center text-caption text-text-tertiary dark:text-text-dark-tertiary">
        错误代码: <code class="font-mono">{{ errorCode }}</code>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ErrorCode } from '~/types/api';

interface Props {
  errorCode?: ErrorCode;
  errorMessage?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  reset: [];
  retry: [];
}>();

const showDetails = ref(false);
const isRetrying = ref(false);

// Error configuration based on error code
const errorConfig = computed(() => {
  const configs: Record<ErrorCode | 'unknown', {
    title: string;
    heading: string;
    description: string;
    icon: string;
    showRetry: boolean;
  }> = {
    pdf_corrupted: {
      title: 'PDF 文件损坏',
      heading: '无法读取 PDF 文件',
      description: '文件可能已损坏或格式不正确。请尝试使用其他 PDF 阅读器打开，或重新导出后再上传。',
      icon: 'i-lucide-file-x',
      showRetry: false,
    },
    pdf_no_text: {
      title: 'PDF 无文本内容',
      heading: '扫描版 PDF 无法处理',
      description: '您上传的 PDF 是扫描版图片，不包含可提取的文本。请上传包含可编辑文本的 PDF 文件。',
      icon: 'i-lucide-scan',
      showRetry: false,
    },
    pdf_too_short: {
      title: 'PDF 内容过少',
      heading: '文档内容不足以提取引用',
      description: 'PDF 中的文本内容太少，无法识别引用章节。请确保上传完整的学术论文。',
      icon: 'i-lucide-file-minus',
      showRetry: false,
    },
    extraction_failed: {
      title: '引用提取失败',
      heading: '无法解析引用章节',
      description: '系统无法从文档中提取引用信息。可能是引用格式不标准或文档结构异常。',
      icon: 'i-lucide-quote',
      showRetry: true,
    },
    no_references_found: {
      title: '未找到引用',
      heading: '文档中没有引用',
      description: 'PDF 中未找到 References 或 Bibliography 章节。请确认上传的是包含引用的学术论文。',
      icon: 'i-lucide-book-open',
      showRetry: false,
    },
    validation_timeout: {
      title: '处理超时',
      heading: '验证过程耗时过长',
      description: '引用验证过程超时。这可能是由于引用数量过多或网络问题导致，建议稍后再试。',
      icon: 'i-lucide-clock',
      showRetry: true,
    },
    search_failed: {
      title: '搜索服务异常',
      heading: '无法连接学术数据库',
      description: '暂时无法连接到学术搜索引擎。请检查网络连接，或稍后重试。',
      icon: 'i-lucide-wifi-off',
      showRetry: true,
    },
    agent_parse_error: {
      title: '解析错误',
      heading: 'AI 响应解析失败',
      description: 'AI 模型的响应格式异常。这通常是临时性问题，建议重试。',
      icon: 'i-lucide-brain-circuit',
      showRetry: true,
    },
    unknown: {
      title: '处理失败',
      heading: '未知错误',
      description: '任务处理过程中发生错误。请检查文件格式是否正确，或稍后重试。',
      icon: 'i-lucide-alert-circle',
      showRetry: true,
    },
  };

  return props.errorCode && configs[props.errorCode]
    ? configs[props.errorCode]
    : configs.unknown;
});

function reset() {
  emit('reset');
}

async function retryTask() {
  isRetrying.value = true;
  try {
    await emit('retry');
  } finally {
    isRetrying.value = false;
  }
}
</script>
