export type TaskStatus = 'pending' | 'processing' | 'retrying' | 'completed' | 'failed' | 'failed_permanently';

export type HallucinationType = 'Real' | 'Fabrication' | 'AttributionError' | 'Irrelevance' | 'Counterfactual';

// Error codes from backend
export type ErrorCode =
  | 'pdf_corrupted'
  | 'pdf_no_text'
  | 'pdf_too_short'
  | 'extraction_failed'
  | 'no_references_found'
  | 'validation_timeout'
  | 'search_failed'
  | 'agent_parse_error';

export interface ValidationResponse {
  task_id: string;
  status: TaskStatus;
  filename: string;
  message: string;
}


export interface ReferenceResult {
  title: string;
  authors: string[];
  venue?: string;
  ccf_rank?: string;
  status: string;
  hallucination_type?: HallucinationType;
  confidence: number;
  reasoning: string;
  evidence: string[];
}

export interface ValidationResult {
  task_id: string;
  filename: string;
  status: TaskStatus;
  total_references: number;
  validated_count: number;
  real_count: number;
  hallucination_count: number;
  references: ReferenceResult[];
  error_code?: ErrorCode;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  duration_seconds?: number;
}


export type TaskStage = 'extraction' | 'validation' | 'completed';

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  filename: string;
  error_code?: ErrorCode;
  stage?: TaskStage;
  progress?: {
    processed: number;
    total: number;
  };
  current_title?: string;
  created_at: string;
  completed_at?: string;
}

export interface TaskHistoryItem {
  task_id: string;
  filename: string;
  status: TaskStatus;
  error_code?: ErrorCode;
  created_at: string;
  result?: ValidationResult;
}
