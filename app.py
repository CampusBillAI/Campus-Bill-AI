from flask import Flask, jsonify
from flask_cors import CORS
import csv

app = Flask(__name__)
CORS(app)


# 消费类型关键词
FOOD_KEYWORDS = ['餐', '饭', '食堂', '外卖', '奶茶', '超市']
SHOPPING_KEYWORDS = ['淘宝', '京东', '拼多多', '购物']


def classify_expense(product_name):
    """根据商品名判断消费类型：food / shopping / fun"""
    for kw in FOOD_KEYWORDS:
        if kw in product_name:
            return 'food'
    for kw in SHOPPING_KEYWORDS:
        if kw in product_name:
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
        # 读取账单 CSV，注意编码
        with open('bill.csv', 'r', encoding='gbk') as f:
            reader = csv.reader(f)

            # 跳过前 17 行说明文字
            for i in range(17):
                next(reader)

            for row in reader:
                if len(row) < 6:
                    continue

                # 提取"收/支"列（昨天改成功的 row[4]）
                trade_type = row[4].strip()

                # 提取"金额"列，去掉符号
                amount_str = row[5].strip().replace('¥', '').replace('￥', '')

                if trade_type == '支出':
                    try:
                        amount = float(amount_str)
                        total_expense += amount

                        # 提取日期部分
                        date_str = row[0].strip().split(' ')[0]
                        if date_str in daily_expense:
                            daily_expense[date_str] += amount
                        else:
                            daily_expense[date_str] = amount

                        # 从"商品"列（索引 3）提取关键词并分类
                        category = classify_expense(row[3].strip())
                        if category == 'food':
                            food_expense[date_str] = food_expense.get(date_str, 0) + amount
                        elif category == 'shopping':
                            shopping_expense[date_str] = shopping_expense.get(date_str, 0) + amount
                        else:
                            fun_expense[date_str] = fun_expense.get(date_str, 0) + amount
                    except ValueError:
                        continue

        # 把整理好的数据打包返回
        return jsonify({
            "status": "success",
            "total_expense": round(total_expense, 2),
            "daily_expense": dict(sorted(daily_expense.items())),
            "food_expense": dict(sorted(food_expense.items())),
            "shopping_expense": dict(sorted(shopping_expense.items())),
            "fun_expense": dict(sorted(fun_expense.items()))
        })

    except FileNotFoundError:
        return jsonify({"status": "error", "message": "找不到 bill.csv 文件，请确认文件在项目根目录"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    print("后端服务器已启动！请打开浏览器访问：http://127.0.0.1:5000")
    app.run(debug=True)