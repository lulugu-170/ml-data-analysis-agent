"""数据字典知识库 + 轻量检索（RAG 的检索部分）。

为保持零第三方依赖，这里用基于术语/别名子串匹配的轻量检索器。
知识条目少、领域明确时足够有效；后续可无缝替换为向量检索
（把 retrieve() 换成 embedding + 相似度即可，接口不变）。
"""
import json
import os

_KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "knowledge.json")

_entries = None


def _load():
    global _entries
    if _entries is None:
        with open(_KB_PATH, encoding="utf-8") as f:
            _entries = json.load(f)
    return _entries


def _score(entry, query):
    """按术语与别名在问题中的命中情况打分。"""
    keys = [entry["term"]] + entry.get("aliases", [])
    score = 0
    for k in keys:
        if k and k in query:
            # 更长的命中更具指示性，给更高权重
            score += len(k)
    return score


def retrieve(query, k=3):
    """返回与问题最相关的前 k 条字典条目（命中的才返回）。"""
    scored = [(e, _score(e, query)) for e in _load()]
    hit = [(e, s) for e, s in scored if s > 0]
    hit.sort(key=lambda x: x[1], reverse=True)
    return [e for e, _ in hit[:k]]


def format_entries(entries):
    """把条目格式化为注入 prompt 的文本。"""
    if not entries:
        return ""
    lines = []
    for e in entries:
        lines.append(
            "- {}（{}）：{} {}".format(
                e["term"],
                "/".join(e.get("aliases", [])[:3]),
                e["definition"],
                e["sql_hint"],
            )
        )
    return "\n".join(lines)
