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
  const currentPDFFile = ref<File | null>(null);

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
  async function loadFromHistory(taskId: string): Promise<'completed' | 'processing' | 'failed' | null> {
    const item = taskHistory.value.find(t => t.task_id === taskId);
    if (!item) return null;

    // Load PDF from IndexedDB
    const pdfFile = await loadPDF(taskId);
    if (pdfFile) {
      currentPDFFile.value = pdfFile;
    }

    // If task failed in history, show error
    if (['failed', 'failed_permanently'].includes(item.status)) {
      pageState.value = 'error';
      errorMessage.value = '任务处理失败';
      return 'failed';
    }

    // If has result and not failed, show completed page
    if (item.result) {
      currentTaskId.value = taskId;
      currentResult.value = item.result;
      currentStatus.value = {
        task_id: taskId,
        filename: item.filename,
        status: 'completed',
        created_at: item.created_at,
      };
      pageState.value = 'completed';
      return 'completed';
    }

    // Check current status from API
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

      // Task completed but no result in history (should fetch result)
      if (status.status === 'completed') {
        const result = await getValidationResult(taskId);
        currentResult.value = result;
        addToHistory(taskId, item.filename, 'completed', result);
        pageState.value = 'completed';
        return 'completed';
      }

      // Task failed
      if (['failed', 'failed_permanently'].includes(status.status)) {
        addToHistory(taskId, item.filename, status.status);
        pageState.value = 'error';
        errorMessage.value = '任务处理失败';
        return 'failed';
      }
    } catch (e) {
      console.error('Failed to load task status:', e);
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
          addToHistory(taskId, filename, status.status);
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

  return {
    pageState,
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
    reset,
  };
});
