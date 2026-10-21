import json
import os
from datetime import datetime

# 自动读取上一步AI处理完的文件
with open("latest_ai_file.txt", "r", encoding="utf-8") as f:
    ai_data_file = f.read().strip()

# 读取所有AI增强后的论文数据
papers = []
with open(ai_data_file, "r", encoding="utf-8") as f:
    for line in f:
        papers.append(json.loads(line))

# 生成Markdown汇总文档
today = datetime.now().strftime("%Y年%m月%d日")
md_content = f"# 光催化固氮 & 接触电催化固氮 最新文献周报\n"
md_content += f"生成日期：{today}\n"
md_content += f"本次共收录 {len(papers)} 篇最新arXiv预印本论文\n\n"

for idx, paper in enumerate(papers, 1):
    md_content += f"## {idx}. {paper['title']}\n"
    md_content += f"- 作者：{', '.join(paper['authors'])}\n"
    md_content += f"- 发表日期：{paper['published']}\n"
    md_content += f"- 论文链接：[{paper['pdf_url']}]({paper['pdf_url']})\n"
    if paper.get("code_url"):
        md_content += f"- 开源代码仓库：[{paper['code_url']}]({paper['code_url']})  Star数：{paper.get('code_stars', 0)}\n"
    md_content += "\n### 核心要点总结\n"
    ai_data = paper.get("AI", {})
    md_content += f"-  **一句话摘要** ：{ai_data.get('tldr', '无')}\n"
    md_content += f"-  **研究动机** ：{ai_data.get('motivation', '无')}\n"
    md_content += f"-  **核心方法** ：{ai_data.get('method', '无')}\n"
    md_content += f"-  **关键结果** ：{ai_data.get('result', '无')}\n"
    md_content += f"-  **最终结论** ：{ai_data.get('conclusion', '无')}\n\n"
    md_content += "---\n\n"

# 保存生成的Markdown文件
output_md = f"固氮领域文献周报_{datetime.now().strftime('%Y%m%d')}.md"
with open(output_md, "w", encoding="utf-8") as f:
    f.write(md_content)

print(f"Markdown汇总文档已生成：{output_md}")
# 把生成的md文件名写到环境变量文件，后面邮件步骤自动读取
with open("latest_md_file.txt", "w", encoding="utf-8") as f:
    f.write(output_md)
