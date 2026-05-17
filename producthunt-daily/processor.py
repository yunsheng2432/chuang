"""
数据处理层 —— 将 API 原始 JSON 清洗为结构化扁平记录。

调用方式:
    from processor import process_posts
    posts = process_posts(raw_data)
"""

import logging

logger = logging.getLogger(__name__)

# GraphQL 响应中每条 node 的字段 → 输出字段 映射 + 默认值
_FIELD_MAP: dict[str, tuple[str, object]] = {
    "name":        ("name",        ""),
    "tagline":     ("tagline",     ""),
    "description": ("description", ""),
    "votesCount":  ("votes_count", 0),
    "website":     ("website",     ""),
    "url":         ("url",         ""),
    "createdAt":   ("created_at",  ""),
}


def process_posts(raw_data: dict) -> list[dict]:
    """将 GraphQL 原始响应解析为排序后的项目记录列表。

    Args:
        raw_data: fetcher.fetch_daily_top() 返回的原始 JSON。

    Returns:
        按 votes_count 降序排列的记录列表。每条记录结构见 _parse_single_post() 注释。
        如果原始数据无结果，返回空列表。
    """
    edges = _extract_edges(raw_data)
    if not edges:
        logger.warning("原始数据中无项目记录")
        return []

    posts = [_parse_single_post(edge["node"]) for edge in edges]
    posts.sort(key=lambda p: p["votes_count"], reverse=True)

    logger.info("处理完成: %d 个项目，最高票数 %d，最低票数 %d",
                len(posts), posts[0]["votes_count"], posts[-1]["votes_count"])
    return posts


def _extract_edges(raw_data: dict) -> list:
    """从原始响应中安全提取 edges 列表。"""
    try:
        return raw_data["data"]["posts"]["edges"]
    except (KeyError, TypeError):
        return []


def _parse_single_post(node: dict) -> dict:
    """将单条 GraphQL node 解析为扁平记录。

    Returns:
        {
            "name":         str   # 项目名称
            "tagline":      str   # 一句话简介
            "description":  str   # 详细描述（截断至 500 字符）
            "votes_count":  int   # 点赞数
            "website":      str   # 官网 URL
            "url":          str   # ProductHunt 页面 URL
            "topics":       list[str]  # 功能标签列表
            "thumbnail":    str   # 缩略图 URL
            "created_at":   str   # 发布时间（ISO 8601）
        }
    """
    record: dict[str, object] = {}

    for node_key, (record_key, default) in _FIELD_MAP.items():
        record[record_key] = node.get(node_key, default)

    # 描述截断
    desc = record.get("description")
    if isinstance(desc, str) and len(desc) > 500:
        record["description"] = desc[:500]

    # topics: {"edges": [{"node": {"name": "..."}}, ...]} 或 null → ["...", ...]
    _topics = node.get("topics") or {}
    topics_list = []
    for t in _topics.get("edges", []):
        topic_node = t.get("node") or {}
        name = topic_node.get("name")
        if name:
            topics_list.append(name)
    record["topics"] = topics_list

    # thumbnail: {"url": "..."} 或 null → "..."
    _thumb = node.get("thumbnail") or {}
    record["thumbnail"] = _thumb.get("url", "") or ""

    return record