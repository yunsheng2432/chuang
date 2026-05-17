"""
调度入口 —— 由 GitHub Actions 在每日 UTC 01:00 调用。
负责按顺序串联所有下游模块：采集 → 处理 → 存储 → 报告。
"""

import logging
from datetime import datetime, timedelta, timezone

import config

logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

# ---- 各模块导入（按层逐步构建，未构建的模块以占位形式存在） ----
# 模块 2：数据采集层
try:
    from fetcher import fetch_daily_top
except ImportError:
    fetch_daily_top = None  # type: ignore
    logger.warning("fetcher 模块尚未实现")

# 模块 3：数据处理层
try:
    from processor import process_posts
except ImportError:
    process_posts = None  # type: ignore
    logger.warning("processor 模块尚未实现")

# 模块 4：存储层
try:
    from storage import save_to_db
except ImportError:
    save_to_db = None  # type: ignore
    logger.warning("storage 模块尚未实现")

# 模块 5：展示层
try:
    from report import generate_markdown, push_webhook
except ImportError:
    generate_markdown = None  # type: ignore
    push_webhook = None  # type: ignore
    logger.warning("report 模块尚未实现")


def resolve_fetch_date() -> str:
    """确定本次采集的目标日期。

    Returns:
        "YYYY-MM-DD" 格式的日期字符串（UTC 时区）。
        优先使用手动指定的 FETCH_DATE_OVERRIDE，否则默认为昨天。
    """
    if config.FETCH_DATE_OVERRIDE:
        logger.info("使用手动指定的采集日期: %s", config.FETCH_DATE_OVERRIDE)
        return config.FETCH_DATE_OVERRIDE

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def main() -> None:
    """主流程：串联采集 → 处理 → 存储 → 报告。"""
    fetch_date = resolve_fetch_date()
    logger.info("===== 开始采集 ProductHunt %s 的 Top %d 项目 =====", fetch_date, config.DEFAULT_TOP_N)

    # ---- 1. 数据采集 ----
    if fetch_daily_top is None:
        logger.error("fetcher 模块未实现，终止。")
        return
    logger.info("[1/4] 正在从 ProductHunt API 拉取数据...")
    raw_data = fetch_daily_top(n=config.DEFAULT_TOP_N, date_str=fetch_date)
    logger.info("[1/4] 数据拉取完成，共 %d 条原始记录", len(raw_data.get("data", {}).get("posts", {}).get("edges", [])))

    # ---- 2. 数据处理 ----
    if process_posts is None:
        logger.error("processor 模块未实现，终止。")
        return
    logger.info("[2/4] 正在清洗和排序数据...")
    posts = process_posts(raw_data)
    logger.info("[2/4] 数据处理完成，有效记录 %d 条", len(posts))

    # ---- 3. 数据存储 ----
    if save_to_db is None:
        logger.error("storage 模块未实现，终止。")
        return
    logger.info("[3/4] 正在写入数据库...")
    save_to_db(posts, fetch_date)
    logger.info("[3/4] 数据库写入完成")

    # ---- 4. 生成日报 ----
    if generate_markdown is None:
        logger.warning("report 模块未实现，跳过日报生成。")
    else:
        logger.info("[4/4] 正在生成 Markdown 日报...")
        generate_markdown(posts, fetch_date)
        logger.info("[4/4] 日报已生成至 %s/report_%s.md", config.REPORTS_DIR, fetch_date)

    # ---- 5. Webhook 推送（可选） ----
    if push_webhook is not None and config.WEBHOOK_URL:
        logger.info("[5/5] 正在推送 Webhook...")
        push_webhook(posts, fetch_date, config.WEBHOOK_URL)
    elif config.WEBHOOK_URL:
        pass  # push_webhook 未导入
    else:
        logger.info("未配置 Webhook，跳过推送")

    logger.info("===== 采集完成 =====")


if __name__ == "__main__":
    main()