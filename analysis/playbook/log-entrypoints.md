# 日志入口

本文档记录运行时问题最常用的日志与快照入口。

## 运行时日志主入口

当前运行时日志以进程 `stdout/stderr` 为主入口。默认情况下，运维排查应优先查看容器日志、Supervisor 日志、systemd journal，或直接查看进程标准输出/标准错误。

## `WORKING_DIR/swe.log` 条件

`WORKING_DIR/swe.log` 仅在 `SWE_FILE_LOG_ENABLED=true` 时生成并持续写入。未开启该开关时，不应将 `swe.log` 视为稳定日志来源。

## daemon 日志命令行为

`/daemon logs` 与 `swe daemon logs` 仅在文件日志启用时读取 `swe.log`。当 `SWE_FILE_LOG_ENABLED` 未开启时，这两个入口不会返回运行时日志内容，只会提示运维改为检查容器日志、Supervisor 日志、systemd journal 或进程 `stdout/stderr`。

## query error dump

`query error dump` 仍可作为请求级故障快照入口，用于补充上下文与失败栈信息，但不替代运行时主日志入口。
