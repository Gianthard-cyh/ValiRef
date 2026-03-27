<template>
  <div class="min-h-[calc(100vh-3.5rem)] flex flex-col items-center px-6">
    <!-- Content container - matches header width -->
    <div class="w-full max-w-5xl bg-surface dark:bg-surface-dark min-h-[calc(100vh-3.5rem)] border-x border-border dark:border-border-dark py-12 relative">
      <div class="px-12">
        <!-- Title -->
        <div class="mb-10 text-center">
          <h1 class="text-display mb-3">
            验证 PDF 引用
          </h1>
          <p class="text-body text-text-secondary dark:text-text-dark-secondary max-w-md mx-auto">
            智能检测学术文献中的引用问题
          </p>
        </div>

        <!-- Detection Types -->
        <div class="mb-10 border border-border dark:border-border-dark overflow-hidden rounded-lg">
          <div class="px-4 py-3 bg-surface-secondary dark:bg-surface-dark-secondary border-b border-border dark:border-border-dark">
            <p class="text-small font-medium">检测类型</p>
          </div>
          <div class="grid grid-cols-2">
            <div class="px-4 py-4 flex items-start gap-3 border-r border-b border-border dark:border-border-dark">
              <span class="i-lucide-x-circle w-4 h-4 text-rose-500 mt-0.5 flex-shrink-0" />
              <div>
                <p class="text-body font-medium">完全虚构</p>
                <p class="text-small text-text-secondary dark:text-text-dark-secondary mt-0.5">引用的论文不存在</p>
              </div>
            </div>
            <div class="px-4 py-4 flex items-start gap-3 border-b border-border dark:border-border-dark">
              <span class="i-lucide-user-x w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
              <div>
                <p class="text-body font-medium">作者错误</p>
                <p class="text-small text-text-secondary dark:text-text-dark-secondary mt-0.5">真实论文但作者不符</p>
              </div>
            </div>
            <div class="px-4 py-4 flex items-start gap-3 border-r border-border dark:border-border-dark">
              <span class="i-lucide-git-compare w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
              <div>
                <p class="text-body font-medium">内容不符</p>
                <p class="text-small text-text-secondary dark:text-text-dark-secondary mt-0.5">引用与论文内容无关</p>
              </div>
            </div>
            <div class="px-4 py-4 flex items-start gap-3">
              <span class="i-lucide-arrow-left-right w-4 h-4 text-violet-500 mt-0.5 flex-shrink-0" />
              <div>
                <p class="text-body font-medium">结论相反</p>
                <p class="text-small text-text-secondary dark:text-text-dark-secondary mt-0.5">论文结论与引用相反</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Upload Zone -->
        <div
          class="border-2 border-dashed rounded-lg p-12 bg-surface dark:bg-surface-dark"
          :class="[
            isDragging || selectedFile
              ? 'border-text dark:border-text-dark bg-surface-secondary dark:bg-surface-dark-secondary'
              : 'border-border dark:border-border-dark',
            pageState === 'error' ? 'border-rose-500' : '',
          ]"
          @dragenter.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @dragover.prevent
          @drop.prevent="handleDrop"
          @click="!selectedFile && fileInput?.click()">

          <div v-if="!selectedFile" class="text-center cursor-pointer">
            <div class="w-14 h-14 mx-auto mb-5 rounded-full bg-surface-secondary dark:bg-surface-dark-secondary border border-border dark:border-border-dark flex items-center justify-center">
              <span class="i-lucide-file-text w-6 h-6 text-text-tertiary dark:text-text-dark-tertiary" />
            </div>
            <div class="space-y-2">
              <p class="text-title">点击或拖放 PDF 文件</p>
              <p class="text-body text-text-secondary dark:text-text-dark-secondary">最大 10MB</p>
            </div>
          </div>

          <div v-else class="text-center">
            <div class="w-14 h-14 mx-auto mb-4 rounded-full bg-surface-tertiary dark:bg-surface-dark-tertiary flex items-center justify-center">
              <span class="i-lucide-file-check w-6 h-6 text-text dark:text-text-dark" />
            </div>
            <p class="text-title truncate max-w-md mx-auto">{{ selectedFile.name }}</p>
            <p class="text-body text-text-secondary dark:text-text-dark-secondary mt-1">{{ formatFileSize(selectedFile.size) }}</p>
            <button
              class="mt-4 text-small text-text-tertiary dark:text-text-dark-tertiary hover:text-text dark:hover:text-text-dark"
              @click.stop="selectedFile = null"
            >
              移除
            </button>
          </div>

          <input ref="fileInput" type="file" accept=".pdf" class="hidden" @change="handleFileSelect">
        </div>

        <!-- Submit -->
        <LineButton
          v-if="selectedFile"
          block
          size="lg"
          class="mt-6"
          :loading="isSubmitting"
          @click="submit">
          {{ isSubmitting ? '上传中...' : '开始验证' }}
        </LineButton>

        <!-- Error -->
        <div v-if="pageState === 'error'" class="mt-6 text-sm text-rose-600 dark:text-rose-400 text-center">
          {{ errorMessage }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const taskStore = useTaskStore();
const { submitValidation } = useApi();

const { pageState, errorMessage } = storeToRefs(taskStore);
const { startPolling } = taskStore;

const selectedFile = ref<File | null>(null);
const searchMode = ref<'local' | 'online'>('local');
const isSubmitting = ref(false);
const fileInput = ref<HTMLInputElement>();
const isDragging = ref(false);

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
  isDragging.value = false;
  const file = e.dataTransfer?.files[0];
  if (file?.type === 'application/pdf') selectedFile.value = file;
}

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
