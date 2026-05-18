"""
生成交互式单页 HTML 看板
运行方式: python producthunt-daily/generate_html.py
生成文件: docs/index.html — 自带全部数据和交互功能，可直接浏览器打开或部署 GitHub Pages
"""

import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from storage import load_history, get_latest_date


def generate_html():
    records = load_history(days=365)
    if not records:
        print("No data found")
        return

    latest_date = get_latest_date()

    # 按日期分组
    data_by_date = defaultdict(list)
    for r in records:
        data_by_date[r["fetch_date"]].append(r)

    all_dates = sorted(data_by_date.keys(), reverse=True)

    # 产品趋势
    product_trends = defaultdict(list)
    for r in records:
        product_trends[r["name"]].append({"date": r["fetch_date"], "votes": r["votes_count"], "rank": r["rank"]})

    repeated = sorted(
        [(n, a) for n, a in product_trends.items() if len(a) > 1],
        key=lambda x: -len(x[1])
    )

    # 标签统计
    all_topics_counter = Counter()
    for r in records:
        try:
            topics = json.loads(r["topics"]) if isinstance(r["topics"], str) else r["topics"]
            all_topics_counter.update(topics)
        except Exception:
            pass

    # 将每条记录转为前端友好的 JSON
    records_json = []
    for r in records:
        try:
            topics = json.loads(r["topics"]) if isinstance(r["topics"], str) else r["topics"]
        except Exception:
            topics = []
        records_json.append({
            "date": r["fetch_date"],
            "rank": r["rank"],
            "name": r["name"],
            "tagline": r.get("tagline", ""),
            "votes": r["votes_count"],
            "website": r.get("website", ""),
            "url": r.get("url", ""),
            "topics": topics,
        })

    # 嵌入 JS 数据
    data_js = json.dumps(records_json, ensure_ascii=False)
    dates_js = json.dumps(all_dates, ensure_ascii=False)
    trend_js = json.dumps({n: a for n, a in product_trends.items()}, ensure_ascii=False)
    topics_js = json.dumps(dict(all_topics_counter.most_common(20)), ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ProductHunt 每日热门产品看板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
header {{ text-align: center; color: white; margin-bottom: 30px; }}
header h1 {{ font-size: 2.2em; margin-bottom: 6px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 30px; }}
.stat-card {{ background: white; padding: 18px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,.1); text-align: center; }}
.stat-card .number {{ font-size: 1.8em; font-weight: bold; color: #667eea; }}
.stat-card .label {{ color: #666; margin-top: 6px; font-size: .9em; }}
.section {{ background: white; border-radius: 10px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 6px rgba(0,0,0,.1); }}
.section h2 {{ color: #333; margin-bottom: 16px; border-bottom: 3px solid #667eea; padding-bottom: 8px; font-size: 1.2em; }}
.controls {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 16px; }}
.controls select, .controls input {{ padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: .95em; }}
.controls label {{ font-weight: 600; color: #555; font-size: .9em; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ background: #f5f5f5; padding: 10px 12px; text-align: left; font-weight: bold; color: #333; border-bottom: 2px solid #ddd; font-size: .9em; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #eee; font-size: .95em; }}
tr:hover {{ background: #f9f9f9; }}
.rank {{ font-weight: bold; color: #667eea; font-size: 1.1em; }}
.votes {{ background: #e8f1ff; padding: 3px 8px; border-radius: 4px; font-weight: bold; color: #667eea; display: inline-block; }}
.tag {{ background: #f0f0f0; padding: 3px 8px; border-radius: 12px; font-size: .85em; color: #666; display: inline-block; margin: 2px; }}
.tag.active {{ background: #667eea; color: white; padding: 6px 14px; font-weight: bold; margin: 3px; }}
a {{ color: #667eea; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.chart-wrap {{ position: relative; height: 320px; margin: 12px 0; }}
.chart-wrap canvas {{ width: 100% !important; }}
footer {{ text-align: center; color: white; margin-top: 30px; padding: 20px; opacity: .8; font-size: .9em; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} .controls {{ flex-direction: column; align-items: stretch; }} }}
</style>
</head>
<body>
<div class="container">
<header>
    <h1>ProductHunt 每日热门产品</h1>
    <p>数据自动采集 · 每日更新 · 最近更新: {latest_date}</p>
</header>

<div class="stats">
    <div class="stat-card"><div class="number" id="stat-total">{len(records)}</div><div class="label">总记录数</div></div>
    <div class="stat-card"><div class="number" id="stat-days">{len(all_dates)}</div><div class="label">采集天数</div></div>
    <div class="stat-card"><div class="number" id="stat-latest">{latest_date}</div><div class="label">最新更新</div></div>
    <div class="stat-card"><div class="number" id="stat-avg">{sum(r["votes_count"] for r in records) // max(len(records), 1)}</div><div class="label">平均票数</div></div>
</div>

<div class="section">
    <h2>每日排行榜</h2>
    <div class="controls">
        <label>选择日期:</label>
        <select id="date-select"></select>
        <label>显示 Top:</label>
        <select id="topn-select">
            <option value="5">Top 5</option>
            <option value="10" selected>Top 10</option>
            <option value="15">Top 15</option>
            <option value="20">Top 20</option>
        </select>
    </div>
    <div id="ranking-table"></div>
</div>

<div class="two-col">
    <div class="section">
        <h2>产品热度趋势</h2>
        <div class="controls">
            <label>选择产品:</label>
            <select id="trend-select"></select>
        </div>
        <div class="chart-wrap"><canvas id="trend-chart"></canvas></div>
    </div>
    <div class="section">
        <h2>热门标签</h2>
        <div class="chart-wrap"><canvas id="topic-chart"></canvas></div>
        <div id="topic-tags" style="margin-top:12px;"></div>
    </div>
</div>

<footer>
    <p>由 ProductHunt API 自动采集 | 数据每日更新</p>
    <p><a href="https://github.com/yunsheng2432/chuang" style="color:white;">GitHub 仓库</a></p>
</footer>
</div>

<script>
// ==== 嵌入全部数据 ====
var ALL = {data_js};
var DATES = {dates_js};
var TRENDS = {trend_js};
var TOPICS = {topics_js};

// 按日期索引
var byDate = {{}};
ALL.forEach(function(r) {{
    if (!byDate[r.date]) byDate[r.date] = [];
    byDate[r.date].push(r);
}});

// ==== 日期选择器 ====
var ds = document.getElementById('date-select');
DATES.forEach(function(d) {{
    var opt = document.createElement('option');
    opt.value = d;
    opt.textContent = d;
    ds.appendChild(opt);
}});
ds.addEventListener('change', renderRanking);
document.getElementById('topn-select').addEventListener('change', renderRanking);

function renderRanking() {{
    var date = ds.value;
    var topn = parseInt(document.getElementById('topn-select').value);
    var items = (byDate[date] || []).slice(0, topn);
    var html = '<table><thead><tr><th>排名</th><th>产品</th><th>简介</th><th>票数</th><th>标签</th></tr></thead><tbody>';
    items.forEach(function(it) {{
        var tags = (it.topics||[]).slice(0,5).map(function(t){{return '<span class="tag">'+t+'</span>';}}).join('');
        html += '<tr><td class="rank">#'+it.rank+'</td>'+
            '<td><strong><a href="'+it.url+'" target="_blank">'+it.name+'</a></strong></td>'+
            '<td>'+(it.tagline||'').substring(0,60)+'</td>'+
            '<td><span class="votes">'+it.votes+'</span></td>'+
            '<td>'+tags+'</td></tr>';
    }});
    html += '</tbody></table>';
    if (items.length === 0) html = '<p style="color:#999;padding:20px;">该日期暂无数据</p>';
    document.getElementById('ranking-table').innerHTML = html;
}}

// ==== 趋势图 ====
var ts = document.getElementById('trend-select');
var trendNames = Object.keys(TRENDS).sort();
trendNames.forEach(function(n) {{
    var opt = document.createElement('option');
    opt.value = n;
    opt.textContent = n + ' (' + TRENDS[n].length + '天)';
    ts.appendChild(opt);
}});
ts.addEventListener('change', renderTrend);

var trendChart = null;
function renderTrend() {{
    var name = ts.value;
    var points = TRENDS[name] || [];
    points.sort(function(a,b){{return a.date.localeCompare(b.date);}});
    var labels = points.map(function(p){{return p.date;}});
    var votes = points.map(function(p){{return p.votes;}});
    if (trendChart) trendChart.destroy();
    var ctx = document.getElementById('trend-chart').getContext('2d');
    trendChart = new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: labels,
            datasets: [{{
                label: name + ' 票数',
                data: votes,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102,126,234,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#667eea'
            }}]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{ y: {{ beginAtZero: false, ticks: {{ font: {{ size: 11 }} }} }}, x: {{ ticks: {{ font: {{ size: 10 }} }} }} }}
        }}
    }});
}}

// ==== 标签图 ====
var topicLabels = Object.keys(TOPICS);
var topicValues = Object.values(TOPICS);
var topicChart = null;
function renderTopics() {{
    var ctx2 = document.getElementById('topic-chart').getContext('2d');
    topicChart = new Chart(ctx2, {{
        type: 'bar',
        data: {{
            labels: topicLabels,
            datasets: [{{
                label: '出现次数',
                data: topicValues,
                backgroundColor: topicLabels.map(function(_,i){{var h=240-i*10;return 'hsl('+h+',70%,60%)';}})
            }}]
        }},
        options: {{
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{ x: {{ ticks: {{ font: {{ size: 10 }} }} }}, y: {{ ticks: {{ font: {{ size: 10 }} }} }} }}
        }}
    }});

    var tagsHtml = topicLabels.map(function(t,i){{
        return '<span class="tag active">'+t+' ('+topicValues[i]+')</span>';
    }}).join(' ');
    document.getElementById('topic-tags').innerHTML = tagsHtml;
}}

// ==== 启动 ====
renderRanking();
if (trendNames.length > 0) {{ ts.value = trendNames[0]; renderTrend(); }}
renderTopics();
</script>
</body>
</html>"""

    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    output = docs_dir / "index.html"
    output.write_text(html, encoding="utf-8")
    print(f"Generated: {output} ({output.stat().st_size} bytes)")
    print(f"Open: file:///{output.absolute()}")


if __name__ == "__main__":
    generate_html()