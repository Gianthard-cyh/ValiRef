import type { ValidationResponse, ValidationResult, TaskStatusResponse } from '~/types/api';

export function useApi() {
  const config = useRuntimeConfig();
  const baseUrl = config.public.apiBaseUrl;

  async function submitValidation(file: File, searchMode: 'local' | 'online' = 'local'): Promise<ValidationResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('search_mode', searchMode);

    return $fetch(`${baseUrl}/validation/submit`, {
      method: 'POST',
      body: formData,
    });
  }

  async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    return $fetch(`${baseUrl}/validation/status/${taskId}`);
  }

  async function getValidationResult(taskId: string): Promise<ValidationResult> {
    return $fetch(`${baseUrl}/validation/result/${taskId}`);
  }

  return {
    submitValidation,
    getTaskStatus,
    getValidationResult,
  };
}
