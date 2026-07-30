"""效果评测：在测试集上运行 Agent，量化其表现。

指标：
- 工具调用成功率：成功执行的工具调用数 / 总工具调用数
- 结论准确率：最终答案是否命中 ground truth（数值型按容差匹配，类别型按包含匹配）
- 平均步数：完成一个任务平均需要的模型轮次

ground truth 由测试集中的 truth_sql 在同一份数据上实时计算，保证与数据一致。

用法：
  python3 eval/run_eval.py
"""
import json
import os
import re
import sys

# 让 eval 能 import src 下的模块
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, _SRC)

from dotenv import load_dotenv  # noqa: E402

import tools  # noqa: E402
from agent import Agent  # noqa: E402

_TESTSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testset.json")
_RESULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_result.json")

_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def compute_truth(sql):
    """在数据上执行 truth_sql，返回单值（标量）。"""
    conn = tools._get_conn()
    row = conn.execute(sql).fetchone()
    return row[0] if row else None


def extract_numbers(text):
    """从文本中抽取所有数字（去掉千分位逗号）。"""
    out = []
    for m in _NUM_RE.findall(text):
        s = m.replace(",", "")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def check_number(answer, expected):
    """答案中是否存在与 expected 匹配的数字（相对容差 2% 或绝对容差 0.5）。"""
    exp = float(expected)
    for n in extract_numbers(answer):
        if abs(n - exp) <= max(0.5, abs(exp) * 0.02):
            return True
    return False


def check_string(answer, expected):
    """类别型：expected 是否作为子串出现在答案中。"""
    return str(expected) in answer


def main():
    load_dotenv()
    with open(_TESTSET, encoding="utf-8") as f:
        cases = json.load(f)

    agent = Agent()
    results = []
    total_tool_calls = 0
    ok_tool_calls = 0

    for case in cases:
        expected = compute_truth(case["truth_sql"])
        out = agent.run_with_trace(case["question"], verbose=False)
        answer = out["answer"]

        if case["kind"] == "number":
            correct = check_number(answer, expected)
        else:
            correct = check_string(answer, expected)

        n_calls = len(out["tool_calls"])
        n_ok = sum(1 for c in out["tool_calls"] if c["ok"])
        total_tool_calls += n_calls
        ok_tool_calls += n_ok

        results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "expected": expected,
                "answer": answer,
                "correct": correct,
                "steps": out["steps"],
                "tool_calls": n_calls,
                "tool_ok": n_ok,
            }
        )
        mark = "✓" if correct else "✗"
        print("[{}] {}  expected={}  steps={}".format(mark, case["id"], expected, out["steps"]))

    n = len(cases)
    acc = sum(1 for r in results if r["correct"]) / n if n else 0.0
    tool_rate = ok_tool_calls / total_tool_calls if total_tool_calls else 0.0
    avg_steps = sum(r["steps"] for r in results) / n if n else 0.0

    summary = {
        "n_cases": n,
        "answer_accuracy": round(acc, 4),
        "tool_success_rate": round(tool_rate, 4),
        "avg_steps": round(avg_steps, 2),
        "total_tool_calls": total_tool_calls,
    }

    print("\n===== 评测汇总 =====")
    print("样本数        : {}".format(n))
    print("结论准确率    : {:.1%}".format(acc))
    print("工具调用成功率: {:.1%} ({}/{})".format(tool_rate, ok_tool_calls, total_tool_calls))
    print("平均步数      : {:.2f}".format(avg_steps))

    with open(_RESULT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
    print("\n详细结果已写入: {}".format(_RESULT))


if __name__ == "__main__":
    main()
