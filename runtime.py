def build_chat_openai_kwargs(model_name, base_url, api_key):
    return {
        "model": model_name,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": 0.3
    }

def raise_if_processing_failed(error_list):
    if len(error_list) > 0:
        raise RuntimeError(f"处理过程中出现 {len(error_list)} 个错误: {error_list}")
