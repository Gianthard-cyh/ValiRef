export type TaskStatus = 'pending' | 'processing' | 'retrying' | 'completed' | 'failed' | 'failed_permanently';

export type HallucinationType = 'Real' | 'Fabrication' | 'AttributionError' | 'Irrelevance' | 'Counterfactual';

export interface PDFValidationResponse {
  task_id: string;
  status: TaskStatus;
  filename: string;
  message: string;
}

export interface ReferenceResult {
  title: string;
  authors: string[];
  status: string;
  hallucination_type?: HallucinationType;
  confidence: number;
  reasoning: string;
  evidence: string[];
}

export interface PDFValidationResult {
  task_id: string;
  filename: string;
  status: TaskStatus;
  total_references: number;
  validated_count: number;
  real_count: number;
  hallucination_count: number;
  references: ReferenceResult[];
  error_message?: string;
  created_at: string;
  completed_at?: string;
  duration_seconds?: number;
}

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  filename: string;
  progress?: {
    processed: number;
    total: number;
  };
  created_at: string;
  completed_at?: string;
}

export interface TaskHistoryItem {
  task_id: string;
  filename: string;
  status: TaskStatus;
  created_at: string;
  result?: PDFValidationResult;
}
