export interface HtmlPreviewClickEventPayload {
  source_id?: string | null;
  user_id?: string | null;
  bbk_id?: string | null;
  cron_task_id?: string | null;
  cron_task_name?: string | null;
  file_url: string;
  file_name?: string | null;
  button_id?: string | null;
  button_name?: string | null;
  button_text?: string | null;
  clicked_at?: string | null;
}

export interface HtmlPreviewClickSubmitResponse {
  success: boolean;
}

export interface HtmlPreviewClickSummaryItem {
  button_label: string;
  button_id?: string | null;
  button_name?: string | null;
  button_text?: string | null;
  bbk_id?: string | null;
  cron_task_id?: string | null;
  cron_task_name?: string | null;
  file_url?: string | null;
  file_name?: string | null;
  click_count: number;
  last_clicked_at?: string | null;
}

export interface HtmlPreviewClickSummaryResponse {
  success: boolean;
  items: HtmlPreviewClickSummaryItem[];
}
