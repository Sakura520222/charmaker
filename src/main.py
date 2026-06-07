import tiktoken
import os
import re
import requests
import tempfile
from image_handler import ImageHandler
from api_handler import APIHandler
from scraper import scrape_with_selenium, is_valid_url_format
from character_card import save_character_card, save_system_prompt
import config_manager
import file_dialogs

def parse_ai_response(ai_response):
    """从 AI 响应中提取角色字段"""
    character_details = {}
    keys = ["NAME", "DESCRIPTION", "PERSONALITY_SUMMARY", "SCENARIO", "GREETING_MESSAGE", "EXAMPLE_MESSAGES"]
    pattern = re.compile(r'(' + '|'.join(keys) + r')\s*:(.*?)(?=\n(?:' + '|'.join(keys) + r')\s*:|\Z)', re.DOTALL | re.IGNORECASE)

    for key, value in pattern.findall(ai_response):
        val = value.strip().replace('**', '').replace('*', '').strip()
        if key.upper().strip() == "NAME":
            val = val[:100]
        character_details[key.upper().strip()] = val

    return character_details

def get_inputs_from_user():
    """通过用户输入获取 URL 和图片，带有改进的验证"""
    urls_to_scrape, image_object = [], None
    print("\n--- 内容输入 ---")
    print("输入要抓取的 URL、图片 URL，或输入 '!' 选择本地文件。")
    print("输入 'done' 完成，或在空行上按回车。")

    while True:
        user_input = input("URL、图片 URL 或命令 (!): ").strip()

        # 检查退出条件
        if not user_input or user_input.lower() == 'done':
            break

        if user_input == '!':
            image_object = ImageHandler.load_image(user_input)
        elif ImageHandler.is_image_url(user_input):
            image_object = ImageHandler.load_image(user_input)
            if image_object:
                print("✓ 图片已从 URL 加载")
        else:
            # 作为普通 URL 处理
            url = user_input if user_input.startswith('http') else 'https://' + user_input

            # 使用 scraper.py 中的验证
            if is_valid_url_format(url):
                urls_to_scrape.append(url)
                print(f"✓ 已添加 '{url}' 到抓取列表")
            else:
                print(f"✗ 无效的 URL 格式：'{user_input}'")
    return urls_to_scrape, image_object

def get_character_image():
    """获取角色卡图片，带有改进的处理"""
    while True:
        print("\n选择角色卡的图片：")
        print("1. 默认模板 (./template.png)")
        print("2. 选择自定义图片文件")
        print("3. 从 URL 下载")

        choice = input("> ").strip()

        if choice == '1':
            return './template.png'
        elif choice == '2':
            return file_dialogs.open_image_dialog()
        elif choice == '3':
            url = input("输入图片 URL：").strip()
            if not url:
                continue

            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                temp_path = ImageHandler.save_temp_image(response.content)
                if temp_path:
                    print("✓ 图片下载成功")
                    return temp_path

            except Exception as e:
                print(f"✗ 下载图片时出错：{e}")
        else:
            print("无效的选择。")

def handle_save(character_details, save_location):
    """处理角色保存，包括图片选择"""
    image_path = get_character_image()
    if image_path and os.path.exists(image_path):
        save_character_card(character_details, image_path, save_location)
        # 如果是临时文件则清理
        ImageHandler.cleanup_temp_file(image_path)
        print("✓ 角色保存成功！")
    else:
        print("✗ 无有效的图片路径。保存已取消。")

def count_tokens(text, model="gpt-4"):
    """使用 tiktoken 计算 token 数量"""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

def _inject_language_instruction(preset_text, language):
    """将输出语言指令追加到预设末尾。"""
    if language and language != "与来源相同":
        return preset_text + f"\n\n<OUTPUT_LANGUAGE>\n你必须在输出中使用 {language}（{language}）。所有内容、描述、对话和文本都必须以 {language}（{language}）撰写。这是一项强制性要求。\n</OUTPUT_LANGUAGE>"
    return preset_text

def _prompt_output_language():
    """提示用户选择输出语言。"""
    languages = ["与来源相同", "中文", "English", "日本語", "한국어", "Español", "Français", "Deutsch", "Português", "Русский"]
    print("\n可选输出语言：")
    for i, lang in enumerate(languages, 1):
        print(f"  {i}. {lang}")
    choice = input(f"选择语言 (1-{len(languages)})，直接回车使用默认：").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(languages):
        return languages[int(choice) - 1]
    return "与来源相同"

def run_system_prompt_flow(config):
    """系统提示词生成工作流"""
    from presets import PRESET_SYSTEM_PROMPT

    engine = config.get('scraper_engine', 'legacy')
    if engine == 'crawl4ai' and not _is_crawl4ai_installed():
        print("\n✗ 错误：crawl4ai 未安装！")
        print("安装 crawl4ai，请运行：")
        print("  pip install crawl4ai")
        print("\n切换回旧版抓取器...")
        config['scraper_engine'] = 'legacy'
        config_manager.save_config(config)
        return

    urls, initial_image_object = get_inputs_from_user()
    if not urls and not initial_image_object:
        print("未提供任何内容。返回菜单。")
        return

    scraped_content = ""
    if urls:
        scraped_content = scrape_with_selenium(urls)
        if not scraped_content or not scraped_content.strip():
            print("警告：未抓取到文本内容。")

    if not scraped_content and not initial_image_object:
        print("✗ 抓取失败且未提供图片。")
        return

    content_info = []
    if scraped_content:
        token_count = count_tokens(scraped_content)
        content_info.append(f"文本（约 {token_count} tokens）")
    if initial_image_object:
        content_info.append("图片")

    if content_info:
        print(f"\n✓ 内容准备就绪：{' + '.join(content_info)}")

    initial_instructions = input("\n输入 AI 的附加指令（可选，按回车跳过）：\n> ").strip()

    # 选择输出语言
    output_lang = _prompt_output_language()

    if input("是否继续生成系统提示词？(yes/no)：").lower() not in ['yes', 'y', '1']:
        return

    # 使用系统提示词专用预设，注入语言指令
    APIHandler.INSTRUCTIONS = _inject_language_instruction(PRESET_SYSTEM_PROMPT, output_lang)
    APIHandler.USER_PROMPT = "根据提供的内容生成系统提示词。"

    content_for_generation = scraped_content
    image_for_generation = initial_image_object
    instructions_for_generation = initial_instructions

    while True:
        try:
            response_text = APIHandler.generate_character(
                config,
                content_for_generation,
                image_for_generation,
                instructions_for_generation
            )

            if not response_text or not response_text.strip():
                raise ValueError("未生成内容")

            print("\n--- 已生成的系统提示词 ---")
            print(response_text)

            action = input("\n1. 保存  2. 重试（附反馈）  3. 丢弃\n> ").strip()

            if action == '1':
                os.makedirs(config['save_location'], exist_ok=True)
                output_path = save_system_prompt(response_text, config['save_location'])
                if output_path:
                    print(f"✓ 系统提示词已保存至 {output_path}")
                else:
                    print("✗ 保存失败。")
                break
            elif action == '2':
                content_for_generation = response_text
                instructions_for_generation = input("\n输入反馈以优化上述文本：\n> ").strip()
                image_for_generation = None
                print("\n✓ 准备优化。之前的文本将用作新的上下文。")
            else:
                print("已丢弃。")
                break

        except Exception as e:
            print(f"✗ 生成失败：{e}")
            if input("是否重试？(yes/no)：").lower() not in ['y', 'yes', '1']:
                return

    # 恢复默认用户提示词
    APIHandler.USER_PROMPT = "根据提供的内容和图片生成角色。"


def run_character_creation_flow(config):
    """主要角色创建工作流"""
    # 检查所选抓取引擎是否可用
    engine = config.get('scraper_engine', 'legacy')
    if engine == 'crawl4ai' and not _is_crawl4ai_installed():
        print("\n✗ 错误：crawl4ai 未安装！")
        print("安装 crawl4ai，请运行：")
        print("  pip install crawl4ai")
        print("\n更多信息请访问：https://github.com/unclecode/crawl4ai")
        print("\n切换回旧版抓取器...")
        config['scraper_engine'] = 'legacy'
        config_manager.save_config(config)
        return

    urls, initial_image_object = get_inputs_from_user()
    if not urls and not initial_image_object:
        print("未提供任何内容。返回菜单。")
        return

    # 如果提供了 URL 则抓取内容
    scraped_content = ""
    if urls:
        scraped_content = scrape_with_selenium(urls)
        if not scraped_content or not scraped_content.strip():
            print("警告：未抓取到文本内容。")

    if not scraped_content and not initial_image_object:
        print("✗ 抓取失败且未提供图片。")
        return

    # 显示内容摘要
    content_info = []
    if scraped_content:
        token_count = count_tokens(scraped_content)
        content_info.append(f"文本（约 {token_count} tokens）")
    if initial_image_object:
        content_info.append("图片")

    if content_info:
        print(f"\n✓ 内容准备就绪：{' + '.join(content_info)}")

    initial_instructions = input("\n输入 AI 的附加指令（可选，按回车跳过）：\n> ").strip()

    # 选择输出语言
    output_lang = _prompt_output_language()

    if input("是否继续 AI 生成？(yes/no)：").lower() not in ['yes', 'y', '1']:
        return

    # 注入语言指令到当前预设
    if output_lang != "与来源相同":
        APIHandler.INSTRUCTIONS = _inject_language_instruction(APIHandler.INSTRUCTIONS, output_lang)


    # 这些变量保存当前生成尝试的状态
    content_for_generation = scraped_content
    image_for_generation = initial_image_object
    instructions_for_generation = initial_instructions

    while True:
        try:
            response_text = APIHandler.generate_character(
                config,
                content_for_generation,
                image_for_generation,
                instructions_for_generation
            )

            character_details = parse_ai_response(response_text)

            if not character_details or not character_details.get("NAME"):
                raise ValueError("未生成角色数据")

            print("\n--- 已生成的角色 ---")
            colors = {
                "NAME": "\033[93m",           # 黄色
                "DESCRIPTION": "\033[92m",    # 绿色
                "PERSONALITY_SUMMARY": "\033[94m",  # 蓝色
                "SCENARIO": "\033[94m",       # 蓝色
                "GREETING_MESSAGE": "\033[93m"  # 橙色（使用黄橙色）
            }
            reset_color = "\033[0m"  # 重置为默认

            for key in ["NAME", "DESCRIPTION", "PERSONALITY_SUMMARY", "SCENARIO", "GREETING_MESSAGE"]:
                value = character_details.get(key, 'N/A')
                color = colors.get(key, "")
                print(f"{color}{key}:{reset_color}")
                print(f"{color}{value}{reset_color}")
                print()  # 在各节之间添加空行

            action = input("\n1. 保存  2. 重试（附反馈）  3. 丢弃\n> ").strip()

            if action == '1':
                handle_save(character_details, config['save_location'])
                break
            elif action == '2':
                content_for_generation = response_text

                instructions_for_generation = input("\n输入反馈以优化上述文本：\n> ").strip()

                image_for_generation = None

                print("\n✓ 准备优化。之前的文本将用作新的上下文。")
            else:
                print("角色已丢弃。")
                break

        except Exception as e:
            print(f"✗ 生成失败：{e}")
            if input("是否重试？(yes/no)：").lower() not in ['y', 'yes', '1']:
                return

def update_config_setting(config, setting_key, prompt, valid_values=None):
    """统一的配置更新器 - 返回 None 表示留在菜单"""
    if setting_key == 'provider_change':
        current = config.get('api_provider', 'groq')
        providers = ['groq', 'openrouter', 'gemini', 'openai']
        print(f"\n当前提供商：{current}\n可用提供商：")
        for p in providers:
            key = config.get(f'{p}_api_key', '')
            status = '✓' if key and 'YOUR_' not in key else '✗'
            current_mark = ' (当前)' if p == current else ''
            print(f"  {status} {p}{current_mark}")

        new = input(f"输入新的提供商 ({'/'.join(providers)})：").lower().strip()
        if new in providers:
            if new == 'groq':
                print("\n⚠️  **警告！**\n最近 Groq 因违反其服务条款开始限制多账户使用，使用该服务时请非常小心，因为可能会导致您的组织受到限制。\n")
                input("按回车继续...")
            if config_manager.change_provider(config, new):
                print(f"✓ 提供商已更改为 {new}")
                return None  # 留在菜单
            print("提供商更改失败。请先配置 API 密钥。")
        else:
            print("无效的提供商选择。")

    elif setting_key == 'model_change':
        provider = config.get('api_provider', 'groq')
        model = config_manager.get_current_model(config)
        print(f"当前提供商：{provider}\n当前模型：{model}")
        new_model = input(f"输入 {provider} 的新模型名称：").strip()
        if new_model:
            config_manager.set_provider_model(config, provider, new_model)
            print(f"✓ 模型已更改为 {new_model}")
            return None  # 留在菜单
        print("未提供模型名称。")

    elif setting_key == 'api_key_setup':
        provider = input("输入要配置 API 密钥的提供商 (groq/openrouter/gemini/openai)：").lower().strip()
        if provider in ['groq', 'openrouter', 'gemini', 'openai']:
            api_key = input(f"输入 {provider} 的 API 密钥：").strip()
            if api_key:
                config[f'{provider}_api_key'] = api_key
                # OpenAI 额外支持自定义 Base URL
                if provider == 'openai':
                    current_base_url = config.get('openai_base_url', '')
                    print(f"当前自定义 Base URL（留空使用默认 https://api.openai.com）：{current_base_url}")
                    base_url = input("输入自定义 Base URL（直接回车跳过）：").strip()
                    config['openai_base_url'] = base_url
                config_manager.save_config(config)
                print(f"✓ {provider} 的 API 密钥配置成功！")
                return None  # 留在菜单
            print("未提供 API 密钥。")
        else:
            print("无效的提供商。")

    elif valid_values:
        value = input(f"{prompt} ({'/'.join(valid_values)})：").lower().strip()
        if value in valid_values:
            config[setting_key] = value
            config_manager.save_config(config)
            print(f"✓ {setting_key} 已更新为 {value}")
            return None  # 留在菜单
    else:
        value = input(f"{prompt}：").strip()
        if value:
            config[setting_key] = value
            config_manager.save_config(config)
            print(f"✓ {setting_key} 已更新为 {value}")
            return None  # 留在菜单

    return None  # 始终留在菜单

def _is_provider_ready(config):
    """检查当前提供商是否已配置"""
    provider = config.get('api_provider', 'groq')
    api_key = config.get(f'{provider}_api_key', '')
    if not api_key or 'YOUR_' in api_key:
        print(f"✗ 错误：{provider} 的 API 密钥未配置！")
        print("请先配置您的 API 密钥（选项 5）。")
        return False
    return True

def _change_save_location(config):
    """更改保存位置 - 返回 None 表示留在菜单"""
    new_path = file_dialogs.open_folder_dialog(config['save_location'])
    if new_path:
        config['save_location'] = new_path
        config_manager.save_config(config)
        print(f"✓ 保存位置已更新为：'{new_path}'")
    return None  # 留在菜单

def _toggle_separate_system_messages(config):
    """切换分离系统消息设置 - 返回 None 表示留在菜单"""
    current = config.get('separate_system_messages', False)
    config['separate_system_messages'] = not current
    config_manager.save_config(config)
    status = "已启用" if config['separate_system_messages'] else "已禁用"
    print(f"✓ 分离系统消息现已{status}。")
    return None  # 留在菜单

def _is_crawl4ai_installed():
    """检查 crawl4ai 库是否已安装"""
    try:
        import crawl4ai
        return True
    except ImportError:
        return False

def _exit_program():
    """退出程序 - 返回 True 以跳出循环"""
    print("正在退出程序。")
    return True

def _toggle_gemini_grounding(config):
    current = config.get('gemini_grounding', False)
    config['gemini_grounding'] = not current
    config_manager.save_config(config)
    status = "已启用" if config['gemini_grounding'] else "已禁用"
    print(f"✓ Gemini 搜索增强现已{status}。")
    return None

def _scraping_options_menu(config):
    while True:
        print(f"\n{'-'*40}")
        print("\t 抓取选项")
        print(f"{'-'*40}")

        engine = config.get('scraper_engine', 'legacy')
        headless = "已启用" if config.get('crawl4ai_headless', True) else "已禁用"

        print(f"  当前引擎：{engine}")
        if engine == 'crawl4ai':
            print(f"  无头模式（建议关闭）：{headless}")
        print(f"{'-'*40}")

        options = [
            "切换抓取引擎 (legacy / crawl4ai)"
        ]

        if _is_crawl4ai_installed():
            options.append("切换 Crawl4AI 无头模式")

        options.append("返回设置")

        for i, opt in enumerate(options, 1):
            print(f"{i}. {opt}")

        choice = input("\n选择选项 > ").strip()

        if choice == '1':
            value = input("选择引擎 (legacy/crawl4ai)：").lower().strip()
            if value == 'crawl4ai':
                if not _is_crawl4ai_installed():
                    print("\n✗ 错误：crawl4ai 未安装！")
                    print("安装 crawl4ai，请运行：")
                    print("  pip install crawl4ai")
                    print("\n更多信息请访问：https://github.com/unclecode/crawl4ai")
                else:
                    config['scraper_engine'] = value
                    config_manager.save_config(config)
                    print(f"✓ 抓取引擎已切换为 {value}")
            elif value == 'legacy':
                config['scraper_engine'] = value
                config_manager.save_config(config)
                print(f"✓ 抓取引擎已切换为 {value}")
            else:
                print("无效的引擎选择。")
        elif choice == '2':
            if _is_crawl4ai_installed():
                # 切换 Crawl4AI 无头模式
                current_h = config.get('crawl4ai_headless', True)
                config['crawl4ai_headless'] = not current_h
                config_manager.save_config(config)
                print(f"✓ 无头模式现已{'启用' if not current_h else '禁用'}。")
            else:
                # 如果未安装，选项 2 是 "返回设置"
                break
        elif choice == '3' and _is_crawl4ai_installed():
            break
        elif choice == '2' and not _is_crawl4ai_installed():
            # 未安装 crawl4ai 时的返回按钮
            break

def _settings_menu(config):
    """设置子菜单循环"""
    while True:
        print(f"\n{'-'*60}")
        print("\t\t\t 设置")
        print(f"{'-'*60}")

        provider = config.get('api_provider', 'groq')
        model = config_manager.get_current_model(config)
        api_key = config.get(f'{provider}_api_key', '')
        key_status = '✓ 已配置' if (api_key and 'YOUR_' not in api_key) else '✗ 未设置'

        print(f"  提供商：{provider.upper()} | 模型：{model}")
        print(f"  API 密钥：{key_status}")
        print(f"  保存位置：'{config['save_location']}'")
        separate_status = "已启用" if config.get('separate_system_messages', False) else "已禁用"
        print(f"  分离系统消息：{separate_status}")

        # 如果提供商是 gemini 则显示 Gemini 搜索增强状态
        if provider == 'gemini':
            grounding_status = "已启用" if config.get('gemini_grounding', False) else "已禁用"
            print(f"  Gemini 搜索增强：{grounding_status}")

        print(f"  预设方案：{config.get('preset', 'Preset 3')}")
        print(f"  抓取引擎：{config.get('scraper_engine', 'legacy')}")
        print(f"{'-'*60}")

        settings_options = [
            "更改保存位置",
            "切换提供商",
            "更改模型（当前提供商）",
            "配置 API 密钥",
            "切换分离系统消息",
            "预设方案选择"
        ]

        if provider == 'gemini':
            settings_options.append("切换 Gemini 搜索增强（Google 搜索）")

        settings_options.append("抓取选项")
        settings_options.append("返回主菜单")

        for i, opt in enumerate(settings_options, 1):
            print(f"{i}. {opt}")

        choice = input("\n选择选项 > ").strip()

        try:
            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(settings_options):
                raise ValueError()
            selected_opt = settings_options[choice_idx]
        except ValueError:
            print("无效的选项，请重试。")
            continue

        if selected_opt == "更改保存位置":
            _change_save_location(config)
        elif selected_opt == "切换提供商":
            update_config_setting(config, 'provider_change', '切换提供商')
        elif selected_opt == "更改模型（当前提供商）":
            update_config_setting(config, 'model_change', '更改模型')
        elif selected_opt == "配置 API 密钥":
            update_config_setting(config, 'api_key_setup', '配置 API 密钥')
        elif selected_opt == "切换分离系统消息":
            _toggle_separate_system_messages(config)
        elif selected_opt == "预设方案选择":
            update_config_setting(config, 'preset', '选择预设', ['preset 1', 'preset 2', 'preset 3'])
        elif selected_opt == "切换 Gemini 搜索增强（Google 搜索）":
            _toggle_gemini_grounding(config)
        elif selected_opt == "抓取选项":
            _scraping_options_menu(config)
        elif selected_opt == "返回主菜单":
            break

def main():
    """主应用程序循环"""
    config = config_manager.load_config()

    menu_actions = {
        '0': lambda: os.system('python interface.py') or _exit_program(),
        '1': lambda: run_character_creation_flow(config) if _is_provider_ready(config) else None,
        '2': lambda: run_system_prompt_flow(config) if _is_provider_ready(config) else None,
        '3': lambda: _settings_menu(config),
        '4': _exit_program
    }

    while True:
        os.makedirs(config['save_location'], exist_ok=True)

        print(f"\n{'='*60}")
        print("\t\t\t CharMaker")
        print(f"{'='*60}")

        menu_options = [
            "🪟  (新功能！) 切换到图形界面模式",
            "🚀 开始角色创建",
            "📝 生成系统提示词（LLM 聊天用）",
            "⚙️ 设置",
            "❌ 退出"
        ]

        for i, opt in enumerate(menu_options, 0):
            print(f"{i}. {opt}")

        choice = input("\n选择选项 > ").strip()

        if choice in menu_actions:
            result = menu_actions[choice]()
            if result is True:  # 仅在明确返回 True 时退出
                break
        else:
            print("无效的选项，请重试。")

if __name__ == "__main__":
    main()
