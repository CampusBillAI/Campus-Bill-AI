import csv

# 微信账单标准格式：编码一般用 gbk
with open('bill.csv', 'r', encoding='gbk') as f:
    reader = csv.reader(f)

    # 跳过前 16 行（微信标准账单前16行是个人信息，第17行是空行，第18行才是表头）
    for i in range(17):
        next(reader)

    total_expense = 0.0
    for row in reader:
        # 微信标准账单：
        # 第 1 列（索引0）：交易时间
        # 第 4 列（索引3）：收/支（显示为"支出"或"收入"）
        # 第 6 列（索引5）：金额（带 ¥ 符号）

        # 先判断这行是不是有效数据（有 6 列以上）
        if len(row) < 6:
            continue

        # 提取"收/支"列
        trade_type = row[4].strip()

        # 提取"金额"列，并去掉可能带有的 "¥" 符号
        amount_str = row[5].strip().replace('¥', '').replace('￥', '')

        # 如果这行标记为"支出"，且金额是数字，就累加
        if trade_type == '支出':
            try:
                amount = float(amount_str)
                total_expense += amount
            except ValueError:
                continue

    print(f"账单分析完毕！你的总支出为：{total_expense:.2f} 元")
    import csv
    from collections import defaultdict

    # 创建一个字典，用来按日期存每天的总花费
    daily_expense = defaultdict(float)

    with open('bill.csv', 'r', encoding='gbk') as f:
        reader = csv.reader(f)

        for i in range(17):
            next(reader)

        total_expense = 0.0
        for row in reader:
            if len(row) < 6:
                continue

            trade_type = row[4].strip()  # 刚刚你改对了，咱们就用 row[4]
            amount_str = row[5].strip().replace('¥', '').replace('￥', '')

            if trade_type == '支出':
                try:
                    amount = float(amount_str)
                    total_expense += amount

                    # 新增：提取日期（通常是第1列，比如"2026-10-12 11:18:36"）
                    date_str = row[0].strip().split(' ')[0]  # 只取前面的日期部分
                    daily_expense[date_str] += amount  # 把今天的消费加上

                except ValueError:
                    continue

        print(f"账单分析完毕！你的总支出为：{total_expense:.2f} 元")

        # 新增：打印每天的消费明细
        print("\n--- 每日消费记录 ---")
        for date, amount in sorted(daily_expense.items()):
            print(f"{date}: {amount:.2f} 元")