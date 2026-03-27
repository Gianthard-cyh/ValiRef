<template>
  <div class="min-h-screen bg-white text-gray-900">
    <!-- Header -->
    <header class="fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-200">
      <div class="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
        <div class="flex items-center gap-2.5 cursor-pointer" @click="reset">
          <div class="w-7 h-7 border border-gray-900 rounded flex items-center justify-center">
            <span class="text-sm font-semibold">V</span>
          </div>
          <span class="text-lg font-semibold tracking-tight">ValiRef</span>
        </div>
        <TaskHistoryDropdown />
      </div>
    </header>

    <!-- Main Content -->
    <main class="pt-14">
      <!-- Upload State -->
      <div v-if="pageState === 'idle' || pageState === 'error'"
           class="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-6">
        <div class="w-full max-w-md space-y-8">
          <!-- Title -->
          <div class="text-center space-y-1">
            <h1 class="text-2xl font-semibold">验证 PDF 引用</h1>
            <p class="text-sm text-gray-500">上传文件，自动检测学术引用问题</p>
          </div>

          <!-- Upload Zone -->
          <div
            class="relative border-2 border-dashed border-gray-300 rounded-lg p-8 transition-colors hover:border-gray-400"
            :class="{ 'border-gray-900 bg-gray-50': selectedFile, 'border-red-300': pageState === 'error' }"
            @dragover.prevent
            @drop.prevent="handleDrop"
            @click="!selectedFile && $refs.fileInput?.click()">

            <div v-if="!selectedFile" class="text-center space-y-3 cursor-pointer">
              <svg class="w-8 h-8 mx-auto text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <div>
                <p class="text-sm font-medium">点击或拖放 PDF 文件</p>
                <p class="text-xs text-gray-400 mt-0.5">最大 10MB</p>
              </div>
            </div>

            <div v-else class="text-center space-y-2">
              <p class="text-sm font-medium truncate">{{ selectedFile.name }}</p>
              <p class="text-xs text-gray-500">{{ formatFileSize(selectedFile.size) }}</p>
              <button class="text-xs text-gray-400 hover:text-gray-600" @click.stop="selectedFile = null">
                移除
              </button>
            </div>

            <input ref="fileInput" type="file" accept=".pdf" class="hidden" @change="handleFileSelect">
          </div>

          <!-- Options -->
          <div v-if="selectedFile" class="flex items-center justify-center gap-4">
            <button
              v-for="mode in ['local', 'online']"
              :key="mode"
              class="px-3 py-1.5 text-sm rounded-md border transition-colors"
              :class="searchMode === mode
                ? 'border-gray-900 bg-gray-900 text-white'
                : 'border-gray-200 hover:border-gray-400'"
              @click="searchMode = mode as 'local' | 'online'">
              {{ mode === 'local' ? '本地搜索' : '联网搜索' }}
            </button>
          </div>

          <!-- Submit -->
          <button
            v-if="selectedFile"
            class="w-full py-2.5 bg-gray-900 text-white text-sm font-medium rounded-lg
                   hover:bg-gray-800 disabled:opacity-50 transition-colors"
            :disabled="isSubmitting"
            @click="submit">
            {{ isSubmitting ? '上传中...' : '开始验证' }}
          </button>

          <!-- Error -->
          <div v-if="pageState === 'error'" class="text-sm text-red-600 text-center">
            {{ errorMessage }}
          </div>
        </div>
      </div>

      <!-- Processing State -->
      <div v-if="pageState === 'processing'"
           class="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-6">
        <div class="w-full max-w-sm space-y-6 text-center">
          <div class="space-y-1">
            <h2 class="text-lg font-medium">正在验证</h2>
            <p class="text-sm text-gray-500">{{ currentStatus?.filename }}</p>
          </div>

          <div class="space-y-2">
            <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div class="h-full bg-gray-900 rounded-full transition-all" :style="{ width: `${progress}%` }" />
            </div>
            <p class="text-xs text-gray-400">
              <span v-if="currentStatus?.progress">
                {{ currentStatus.progress.processed }} / {{ currentStatus.progress.total }} 个引用
              </span>
              <span v-else>准备中...</span>
            </p>
          </div>
        </div>
      </div>

      <!-- Results State -->
      <div v-if="pageState === 'completed' && currentResult" class="h-[calc(100vh-3.5rem)] flex flex-col">
        <!-- Top Bar -->
        <div class="flex-shrink-0 px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 class="text-lg font-semibold">验证结果</h2>
            <p class="text-xs text-gray-500">{{ currentResult.filename }}</p>
          </div>
          <button
            class="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-200 rounded-md
                   hover:border-gray-400 transition-colors"
            @click="reset">
            <span class="text-xs">↺</span>
            新文件
          </button>
        </div>

        <!-- Content -->
        <div class="flex-1 min-h-0 flex flex-col lg:flex-row">
          <!-- PDF -->
          <div class="flex-1 min-h-0 border-r border-gray-200 flex flex-col">
            <div class="flex-shrink-0 px-4 py-2 border-b border-gray-100 flex items-center justify-between bg-gray-50">
              <span class="text-xs text-gray-500">PDF 预览</span>
              <a v-if="pdfUrl" :href="pdfUrl" target="_blank" class="text-xs text-gray-400 hover:text-gray-600">
                打开 ↗
              </a>
            </div>
            <div class="flex-1 min-h-0 p-4 bg-gray-50">
              <iframe v-if="pdfUrl" :src="pdfUrl" class="w-full h-full bg-white border border-gray-200 rounded" />
              <div v-else class="w-full h-full flex items-center justify-center text-gray-400 text-sm">
                PDF 无法预览
              </div>
            </div>
          </div>

          <!-- Results -->
          <div class="flex-1 min-h-0 lg:w-96 flex flex-col bg-white">
            <AccordionGroupedRefs :result="currentResult" />
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const taskStore = useTaskStore();
const { submitValidation } = useApi();

const { pageState, errorMessage, currentStatus, currentResult, currentPDFFile, progress } = storeToRefs(taskStore);
const { startPolling, reset } = taskStore;

const selectedFile = ref<File | null>(null);
const searchMode = ref<'local' | 'online'>('local');
const isSubmitting = ref(false);
const pdfUrl = ref<string>('');
const fileInput = ref<HTMLInputElement>();

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement;
  if (target.files?.[0]) selectedFile.value = target.files[0];
}

function handleDrop(e: DragEvent) {
  const file = e.dataTransfer?.files[0];
  if (file?.type === 'application/pdf') selectedFile.value = file;
}

watch(currentResult, (result) => {
  if (result?.filename && currentPDFFile.value) {
    pdfUrl.value = URL.createObjectURL(currentPDFFile.value);
  }
});

onUnmounted(() => {
  if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value);
});

async function submit() {
  if (!selectedFile.value) return;
  isSubmitting.value = true;
  try {
    const response = await submitValidation(selectedFile.value, searchMode.value);
    await startPolling(response.task_id, response.filename, selectedFile.value);
  } catch (e: any) {
    pageState.value = 'error';
    errorMessage.value = e?.message || '上传失败';
  } finally {
    isSubmitting.value = false;
  }
}
</script>
