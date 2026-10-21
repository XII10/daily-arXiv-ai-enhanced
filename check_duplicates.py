import json
import os

# 读取上一步生成的最新数据文件名
with open("latest_data_file.txt", "r") as f:
    data_file = f.read().strip()

# 读取历史已推送过的论文ID，避免重复推送
history_ids = set()
if os.path.exists("history_paper_ids.txt"):
    with open("history_paper_ids.txt", "r") as f:
        history_ids = set(line.strip() for line in f)

# 过滤掉已经推送过的旧论文
new_papers = []
with open(data_file, "r") as f:
    for line in f:
        paper = json.loads(line)
        if paper["id"] not in history_ids:
            new_papers.append(paper)
            history_ids.add(paper["id"])

# 保存过滤后的新论文
with open(data_file, "w", encoding="utf-8") as f:
    for p in new_papers:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

# 更新历史ID库
with open("history_paper_ids.txt", "w") as f:
    for pid in history_ids:
        f.write(pid + "\n")

print(f"去重完成，剩余 {len(new_papers)} 篇未推送的新论文")
