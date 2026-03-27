import type { TaskHistoryItem, PDFValidationResult, TaskStatusResponse, TaskStatus } from '~/types/api';

export type PageState = 'idle' | 'uploading' | 'processing' | 'completed' | 'error';

const HISTORY_KEY = 'valiref-task-history';
const MAX_HISTORY = 10;

export const useTaskStore = defineStore('task', () => {
  // Page state
  const pageState = ref<PageState>('idle');
  const errorMessage = ref('');

  // Current task
  const currentTaskId = ref<string>('');
  const currentStatus = ref<TaskStatusResponse | null>(null);
  const currentResult = ref<PDFValidationResult | null>(null);

  // History
  const taskHistory = ref<TaskHistoryItem[]>([]);

  // Polling
  let pollingInterval: ReturnType<typeof setInterval> | null = null;

  // Load history from localStorage
  function loadHistory() {
    if (process.client) {
      const saved = localStorage.getItem(HISTORY_KEY);
      if (saved) {
        try {
          taskHistory.value = JSON.parse(saved);
        } catch {
          taskHistory.value = [];
        }
      }
    }
  }

  // Save history to localStorage
  function saveHistory() {
    if (process.client) {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(taskHistory.value));
    }
  }

  // Add task to history
  function addToHistory(taskId: string, filename: string, status: TaskStatus, result?: PDFValidationResult) {
    const existingIndex = taskHistory.value.findIndex(t => t.task_id === taskId);
    const item: TaskHistoryItem = {
      task_id: taskId,
      filename,
      status,
      created_at: new Date().toISOString(),
      result,
    };

    if (existingIndex >= 0) {
      taskHistory.value[existingIndex] = item;
    } else {
      taskHistory.value.unshift(item);
      if (taskHistory.value.length > MAX_HISTORY) {
        taskHistory.value = taskHistory.value.slice(0, MAX_HISTORY);
      }
    }
    saveHistory();
  }

  // Clear history
  function clearHistory() {
    taskHistory.value = [];
    saveHistory();
  }

  // Load result from history
  function loadFromHistory(taskId: string): boolean {
    const item = taskHistory.value.find(t => t.task_id === taskId);
    if (item?.result) {
      currentTaskId.value = taskId;
      currentResult.value = item.result;
      currentStatus.value = {
        task_id: taskId,
        filename: item.filename,
        status: item.status,
        created_at: item.created_at,
      };
      pageState.value = 'completed';
      return true;
    }
    return false;
  }

  // Start polling task status
  async function startPolling(taskId: string, filename: string) {
    stopPolling();
    currentTaskId.value = taskId;
    pageState.value = 'processing';

    const { getTaskStatus, getValidationResult } = useApi();

    pollingInterval = setInterval(async () => {
      try {
        const status = await getTaskStatus(taskId);
        currentStatus.value = status;

        // Update history
        addToHistory(taskId, filename, status.status);

        // Task completed
        if (status.status === 'completed') {
          const result = await getValidationResult(taskId);
          currentResult.value = result;
          addToHistory(taskId, filename, 'completed', result);
          pageState.value = 'completed';
          stopPolling();
        }

        // Task failed
        if (['failed', 'failed_permanently'].includes(status.status)) {
          pageState.value = 'error';
          errorMessage.value = '任务处理失败';
          stopPolling();
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 2000);
  }

  // Stop polling
  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }

  // Reset state
  function reset() {
    stopPolling();
    pageState.value = 'idle';
    errorMessage.value = '';
    currentTaskId.value = '';
    currentStatus.value = null;
    currentResult.value = null;
  }

  // Computed
  const progress = computed(() => {
    if (!currentStatus.value?.progress) return 0;
    const { processed, total } = currentStatus.value.progress;
    return total > 0 ? Math.round((processed / total) * 100) : 0;
  });

  const isProcessing = computed(() => pageState.value === 'processing');

  // Load history on init
  loadHistory();

  return {
    pageState,
    errorMessage,
    currentTaskId,
    currentStatus,
    currentResult,
    taskHistory,
    progress,
    isProcessing,
    addToHistory,
    clearHistory,
    loadFromHistory,
    startPolling,
    stopPolling,
    reset,
  };
});
