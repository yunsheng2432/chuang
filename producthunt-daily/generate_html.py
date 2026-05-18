"""
生成静态 HTML 网页
运行方式: python generate_html.py
生成文件: docs/index.html 可直接在浏览器打开
"""

import json
from pathlib import Path
from collections import defaultdict, Counter
from storage import load_history, get_latest_date

def generate_html():
    """生成单页 HTML 网站"""
    
    records = load_history(days=30)
    if not records:
        print("❌ 暂无数据")
        return
    
    latest_date = get_latest_date()
    
    # 按日期分组
    data_by_date = defaultdict(list)
    for r in records:
        data_by_date[r['fetch_date']].append(r)
    
    # 热门标签
    all_topics = []
    for r in records:
        try:
            topics = json.loads(r['topics']) if isinstance(r['topics'], str) else r['topics']
            all_topics.extend(topics)
        except:
            pass
    
    topic_counts = Counter(all_topics)
    top_topics = topic_counts.most_common(10)
    
    # 产品趋势
    product_trends = defaultdict(list)
    for r in records:
        product_trends[r['name']].append({
            'date': r['fetch_date'],
            'votes': r['votes_count']
        })
    
    repeated_products = [
        (name, appearances) for name, appearances in product_trends.items() 
        if len(appearances) > 1
    ]
    repeated_products.sort(key=lambda x: -len(x[1]))
    
    # 生成 HTML
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProductHunt 每日热门产品数据看板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }}
        
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-align: center;
        }}
        
        .stat-card .number {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-card .label {{
            color: #666;
            margin-top: 10px;
        }}
        
        .section {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        .section h2 {{
            color: #333;
            margin-bottom: 20px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        
        .ranking-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        
        .ranking-table th {{
            background: #f5f5f5;
            padding: 12px;
            text-align: left;
            font-weight: bold;
            color: #333;
            border-bottom: 2px solid #ddd;
        }}
        
        .ranking-table td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}
        
        .ranking-table tr:hover {{
            background: #f9f9f9;
        }}
        
        .rank {{
            font-weight: bold;
            color: #667eea;
            font-size: 1.2em;
        }}
        
        .votes {{
            background: #e8f1ff;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            color: #667eea;
        }}
        
        .tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }}
        
        .tag {{
            background: #f0f0f0;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.9em;
            color: #666;
        }}
        
        .date-header {{
            background: #f5f5f5;
            padding: 15px;
            margin: 20px 0 15px 0;
            border-radius: 5px;
            font-weight: bold;
            color: #333;
        }}
        
        .chart-container {{
            position: relative;
            width: 100%;
            height: 300px;
            margin: 20px 0;
        }}
        
        footer {{
            text-align: center;
            color: white;
            margin-top: 40px;
            padding: 20px;
        }}
        
        footer p {{
            opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 ProductHunt 每日热门产品</h1>
            <p>数据自动采集 · 每日更新</p>
        </header>
        
        <div class="stats">
            <div class="stat-card">
                <div class="number">{len(records)}</div>
                <div class="label">总记录数</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(data_by_date)}</div>
                <div class="label">采集天数</div>
            </div>
            <div class="stat-card">
                <div class="number">{latest_date}</div>
                <div class="label">最新更新</div>
            </div>
            <div class="stat-card">
                <div class="number">{sum(r['votes_count'] for r in records) // len(records)}</div>
                <div class="label">平均票数</div>
            </div>
        </div>
        
        <!-- 排行榜 -->
        <div class="section">
            <h2>📊 每日排行榜（最近 3 天）</h2>
"""
    
    for date in sorted(data_by_date.keys(), reverse=True)[:3]:
        items = sorted(data_by_date[date], key=lambda x: x['rank'])[:10]
        
        html_content += f"""
            <div class="date-header">📅 {date} ({len(data_by_date[date])} 个产品)</div>
            <table class="ranking-table">
                <thead>
                    <tr>
                        <th style="width: 60px;">排名</th>
                        <th>产品名</th>
                        <th style="width: 100px;">票数</th>
                        <th>标签</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        for item in items:
            try:
                topics = json.loads(item['topics']) if isinstance(item['topics'], str) else item['topics']
                tags_html = ''.join(f'<span class="tag">{tag}</span>' for tag in topics[:3])
            except:
                tags_html = ''
            
            html_content += f"""
                    <tr>
                        <td class="rank">#{item['rank']}</td>
                        <td><strong>{item['name']}</strong></td>
                        <td class="votes">{item['votes_count']}</td>
                        <td><div class="tags">{tags_html}</div></td>
                    </tr>
"""
        
        html_content += """
                </tbody>
            </table>
"""
    
    # 热门标签
    html_content += """
        </div>
        
        <div class="section">
            <h2>🏷️ 热门标签</h2>
            <div class="tags" style="gap: 10px;">
"""
    
    for topic, count in top_topics:
        html_content += f'<span class="tag" style="background: #667eea; color: white; padding: 8px 12px; font-weight: bold;">{topic} <span style="opacity: 0.8;">({count})</span></span>'
    
    html_content += """
            </div>
        </div>
        
        <footer>
            <p>💡 由 ProductHunt API 自动采集 | 数据每日更新</p>
            <p style="font-size: 0.9em; margin-top: 10px;">最后更新: """ + latest_date + """</p>
        </footer>
    </div>
</body>
</html>
"""
    
    # 保存文件
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    
    output_file = docs_dir / "index.html"
    output_file.write_text(html_content, encoding='utf-8')
    
    print(f"✅ 网页已生成: {output_file}")
    print(f"📖 在浏览器打开: file:///{output_file.absolute()}")

if __name__ == "__main__":
    generate_html()
