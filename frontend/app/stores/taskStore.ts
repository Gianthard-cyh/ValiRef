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

  // SSE
  let eventSource: EventSource | null = null;

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

  // Start SSE connection for real-time updates
  function connectSSE(taskId: string, filename: string) {
    disconnectSSE(); // Close any existing connection
    currentTaskId.value = taskId;
    pageState.value = 'processing';

    const { getTaskStatus, getValidationResult } = useApi();
    const config = useRuntimeConfig();
    const baseURL = config.public.apiBaseUrl || '/api';

    eventSource = new EventSource(`${baseURL}/validation/stream/${taskId}`);

    eventSource.onmessage = async (e) => {
      // Ignore heartbeat
      if (e.data.startsWith(':')) return;

      try {
        const data = JSON.parse(e.data);

        // Update current status
        currentStatus.value = {
          task_id: taskId,
          filename,
          status: data.status,
          stage: data.stage,
          progress: {
            processed: data.processed,
            total: data.total,
          },
          current_title: data.current_title,
          created_at: currentStatus.value?.created_at || new Date().toISOString(),
        };

        // Task completed
        if (data.status === 'completed') {
          disconnectSSE();
          const result = await getValidationResult(taskId);
          currentResult.value = result;
          addToHistory(taskId, filename, 'completed', result);
          pageState.value = 'completed';
        }

        // Task failed
        if (['failed', 'failed_permanently'].includes(data.status)) {
          disconnectSSE();
          const status = await getTaskStatus(taskId);
          errorCode.value = status.error_code;
          errorMessage.value = status.error_code ? undefined : '任务处理失败';
          addToHistory(taskId, filename, data.status, undefined, status.error_code);
          pageState.value = 'error';
        }
      } catch (e) {
        console.error('SSE message parse error:', e);
      }
    };

    eventSource.onerror = () => {
      // Connection error, close and retry after 3 seconds
      disconnectSSE();
      setTimeout(() => {
        if (pageState.value === 'processing' && currentTaskId.value === taskId) {
          connectSSE(taskId, filename);
        }
      }, 3000);
    };
  }

  // Disconnect SSE
  function disconnectSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  // Start polling (deprecated, use SSE instead)
  async function startPolling(taskId: string, filename: string, file?: File) {
    // Use SSE instead of polling
    connectSSE(taskId, filename);

    // Save PDF to IndexedDB if provided
    if (file) {
      currentPDFFile.value = file;
      await savePDF(taskId, filename, file);
    }
  }

  // Stop polling
  function stopPolling() {
    disconnectSSE();
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
