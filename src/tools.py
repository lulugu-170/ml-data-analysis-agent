"""工具层：把数据能力封装为 Agent 可调用的 function。

仅使用标准库（sqlite3 + csv），零第三方依赖，便于离线测试。

对外暴露：
- TOOL_SCHEMAS: 供 function calling 的工具定义列表
- dispatch(name, args): 按工具名执行并返回字符串结果
"""
import csv
import os
import re
import sqlite3

_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "orders.csv")
_TABLE_NAME = "orders"

# 只读校验：拦截可能修改数据/结构的语句
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|pragma)\b",
    re.IGNORECASE,
)

# 数值列（用于建表时的类型推断）
_NUMERIC_COLS = {"order_id", "user_id", "amount", "is_repurchase"}

_conn = None


def _get_conn():
    """惰性加载 CSV 到内存 SQLite，只做一次。"""
    global _conn
    if _conn is not None:
        return _conn
    if not os.path.exists(_CSV_PATH):
        raise FileNotFoundError("未找到数据集，请先运行: python3 data/generate_data.py")

    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    col_defs = ", ".join(
        '"{}" {}'.format(c, "REAL" if c == "amount" else ("INTEGER" if c in _NUMERIC_COLS else "TEXT"))
        for c in header
    )
    conn = sqlite3.connect(":memory:")
    conn.execute('CREATE TABLE "{}" ({})'.format(_TABLE_NAME, col_defs))
    placeholders = ",".join(["?"] * len(header))
    # 类型转换：数值列转为 int/float
    typed_rows = []
    for r in rows:
        typed = []
        for c, v in zip(header, r):
            if c == "amount":
                typed.append(float(v))
            elif c in _NUMERIC_COLS:
                typed.append(int(v))
            else:
                typed.append(v)
        typed_rows.append(typed)
    conn.executemany(
        'INSERT INTO "{}" VALUES ({})'.format(_TABLE_NAME, placeholders), typed_rows
    )
    conn.commit()
    _conn = conn
    return _conn


def _format_table(columns, rows, max_rows=50):
    """把查询结果格式化为简单的文本表格。"""
    if not rows:
        return "查询成功，但结果为空。"
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]

    cells = [list(columns)] + [[str(v) for v in r] for r in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(columns))]

    def fmt(row):
        return " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(row))

    sep = "-+-".join("-" * w for w in widths)
    lines = [fmt(cells[0]), sep] + [fmt(r) for r in cells[1:]]
    text = "\n".join(lines)
    if truncated:
        text += "\n（结果超过 {} 行，仅显示前 {} 行）".format(max_rows, max_rows)
    return text


def run_sql(query: str) -> str:
    """执行只读 SQL 查询，返回结果表（文本）。"""
    if _FORBIDDEN.search(query):
        return "错误：仅允许只读查询（SELECT），已拦截可能修改数据的语句。"
    try:
        conn = _get_conn()
        cur = conn.execute(query)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
    except Exception as e:  # noqa: BLE001 - 需把错误反馈给模型以便重试
        return "SQL 执行出错: {}".format(e)
    return _format_table(columns, rows)


def list_tables(_: str = "") -> str:
    """返回数据表的字段结构与示例，帮助模型理解数据。"""
    conn = _get_conn()
    schema = conn.execute('PRAGMA table_info("{}")'.format(_TABLE_NAME)).fetchall()
    cols = "\n".join("  - {} ({})".format(row[1], row[2]) for row in schema)
    sample_cur = conn.execute('SELECT * FROM "{}" LIMIT 3'.format(_TABLE_NAME))
    sample_cols = [d[0] for d in sample_cur.description]
    sample = _format_table(sample_cols, sample_cur.fetchall())
    return "表名: {}\n\n字段:\n{}\n\n示例数据:\n{}".format(_TABLE_NAME, cols, sample)


# --- function calling 定义 ---

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "查看数据表的字段结构、类型与示例数据。分析前应先调用此工具了解数据。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "在订单数据表上执行只读 SQL（SQLite 语法）查询并返回结果。"
                "表名为 orders。仅支持 SELECT 查询。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要执行的 SELECT 语句"}
                },
                "required": ["query"],
            },
        },
    },
]

_HANDLERS = {
    "run_sql": lambda args: run_sql(args["query"]),
    "list_tables": lambda args: list_tables(),
}


def dispatch(name: str, args: dict) -> str:
    """按工具名执行，返回结果字符串。"""
    handler = _HANDLERS.get(name)
    if handler is None:
        return "未知工具: {}".format(name)
    return handler(args)
