import sys
sys.stdout.reconfigure(encoding='utf-8')

from knowledge_ai import ask_ai_with_knowledge, load_knowledge_base

# 预加载向量库（避免第一个问题等 25s 冷启动）
print("⏳ 预加载知识库...")
load_knowledge_base()
print("✅ 准备就绪！\n")

test_questions = [
    "计算机联锁系统的功能和安全性指标是什么？",          # 文档中有
    "系统基本结构分为哪三层？",                          # 问题模糊
    "软件设计中数据结构通常采用什么？",                  # 问题模糊
    "今天天气怎么样？",                                  # 文档中肯定没有
    "请介绍一下二乘二取二冗余结构的特点",                 # 文档中有（硬件冗余部分）
]

for q in test_questions:
    print("=" * 60)
    print(f"🙋 用户：{q}")
    try:
        answer = ask_ai_with_knowledge(q, distance_threshold=0.8)
        print(f"🤖 AI：{answer}")
    except Exception as e:
        print(f"❌ 出错：{e}")

print("=" * 60)
print("测试结束。")