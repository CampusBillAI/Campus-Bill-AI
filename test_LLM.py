# -*- coding: utf-8 -*-
"""
test_LLM.py — 调用大模型识别账单截图，提取交易时间、交易金额、商户名称

使用前请填写下面的 API_KEY 和 BASE_URL 两个变量，并确保当前目录存在 test.jpg。
运行：python test_LLM.py
"""
import base64
import json
import os

import requests

# ============ 需要你自己填写这两个变量 ============
API_KEY = "sk-edc122f9618f499f9e6d899bf19794fb"                                   # 例如："sk-xxxxxxxxxxxxxxxx"
BASE_URL = "https://api.deepseek.com/v1"                               # 例如："https://api.deepseek.com/v1"
MODEL_NAME = "deepseek-flash"                  # 要调用的模型名
# =================================================

IMAGE_FILE = "test.jpg"


def encode_image(path):
    """把图片读成 base64 字符串"""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def main():
    # 基本检查
    if not API_KEY or not BASE_URL:
        print("请先在代码里填写 API_KEY 和 BASE_URL 再运行！")
        return
    if not os.path.exists(IMAGE_FILE):
        print("找不到图片文件：", IMAGE_FILE)
        return

    image_base64 = encode_image(IMAGE_FILE)

    # 提示词：要求模型只返回 JSON
    prompt = (
        "请识别这张账单截图，提取以下三个字段：\n"
        "1. 交易时间\n"
        "2. 交易金额\n"
        "3. 商户名称\n"
        "请只返回 JSON 格式，不要输出任何多余的文字或解释，格式如下：\n"
        '{"交易时间": "", "交易金额": "", "商户名称": ""}'
    )

    # OpenAI 通用格式的请求体
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
                            "url": "data:image/jpeg;base64," + image_base64
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

    url = BASE_URL.rstrip("/") + "/chat/completions"

    print("正在请求大模型，请稍候...")
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
    except Exception as e:
        print("请求失败：", e)
        return

    # 打印原始状态码
    print("HTTP 状态码：", resp.status_code)

    if resp.status_code != 200:
        print("接口返回异常，原始内容如下：")
        print(resp.text)
        return

    result = resp.json()

    # 取出模型回答的文本内容
    content = result["choices"][0]["message"]["content"]

    print("\n===== 大模型返回的原始内容 =====")
    print(content)

    # 尝试把返回内容解析成 JSON，方便查看
    print("\n===== 尝试解析为 JSON =====")
    try:
        data = json.loads(content)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print("返回内容不是标准 JSON（可能是模型加了额外文字或代码块符号）")


if __name__ == "__main__":
    main()
