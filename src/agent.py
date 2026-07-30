"""Agent 主循环：基于 OpenAI 兼容的 function calling 实现。

流程：
  用户提问 -> 模型决定是否调用工具 -> 执行工具 -> 结果回灌 -> 直到模型给出最终答案
"""
import json
import os

from openai import OpenAI

import knowledge
import tools

SYSTEM_PROMPT = (
    "你是一个数据分析助手。你可以通过工具查询一张电商订单表来回答用户的分析问题。\n"
    "工作方式：\n"
    "1. 如果还不了解数据结构，先调用 list_tables。\n"
    "2. 写 SQL 前，先想清楚用户要的指标口径：'数量'用 COUNT(*)，'金额/GMV'用 SUM(amount)，"
    "'客单价'用 AVG(amount)——务必区分【数量】与【金额】，不要混淆。\n"
    "3. 根据问题编写 SQL，调用 run_sql 获取数据。可以多次查询、逐步推进。\n"
    "4. 给出最终答案前，自检：我的 SQL 统计的口径是否真的匹配用户问的指标？若不匹配则重写。\n"
    "5. 用中文给出清晰、可解释的结论；涉及数字要说明口径。\n"
    "注意：只能做只读查询；如果 SQL 报错，阅读错误信息并修正后重试。"
)

MAX_STEPS = 8


def build_system_prompt(question):
    """在基础 prompt 上，检索相关数据字典条目并注入（RAG）。"""
    entries = knowledge.retrieve(question, k=3)
    kb = knowledge.format_entries(entries)
    if not kb:
        return SYSTEM_PROMPT
    return SYSTEM_PROMPT + "\n\n相关数据字典（参考口径，帮助你写对 SQL）：\n" + kb


class Agent:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        )
        self.model = os.environ.get("MODEL", "gpt-4o-mini")

    def run(self, question: str, verbose: bool = True) -> str:
        """返回最终答案文本（供 CLI 使用）。"""
        return self.run_with_trace(question, verbose)["answer"]

    def run_with_trace(self, question: str, verbose: bool = True) -> dict:
        """执行并返回 {answer, steps, tool_calls}。

        tool_calls: 每个工具调用的 {name, args, ok}，ok 表示工具是否成功执行。
        供评测统计工具调用成功率、步数等指标。
        """
        messages = [
            {"role": "system", "content": build_system_prompt(question)},
            {"role": "user", "content": question},
        ]
        trace = []

        for step in range(1, MAX_STEPS + 1):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools.TOOL_SCHEMAS,
                tool_choice="auto",
            )
            msg = resp.choices[0].message

            # 没有工具调用 -> 最终答案
            if not msg.tool_calls:
                return {"answer": msg.content or "", "steps": step, "tool_calls": trace}

            # 记录本轮 assistant 消息（含 tool_calls）
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )

            # 逐个执行工具调用
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if verbose:
                    print("  [工具] {} <- {}".format(name, args))
                result = tools.dispatch(name, args)
                ok = not result.startswith(("SQL 执行出错", "错误：", "未知工具"))
                trace.append({"name": name, "args": args, "ok": ok})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

        return {
            "answer": "已达到最大步数，未能得出最终结论。",
            "steps": MAX_STEPS,
            "tool_calls": trace,
        }
