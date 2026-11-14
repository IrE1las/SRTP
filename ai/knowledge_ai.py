"""
knowledge_ai.py —— 仅基于本地 knowledge/ 文件夹内的专业资料进行回答。
若问题超出资料范围则直接拒绝回答，绝不使用网络或模型预训练知识。

使用前请安装依赖（国内镜像）：
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple openai python-dotenv langchain langchain-community chromadb sentence-transformers langchain-huggingface langchain-chroma pypdf docx2txt tqdm

首次运行需要构建知识库：
python knowledge_ai.py --build

提问示例：
python knowledge_ai.py "什么是XX术语？"
"""

import os
import sys
import warnings

# ===== 1. 硬编码 Hugging Face 国内镜像 =====
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# ===== 2. 彻底关闭进度条和冗余警告 =====
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["DISABLE_TQDM"] = "1"

# 如果 tqdm 已安装，直接全局禁用进度条
try:
    import tqdm
    tqdm.tqdm.disable = True
except ImportError:
    pass

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from openai import OpenAI

# ===== 3. 全局嵌入模型缓存（只加载一次，且无进度条） =====
EMBEDDING_MODEL = None

def get_embedding_model():
    """获取全局唯一的嵌入模型实例，避免每次提问都重新加载权重"""
    global EMBEDDING_MODEL
    if EMBEDDING_MODEL is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        EMBEDDING_MODEL = HuggingFaceEmbeddings(
            model_name="shibing624/text2vec-base-chinese",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    return EMBEDDING_MODEL

# ===== 路径配置 =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, 'key.env')
KNOWLEDGE_DIR = os.path.join(SCRIPT_DIR, "knowledge")
VECTOR_DB_DIR = os.path.join(SCRIPT_DIR, "vector_db")

load_dotenv(ENV_PATH)

# ================== 知识库构建 ==================
def build_knowledge_base():
    loader_map = {}
    try:
        from langchain_community.document_loaders import TextLoader
        loader_map[".txt"] = (TextLoader, {"autodetect_encoding": True})
    except ImportError:
        print("错误：请安装 langchain-community")
        return None

    try:
        from langchain_community.document_loaders import UnstructuredMarkdownLoader
        loader_map[".md"] = (UnstructuredMarkdownLoader, {})
    except ImportError:
        print("提示：pip install unstructured markdown  以支持 .md")

    try:
        from langchain_community.document_loaders import PyPDFLoader
        loader_map[".pdf"] = (PyPDFLoader, {})
    except ImportError:
        print("提示：pip install pypdf  以支持 .pdf")

    try:
        from langchain_community.document_loaders import Docx2txtLoader
        loader_map[".docx"] = (Docx2txtLoader, {})
    except ImportError:
        print("提示：pip install docx2txt  以支持 .docx")

    if not os.path.exists(KNOWLEDGE_DIR):
        os.makedirs(KNOWLEDGE_DIR)
        print(f"已创建 {KNOWLEDGE_DIR}，请放入资料后重试。")
        return None

    from langchain_community.document_loaders import DirectoryLoader
    documents = []
    for ext, (loader_cls, kwargs) in loader_map.items():
        pattern = f"**/*{ext}"
        try:
            loader = DirectoryLoader(KNOWLEDGE_DIR, glob=pattern,
                                     loader_cls=loader_cls, loader_kwargs=kwargs,
                                     show_progress=False, use_multithreading=True)
            docs = loader.load()
            print(f"已加载 {len(docs)} 个 {ext} 文件")
            documents.extend(docs)
        except Exception as e:
            print(f"读取 {pattern} 出错：{e}")

    if not documents:
        print("知识库为空！")
        return None

    # 文本分割器（兼容新旧版本）
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        from langchain.text_splitter import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=100,
        separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"切分为 {len(chunks)} 个文本块。")

    # 使用 langchain-chroma 消除弃用警告
    try:
        from langchain_chroma import Chroma
    except ImportError:
        print("提示：请安装 langchain-chroma 以消除警告：pip install langchain-chroma")
        from langchain_community.vectorstores import Chroma

    embeddings = get_embedding_model()
    vectordb = Chroma.from_documents(documents=chunks,
                                     embedding=embeddings,
                                     persist_directory=VECTOR_DB_DIR)
    try:
        vectordb.persist()
    except AttributeError:
        pass
    print(f"知识库构建完成，索引保存在 {VECTOR_DB_DIR}")
    return vectordb

# ================== 加载知识库 ==================
def load_knowledge_base():
    if not os.path.exists(VECTOR_DB_DIR):
        return None

    try:
        from langchain_chroma import Chroma
    except ImportError:
        from langchain_community.vectorstores import Chroma

    embeddings = get_embedding_model()
    return Chroma(persist_directory=VECTOR_DB_DIR, embedding_function=embeddings)

# ================== DeepSeek 客户端 ==================
api_key = os.environ.get("DEEPSEEK_API_KEY")
if not api_key:
    raise RuntimeError("请在 key.env 中设置 DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ================== 核心问答函数 ==================
def ask_ai_with_knowledge(user_message: str,
                          distance_threshold: float = 0.8,
                          top_k: int = 7) -> str:
    """
    基于本地知识库回答用户问题。

    参数:
        user_message      : 用户问题
        distance_threshold: 向量距离阈值，越小越严格。默认 0.8 较严格，可放宽到 1.0。
        top_k             : 检索块数，默认 7，提高短句命中率。
    """
    vectordb = load_knowledge_base()
    if vectordb is None:
        return "知识库尚未构建。请先运行: python knowledge_ai.py --build"

    docs_with_scores = vectordb.similarity_search_with_score(user_message, k=top_k)

    relevant_chunks = []
    for doc, dist in docs_with_scores:
        if dist < distance_threshold:
            relevant_chunks.append(doc.page_content)

    if not relevant_chunks:
        return "抱歉，我无法回答这个问题。提供的专业资料中未找到相关信息。"

    context = "\n\n---\n\n".join(relevant_chunks)
    system_prompt = (
        "你是一个严格的专业助手，只依据以下【参考资料】回答用户问题。\n"
        "规则：\n"
        "1. 回答必须完全基于参考资料中的内容，不得使用任何外部知识、常识或网络信息。\n"
        "2. 如果参考资料中不包含回答问题所需的信息，你必须明确回复：\n"
        '   "抱歉，提供的资料中不包含相关信息，无法回答。"\n'
        "3. 回答时尽量引用参考资料中的原句，并使用中文。\n\n"
        f"【参考资料】\n{context}"
    )

    response = client.chat.completions.create(
        model="deepseek-v4-flash",          # 或 deepseek-v4-pro
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        stream=False,
        temperature=0.0,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )
    return response.choices[0].message.content

# ================== 命令行入口 ==================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：")
        print("  构建知识库：python knowledge_ai.py --build")
        print("  提问：      python knowledge_ai.py \"你的问题\"")
        sys.exit(1)

    if sys.argv[1] == "--build":
        print("开始构建知识库，请稍候...")
        build_knowledge_base()
    else:
        print(ask_ai_with_knowledge(sys.argv[1]))