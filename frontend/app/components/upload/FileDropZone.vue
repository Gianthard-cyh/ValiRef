<template>
  <div
    :class="[
      'border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer',
      isDragging ? 'border-gray-900 bg-gray-50' : 'border-gray-300 hover:border-gray-400',
      file ? 'bg-gray-50' : '',
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

    <div v-if="!file" class="space-y-2">
      <div class="w-8 h-8 mx-auto text-gray-400 text-2xl">☁</div>
      <p class="text-gray-700">
        拖拽PDF文件到这里
      </p>
      <p class="text-sm text-gray-500">
        或点击选择文件
      </p>
      <p class="text-xs text-gray-400">
        支持 PDF 格式，最大 50MB
      </p>
    </div>

    <div v-else class="space-y-2">
      <div class="w-8 h-8 mx-auto text-gray-600 text-2xl">📄</div>
      <p class="text-gray-900 font-medium">{{ file.name }}</p>
      <p class="text-sm text-gray-500">{{ formatFileSize(file.size) }}</p>
      <button
        class="text-sm text-gray-500 hover:text-gray-900 underline"
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
