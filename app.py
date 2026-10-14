from flask import Flask, jsonify
import csv

app = Flask(__name__)


@app.route('/')
def get_bill_data():
    daily_expense = {}
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
                    except ValueError:
                        continue

        # 把整理好的数据打包返回
        return jsonify({
            "status": "success",
            "total_expense": round(total_expense, 2),
            "daily_expense": dict(sorted(daily_expense.items()))
        })

    except FileNotFoundError:
        return jsonify({"status": "error", "message": "找不到 bill.csv 文件，请确认文件在项目根目录"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    print("后端服务器已启动！请打开浏览器访问：http://127.0.0.1:5000")
    app.run(debug=True)