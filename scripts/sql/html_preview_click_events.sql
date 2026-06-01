CREATE TABLE IF NOT EXISTS swe_html_preview_click_events (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,

  source_id VARCHAR(64) NULL COMMENT '来源标识',
  user_id VARCHAR(128) NULL COMMENT '点击用户标识',
  bbk_id VARCHAR(128) NULL COMMENT '分行/机构标识，预留给运营看板筛选',

  cron_task_id VARCHAR(128) NULL COMMENT '定时任务ID',
  cron_task_name VARCHAR(255) NULL COMMENT '定时任务名称',

  file_url TEXT NOT NULL COMMENT 'HTML 文件链接',
  file_name VARCHAR(512) NULL COMMENT 'HTML 文件名',

  button_id VARCHAR(255) NULL COMMENT '按钮稳定标识',
  button_name VARCHAR(255) NULL COMMENT '按钮展示名称',
  button_text VARCHAR(512) NULL COMMENT '按钮文本兜底',

  clicked_at DATETIME NOT NULL COMMENT '前端点击时间',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',

  INDEX idx_clicked_at (clicked_at),
  INDEX idx_task_clicked (cron_task_id, clicked_at),
  INDEX idx_button_clicked (button_id, clicked_at),
  INDEX idx_bbk_clicked (bbk_id, clicked_at),
  INDEX idx_source_clicked (source_id, clicked_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='HTML 预览按钮点击明细';
