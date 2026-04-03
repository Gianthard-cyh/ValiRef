import type { TaskHistoryItem, PDFValidationResult, TaskStatusResponse, TaskStatus, ErrorCode } from '~/types/api';

export type PageState = 'idle' | 'uploading' | 'processing' | 'completed' | 'error';

const HISTORY_KEY = 'valiref-task-history';
const MAX_HISTORY = 10;

export const useTaskStore = defineStore('task', () => {
  // Page state
  const pageState = ref<PageState>('idle');
  const errorCode = ref<ErrorCode | undefined>(undefined);
  const errorMessage = ref('');

  // Current task
  const currentTaskId = ref<string>('');
  const currentStatus = ref<TaskStatusResponse | null>(null);
  const currentResult = ref<PDFValidationResult | null>(null);
  const currentPDFFile = ref<File | null>(null);

  // History
  const taskHistory = ref<TaskHistoryItem[]>([]);

  // Polling
  let pollingInterval: ReturnType<typeof setTimeout> | null = null;

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

  // Refresh processing tasks on init
  async function refreshProcessingTasks() {
    const processingTasks = taskHistory.value.filter(t =>
      ['pending', 'processing', 'retrying'].includes(t.status)
    );

    if (processingTasks.length === 0) return;

    const { getTaskStatus, getValidationResult } = useApi();

    for (const task of processingTasks) {
      try {
        const status = await getTaskStatus(task.task_id);

        // Task completed - fetch result and update
        if (status.status === 'completed') {
          const result = await getValidationResult(task.task_id);
          addToHistory(task.task_id, task.filename, 'completed', result);
          continue;
        }

        // Task failed - update status with error code
        if (['failed', 'failed_permanently'].includes(status.status)) {
          addToHistory(task.task_id, task.filename, status.status, undefined, status.error_code);
          continue;
        }

        // Still processing - status already matches, no update needed
      } catch (e) {
        console.error(`Failed to refresh task ${task.task_id}:`, e);
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
  function addToHistory(taskId: string, filename: string, status: TaskStatus, result?: PDFValidationResult, errorCodeFromStatus?: ErrorCode) {
    const existingIndex = taskHistory.value.findIndex(t => t.task_id === taskId);
    const item: TaskHistoryItem = {
      task_id: taskId,
      filename,
      status,
      created_at: new Date().toISOString(),
      result,
      error_code: errorCodeFromStatus,
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

  // Load result from history - always fetch latest from API
  async function loadFromHistory(taskId: string): Promise<'completed' | 'processing' | 'failed' | null> {
    const item = taskHistory.value.find(t => t.task_id === taskId);
    if (!item) return null;

    // Load PDF from IndexedDB
    const pdfFile = await loadPDF(taskId);
    if (pdfFile) {
      currentPDFFile.value = pdfFile;
    }

    // Always fetch latest status from API
    try {
      const { getTaskStatus, getValidationResult } = useApi();
      const status = await getTaskStatus(taskId);

      currentTaskId.value = taskId;
      currentStatus.value = {
        task_id: taskId,
        filename: item.filename,
        status: status.status,
        created_at: item.created_at,
      };

      // Task still processing
      if (['pending', 'processing', 'retrying'].includes(status.status)) {
        pageState.value = 'processing';
        // Start polling
        startPolling(taskId, item.filename);
        return 'processing';
      }

      // Task completed - fetch result and update history
      if (status.status === 'completed') {
        const result = await getValidationResult(taskId);
        currentResult.value = result;
        addToHistory(taskId, item.filename, 'completed', result);
        pageState.value = 'completed';
        return 'completed';
      }

      // Task failed - capture error_code from API
      if (['failed', 'failed_permanently'].includes(status.status)) {
        addToHistory(taskId, item.filename, status.status, undefined, status.error_code);
        pageState.value = 'error';
        errorCode.value = status.error_code;
        errorMessage.value = status.error_code ? undefined : '任务处理失败';
        return 'failed';
      }
    } catch (e) {
      console.error('Failed to load task status:', e);
      // Fallback to cached data if API fails
      if (item.result) {
        currentResult.value = item.result;
        pageState.value = 'completed';
        return 'completed';
      }
      if (['failed', 'failed_permanently'].includes(item.status)) {
        pageState.value = 'error';
        errorCode.value = item.error_code;
        errorMessage.value = item.result?.error_message || '任务处理失败';
        return 'failed';
      }
      return null;
    }

    return null;
  }

  // Start polling task status
  async function startPolling(taskId: string, filename: string, file?: File) {
    stopPolling();
    currentTaskId.value = taskId;
    pageState.value = 'processing';

    // Save PDF to IndexedDB if provided
    if (file) {
      currentPDFFile.value = file;
      await savePDF(taskId, filename, file);
    }

    const { getTaskStatus, getValidationResult } = useApi();
    let pollDelay = 2000; // Start with 2 seconds

    const poll = async () => {
      try {
        const status = await getTaskStatus(taskId);
        currentStatus.value = status;

        // Task completed
        if (status.status === 'completed') {
          const result = await getValidationResult(taskId);
          currentResult.value = result;
          addToHistory(taskId, filename, 'completed', result);
          pageState.value = 'completed';
          return; // Stop polling
        }

        // Task failed - capture error_code
        if (['failed', 'failed_permanently'].includes(status.status)) {
          pageState.value = 'error';
          errorCode.value = status.error_code;
          errorMessage.value = status.error_code ? undefined : '任务处理失败';
          addToHistory(taskId, filename, status.status, undefined, status.error_code);
          return; // Stop polling
        }

        // Still processing - continue polling with exponential backoff (max 30s)
        pollDelay = Math.min(pollDelay * 1.5, 30000);
        pollingInterval = setTimeout(poll, pollDelay);
      } catch (e) {
        console.error('Polling error:', e);
        // Retry on error with same delay
        pollingInterval = setTimeout(poll, pollDelay);
      }
    };

    // Start first poll
    pollingInterval = setTimeout(poll, pollDelay);
  }

  // Stop polling
  function stopPolling() {
    if (pollingInterval) {
      clearTimeout(pollingInterval);
      pollingInterval = null;
    }
  }

  // Reset state
  function reset() {
    stopPolling();
    pageState.value = 'idle';
    errorCode.value = undefined;
    errorMessage.value = '';
    currentTaskId.value = '';
    currentStatus.value = null;
    currentResult.value = null;
    currentPDFFile.value = null;
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
  refreshProcessingTasks();

  return {
    pageState,
    errorCode,
    errorMessage,
    currentTaskId,
    currentStatus,
    currentResult,
    currentPDFFile,
    taskHistory,
    progress,
    isProcessing,
    addToHistory,
    clearHistory,
    loadFromHistory,
    startPolling,
    stopPolling,
    refreshProcessingTasks,
    reset,
  };
});
