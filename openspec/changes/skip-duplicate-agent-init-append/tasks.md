## 1. Router And File Write Semantics

- [x] 1.1 在 `AgentMdManager.append_working_md()` 中加入文件尾部精确匹配判断，仅在尾部不一致时执行追加
- [x] 1.2 保持 `src/swe/app/routers/agent.py` 的 `/api/agent/init` 请求校验与成功响应链路兼容新的幂等追加语义

## 2. Verification

- [x] 2.1 在 `tests/unit/routers/test_agent_init.py` 新增“尾部一致时跳过追加”的测试
- [x] 2.2 补充或更新“尾部不一致时继续追加”的测试，确认现有行为未回归
- [x] 2.3 运行目标测试文件，确认 `/api/agent/init` 的新增语义通过验证
