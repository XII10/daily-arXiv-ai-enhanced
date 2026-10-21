import arxiv
import json
import os
from datetime import datetime, timedelta

# 你要的两个目标领域关键词
SEARCH_QUERIES = [
    "photocatalytic nitrogen fixation",
    "contact electrification nitrogen fixation"
]
# 只爬取最近7天的最新论文
TIME_RANGE = timedelta(days=7)

client = arxiv.Client(page_size=100)
all_papers = []

for query in SEARCH_QUERIES:
    search = arxiv.Search(
        query=query,
        max_results=50,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    for result in client.results(search):
        # 过滤掉超过7天的旧论文
        if result.published >= datetime.now(result.published.tzinfo) - TIME_RANGE:
            paper = {
                "id": result.entry_id.split("/")[-1],
                "title": result.title,
                "authors": [a.name for a in result.authors],
                "summary": result.summary,
                "published": str(result.published.date()),
                "pdf_url": result.pdf_url,
                "query_tag": query
            }
            all_papers.append(paper)

# 去重，避免同一篇论文被两个关键词重复抓取
unique_papers = list({p["id"]:p for p in all_papers}.values())

# 保存结果
output_file = f"arxiv_papers_{datetime.now().strftime('%Y%m%d')}.jsonl"
with open(output_file, "w", encoding="utf-8") as f:
    for p in unique_papers:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

print(f"成功爬取到 {len(unique_papers)} 篇最新目标领域论文，已保存到 {output_file}")
# 把文件名写到环境变量里，后面步骤自动读取
with open("latest_data_file.txt", "w") as f:
    f.write(output_file)
