"""CLI 入口：交互式提问，或用命令行参数单次提问。

用法：
  python3 src/main.py                 # 进入交互模式
  python3 src/main.py "你的问题"       # 单次提问
"""
import sys

from dotenv import load_dotenv

from agent import Agent


def main():
    load_dotenv()
    agent = Agent()

    # 单次提问模式
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(agent.run(question))
        return

    # 交互模式
    print("ML 数据分析助手 Agent（输入 exit 退出）")
    print("-" * 40)
    while True:
        try:
            question = input("\n你的问题> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            print("再见")
            break
        answer = agent.run(question)
        print("\n" + answer)


if __name__ == "__main__":
    main()
