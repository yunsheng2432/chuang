"""
展示层 —— 生成 Markdown 日报文件，可选推送到飞书/企业微信 Webhook。

调用方式:
    from report import generate_markdown
    generate_markdown(posts, "2026-05-16")

    from report import push_webhook
    push_webhook(posts, "2026-05-16", "https://hooks.example.com/xxx")
"""

import logging
from datetime import datetime
from pathlib import Path

import requests

import config

logger = logging.getLogger(__name__)

_REPORT_TEMPLATE = """#  ProductHunt 每日热门项目 — {date_str}

> 统计日期：{date_str}  |  共 {total} 个项目  |  自动采集于 {now}

---

{entries}
"""

_ENTRY_TEMPLATE = """## {rank}. [{name}]({url})  —  {votes_count} 票

> {tagline}

{description}

**标签**: {topics}  |  **官网**: {website}

---

"""


def generate_markdown(posts: list[dict], date_str: str) -> str:
    """将处理后的项目列表生成 Markdown 日报，写入 reports/ 目录。

    Args:
        posts: processor.process_posts() 返回的记录列表（已排序）。
        date_str: "YYYY-MM-DD" 采集日期。

    Returns:
        生成的报告文件路径。
    """
    reports_dir = _resolve_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    entries = []
    for i, p in enumerate(posts, 1):
        topics = ", ".join(p.get("topics", [])[:8])
        if not topics:
            topics = "-"

        entries.append(_ENTRY_TEMPLATE.format(
            rank=i,
            name=p.get("name", ""),
            url=p.get("url", ""),
            votes_count=p.get("votes_count", 0),
            tagline=p.get("tagline", "") or "(无简介)",
            description=(p.get("description", "") or "")[:300],
            topics=topics,
            website=p.get("website", "") or "-",
        ))

    content = _REPORT_TEMPLATE.format(
        date_str=date_str,
        total=len(posts),
        now=now,
        entries="".join(entries),
    )

    file_path = reports_dir / f"report_{date_str}.md"
    file_path.write_text(content, encoding="utf-8")
    logger.info("日报已生成: %s (%d 个项目)", file_path, len(posts))
    return str(file_path)


def push_webhook(posts: list[dict], date_str: str, webhook_url: str, top_n: int = 5) -> None:
    """通过 Webhook 推送当日 Top N 摘要到 IM 工具。

    Args:
        posts: processor.process_posts() 返回的记录列表。
        date_str: "YYYY-MM-DD" 采集日期。
        webhook_url: 飞书/企业微信的 Webhook 地址。
        top_n: 推送前几名，默认 5。
    """
    if not webhook_url:
        logger.warning("未配置 Webhook URL，跳过推送")
        return

    tops = posts[:top_n]
    lines = [f"##  ProductHunt {date_str} Top {top_n}\n"]
    for i, p in enumerate(tops, 1):
        line = (
            f"{i}. **[{p.get('name', '')}]({p.get('url', '')})**  "
            f"{p.get('votes_count', 0)}票  —  {p.get('tagline', '')}"
        )
        lines.append(line)

    content = "\n".join(lines)
    payload = {"msgtype": "markdown", "markdown": {"content": content}}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Webhook 推送成功 (%d 条)", len(tops))
    except requests.RequestException as e:
        logger.warning("Webhook 推送失败: %s", e)


def _resolve_reports_dir() -> Path:
    path = Path(config.REPORTS_DIR)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path