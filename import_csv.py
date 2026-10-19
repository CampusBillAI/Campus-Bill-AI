# -*- coding: utf-8 -*-
"""
import_csv.py — 将微信账单 bill.csv 导入 SQLite 数据库 bill.db

列索引（依据表头行，跳过前 17 行说明文字后紧跟的第 18 行）：
    0  交易时间   如 2026-10-12 11:18:36
    1  交易类型   如 商户消费 / 转账 / 其他
    2  交易对方   商户名（本脚本提取的"商户"字段）
    3  商品
    4  收/支      收入 / 支出 / /
    5  金额(元)   如 ￥57.70（注意 ￥1,000.00 带千分位逗号）
    6  支付方式
    7  当前状态
    8  交易单号
    9  商户单号
    10 备注
"""
import csv
import sqlite3

CSV_FILE = 'bill.csv'
DB_FILE = 'bill.db'


def parse_amount(raw):
    """金额清洗：去掉货币符号和千分位逗号"""
    return float(raw.replace('¥', '').replace('￥', '').replace(',', '').strip())


def main():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            date     TEXT NOT NULL,      -- 交易日期 yyyy-mm-dd
            datetime TEXT,               -- 完整交易时间
            merchant TEXT,               -- 交易对方（商户）
            type     TEXT NOT NULL,      -- 收/支
            amount   REAL NOT NULL       -- 金额（正数）
        )
    ''')
    cur.execute('DELETE FROM bills')  # 重复运行时先清空，保证可重复导入

    with open(CSV_FILE, 'r', encoding='gbk') as f:
        reader = csv.reader(f)
        for _ in range(17):          # 跳过前 17 行说明文字
            next(reader)
        next(reader)                 # 跳过表头行（索引 17）

        for row in reader:
            if len(row) < 6:
                continue
            if row[4].strip() != '支出':      # 只导入"支出"行
                continue
            try:
                amount = parse_amount(row[5])
            except ValueError:
                print('金额无法解析，已跳过:', row[:6])
                continue
            dt = row[0].strip()               # 完整交易时间
            date = dt.split(' ')[0]           # 只取日期部分
            merchant = row[2].strip()         # 交易对方 = 商户
            cur.execute(
                'INSERT INTO bills (date, datetime, merchant, type, amount) VALUES (?, ?, ?, ?, ?)',
                (date, dt, merchant, '支出', amount)
            )

    conn.commit()

    # 核对结果
    cur.execute('SELECT COUNT(*), SUM(amount) FROM bills')
    cnt, total = cur.fetchone()
    print(f'导入完成：COUNT = {cnt}，SUM(amount) = {round(total, 2)}')
    conn.close()


if __name__ == '__main__':
    main()
