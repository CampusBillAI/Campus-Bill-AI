from flask import Flask, jsonify
from flask_cors import CORS
import os
import sqlite3

app = Flask(__name__)
CORS(app)

DB_FILE = 'bill.db'

# 消费类型关键词（按商户名匹配）
FOOD_KEYWORDS = ['餐', '饭', '食堂', '外卖', '奶茶', '超市']
SHOPPING_KEYWORDS = ['淘宝', '京东', '拼多多', '购物']


def classify_expense(merchant):
    """根据商户名判断消费类型：food / shopping / fun"""
    for kw in FOOD_KEYWORDS:
        if kw in merchant:
            return 'food'
    for kw in SHOPPING_KEYWORDS:
        if kw in merchant:
            return 'shopping'
    return 'fun'


@app.route('/')
def get_bill_data():
    daily_expense = {}
    food_expense = {}
    shopping_expense = {}
    fun_expense = {}
    total_expense = 0.0

    try:
        if not os.path.exists(DB_FILE):
            return jsonify({"status": "error", "message": "找不到 bill.db，请先运行 import_csv.py 导入数据"}), 404

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT date, merchant, amount FROM bills WHERE type = '支出'")
        rows = cursor.fetchall()
        conn.close()

        for date, merchant, amount in rows:
            total_expense += amount

            # 按日期累加
            if date in daily_expense:
                daily_expense[date] += amount
            else:
                daily_expense[date] = amount

            # 按商户名分类后按日期累加
            category = classify_expense(merchant or '')
            if category == 'food':
                food_expense[date] = food_expense.get(date, 0) + amount
            elif category == 'shopping':
                shopping_expense[date] = shopping_expense.get(date, 0) + amount
            else:
                fun_expense[date] = fun_expense.get(date, 0) + amount

        # 把整理好的数据打包返回（字段名与之前完全一致，前端无需改动）
        return jsonify({
            "status": "success",
            "total_expense": round(total_expense, 2),
            "daily_expense": dict(sorted(daily_expense.items())),
            "food_expense": dict(sorted(food_expense.items())),
            "shopping_expense": dict(sorted(shopping_expense.items())),
            "fun_expense": dict(sorted(fun_expense.items()))
        })

    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": f"数据库读取失败: {e}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    print("后端服务器已启动！请打开浏览器访问：http://127.0.0.1:5000")
    app.run(debug=True)
