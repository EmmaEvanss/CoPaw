## Tenant / Source 目录迁移工具

  当前运行时目录按 `tenant_id + source_id` 生成的 canonical scope 隔离：

  ```text
  <encoded-tenant>.<encoded-source>

  例如：

  tenant_id = user-001
  source_id = ruice

  scope_id = dXNlci0wMDE.cnVpY2U

  ### 1. 历史 tenant 目录迁移

  脚本：

  scripts/migrate_tenant_scope_dirs.py

  用于将历史裸租户目录：

  ~/.swe/<tenant-id>/
  ~/.swe.secret/<tenant-id>/

  迁移为当前 scope 目录：

  ~/.swe/<encoded-tenant>.<encoded-source>/
  ~/.swe.secret/<encoded-tenant>.<encoded-source>/

  迁移时会同步修正工作目录内 JSON 文件中引用旧绝对路径的配置，例如：

  - config.json
  - workspaces/default/agent.json

  #### 单租户迁移

  建议先执行预演：

  venv/bin/python scripts/migrate_tenant_scope_dirs.py \
    --tenant-id user-001 \
    --source-id ruice \
    --dry-run

  确认输出无误后执行正式迁移：

  venv/bin/python scripts/migrate_tenant_scope_dirs.py \
    --tenant-id user-001 \
    --source-id ruice

  #### 批量迁移

  同一 source_id 下多个租户可批量迁移：

  venv/bin/python scripts/migrate_tenant_scope_dirs.py \
    --tenant-ids user-001,user-002,user-003 \
    --source-id ruice \
    --dry-run

  正式执行：

  venv/bin/python scripts/migrate_tenant_scope_dirs.py \
    --tenant-ids user-001,user-002,user-003 \
    --source-id ruice

  #### 指定自定义目录

  如果部署环境未使用默认目录，可显式指定根路径：

  venv/bin/python scripts/migrate_tenant_scope_dirs.py \
    --tenant-id user-001 \
    --source-id ruice \
    --working-dir /data/swe \
    --secret-dir /data/swe.secret

  #### 输出示例

  scope_id: dXNlci0wMDE.cnVpY2U
  working: /Users/ops/.swe/user-001 -> /Users/ops/.swe/
  dXNlci0wMDE.cnVpY2U
  secret : /Users/ops/.swe.secret/user-001 -> /Users/ops/.swe.secret/
  dXNlci0wMDE.cnVpY2U
  move working dir: True
  move secret dir : True
  rewritten json files:
    - /Users/ops/.swe/dXNlci0wMDE.cnVpY2U/config.json
    - /Users/ops/.swe/dXNlci0wMDE.cnVpY2U/workspaces/default/agent.json

  #### 注意事项

  - 生产执行前建议先使用 --dry-run
  - 批量模式会先对整批租户执行预检查
  - 只要任一目标 scope 目录已存在，整批迁移会直接拒绝，避免产生半迁移状态
  - default_<source> 是模板目录，不是运行时租户目录，不应通过该脚本迁移
  - 该脚本只迁移显式指定的 tenant，不会自动扫描或猜测目录归属

  ———

  ### 2. Scope ID 反向解析

  脚本：

  scripts/decode_scope_ids.py

  用于将当前 canonical scope ID 反向解析为：

  - tenant_id
  - source_id

  #### 单个解析

  venv/bin/python scripts/decode_scope_ids.py \
    --scope-id dXNlci0wMDE.cnVpY2U

  输出：

  scope_id: dXNlci0wMDE.cnVpY2U
  tenant_id: user-001
  source_id: ruice

  #### 批量解析

  venv/bin/python scripts/decode_scope_ids.py \
    --scope-ids dXNlci0wMDE.cnVpY2U,ZGVmYXVsdA.cnVpY2U

  输出：

  scope_id: dXNlci0wMDE.cnVpY2U
  tenant_id: user-001
  source_id: ruice

  scope_id: ZGVmYXVsdA.cnVpY2U
  tenant_id: default
  source_id: ruice

  #### 注意事项

  - 该脚本只支持当前 canonical scope 格式：

    <encoded-tenant>.<encoded-source>

  - 不支持历史旧格式：

    scope.v1.<encoded-tenant>.<encoded-source>

  ———

  ### 3. 推荐运维流程

  #### 场景：将旧租户目录迁移到某个 source 下

  1. 确认旧目录存在：

     ls ~/.swe/user-001
     ls ~/.swe.secret/user-001

  2. 先执行 dry-run：

     venv/bin/python scripts/migrate_tenant_scope_dirs.py \
       --tenant-id user-001 \
       --source-id ruice \
       --dry-run

  3. 确认目标 scope ID 与目录无误后执行正式迁移：

     venv/bin/python scripts/migrate_tenant_scope_dirs.py \
       --tenant-id user-001 \
       --source-id ruice

  4. 如需核对迁移后的目录归属，可反向解析：

     venv/bin/python scripts/decode_scope_ids.py \
       --scope-id dXNlci0wMDE.cnVpY2U

  5. 最后确认目录结构：

     ls ~/.swe/dXNlci0wMDE.cnVpY2U
     ls ~/.swe.secret/dXNlci0wMDE.cnVpY2U