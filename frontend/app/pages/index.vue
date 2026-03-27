<template>
  <div class="h-screen flex flex-col bg-white overflow-hidden">
    <!-- Header -->
    <header class="border-b border-gray-200 flex-shrink-0">
      <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 border-2 border-gray-900 rounded flex items-center justify-center">
            <span class="text-sm font-bold text-gray-900">V</span>
          </div>
          <h1 class="text-xl font-bold text-gray-900">ValiRef</h1>
        </div>
        <TaskHistoryDropdown />
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 overflow-hidden">
      <div class="h-full max-w-7xl mx-auto px-4 py-6">
        <!-- Upload Section -->
      <div v-if="pageState === 'idle' || pageState === 'error'" class="h-full flex flex-col justify-center max-w-xl mx-auto space-y-8">
        <div class="text-center space-y-2">
          <h2 class="text-2xl font-bold text-gray-900">验证PDF引用</h2>
          <p class="text-gray-500">上传PDF文件，AI将自动验证其中的学术引用</p>
        </div>

        <FileDropZone v-model="selectedFile" />

        <div v-if="selectedFile" class="space-y-6">
          <SearchModeToggle v-model="searchMode" />

          <LineButton block :disabled="isSubmitting" @click="submit">
            <span v-if="isSubmitting">⏳</span>
            <span v-else>✓</span>
            {{ isSubmitting ? '上传中...' : '开始验证' }}
          </LineButton>
        </div>

        <div v-if="pageState === 'error'" class="p-4 border border-rose-200 bg-rose-50 rounded text-rose-700 text-center">
          {{ errorMessage }}
        </div>
      </div>

      <!-- Processing Section -->
      <div v-if="pageState === 'processing'" class="h-full flex flex-col justify-center max-w-xl mx-auto space-y-8">
        <div class="text-center space-y-2">
          <h2 class="text-2xl font-bold text-gray-900">正在验证</h2>
          <p class="text-gray-500">请稍候，AI正在分析PDF中的引用...</p>
        </div>

        <LineCard class="space-y-6">
          <div class="flex items-center justify-between text-sm text-gray-600">
            <span>{{ currentStatus?.filename }}</span>
            <StatusBadge :status="currentStatus?.status || 'pending'" />
          </div>

          <LineProgress
            :percentage="progress"
            :label="progressLabel"
          />

          <div class="text-center text-sm text-gray-500">
            <span v-if="currentStatus?.progress">
              已处理 {{ currentStatus.progress.processed }} / {{ currentStatus.progress.total }} 个引用
            </span>
            <span v-else>正在初始化...</span>
          </div>
        </LineCard>
      </div>

      <!-- Results Section - Split View -->
      <div v-if="pageState === 'completed' && currentResult" class="h-full flex flex-col gap-4">
        <!-- Top Actions -->
        <div class="flex items-center justify-between flex-shrink-0">
          <div>
            <h2 class="text-xl font-bold text-gray-900">验证结果</h2>
            <p class="text-sm text-gray-500">{{ currentResult.filename }}</p>
          </div>
          <LineButton variant="outline" @click="reset">
            <span>↺</span>
            上传新文件
          </LineButton>
        </div>

        <!-- Split View Content -->
        <div class="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-0">
          <!-- Left: PDF Viewer -->
          <div class="border border-gray-200 rounded overflow-hidden bg-gray-50 flex flex-col">
            <div class="bg-gray-100 px-4 py-2 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
              <span class="text-sm font-medium text-gray-700">PDF 预览</span>
              <a
                v-if="pdfUrl"
                :href="pdfUrl"
                target="_blank"
                class="text-xs text-gray-500 hover:text-gray-900"
              >
                在新窗口打开 ↗
              </a>
            </div>
            <div class="flex-1 overflow-auto p-4 min-h-0">
              <iframe
                v-if="pdfUrl"
                :src="pdfUrl"
                class="w-full h-full border-0"
                type="application/pdf"
              />
              <div v-else class="flex items-center justify-center h-full text-gray-400">
                PDF 无法预览
              </div>
            </div>
          </div>

          <!-- Right: Accordion Grouped Results -->
          <div class="rounded overflow-hidden bg-white">
            <AccordionGroupedRefs :result="currentResult" />
          </div>
        </div>
      </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-gray-200 flex-shrink-0">
      <div class="max-w-7xl mx-auto px-4 py-4 text-center text-sm text-gray-500">
        ValiRef - AI驱动的学术引用验证工具
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
const taskStore = useTaskStore();
const { submitValidation } = useApi();

const { pageState, errorMessage, currentStatus, currentResult, currentPDFFile, progress, isProcessing } = storeToRefs(taskStore);
const { startPolling, reset } = taskStore;

const selectedFile = ref<File | null>(null);
const searchMode = ref<'local' | 'online'>('local');
const isSubmitting = ref(false);
const pdfUrl = ref<string>('');

const progressLabel = computed(() => {
  if (!currentStatus.value?.progress) return '准备中';
  return `正在验证 (${currentStatus.value.progress.processed}/${currentStatus.value.progress.total})`;
});

watch(currentResult, (result) => {
  if (result?.filename && currentPDFFile.value) {
    const file = currentPDFFile.value;
    if (file.type === 'application/pdf') {
      pdfUrl.value = URL.createObjectURL(file);
    }
  }
});

onUnmounted(() => {
  if (pdfUrl.value) {
    URL.revokeObjectURL(pdfUrl.value);
  }
});

async function submit() {
  if (!selectedFile.value) return;

  isSubmitting.value = true;
  try {
    const response = await submitValidation(selectedFile.value, searchMode.value);
    await startPolling(response.task_id, response.filename, selectedFile.value);
  } catch (e: any) {
    pageState.value = 'error';
    errorMessage.value = e?.message || '上传失败，请重试';
  } finally {
    isSubmitting.value = false;
  }
}
</script>
