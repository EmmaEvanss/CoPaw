## ADDED Requirements

### Requirement: is_tenant_source 判断方法
系统 SHALL 提供便捷方法判断租户是否属于指定 source。

#### Scenario: 租户属于指定 source
- **WHEN** 调用 `is_tenant_source(tenant_id, "RMASSIST")`
- **AND** 该租户在 `swe_tenant_init_source` 表中存在 `source_id="RMASSIST"` 的记录
- **THEN** SHALL 返回 `True`

#### Scenario: 租户不属于指定 source
- **WHEN** 调用 `is_tenant_source(tenant_id, "RMASSIST")`
- **AND** 该租户在 `swe_tenant_init_source` 表中没有 `source_id="RMASSIST"` 的记录
- **THEN** SHALL 返回 `False`

#### Scenario: 无数据库连接时的兜底
- **WHEN** 调用 `is_tenant_source(tenant_id, "RMASSIST")`
- **AND** `get_tenant_init_source_store()` 返回 `None`（无数据库连接）
- **THEN** SHALL 返回 `False`

### Requirement: CronManager 通知按 source 控制跳转链接
`CronManager._push_task_success_notification` SHALL 根据租户 source_id 决定是否拼接跳转链接。

#### Scenario: RMASSIST 租户包含跳转链接
- **WHEN** 定时任务完成通知推送给 `creator_id` 对应的租户
- **AND** 该租户的 `source_id` 为 `RMASSIST`
- **THEN** 通知 meta 中 SHALL 包含 `link_url` 和 `link_text`

#### Scenario: 非 RMASSIST 租户不包含跳转链接
- **WHEN** 定时任务完成通知推送给 `creator_id` 对应的租户
- **AND** 该租户的 `source_id` 不是 `RMASSIST`
- **THEN** 通知 meta 中 SHALL NOT 包含 `link_url` 和 `link_text`

#### Scenario: 无 source 记录的租户不包含跳转链接
- **WHEN** 定时任务完成通知推送给 `creator_id` 对应的租户
- **AND** 该租户在 `swe_tenant_init_source` 表中无记录
- **THEN** 通知 meta 中 SHALL NOT 包含 `link_url` 和 `link_text`
