"""
ProductHunt 数据看板 - Streamlit 版本
运行方式: cd producthunt-daily && streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import json
from collections import defaultdict, Counter
from storage import load_history, get_latest_date

st.set_page_config(
    page_title="ProductHunt 每日热门产品",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚀 ProductHunt 每日热门产品看板")

# ---- 加载全部数据 ----
@st.cache_data(ttl=60)
def get_all_data():
    return load_history(days=365)

records = get_all_data()

if not records:
    st.warning("📭 暂无数据，请先运行采集脚本（python main.py）")
    st.stop()

# 按日期分组
data_by_date = defaultdict(list)
for r in records:
    data_by_date[r["fetch_date"]].append(r)

all_dates = sorted(data_by_date.keys(), reverse=True)
latest_date = get_latest_date()

# ---- 侧边栏：日期选择 ----
with st.sidebar:
    st.header("📅 选择日期")
    date_option = st.radio(
        "查看方式",
        options=["最新一天", "选择指定日期", "查看全部日期"],
        index=0,
    )

    if date_option == "选择指定日期":
        selected_date = st.selectbox("选择日期", options=all_dates, index=0)
    elif date_option == "最新一天":
        selected_date = latest_date
    else:
        selected_date = None  # 全部

    st.divider()
    st.header("⚙️ 显示选项")
    top_n = st.slider("显示 Top N", min_value=1, max_value=20, value=10)

# ---- 统计卡片 ----
total_records = len(records)
unique_dates = len(all_dates)
avg_votes = sum(r["votes_count"] for r in records) // max(len(records), 1)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📊 总记录数", str(total_records))
with col2:
    st.metric("📅 采集天数", str(unique_dates))
with col3:
    st.metric("🔄 最新更新", latest_date or "无")
with col4:
    st.metric("📈 平均票数", str(avg_votes))

st.divider()

# ---- 排行榜 ----
if selected_date:
    st.header(f"📊 {selected_date} 排行榜")
    items = data_by_date.get(selected_date, [])[:top_n]

    if not items:
        st.info(f"{selected_date} 暂无数据")
    else:
        rows = []
        for item in items:
            try:
                topics = json.loads(item["topics"]) if isinstance(item["topics"], str) else item["topics"]
                topics_str = ", ".join(topics[:5])
            except Exception:
                topics_str = ""
            rows.append({
                "排名": item["rank"],
                "产品名": item["name"],
                "简介": (item.get("tagline") or "")[:60],
                "票数": item["votes_count"],
                "标签": topics_str,
                "官网": item.get("website", ""),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={
                         "官网": st.column_config.LinkColumn("官网"),
                         "排名": st.column_config.NumberColumn("排名", width="small"),
                         "票数": st.column_config.NumberColumn("票数", width="small"),
                     })
else:
    # 全部日期模式：每个日期一个 expander
    st.header(f"📊 全部日期排行榜（共 {unique_dates} 天）")
    for date in all_dates:
        items = data_by_date[date][:top_n]
        with st.expander(f"📅 {date} — Top {len(items)} 个项目", expanded=(date == latest_date)):
            rows = []
            for item in items:
                try:
                    topics = json.loads(item["topics"]) if isinstance(item["topics"], str) else item["topics"]
                    topics_str = ", ".join(topics[:5])
                except Exception:
                    topics_str = ""
                rows.append({
                    "排名": item["rank"],
                    "产品名": item["name"],
                    "简介": (item.get("tagline") or "")[:60],
                    "票数": item["votes_count"],
                    "标签": topics_str,
                    "官网": item.get("website", ""),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

# ---- 趋势分析 ----
st.header("📈 产品热度趋势")

product_trends = defaultdict(list)
for r in records:
    product_trends[r["name"]].append({
        "date": r["fetch_date"],
        "rank": r["rank"],
        "votes": r["votes_count"]
    })

repeated = sorted(
    [(name, apps) for name, apps in product_trends.items() if len(apps) > 1],
    key=lambda x: -len(x[1])
)

if repeated:
    selected_product = st.selectbox(
        "选择出现多天的产品查看票数走势",
        options=[name for name, _ in repeated],
        format_func=lambda x: f"{x}（出现 {len(product_trends[x])} 天）"
    )
    if selected_product:
        trend = sorted(product_trends[selected_product], key=lambda d: d["date"])
        trend_df = pd.DataFrame(trend)
        col1, col2 = st.columns([2, 1])
        with col1:
            st.line_chart(trend_df.set_index("date")[["votes"]], use_container_width=True)
        with col2:
            st.dataframe(trend_df.rename(columns={"date": "日期", "rank": "排名", "votes": "票数"}), hide_index=True)
else:
    st.info("需要至少 2 天数据才能显示趋势")

st.divider()

# ---- 热门标签 ----
st.header("🏷️ 热门标签")

all_topics = []
for r in records:
    try:
        topics = json.loads(r["topics"]) if isinstance(r["topics"], str) else r["topics"]
        all_topics.extend(topics)
    except Exception:
        pass

if all_topics:
    topic_counts = Counter(all_topics)
    top_topics = dict(topic_counts.most_common(15))

    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("🏷️ 不同标签数", str(len(topic_counts)))
        st.dataframe(
            pd.DataFrame(top_topics.items(), columns=["标签", "出现次数"]).set_index("标签"),
            use_container_width=True
        )
    with col2:
        st.bar_chart(pd.Series(top_topics, name="出现次数"), use_container_width=True)
else:
    st.info("暂无标签数据")

st.divider()

# ---- 导出 ----
st.header("💾 数据导出")

col1, col2 = st.columns(2)
with col1:
    csv = pd.DataFrame(records).to_csv(index=False).encode("utf-8")
    st.download_button("📥 下载 CSV", csv, f"producthunt_{latest_date}.csv", "text/csv")
with col2:
    st.download_button("📥 下载 JSON", json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8"),
                       f"producthunt_{latest_date}.json", "application/json")

st.caption(f"💡 数据最后更新: {latest_date} | 共 {total_records} 条记录 | 由 ProductHunt API 采集")