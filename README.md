# ML 数据分析助手 Agent

一个"懂数据的分析助手"：用户用自然语言提出分析需求，Agent 自动选择并调用工具（SQL 查询、统计分析），返回可解释的结论。

已实现 **function calling 工具调用、数据字典 RAG、多步推理与意图自检、自建效果评测体系**，并通过评测驱动优化将结论准确率从 87.5% 提升到 100%（见下方评测章节）。

## 核心能力

- 自然语言驱动的数据问答（多步推理，自动规划取数与分析步骤）
- **Function calling 工具调用**：`run_sql`（只读 SQL 沙箱）、`list_tables`（查看表结构）
- **数据字典 RAG**：按问题检索指标口径并注入 prompt，减少语义理解偏差
- **意图自检**：写 SQL 前先区分"数量/金额/客单价"等口径，答复前自检
- **效果评测体系**：测试集 + 结论准确率 / 工具调用成功率 / 平均步数
- 基于合成电商数据集（用户、订单、复购）演示

## 快速开始

```bash
# 1. 安装依赖
pip3 install -r requirements.txt

# 2. 配置 API（默认已配好智谱 GLM-4-Flash，永久免费，只需填 key）
cp .env.example .env
#   编辑 .env，把 OPENAI_API_KEY 换成你在 open.bigmodel.cn 创建的 key
#   如需换其他兼容服务（DeepSeek/硅基流动等），改 OPENAI_BASE_URL 和 MODEL 即可

# 3. 生成合成数据集
python3 data/generate_data.py

# 4. 启动交互式 Agent
python3 src/main.py
```

## 示例提问

```
各品类的订单数和 GMV 分别是多少？
30 天内有复购的用户占比是多少？
哪个品类的客单价最高？
按月统计订单量趋势
```

## 效果评测

在测试集上量化 Agent 表现，跑一条命令即可：

```bash
python3 eval/run_eval.py
```

输出三项指标：
- **结论准确率**：最终答案是否命中 ground truth（数值型按容差匹配，类别型按包含匹配）
- **工具调用成功率**：成功执行的工具调用 / 总工具调用
- **平均步数**：完成一个任务平均需要的模型轮次

测试集在 `eval/testset.json`，每条题目带一个 `truth_sql`——ground truth 在同一份数据上实时计算，保证与数据一致，改数据也不用改答案。详细结果写入 `eval/eval_result.json`。

**评测驱动优化案例**：初版评测发现模型在"订单数量最多的品类"上把【数量】误解为【金额】（用 `SUM(amount)` 而非 `COUNT(*)`）。通过引入数据字典 RAG + 意图自检，将结论准确率从 **87.5% 提升到 100%**，工具调用成功率保持 100%。

> 这套评测是本项目区别于普通 Agent demo 的关键：它让"效果"可量化、可复现，也是优化前后对比的依据。

## 目录结构

```
ml-agent/
├── data/
│   ├── generate_data.py   # 生成合成电商数据（orders.csv）
│   ├── knowledge.json     # 数据字典知识库（指标口径）
│   └── orders.csv         # 运行脚本后生成
├── src/
│   ├── tools.py           # 工具层：SQL 执行、表结构查看 + tool schema
│   ├── knowledge.py       # 数据字典检索（RAG 检索部分）
│   ├── agent.py           # Agent 主循环（function calling + 字典注入 + 意图自检）
│   └── main.py            # CLI 入口
├── eval/
│   ├── testset.json       # 评测集（题目 + ground truth SQL）
│   └── run_eval.py        # 评测脚本（准确率 / 工具成功率 / 步数）
├── requirements.txt
├── .env.example
└── README.md
```

## 设计说明

- **工具层与 Agent 解耦**：`tools.py` 只负责"能做什么"，`agent.py` 负责"什么时候调用什么"。便于后续扩展工具（画图、跑分析脚本）而不改动主循环。
- **SQL 沙箱**：数据加载到内存 SQLite，仅允许只读查询（拦截 DML/DDL），避免模型误操作数据。
- **OpenAI 兼容接口**：通过 `OPENAI_BASE_URL` 可切换到任意兼容 function calling 的服务（GPT / 兼容网关 / 本地模型）。

## 后续规划

- 多智能体协作（规划 / 执行 / 审查），并与单 Agent 版本做评测对比
- 扩展工具：图表可视化、执行分析脚本
- 检索升级：数据字典检索从术语匹配升级为向量检索
