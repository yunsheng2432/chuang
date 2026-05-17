"""
ProductHunt 数据看板 - Streamlit 版本
运行方式: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import json
from collections import Counter
from datetime import datetime, timedelta
from storage import load_history, get_latest_date

# 页面配置
st.set_page_config(
    page_title="ProductHunt 每日热门产品",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚀 ProductHunt 每日热门产品看板")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 筛选选项")
    days = st.slider("查询天数", min_value=1, max_value=90, value=7)
    top_n = st.slider("每天显示 Top N", min_value=1, max_value=20, value=5)

# 获取数据
@st.cache_data
def get_data(days):
    return load_history(days=days)

records = get_data(days)

if not records:
    st.warning("📭 暂无数据，请先运行采集脚本")
    st.stop()

# 数据汇总
latest_date = get_latest_date()
total_records = len(records)
unique_dates = len(set(r['fetch_date'] for r in records))

# 显示统计卡片
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📊 总记录数", f"{total_records}")
with col2:
    st.metric("📅 采集天数", f"{unique_dates}")
with col3:
    st.metric("🔄 最新更新", latest_date or "无")
with col4:
    avg_votes = sum(r['votes_count'] for r in records) / len(records) if records else 0
    st.metric("📈 平均票数", f"{avg_votes:.0f}")

st.divider()

# ===== 1️⃣ 按日期显示排行榜 =====
st.header("1️⃣ 按日期排行榜")

from collections import defaultdict
data_by_date = defaultdict(list)
for r in records:
    data_by_date[r['fetch_date']].append(r)

for date in sorted(data_by_date.keys(), reverse=True)[:3]:  # 显示最近 3 天
    with st.expander(f"📅 {date} ({len(data_by_date[date])} 个产品)", expanded=(date == latest_date)):
        items = data_by_date[date][:top_n]
        
        # 用表格显示
        df = pd.DataFrame([
            {
                '排名': item['rank'],
                '产品名': item['name'],
                '票数': item['votes_count'],
                '标签': ', '.join(json.loads(item['topics']) if isinstance(item['topics'], str) else [])[:40],
                '官网': item['website']
            }
            for item in items
        ])
        
        st.dataframe(df, use_container_width=True)

st.divider()

# ===== 2️⃣ 趋势分析 =====
st.header("2️⃣ 📈 趋势分析：产品热度走势")

product_trends = defaultdict(list)
for r in records:
    product_trends[r['name']].append({
        'date': r['fetch_date'],
        'rank': r['rank'],
        'votes': r['votes_count']
    })

# 找出出现多次的产品
repeated_products = sorted(
    [(name, appearances) for name, appearances in product_trends.items() if len(appearances) > 1],
    key=lambda x: -len(x[1])
)

if repeated_products:
    selected_product = st.selectbox(
        "选择产品查看走势",
        options=[name for name, _ in repeated_products],
        format_func=lambda x: f"{x} ({len(product_trends[x])} 天)"
    )
    
    if selected_product:
        product_data = product_trends[selected_product]
        
        # 构建数据
        trend_df = pd.DataFrame([
            {
                '日期': app['date'],
                '排名': app['rank'],
                '票数': app['votes']
            }
            for app in sorted(product_data, key=lambda x: x['date'])
        ])
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.line_chart(
                trend_df.set_index('日期')[['票数']],
                use_container_width=True
            )
        
        with col2:
            st.dataframe(trend_df, use_container_width=True)
else:
    st.info("📌 需要至少 2 天的数据才能显示趋势")

st.divider()

# ===== 3️⃣ 热门标签分析 =====
st.header("3️⃣ 🏷️ 热门标签分析")

all_topics = []
for r in records:
    try:
        topics = json.loads(r['topics']) if isinstance(r['topics'], str) else r['topics']
        all_topics.extend(topics)
    except:
        pass

if all_topics:
    topic_counts = Counter(all_topics)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.metric("🏷️ 不同标签数", len(topic_counts))
    
    with col2:
        top_topics = dict(topic_counts.most_common(10))
        
        # 条形图
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 6))
        topics_names = list(top_topics.keys())
        topics_values = list(top_topics.values())
        
        bars = ax.barh(topics_names, topics_values, color='#1f77b4')
        ax.set_xlabel('出现次数')
        ax.set_title('Top 10 热门标签')
        
        # 在条形末尾显示数值
        for i, (bar, value) in enumerate(zip(bars, topics_values)):
            ax.text(value, i, f' {value}', va='center')
        
        plt.tight_layout()
        st.pyplot(fig)
else:
    st.info("📭 暂无标签数据")

st.divider()

# ===== 4️⃣ 数据导出 =====
st.header("4️⃣ 💾 数据导出")

# 导出为 CSV
df_export = pd.DataFrame(records)
csv_data = df_export.to_csv(index=False).encode('utf-8')

st.download_button(
    label="📥 下载为 CSV",
    data=csv_data,
    file_name=f"producthunt_data_{latest_date}.csv",
    mime="text/csv"
)

# 导出为 JSON
json_data = json.dumps(records, ensure_ascii=False, indent=2).encode('utf-8')

st.download_button(
    label="📥 下载为 JSON",
    data=json_data,
    file_name=f"producthunt_data_{latest_date}.json",
    mime="application/json"
)

st.divider()

# 页脚
st.caption(f"💡 数据最后更新: {latest_date} | 共 {total_records} 条记录 | 由 ProductHunt API 采集")
