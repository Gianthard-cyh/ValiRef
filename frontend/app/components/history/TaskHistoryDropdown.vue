<template>
  <div class="relative">
    <button
      class="inline-flex items-center gap-2 h-8 px-3 border border-border dark:border-border-dark rounded-lg text-small text-text-secondary dark:text-text-dark-secondary hover:border-border-strong dark:hover:border-border-dark-strong hover:text-text dark:hover:text-text-dark transition-all duration-200"
      @click="isOpen = !isOpen"
    >
      <span class="i-lucide-history w-4 h-4" />
      历史
      <span
        v-if="taskHistory.length"
        class="bg-text dark:bg-text-dark text-surface dark:text-surface-dark text-caption px-1.5 py-0.5 rounded-md font-medium"
      >
        {{ taskHistory.length }}
      </span>
      <span
        class="i-lucide-chevron-down w-4 h-4 transition-transform duration-200"
        :class="isOpen ? 'rotate-180' : ''"
      />
    </button>

    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-1 scale-95"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0 scale-100"
      leave-to-class="opacity-0 translate-y-1 scale-95"
    >
      <div
        v-if="isOpen"
        class="absolute right-0 top-full mt-2 w-80 bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-xl shadow-lg dark:shadow-surface-dark/50 z-50 overflow-hidden"
      >
        <div class="p-3 border-b border-border dark:border-border-dark flex justify-between items-center">
          <span class="font-medium text-text dark:text-text-dark text-small">最近任务</span>
          <button
            v-if="taskHistory.length"
            class="text-caption text-text-tertiary dark:text-text-dark-tertiary hover:text-rose-600 dark:hover:text-rose-400 transition-colors"
            @click="clearHistory"
          >
            清空
          </button>
        </div>

        <div v-if="taskHistory.length === 0" class="p-6 text-center text-text-secondary dark:text-text-dark-secondary text-small">
          暂无历史任务
        </div>

        <div v-else class="max-h-80 overflow-y-auto">
          <div
            v-for="task in taskHistory"
            :key="task.task_id"
            class="p-3 border-b border-border-subtle dark:border-border-dark-subtle last:border-b-0 hover:bg-surface-secondary dark:hover:bg-surface-dark-secondary cursor-pointer transition-colors duration-200"
            @click="loadTask(task.task_id)"
          >
            <div class="flex items-center justify-between gap-3">
              <div class="flex-1 min-w-0">
                <p class="text-small font-medium text-text dark:text-text-dark truncate">
                  {{ task.filename }}
                </p>
                <p class="text-caption text-text-secondary dark:text-text-dark-secondary mt-0.5">
                  {{ formatDate(task.created_at) }}
                </p>
              </div>
              <StatusBadge :status="task.status" />
            </div>
          </div>
        </div>
      </div>
    </Transition>

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

async function loadTask(taskId: string) {
  const result = await loadFromHistory(taskId);
  if (result) {
    isOpen.value = false;
  } else {
    alert('无法加载该任务，请重新上传');
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
