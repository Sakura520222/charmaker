import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
DEFAULT_CONFIG = {
    "save_location": "saved_characters",
    "api_provider": "groq",
    "dark_mode": False,
    "preset": "Preset 3",
    "check_token_count": True,
    "groq_api_key": "YOUR_GROQ_API_KEY_HERE",
    "openrouter_api_key": "YOUR_OPENROUTER_API_KEY_HERE",
    "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
    "openai_api_key": "YOUR_OPENAI_API_KEY_HERE",
    "openai_base_url": "",
    "separate_system_messages": False,
    "output_language": "与来源相同",
    "browser_config": {
        "browser_type": None,
        "binary_path": None
    },
    # 各提供商专属模型配置
    "provider_models": {
        "groq": "llama-3.1-70b-versatile",
        "openrouter": "openai/gpt-4o-mini",
        "gemini": "gemini-2.0-flash-exp",
        "openai": "gpt-4o-mini"
    }
}

def load_config():
    """从 config.json 加载配置，如果不存在则创建。"""
    if not os.path.exists(CONFIG_FILE):
        print(f"未找到配置文件。正在创建 '{CONFIG_FILE}' 并使用默认值。")
        config = DEFAULT_CONFIG.copy()
        save_config(config)
    else:
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)

            for key, value in DEFAULT_CONFIG.items():
                if key not in config and key != "model_name":
                    config[key] = value

            # 迁移：将旧的 model_name 转换为提供商专属模型
            if "model_name" in config and "provider_models" not in config:
                print("正在迁移配置到提供商专属模型...")
                config["provider_models"] = DEFAULT_CONFIG["provider_models"].copy()
                # 尝试为当前提供商保留旧模型
                current_provider = config.get("api_provider", "groq")
                if current_provider in config["provider_models"]:
                    config["provider_models"][current_provider] = config["model_name"]

                print("迁移完成后移除旧版 model_name 字段。")
                del config["model_name"]
                save_config(config)

            if "provider_models" in config:
                for provider in DEFAULT_CONFIG["provider_models"]:
                    if provider not in config["provider_models"]:
                        config["provider_models"][provider] = DEFAULT_CONFIG["provider_models"][provider]

        except (json.JSONDecodeError, IOError) as e:
            print(f"读取配置文件时出错：{e}。加载默认配置。")
            config = DEFAULT_CONFIG.copy()

    return config

def save_config(config_data):
    """将给定的配置字典保存到 config.json。"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
        print("配置保存成功。")
    except IOError as e:
        print(f"保存配置文件时出错：{e}")

def get_current_model(config):
    """获取当前提供商的模型名称。"""
    current_provider = config.get("api_provider", "groq")
    provider_models = config.get("provider_models", {})

    # 如果可用则返回提供商专属模型
    if current_provider in provider_models:
        return provider_models[current_provider]

    # 回退到旧版 model_name
    return config.get("model_name", DEFAULT_CONFIG["provider_models"].get(current_provider, ""))

def set_provider_model(config, provider, model_name):
    """设置指定提供商的模型名称。"""
    if "provider_models" not in config:
        config["provider_models"] = DEFAULT_CONFIG["provider_models"].copy()

    config["provider_models"][provider] = model_name
    save_config(config)
    print(f"{provider} 的模型已设置为：{model_name}")

def change_provider(config, new_provider):
    """切换当前提供商，同时保留所有 API 密钥和模型。"""
    valid_providers = ["groq", "openrouter", "gemini", "openai"]
    if new_provider not in valid_providers:
        print(f"无效的提供商：{new_provider}")
        return False

    old_provider = config.get("api_provider")
    config["api_provider"] = new_provider

    current_model = get_current_model(config)
    print(f"已从 {old_provider} 切换到 {new_provider}")
    print(f"使用模型：{current_model}")

    # 检查 API 密钥是否已配置
    api_key = config.get(f"{new_provider}_api_key", "")
    if not api_key or "YOUR_" in api_key:
        print(f"警告：{new_provider} 的 API 密钥未配置！")
        return False

    save_config(config)
    return True

def get_provider_info(config):
    """获取所有提供商的综合信息。"""
    current_provider = config.get("api_provider", "groq")
    provider_models = config.get("provider_models", {})

    info = {
        "current_provider": current_provider,
        "current_model": get_current_model(config),
        "providers": {}
    }

    for provider in ["groq", "openrouter", "gemini", "openai"]:
        api_key = config.get(f"{provider}_api_key", "")
        has_key = api_key and "YOUR_" not in api_key
        model = provider_models.get(provider, "未设置")

        info["providers"][provider] = {
            "has_api_key": has_key,
            "model": model,
            "is_current": provider == current_provider
        }

    return info

# 向后兼容函数
def get_model_name(config):
    """旧版兼容函数。"""
    return get_current_model(config)
