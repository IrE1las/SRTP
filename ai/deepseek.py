# deepseek.py
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from openai import OpenAI

# ---- 初始化部分（只执行一次） ----
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, 'key.env')
load_dotenv(env_path)

api_key = os.environ.get("DEEPSEEK_API_KEY")
if not api_key:
    raise RuntimeError("请设置 DEEPSEEK_API_KEY 环境变量（在 key.env 中）")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# ---- 核心函数：供其他程序调用 ----
def ask_ai(user_message: str, system_prompt: str = "你是一个有帮助的助手，请始终用中文回答。") -> str:
    """向 DeepSeek 提问并返回回答文本"""
    response = client.chat.completions.create(
        model="deepseek-v4-flash",   # 根据你的实际情况修改
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )
    return response.choices[0].message.content

# ---- 如果直接运行此脚本，则从命令行读取参数 ----
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python deepseek.py <你的问题>")
        sys.exit(1)
    user_msg = sys.argv[1]
    result = ask_ai(user_msg)
    print(result)