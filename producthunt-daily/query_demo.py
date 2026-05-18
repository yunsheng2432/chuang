"""
演示：如何使用 SQLite 数据库查询历史数据
"""

from storage import load_history, get_latest_date

print("=" * 60)
print("ProductHunt 数据库查询演示")
print("=" * 60)

# 1️⃣ 查看最新的数据日期
latest_date = get_latest_date()
print(f"\n✅ 最新数据日期: {latest_date}")

# 2️⃣ 查询最近 7 天的所有数据
print(f"\n📊 查询最近 7 天的数据...")
records = load_history(days=7)
print(f"   共找到 {len(records)} 条记录\n")

# 3️⃣ 按日期分组显示
from collections import defaultdict

data_by_date = defaultdict(list)
for r in records:
    data_by_date[r['fetch_date']].append(r)

for date in sorted(data_by_date.keys(), reverse=True):
    items = data_by_date[date]
    print(f"\n📅 {date} ({len(items)} 个项目)")
    print("   " + "-" * 55)
    
    for item in items[:5]:  # 只显示前 5 个
        print(f"   #{item['rank']:2d} | {item['name'][:20]:20s} | {item['votes_count']:4d} 票")
    
    if len(items) > 5:
        print(f"   ... 还有 {len(items) - 5} 个项目")

# 4️⃣ 趋势分析：哪个产品最稳定（多天出现）
print("\n\n📈 趋势分析：哪些产品出现了多次？")
print("   " + "-" * 55)

product_appearances = defaultdict(list)
for r in records:
    product_appearances[r['name']].append({
        'date': r['fetch_date'],
        'rank': r['rank'],
        'votes': r['votes_count']
    })

# 找出出现 2 次以上的产品
repeated_products = {k: v for k, v in product_appearances.items() if len(v) > 1}

if repeated_products:
    for product_name, appearances in sorted(repeated_products.items(), key=lambda x: -len(x[1]))[:5]:
        print(f"\n   {product_name}")
        for app in appearances:
            print(f"      {app['date']} 排名 #{app['rank']} ({app['votes']} 票)")
else:
    print("   没有重复出现的产品（可能数据太新）")

# 5️⃣ 热门话题统计
print("\n\n🏷️ 热门话题统计：哪些标签最常见？")
print("   " + "-" * 55)

import json
from collections import Counter

all_topics = []
for r in records:
    try:
        topics = json.loads(r['topics'])
        all_topics.extend(topics)
    except:
        pass

if all_topics:
    topic_counts = Counter(all_topics)
    print()
    for topic, count in topic_counts.most_common(10):
        print(f"   {topic:20s} 出现 {count} 次")
else:
    print("   （暂无话题数据）")

print("\n" + "=" * 60)
