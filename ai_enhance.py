import os
import json
import sys
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from queue import Queue
from threading import Lock
import dotenv
import argparse
from tqdm import tqdm
import langchain_core.exceptions
from langchain_openai import ChatOpenAI
# ✅ 修改导入：使用 langchain_core.prompts
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from structure import Structure
from content_filter import is_sensitive
from runtime import build_chat_openai_kwargs, raise_if_processing_failed

if os.path.exists('.env'):
    dotenv.load_dotenv()

template = open("template.txt", "r", encoding="utf-8").read()
system = open("system.txt", "r", encoding="utf-8").read()

def parse_args():
    """解析命令行参数，适配Workflow无参数运行场景"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="", help="jsonline data file")
    parser.add_argument("--max_workers", type=int, default=2, help="Maximum number of parallel workers")
    # 自动读取上一步生成的最新数据文件
    args, unknown = parser.parse_known_args()
    if not args.data and os.path.exists("latest_data_file.txt"):
        with open("latest_data_file.txt", "r") as f:
            args.data = f.read().strip()
    return args

def process_single_item(chain, item: Dict, language: str) -> Dict:
    def check_github_code(content: str) -> Dict:
        """提取并验证 GitHub 链接"""
        code_info = {}
        # 1. 优先匹配 github.com/owner/repo 格式
        github_pattern = r"https?://github\.com/([a-zA-Z0-9-_]+)/([a-zA-Z0-9-_\.]+)"
        match = re.search(github_pattern, content)
        
        if match:
            owner, repo = match.groups()
            # 清理 repo 名称，去掉可能的 .git 后缀或末尾的标点
            repo = repo.rstrip(".git").rstrip(".,)")
            
            full_url = f"https://github.com/{owner}/{repo}"
            code_info["code_url"] = full_url
            
            # 尝试调用 GitHub API 获取信息
            github_token = os.environ.get("TOKEN_GITHUB")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"
            
            try:
                api_url = f"https://api.github.com/repos/{owner}/{repo}"
                resp = requests.get(api_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    code_info["code_stars"] = data.get("stargazers_count", 0)
                    code_info["code_last_update"] = data.get("pushed_at", "")[:10]
            except Exception:
                # API 调用失败不影响主流程
                pass
            return code_info
        # 2. 如果没有 github.com，尝试匹配 github.io
        github_io_pattern = r"https?://[a-zA-Z0-9-_]+\.github\.io(?:/[a-zA-Z0-9-_\.]+)*"
        match_io = re.search(github_io_pattern, content)
        
        if match_io:
            url = match_io.group(0)
            # 清理末尾标点
            url = url.rstrip(".,)")
            code_info["code_url"] = url
            # github.io 不进行 star 和 update 判断
                
        return code_info
    # 检查 summary 字段
    if is_sensitive(item.get("summary", "")):
        return None
    # 检测代码可用性
    code_info = check_github_code(item.get("summary", ""))
    if code_info:
        item.update(code_info)
    """处理单个数据项"""
    # Default structure with meaningful fallback values
    default_ai_fields = {
        "tldr": "Summary generation failed",
        "motivation": "Motivation analysis unavailable",
        "method": "Method extraction failed",
        "result": "Result analysis unavailable",
        "conclusion": "Conclusion extraction failed"
    }
    
    try:
        response: Structure = chain.invoke({
            "language": language,
            "content": item['summary']
        })
        item['AI'] = response.model_dump()
    except langchain_core.exceptions.OutputParserException as e:
        # 尝试从错误信息中提取 JSON 字符串并修复
        error_msg = str(e)
        partial_data = {}
        
        if "Function Structure arguments:" in error_msg:
            try:
                # 提取 JSON 字符串
                json_str = error_msg.split("Function Structure arguments:", 1)[1].strip().split('are not valid JSON')[0].strip()
                # 预处理 LaTeX 数学符号 - 使用四个反斜杠来确保正确转义
                json_str = json_str.replace('\\', '\\\\')
                # 尝试解析修复后的 JSON
                partial_data = json.loads(json_str)
            except Exception as json_e:
                print(f"Failed to parse JSON for {item.get('id', 'unknown')}: {json_e}", file=sys.stderr)
        
        # Merge partial data with defaults to ensure all fields exist
        item['AI'] = { **default_ai_fields, ** partial_data}
        print(f"Using partial AI data for {item.get('id', 'unknown')}: {list(partial_data.keys())}", file=sys.stderr)
     except Exception as e:
        import traceback
        err_msg = str(e)
        print(f"Unexpected error for {item.get('id', 'unknown')}: {err_msg}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)

        # 额度不足、余额不足场景，直接返回None跳过本条，不中断整体任务
        if "Insufficient Balance" in err_msg or "402" in err_msg or "quota" in err_msg or "余额" in err_msg:
            print(f"❗ 模型额度不足，跳过文献 {item.get('id', 'unknown')}", file=sys.stderr)
            return None
        else:
            # 其他未知异常继续抛出
            raise RuntimeError(f"AI request failed for {item.get('id', 'unknown')}") from e

    # Final validation to ensure all required fields exist
    for field in default_ai_fields.keys():
        if field not in item['AI']:
            item['AI'][field] = default_ai_fields[field]
    # 检查 AI 生成的所有字段
    for v in item.get("AI", {}).values():
        if is_sensitive(str(v)):
            return None
    return item

def process_all_items(data: List[Dict], model_name: str, language: str, max_workers: int) -> List[Dict]:
    """并行处理所有数据项，已完全适配DeepSeek接口"""
    llm = ChatOpenAI(
        **build_chat_openai_kwargs(
            model_name=model_name,
            base_url="https://api.deepseek.com/v1",
            api_key=os.environ.get("LLM_API_KEY", ""),
        )
    ).with_structured_output(Structure, method="function_calling")
    print('Connect to DeepSeek:', model_name, file=sys.stderr)
    
    prompt_template = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system),
        HumanMessagePromptTemplate.from_template(template=template)
    ])
    chain = prompt_template | llm
    
    # 使用线程池并行处理
    processed_data = [None] * len(data)  # 预分配结果列表
    processing_errors = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_idx = {
            executor.submit(process_single_item, chain, item, language): idx
            for idx, item in enumerate(data)
        }
        
        # 使用tqdm显示进度
        for future in tqdm(
            as_completed(future_to_idx),
            total=len(data),
            desc="Processing items"
        ):
            idx = future_to_idx[future]
            try:
                result = future.result()
                processed_data[idx] = result
            except Exception as e:
                print(f"Item at index {idx} generated an exception: {e}", file=sys.stderr)
                processing_errors.append(str(e))
                
    # raise_if_processing_failed(processing_errors)
    if processing_errors:
        print(f"⚠️ 共 {len(processing_errors)} 条文献发生AI处理异常，继续执行后续流程", file=sys.stderr)

    return processed_data

def main():
    args = parse_args()
    # DeepSeek官方推荐模型名，直接生效
    model_name = os.environ.get("MODEL_NAME", "deepseek-chat")
    language = os.environ.get("LANGUAGE", 'Chinese')
    # 检查并删除目标文件
    target_file = args.data.replace('.jsonl', f'_AI_enhanced_{language}.jsonl')
    if os.path.exists(target_file):
        os.remove(target_file)
        print(f'Removed existing file: {target_file}', file=sys.stderr)
    # 读取数据
    data = []
    with open(args.data, "r", encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
    # 去重
    seen_ids = set()
    unique_data = []
    for item in data:
        if item['id'] not in seen_ids:
            seen_ids.add(item['id'])
            unique_data.append(item)
    data = unique_data
    print('Open:', args.data, file=sys.stderr)
    
    # 并行处理所有数据
    processed_data = process_all_items(
        data,
        model_name,
        language,
        args.max_workers
    )
    
    # 保存结果
    with open(target_file, "w", encoding="utf-8") as f:
        for item in processed_data:
            if item is not None:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
    # 把AI处理后的文件名写到环境变量文件，后面步骤自动读取
    with open("latest_ai_file.txt", "w") as f:
        f.write(target_file)

if __name__ == "__main__":
    main()
