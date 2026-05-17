"""
存储层 —— 将处理后的项目记录持久化到 SQLite 数据库。

调用方式:
    from storage import save_to_db
    save_to_db(posts, "2026-05-16")
"""

import json
import logging
import sqlite3
from pathlib import Path

import config

logger = logging.getLogger(__name__)

_TABLE_NAME = "daily_top_products"

_CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {_TABLE_NAME} (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_date  DATE NOT NULL,
    rank        INTEGER NOT NULL,
    name        TEXT NOT NULL,
    tagline     TEXT,
    description TEXT,
    votes_count INTEGER,
    website     TEXT,
    url         TEXT,
    topics      TEXT,
    thumbnail   TEXT,
    created_at  TIMESTAMP,
    UNIQUE(fetch_date, rank)
);
"""

_INSERT_SQL = f"""
INSERT OR REPLACE INTO {_TABLE_NAME}
    (fetch_date, rank, name, tagline, description, votes_count, website, url, topics, thumbnail, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def save_to_db(posts: list[dict], fetch_date: str) -> None:
    """将处理后的项目列表写入 SQLite。

    Args:
        posts: processor.process_posts() 返回的记录列表（已排序）。
        fetch_date: "YYYY-MM-DD" 采集日期。

    同一天重复写入时会覆盖旧数据（INSERT OR REPLACE），避免重复执行导致冗余记录。
    """
    db_path = _resolve_path()
    logger.info("写入数据库: %s, 日期=%s, 共 %d 条", db_path, fetch_date, len(posts))

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(_CREATE_TABLE_SQL)

        rows = [_to_row(p, i + 1, fetch_date) for i, p in enumerate(posts)]
        conn.executemany(_INSERT_SQL, rows)
        conn.commit()

        row_count = conn.execute(
            f"SELECT COUNT(*) FROM {_TABLE_NAME} WHERE fetch_date = ?", (fetch_date,)
        ).fetchone()[0]
        logger.info("写入完成: %d 条记录已持久化", row_count)
    finally:
        conn.close()


def load_history(days: int = 30) -> list[dict]:
    """查询最近 N 天的历史数据。

    Args:
        days: 查询天数，默认 30。

    Returns:
        按日期降序、排名升序的记录列表。
    """
    db_path = _resolve_path()
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT * FROM {_TABLE_NAME} "
            "WHERE fetch_date >= date('now', ?) "
            "ORDER BY fetch_date DESC, rank ASC",
            (f"-{days} days",),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_date() -> str | None:
    """获取数据库中最新一条记录的日期，供增量判断使用。"""
    db_path = _resolve_path()
    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            f"SELECT MAX(fetch_date) FROM {_TABLE_NAME}"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _resolve_path() -> Path:
    """解析数据库文件路径。相对路径基于项目根目录。"""
    path = Path(config.DB_PATH)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path


def _to_row(post: dict, rank: int, fetch_date: str) -> tuple:
    """将单条 post 记录转换为 INSERT 的 tuple 参数。"""
    return (
        fetch_date,
        rank,
        post.get("name", ""),
        post.get("tagline", ""),
        post.get("description", ""),
        post.get("votes_count", 0),
        post.get("website", ""),
        post.get("url", ""),
        json.dumps(post.get("topics", []), ensure_ascii=False),
        post.get("thumbnail", ""),
        post.get("created_at", ""),
    )