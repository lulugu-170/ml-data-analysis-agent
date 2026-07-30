"""生成合成电商数据集（用户 / 订单 / 复购），用于 Agent 演示。

输出：data/orders.csv
字段：order_id, user_id, category, amount, order_date, is_repurchase
"""
import csv
import os
import random
from datetime import date, timedelta

random.seed(42)

CATEGORIES = ["美妆", "服饰", "食品", "家居", "数码", "母婴"]
N_USERS = 800
N_ORDERS = 5000
START_DATE = date(2026, 1, 1)
DAYS_SPAN = 180

# 不同品类的价格区间（客单价差异），用于让分析结论有区分度
CATEGORY_PRICE = {
    "美妆": (80, 400),
    "服饰": (100, 600),
    "食品": (20, 150),
    "家居": (150, 900),
    "数码": (300, 3000),
    "母婴": (60, 500),
}


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "orders.csv")

    # 记录每个用户已下单的次数，用于标记复购
    user_order_count = {}
    rows = []

    for i in range(1, N_ORDERS + 1):
        user_id = random.randint(1, N_USERS)
        category = random.choice(CATEGORIES)
        low, high = CATEGORY_PRICE[category]
        amount = round(random.uniform(low, high), 2)
        order_date = START_DATE + timedelta(days=random.randint(0, DAYS_SPAN - 1))

        count = user_order_count.get(user_id, 0)
        is_repurchase = 1 if count >= 1 else 0
        user_order_count[user_id] = count + 1

        rows.append(
            {
                "order_id": i,
                "user_id": user_id,
                "category": category,
                "amount": amount,
                "order_date": order_date.isoformat(),
                "is_repurchase": is_repurchase,
            }
        )

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "order_id",
                "user_id",
                "category",
                "amount",
                "order_date",
                "is_repurchase",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print("已生成 {} 条订单 -> {}".format(len(rows), out_path))


if __name__ == "__main__":
    main()
