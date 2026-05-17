"""
全局配置模块 —— 统一管理环境变量、API 端点和常量。
所有其他模块从此文件读取配置，不直接接触 os.environ。
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    _ENV_PATH = Path(__file__).resolve().parent / ".env"
    load_dotenv(_ENV_PATH)
except ImportError:
    pass  # CI 环境中不需要 python-dotenv

# ---- ProductHunt API ----
PRODUCTHUNT_API_URL = "https://api.producthunt.com/v2/api/graphql"
PRODUCTHUNT_TOKEN = os.environ.get("PRODUCTHUNT_TOKEN", "")  # 允许导入时为空，采集时由 fetcher 校验

# ---- 采集参数 ----
DEFAULT_TOP_N = 20                     # 每日拉取的 Top N 项目数
FETCH_DATE_OVERRIDE = os.environ.get("FETCH_DATE_OVERRIDE", "")  # 手动指定日期，空串表示自动取昨天

# ---- 文件路径 ----
DB_PATH = "producthunt.db"
REPORTS_DIR = "reports"

# ---- Webhook（可选） ----
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")  # 飞书/企业微信 Webhook 地址，留空则不推送

# ---- 日志 ----
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"