from flask import Flask, jsonify, request
from flask_cors import CORS
import base64
import datetime
import json
import os
import re
import sqlite3

import requests
from dotenv import load_dotenv

# 读取同目录下的 .env（该文件已被 .gitignore 忽略，不会提交到 Git）
load_dotenv()

app = Flask(__name__)
CORS(app)

DB_FILE = 'bill.db'

# ============ 大模型配置（从环境变量读取，密钥存放在 .env）============
API_KEY = os.environ.get('API_KEY', '')
BASE_URL = os.environ.get('BASE_URL', 'https://api.deepseek.com/v1')
MODEL_NAME = os.environ.get('MODEL_NAME', 'deepseek-flash')
# ====================================================================

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


def get_connection():
    """连接数据库，并确保 bills 表存在 category 列"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('PRAGMA table_info(bills)')
    columns = [row[1] for row in cur.fetchall()]
    if 'category' not in columns:
        cur.execute("ALTER TABLE bills ADD COLUMN category TEXT DEFAULT '其他'")
        conn.commit()
    return conn


def parse_json_content(content):
    """从大模型回答中提取 JSON（兼容 ```json 代码块包裹的情况）"""
    text = content.strip()
    # 去掉 markdown 代码块符号
    text = re.sub(r'^```(?:json)?', '', text).strip()
    text = re.sub(r'```$', '', text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 兜底：截取第一个 { 到最后一个 }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError('无法从大模型返回中解析出 JSON：' + content)


def recognize_bill(image_base64, mime='image/jpeg'):
    """把图片发给大模型，返回 {交易时间, 交易金额, 商户名称} 字典"""
    if not API_KEY:
        raise RuntimeError('未配置 API_KEY，请在项目根目录的 .env 中设置 API_KEY=...')

    prompt = (
        "请识别这张账单截图，提取以下三个字段：\n"
        "1. 交易时间\n"
        "2. 交易金额\n"
        "3. 商户名称\n"
        "请只返回 JSON 格式，不要输出任何多余的文字或解释，格式如下：\n"
        '{"交易时间": "", "交易金额": "", "商户名称": ""}'
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:%s;base64,%s" % (mime, image_base64)
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
    }

    headers = {
        "Authorization": "Bearer " + API_KEY,
        "Content-Type": "application/json",
    }

    url = BASE_URL.rstrip('/') + '/chat/completions'
    resp = requests.post(url, headers=headers, json=payload, timeout=120)

    if resp.status_code != 200:
        raise RuntimeError('大模型接口返回异常(%s)：%s' % (resp.status_code, resp.text))

    content = resp.json()['choices'][0]['message']['content']
    return parse_json_content(content)


def to_positive_amount(value):
    """把大模型返回的金额转成正数：-16.00 -> 16.0"""
    text = str(value).replace('¥', '').replace('￥', '').replace(',', '').strip()
    return abs(float(text))


# 日期/时间解析用的正则
DATE_PATTERN = re.compile(r'(\d{4})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})')
COMPACT_DATE_PATTERN = re.compile(r'(\d{4})(\d{2})(\d{2})')
TIME_PATTERN = re.compile(r'(\d{1,2})\s*[:：]\s*(\d{1,2})(?:\s*[:：]\s*(\d{1,2}))?')


def normalize_datetime(raw):
    """
    把大模型返回的任意日期时间格式统一成标准格式：
        date_str     -> YYYY-MM-DD
        datetime_str -> YYYY-MM-DD HH:MM:SS
    支持：2026年10月16日 / 2026-10-16 / 2026/10/16 / 2026.10.16 / 20261016
    以及可选的 时分秒 部分；解析失败时回退到今天。
    """
    text = str(raw).strip()

    year = month = day = None

    # 1. 带分隔符的日期
    m = DATE_PATTERN.search(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        # 2. 纯数字日期 20261016
        m = COMPACT_DATE_PATTERN.search(text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))

    # 3. 时间部分（没有就按 00:00:00）
    hour = minute = second = 0
    tm = TIME_PATTERN.search(text)
    if tm:
        hour = int(tm.group(1))
        minute = int(tm.group(2))
        second = int(tm.group(3) or 0)

    # 4. 日期缺省或非法时回退到今天
    if year is None:
        today = datetime.date.today()
        year, month, day = today.year, today.month, today.day

    try:
        dt = datetime.datetime(year, month, day, hour, minute, second)
    except ValueError:
        today = datetime.date.today()
        dt = datetime.datetime(today.year, today.month, today.day)

    return dt.strftime('%Y-%m-%d'), dt.strftime('%Y-%m-%d %H:%M:%S')


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

        conn = get_connection()
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


@app.route('/api/upload', methods=['POST'])
def upload_bill():
    """接收网页上传的账单截图，识别后写入数据库"""
    file = request.files.get('file') or request.files.get('image')
    if file is None:
        return jsonify({"status": "error", "message": "没有收到图片，请用 file 字段上传"}), 400

    try:
        # 1. 图片转 base64 交给大模型识别
        image_base64 = base64.b64encode(file.read()).decode('utf-8')
        mime = file.mimetype or 'image/jpeg'
        result = recognize_bill(image_base64, mime)

        # 2. 取出识别结果
        merchant = str(result.get('商户名称', '')).strip()
        amount = to_positive_amount(result.get('交易金额', 0))   # 负号转正

        # 交易时间统一格式化为 YYYY-MM-DD / YYYY-MM-DD HH:MM:SS
        date_str, datetime_str = normalize_datetime(result.get('交易时间', ''))

        # 3. 写入数据库（分类先默认 '其他'）
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bills (date, datetime, merchant, type, amount, category) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (date_str, datetime_str, merchant, '支出', amount, '其他')
        )
        conn.commit()
        conn.close()

        # 4. 只返回 success，让网页知道搞定了
        return jsonify({"status": "success"})

    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": f"数据库写入失败: {e}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/recent', methods=['GET'])
def get_recent_bills():
    """返回最新 5 条账单记录（按 id 倒序）"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, date, datetime, merchant, amount, category "
            "FROM bills ORDER BY id DESC LIMIT 5"
        )
        rows = cur.fetchall()
        conn.close()
        items = [
            {
                "id": r[0],
                "date": r[1],
                "datetime": r[2],
                "merchant": r[3],
                "amount": r[4],
                "category": r[5]
            }
            for r in rows
        ]
        return jsonify({"status": "success", "items": items})
    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/bills/<int:bill_id>', methods=['DELETE'])
def delete_bill(bill_id):
    """按 id 删除一条账单记录"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        if deleted == 0:
            return jsonify({"status": "error", "message": "记录不存在"}), 404
        return jsonify({"status": "success"})
    except sqlite3.Error as e:
        return jsonify({"status": "error", "message": f"删除失败: {e}"}), 500


if __name__ == '__main__':
    print("后端服务器已启动！请打开浏览器访问：http://127.0.0.1:5000")
    app.run(debug=True)
