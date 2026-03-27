<template>
  <div class="relative">
    <button
      class="inline-flex items-center gap-2 px-3 py-2 border border-gray-200 rounded text-sm text-gray-700 hover:border-gray-400 transition-colors"
      @click="isOpen = !isOpen"
    >
      <span class="i-lucide-history w-4 h-4" />
      历史
      <span v-if="taskHistory.length" class="bg-gray-900 text-white text-xs px-1.5 py-0.5 rounded">
        {{ taskHistory.length }}
      </span>
      <span class="i-lucide-chevron-down w-4 h-4" :class="isOpen ? 'rotate-180' : ''" />
    </button>

    <div
      v-if="isOpen"
      class="absolute right-0 top-full mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-lg z-50"
    >
      <div class="p-3 border-b border-gray-200 flex justify-between items-center">
        <span class="font-medium text-gray-900">最近任务</span>
        <button
          v-if="taskHistory.length"
          class="text-xs text-gray-500 hover:text-rose-600"
          @click="clearHistory"
        >
          清空
        </button>
      </div>

      <div v-if="taskHistory.length === 0" class="p-6 text-center text-gray-500 text-sm">
        暂无历史任务
      </div>

      <div v-else class="max-h-80 overflow-y-auto">
        <div
          v-for="task in taskHistory"
          :key="task.task_id"
          class="p-3 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 cursor-pointer transition-colors"
          @click="loadTask(task.task_id)"
        >
          <div class="flex items-center justify-between">
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-900 truncate">
                {{ task.filename }}
              </p>
              <p class="text-xs text-gray-500 mt-0.5">
                {{ formatDate(task.created_at) }}
              </p>
            </div>
            <StatusBadge :status="task.status" />
          </div>
        </div>
      </div>
    </div>

    <!-- Click outside to close -->
    <div
      v-if="isOpen"
      class="fixed inset-0 z-40"
      @click="isOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
const taskStore = useTaskStore();
const { taskHistory, clearHistory, loadFromHistory } = taskStore;

const isOpen = ref(false);

function loadTask(taskId: string) {
  if (loadFromHistory(taskId)) {
    isOpen.value = false;
  } else {
    alert('该任务结果已过期，请重新上传');
  }
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();

  // Less than 1 hour
  if (diff < 3600000) {
    const minutes = Math.floor(diff / 60000);
    return minutes < 1 ? '刚刚' : `${minutes}分钟前`;
  }

  // Less than 24 hours
  if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000);
    return `${hours}小时前`;
  }

  return date.toLocaleDateString('zh-CN');
}
</script>
