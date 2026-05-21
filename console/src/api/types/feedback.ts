export interface FeedbackSubmitPayload {
  id?: number | null;
  feedback_content: string;
  feedback_options?: string[];

  response_id?: string | null;
  trace_id?: string | null;
  chat_id?: string | null;
  session_id?: string | null;
  cron_task_name?: string | null;
  cron_task_id?: string | null;
  feedback_user_name?: string | null;
  feedback_user_sap?: string | null;
  feedback_branch?: string | null;
  feedback_sub_branch?: string | null;
  feedback_position?: string | null;
}

export interface FeedbackRecord {
  id: number;
  source_id?: string | null;
  feedback_content: string;
  feedback_options: string[];
  response_id?: string | null;
  trace_id?: string | null;
  chat_id?: string | null;
  session_id?: string | null;
  cron_task_name?: string | null;
  cron_task_id?: string | null;
  feedback_user_name?: string | null;
  feedback_user_sap?: string | null;
  feedback_branch?: string | null;
  feedback_sub_branch?: string | null;
  feedback_position?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface FeedbackLookupResponse {
  success: boolean;
  feedback?: FeedbackRecord | null;
}

export interface FeedbackSessionLookupResponse {
  success: boolean;
  items: FeedbackRecord[];
}

export interface FeedbackSubmitResponse {
  success: boolean;
  feedback_id?: number | null;
  updated?: boolean;
  trace_id?: string | null;
}
