"""
数据采集层 —— 通过 ProductHunt GraphQL API v2 拉取每日热门项目。

调用方式:
    from fetcher import fetch_daily_top
    raw_data = fetch_daily_top(n=20)
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import requests

import config

logger = logging.getLogger(__name__)

# GraphQL 查询：按投票数降序，筛选指定日期之后发布的 featured 项目
_QUERY = """
query DailyTopPosts($postedAfter: DateTime!, $first: Int!) {
  posts(
    postedAfter: $postedAfter
    first: $first
    order: VOTES
    featured: true
  ) {
    edges {
      node {
        id
        name
        tagline
        description
        votesCount
        website
        url
        topics {
          edges { node { name } }
        }
        thumbnail { url }
        createdAt
      }
    }
  }
}
"""

# 将 "YYYY-MM-DD" 转为 GraphQL 要求的 DateTime 字符串
def _to_utc_datetime_str(date_str: str) -> str:
    return f"{date_str}T00:00:00Z"


def fetch_daily_top(n: int = config.DEFAULT_TOP_N, date_str: str = "") -> dict:
    """从 ProductHunt API 拉取指定日期投票最高的前 n 个项目。

    Args:
        n: 拉取数量，默认取自 config.DEFAULT_TOP_N（20）。
        date_str: "YYYY-MM-DD" 目标日期，空字符串时优先用 FETCH_DATE_OVERRIDE 环境变量，
                  否则默认取 UTC 昨天。

    Returns:
        GraphQL 原始响应 dict，结构为 {"data": {"posts": {"edges": [...]}}}。

    Raises:
        RuntimeError: Token 未配置。
        requests.HTTPError: API 返回非 2xx 状态。
        requests.Timeout: 请求超时。
    """
    _validate_token()

    # 日期确定顺序：参数 > 环境变量 > UTC 昨天
    if not date_str:
        date_str = config.FETCH_DATE_OVERRIDE or (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).strftime("%Y-%m-%d")
    posted_after = _to_utc_datetime_str(date_str)

    logger.info("开始采集: postedAfter=%s, first=%d", posted_after, n)

    headers = {
        "Authorization": f"Bearer {config.PRODUCTHUNT_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "query": _QUERY,
        "variables": {
            "postedAfter": posted_after,
            "first": n,
        },
    }

    # 最多重试 3 次，处理瞬时网络故障和 429 限流
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                config.PRODUCTHUNT_API_URL,
                json=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            body = resp.json()

            # GraphQL 可能返回 200 但携带 errors 字段
            if "errors" in body:
                _handle_graphql_errors(body["errors"])

            edge_count = len(body.get("data", {}).get("posts", {}).get("edges", []))
            logger.info("采集成功: 获取到 %d 个项目（第 %d 次尝试）", edge_count, attempt)
            return body

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 429:
                _retry_sleep(attempt, "触发速率限制 (429)")
            elif status in (401, 403):
                raise RuntimeError(
                    f"API 认证失败 (HTTP {status})，请检查 PRODUCTHUNT_TOKEN 是否有效"
                ) from e
            elif status and status >= 500:
                _retry_sleep(attempt, f"服务端错误 (HTTP {status})")
            else:
                raise

        except requests.Timeout:
            _retry_sleep(attempt, "请求超时")

    raise RuntimeError("采集失败：已重试 3 次仍不成功")


def _validate_token() -> None:
    if not config.PRODUCTHUNT_TOKEN:
        raise RuntimeError(
            "PRODUCTHUNT_TOKEN 未设置。请在 GitHub Secrets 或本地 .env 文件中配置。\n"
            "获取方式: https://www.producthunt.com/v2/oauth/applications → 创建 Application → Developer Token"
        )


def _handle_graphql_errors(errors: list) -> None:
    messages = "; ".join(err.get("message", str(err)) for err in errors)
    raise RuntimeError(f"GraphQL 错误: {messages}")


def _retry_sleep(attempt: int, reason: str) -> None:
    delay = 2 ** attempt  # 2s, 4s, 8s 指数退避
    logger.warning("%s，%ds 后重试（第 %d/3 次）", reason, delay, attempt)
    time.sleep(delay)