<template>
  <div
    :class="[
      'border-2 border-dashed rounded-xl p-10 text-center transition-all duration-300 cursor-pointer',
      isDragging
        ? 'border-text dark:border-text-dark bg-surface-secondary dark:bg-surface-dark-secondary'
        : 'border-border dark:border-border-dark hover:border-border-strong dark:hover:border-border-dark-strong',
      file ? 'border-text dark:border-text-dark bg-surface-secondary dark:bg-surface-dark-secondary' : '',
    ]"
    @dragenter.prevent="isDragging = true"
    @dragleave.prevent="isDragging = false"
    @dragover.prevent
    @drop.prevent="handleDrop"
    @click="triggerFileInput"
  >
    <input
      ref="fileInput"
      type="file"
      accept=".pdf"
      class="hidden"
      @change="handleFileSelect"
    >

    <div v-if="!file" class="space-y-4">
      <div class="w-12 h-12 mx-auto rounded-full bg-surface-secondary dark:bg-surface-dark-secondary flex items-center justify-center">
        <span class="i-lucide-cloud-upload w-6 h-6 text-text-tertiary dark:text-text-dark-tertiary" />
      </div>
      <div class="space-y-1">
        <p class="text-body font-medium text-text dark:text-text-dark">拖拽PDF文件到这里</p>
        <p class="text-small text-text-secondary dark:text-text-dark-secondary">或点击选择文件</p>
        <p class="text-caption text-text-muted dark:text-text-dark-tertiary">支持 PDF 格式，最大 50MB</p>
      </div>
    </div>

    <div v-else class="space-y-3">
      <div class="w-12 h-12 mx-auto rounded-full bg-surface-tertiary dark:bg-surface-dark-tertiary flex items-center justify-center">
        <span class="i-lucide-file-check w-6 h-6 text-text dark:text-text-dark" />
      </div>
      <div>
        <p class="text-body font-medium text-text dark:text-text-dark truncate max-w-[280px] mx-auto">{{ file.name }}</p>
        <p class="text-small text-text-secondary dark:text-text-dark-secondary">{{ formatFileSize(file.size) }}</p>
      </div>
      <button
        class="text-small text-text-tertiary dark:text-text-dark-tertiary hover:text-text dark:hover:text-text-dark transition-colors"
        @click.stop="clearFile"
      >
        重新选择
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
const file = defineModel<File | null>('modelValue', { default: null });

const fileInput = ref<HTMLInputElement>();
const isDragging = ref(false);

function triggerFileInput() {
  fileInput.value?.click();
}

function handleDrop(e: DragEvent) {
  isDragging.value = false;
  const droppedFile = e.dataTransfer?.files[0];
  if (droppedFile && validateFile(droppedFile)) {
    file.value = droppedFile;
  }
}

function handleFileSelect(e: Event) {
  const selectedFile = (e.target as HTMLInputElement).files?.[0];
  if (selectedFile && validateFile(selectedFile)) {
    file.value = selectedFile;
  }
}

function validateFile(file: File): boolean {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    alert('请上传PDF文件');
    return false;
  }
  if (file.size > 50 * 1024 * 1024) {
    alert('文件大小不能超过50MB');
    return false;
  }
  return true;
}

function clearFile() {
  file.value = null;
  if (fileInput.value) {
    fileInput.value.value = '';
  }
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
</script>
