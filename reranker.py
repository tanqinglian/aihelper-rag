"""重排序模块 - BM25 + 向量相似度混合"""
import math
import re
import jieba


def tokenize(text: str) -> list[str]:
    """分词（中英文混合）"""
    # 提取英文单词和中文
    tokens = []
    # 使用 jieba 分词
    for word in jieba.cut(text):
        word = word.strip().lower()
        if word and len(word) > 1:  # 过滤单字符
            tokens.append(word)
    # 额外提取驼峰命名的单词
    camel_words = re.findall(r'[A-Z][a-z]+|[a-z]+', text)
    tokens.extend([w.lower() for w in camel_words if len(w) > 1])
    return tokens


def compute_bm25_score(query_tokens: list[str], doc_tokens: list[str],
                       avg_doc_len: float, k1: float = 1.5, b: float = 0.75) -> float:
    """计算 BM25 分数"""
    if not query_tokens or not doc_tokens:
        return 0.0

    doc_len = len(doc_tokens)
    doc_freq = {}
    for token in doc_tokens:
        doc_freq[token] = doc_freq.get(token, 0) + 1

    score = 0.0
    for token in query_tokens:
        if token in doc_freq:
            tf = doc_freq[token]
            # 简化的 IDF (假设所有文档都包含该词的概率)
            idf = math.log(2.0)  # 简化处理
            # BM25 公式
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * doc_len / avg_doc_len)
            score += idf * numerator / denominator

    return score


def rerank_documents(query: str, docs: list[dict], top_n: int = 5,
                     vector_weight: float = 0.4, bm25_weight: float = 0.6) -> list[dict]:
    """
    混合重排序：结合向量相似度和 BM25 关键词匹配

    Args:
        query: 用户问题
        docs: 检索到的文档列表，每个文档包含 {path, module, content, score}
        top_n: 返回的文档数量
        vector_weight: 向量相似度权重
        bm25_weight: BM25 权重

    Returns:
        重排序后的文档列表
    """
    if not docs:
        return []

    if len(docs) <= top_n:
        return docs

    # 分词
    query_tokens = tokenize(query)

    # 计算每个文档的 BM25 分数
    doc_tokens_list = []
    for doc in docs:
        # 合并路径和内容进行分词
        text = f"{doc['path']} {doc['content']}"
        doc_tokens_list.append(tokenize(text))

    # 平均文档长度
    avg_doc_len = sum(len(tokens) for tokens in doc_tokens_list) / len(doc_tokens_list)

    # 计算 BM25 分数
    bm25_scores = []
    for doc_tokens in doc_tokens_list:
        score = compute_bm25_score(query_tokens, doc_tokens, avg_doc_len)
        bm25_scores.append(score)

    # 归一化 BM25 分数到 [0, 1]
    max_bm25 = max(bm25_scores) if bm25_scores else 1
    min_bm25 = min(bm25_scores) if bm25_scores else 0
    if max_bm25 > min_bm25:
        bm25_scores = [(s - min_bm25) / (max_bm25 - min_bm25) for s in bm25_scores]
    else:
        bm25_scores = [0.5] * len(bm25_scores)

    # 计算混合分数
    scored_docs = []
    for i, doc in enumerate(docs):
        vector_score = doc.get("score", 0)
        bm25_score = bm25_scores[i]

        # 混合分数
        hybrid_score = vector_weight * vector_score + bm25_weight * bm25_score

        scored_docs.append({
            **doc,
            "vector_score": vector_score,
            "bm25_score": bm25_score,
            "score": hybrid_score,  # 更新为混合分数
        })

    # 按混合分数排序
    scored_docs.sort(key=lambda x: x["score"], reverse=True)

    # 返回 top_n
    return scored_docs[:top_n]


if __name__ == "__main__":
    # 测试
    test_query = "科目数据从哪里获取"
    test_docs = [
        {"path": "pages/Clazz/api.js", "module": "Clazz", "content": "export function getSubjectList() { ... }", "score": 0.65},
        {"path": "pages/Home/index.js", "module": "Home", "content": "render home page", "score": 0.70},
        {"path": "utils/dict.js", "module": "utils", "content": "获取字典数据 getDictList 科目", "score": 0.60},
    ]

    result = rerank_documents(test_query, test_docs, top_n=2)
    for doc in result:
        print(f"[{doc['score']:.3f}] (vec:{doc['vector_score']:.3f} bm25:{doc['bm25_score']:.3f}) {doc['path']}")
