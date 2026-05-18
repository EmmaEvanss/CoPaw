# -*- coding: utf-8 -*-
"""生成 Business Overview 页面测试数据.

用于填充 swe_tracing_traces 和 swe_tracing_spans 表，
验证 Business Overview 页面的 UI 展示。

使用方法：
    python scripts/generate_business_overview_test_data.py
"""

import asyncio
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# 加载用户配置的环境变量（从 ~/.swe.secret/envs.json）
from swe.envs import load_envs_into_environ
load_envs_into_environ()

from swe.database import get_database_config, DatabaseConnection


# 测试数据配置
SOURCE_IDS = [
    "CMSJY",      # 远程RM助手Claw
    "UPPCLAW",    # 智像助手CLAW
    "copilotClaw", # 数据赋能助手CLAW
    "ruice",      # 睿策助手Claw
    "privatebanking", # 私行助手Claw
    "SZLS",       # 数智零售Claw
]

BBK_IDS = [
    ("010", "北京分行"),
    ("020", "天津分行"),
    ("030", "河北分行"),
    ("040", "山西分行"),
    ("050", "内蒙古分行"),
    ("110", "辽宁分行"),
    ("120", "吉林分行"),
    ("130", "黑龙江分行"),
    ("210", "上海分行"),
    ("220", "江苏分行"),
    ("230", "浙江分行"),
    ("240", "安徽分行"),
    ("250", "福建分行"),
    ("310", "山东分行"),
    ("320", "河南分行"),
    ("330", "湖北分行"),
    ("340", "湖南分行"),
    ("350", "广东分行"),
    ("360", "广西分行"),
    ("410", "四川分行"),
    ("420", "重庆分行"),
    ("430", "贵州分行"),
    ("440", "云南分行"),
    ("510", "陕西分行"),
]

SKILLS = [
    "数据查询",
    "报表生成",
    "客户分析",
    "风险评估",
    "智能问答",
    "文档处理",
    "流程审批",
    "邮件生成",
    "数据导出",
    "图表绘制",
]

MCP_SERVERS = [
    ("mysql_reader", ["query_table", "execute_sql", "get_schema"]),
    ("excel_writer", ["write_sheet", "format_cells", "save_file"]),
    ("web_search", ["search", "get_page", "extract_content"]),
    ("email_sender", ["send_email", "create_draft", "schedule_send"]),
    ("chart_generator", ["create_chart", "export_image", "set_style"]),
    ("pdf_processor", ["extract_text", "merge_files", "convert_to_image"]),
]

# 生成随机用户数据
def generate_users(count: int) -> list[dict]:
    """生成随机用户列表."""
    users = []
    for i in range(count):
        user_id = f"user_{random.randint(10000, 99999)}"
        user_name = f"张{i + 1}" if random.random() > 0.3 else f"王{i + 1}"
        bbk_code, bbk_name = random.choice(BBK_IDS)
        users.append({
            "user_id": user_id,
            "user_name": user_name,
            "bbk_id": bbk_code,
            "bbk_name": bbk_name,
        })
    return users


def generate_test_data(
    days: int = 7,
    traces_per_day: int = 50,
    users_count: int = 30,
) -> tuple[list[dict], list[dict]]:
    """生成测试数据.

    Args:
        days: 生成多少天的数据
        traces_per_day: 每天生成多少条 trace
        users_count: 用户数量

    Returns:
        (traces, spans) 元组
    """
    users = generate_users(users_count)
    traces = []
    spans = []

    now = datetime.now()

    for day_offset in range(days):
        day_date = now - timedelta(days=day_offset)

        for _ in range(traces_per_day):
            source_id = random.choice(SOURCE_IDS)
            user = random.choice(users)
            user_id = user["user_id"]
            user_name = user["user_name"]
            bbk_id = user["bbk_id"]

            # 生成时间
            hour = random.randint(8, 18)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            start_time = day_date.replace(
                hour=hour, minute=minute, second=second, microsecond=0
            )

            # 生成 trace_id 和 session_id
            trace_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())

            # 生成持续时间
            duration_ms = random.randint(500, 30000)

            # 生成 token 数
            input_tokens = random.randint(100, 2000)
            output_tokens = random.randint(50, 1500)
            total_tokens = input_tokens + output_tokens

            # 生成技能和工具使用
            skills_used = random.sample(SKILLS, k=random.randint(1, 3))
            tools_used = []
            for server_name, tool_names in random.sample(
                MCP_SERVERS, k=random.randint(1, 2)
            ):
                tools_used.extend(random.sample(tool_names, k=random.randint(1, 2)))

            # 决定状态
            status = random.choices(
                ["completed", "error", "running"],
                weights=[85, 10, 5],
            )[0]

            # 用户消息
            user_message = random.choice([
                "帮我查询本月销售数据",
                "生成客户分析报告",
                "分析这个客户的风险等级",
                "查询账户余额",
                "导出上周的交易明细",
                "帮我写一封客户回访邮件",
                "审批这个流程",
            ])

            # 创建 trace
            trace = {
                "trace_id": trace_id,
                "source_id": source_id,
                "user_id": user_id,
                "user_name": user_name,
                "bbk_id": bbk_id,
                "session_id": session_id,
                "channel": random.choice(["console", "webhook", "api"]),
                "start_time": start_time,
                "end_time": start_time + timedelta(milliseconds=duration_ms),
                "duration_ms": duration_ms,
                "model_name": random.choice([
                    "claude-3-opus",
                    "claude-3-sonnet",
                    "gpt-4",
                    "gpt-3.5-turbo",
                ]),
                "total_input_tokens": input_tokens,
                "total_output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "tools_used": json.dumps(tools_used),
                "skills_used": json.dumps(skills_used),
                "status": status,
                "error": None if status == "completed" else "模拟错误",
                "user_message": user_message,
            }
            traces.append(trace)

            # 为每个技能创建 skill_invocation span
            span_start = start_time
            for skill_name in skills_used:
                skill_duration = random.randint(100, 5000)
                skill_span_id = str(uuid.uuid4())

                span = {
                    "span_id": skill_span_id,
                    "trace_id": trace_id,
                    "source_id": source_id,
                    "name": skill_name,
                    "event_type": "skill_invocation",
                    "start_time": span_start,
                    "end_time": span_start + timedelta(milliseconds=skill_duration),
                    "duration_ms": skill_duration,
                    "user_id": user_id,
                    "user_name": user_name,
                    "bbk_id": bbk_id,
                    "session_id": session_id,
                    "channel": trace["channel"],
                    "skill_name": skill_name,
                    "mcp_server": None,
                    "tool_name": None,
                }
                spans.append(span)

                # 为该技能创建工具调用 spans
                for server_name, tool_names in MCP_SERVERS:
                    if random.random() > 0.6:
                        continue
                    tool_name = random.choice(tool_names)
                    tool_duration = random.randint(50, 2000)
                    tool_span_id = str(uuid.uuid4())

                    tool_span = {
                        "span_id": tool_span_id,
                        "trace_id": trace_id,
                        "source_id": source_id,
                        "name": tool_name,
                        "event_type": "tool_call_end",
                        "start_time": span_start + timedelta(milliseconds=100),
                        "end_time": span_start + timedelta(milliseconds=100 + tool_duration),
                        "duration_ms": tool_duration,
                        "user_id": user_id,
                        "user_name": user_name,
                        "bbk_id": bbk_id,
                        "session_id": session_id,
                        "channel": trace["channel"],
                        "skill_name": skill_name,
                        "mcp_server": server_name,
                        "tool_name": tool_name,
                    }
                    spans.append(tool_span)

                span_start += timedelta(milliseconds=skill_duration + 100)

            # 创建 LLM 调用 spans
            llm_span_id = str(uuid.uuid4())
            llm_duration = random.randint(500, 5000)
            llm_span = {
                "span_id": llm_span_id,
                "trace_id": trace_id,
                "source_id": source_id,
                "name": "llm_call",
                "event_type": "llm_output",
                "start_time": span_start,
                "end_time": span_start + timedelta(milliseconds=llm_duration),
                "duration_ms": llm_duration,
                "user_id": user_id,
                "user_name": user_name,
                "bbk_id": bbk_id,
                "session_id": session_id,
                "channel": trace["channel"],
                "model_name": trace["model_name"],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "skill_name": None,
                "mcp_server": None,
                "tool_name": None,
            }
            spans.append(llm_span)

    return traces, spans


async def insert_traces(db: DatabaseConnection, traces: list[dict]) -> int:
    """批量插入 traces."""
    query = """
        INSERT INTO swe_tracing_traces (
            trace_id, source_id, user_id, user_name, bbk_id,
            session_id, channel, start_time, end_time,
            duration_ms, model_name, total_input_tokens, total_output_tokens,
            total_tokens, tools_used, skills_used, status, error, user_message
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    params_list = []
    for trace in traces:
        params_list.append(
            (
                trace["trace_id"],
                trace["source_id"],
                trace["user_id"],
                trace["user_name"],
                trace["bbk_id"],
                trace["session_id"],
                trace["channel"],
                trace["start_time"],
                trace["end_time"],
                trace["duration_ms"],
                trace["model_name"],
                trace["total_input_tokens"],
                trace["total_output_tokens"],
                trace["total_tokens"],
                trace["tools_used"],
                trace["skills_used"],
                trace["status"],
                trace["error"],
                trace["user_message"],
            )
        )

    await db.execute_many(query, params_list)
    return len(traces)


async def insert_spans(db: DatabaseConnection, spans: list[dict]) -> int:
    """批量插入 spans."""
    query = """
        INSERT INTO swe_tracing_spans (
            span_id, trace_id, source_id, name, event_type,
            start_time, end_time, duration_ms, user_id, user_name, bbk_id,
            session_id, channel, model_name, input_tokens, output_tokens,
            skill_name, mcp_server, tool_name
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    params_list = []
    for span in spans:
        params_list.append(
            (
                span["span_id"],
                span["trace_id"],
                span["source_id"],
                span["name"],
                span["event_type"],
                span["start_time"],
                span["end_time"],
                span["duration_ms"],
                span["user_id"],
                span["user_name"],
                span["bbk_id"],
                span["session_id"],
                span["channel"],
                span.get("model_name"),
                span.get("input_tokens"),
                span.get("output_tokens"),
                span.get("skill_name"),
                span.get("mcp_server"),
                span.get("tool_name"),
            )
        )

    await db.execute_many(query, params_list)
    return len(spans)


async def main():
    """主函数."""
    # 获取数据库配置
    db_config = get_database_config()
    print(
        f"数据库配置: host={db_config.host}, port={db_config.port}, "
        f"database={db_config.database}, user={db_config.user}"
    )

    # 连接数据库
    db = DatabaseConnection(db_config)
    try:
        await db.connect()
        print(f"数据库连接状态: {db.is_connected}")

        if not db.is_connected:
            print("数据库未连接，请检查配置")
            return

        # 生成测试数据
        print("\n生成测试数据...")
        traces, spans = generate_test_data(
            days=7,
            traces_per_day=100,
            users_count=50,
        )
        print(f"  - traces: {len(traces)} 条")
        print(f"  - spans: {len(spans)} 条")

        # 插入数据
        print("\n插入数据...")
        trace_count = await insert_traces(db, traces)
        print(f"  - 已插入 traces: {trace_count} 条")

        span_count = await insert_spans(db, spans)
        print(f"  - 已插入 spans: {span_count} 条")

        # 验证数据
        print("\n验证数据...")
        trace_check = await db.fetch_one(
            "SELECT COUNT(*) as count FROM swe_tracing_traces"
        )
        span_check = await db.fetch_one(
            "SELECT COUNT(*) as count FROM swe_tracing_spans"
        )
        print(f"  - 数据库中 traces 总数: {trace_check['count']}")
        print(f"  - 数据库中 spans 总数: {span_check['count']}")

        # 查看分行分布
        bbk_query = """
            SELECT bbk_id, COUNT(*) as count
            FROM swe_tracing_traces
            WHERE bbk_id IS NOT NULL
            GROUP BY bbk_id
            ORDER BY count DESC
            LIMIT 10
        """
        bbk_rows = await db.fetch_all(bbk_query)
        print("\n  Top 10 分行分布:")
        for row in bbk_rows:
            bbk_name = next(
                (name for code, name in BBK_IDS if code == row["bbk_id"]),
                row["bbk_id"]
            )
            print(f"    - {bbk_name}: {row['count']} 次")

        # 查看技能分布
        skill_query = """
            SELECT skill_name, COUNT(*) as count
            FROM swe_tracing_spans
            WHERE event_type = 'skill_invocation' AND skill_name IS NOT NULL
            GROUP BY skill_name
            ORDER BY count DESC
            LIMIT 10
        """
        skill_rows = await db.fetch_all(skill_query)
        print("\n  Top 10 技能调用:")
        for row in skill_rows:
            print(f"    - {row['skill_name']}: {row['count']} 次")

        # 查看 MCP 服务器分布
        mcp_query = """
            SELECT mcp_server, COUNT(*) as count
            FROM swe_tracing_spans
            WHERE mcp_server IS NOT NULL AND mcp_server != ''
            GROUP BY mcp_server
            ORDER BY count DESC
            LIMIT 10
        """
        mcp_rows = await db.fetch_all(mcp_query)
        print("\n  Top 10 MCP 服务器调用:")
        for row in mcp_rows:
            print(f"    - {row['mcp_server']}: {row['count']} 次")

        print("\n测试数据生成完成！")

    except Exception as e:
        print(f"操作失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())