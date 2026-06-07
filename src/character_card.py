import json
import base64
import os
import re
from PIL import Image
from PIL.PngImagePlugin import PngInfo

def sanitize_filename(name):
    """接受一个字符串并返回一个有效的文件名。"""
    if not name:
        return "unnamed_character"
    name = name.strip().replace('**', '').replace('*', '')
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name[:100]

def save_character_card(character_data, image_path, save_location):
    """使用 V3 格式将角色数据保存到 PNG 图片的 tEXt 块中。"""
    try:
        char_name = character_data.get("NAME", "")[:100]
        card = {
            "data": {
                "name": char_name,
                "description": character_data.get("DESCRIPTION", ""),
                "personality": character_data.get("PERSONALITY_SUMMARY", ""),
                "first_mes": character_data.get("GREETING_MESSAGE", ""),
                "avatar": "none",
                "mes_example": character_data.get("EXAMPLE_MESSAGES", ""),
                "scenario": character_data.get("SCENARIO", ""),
                "creator_notes": "",
                "system_prompt": "",
                "post_history_instructions": "",
                "alternate_greetings": [],
                "tags": [],
                "creator": "Anonymous",
                "character_version": "",
                "extensions": {
                    "depth_prompt": {
                        "prompt": "",
                        "depth": 0,
                        "role": "system"
                    },
                    "fav": False,
                    "talkativeness": "0.5",
                    "world": ""
                },
                "group_only_greetings": []
            },
            "spec": "chara_card_v3",
            "spec_version": "3.0",
            # 为了兼容性，这些字段在根级别重复
            "name": char_name,
            "fav": False,
            "description": character_data.get("DESCRIPTION", ""),
            "personality": character_data.get("PERSONALITY_SUMMARY", ""),
            "scenario": character_data.get("SCENARIO", ""),
            "first_mes": character_data.get("GREETING_MESSAGE", ""),
            "mes_example": character_data.get("EXAMPLE_MESSAGES", "")
        }

        chara_data_str = json.dumps(card, ensure_ascii=False)
        chara_data_base64 = base64.b64encode(chara_data_str.encode('utf-8')).decode('utf-8')

        img = Image.open(image_path)
        metadata = PngInfo()
        metadata.add_text("chara", chara_data_base64)

        clean_name = sanitize_filename(char_name)
        output_path = os.path.join(save_location, f"{clean_name}.png")

        img.save(output_path, "png", pnginfo=metadata)
        print(f"\n角色卡已成功保存到 {output_path}")

    except FileNotFoundError:
        print(f"错误：找不到图片路径 '{image_path}'。")
    except Exception as e:
        print(f"\n保存角色卡时出错：{e}")

def save_system_prompt(response_text, save_location):
    """将 AI 生成的系统提示词保存为文本文件。

    响应的第一行格式应为 'CHARACTER: [角色名]'，用于提取文件名。
    其余部分作为系统提示词正文保存。
    """
    try:
        lines = response_text.strip().split('\n')

        # 尝试从第一行提取角色名
        char_name = "character"
        prompt_lines = lines
        first_line = lines[0].strip()
        if first_line.upper().startswith('CHARACTER:'):
            char_name = first_line.split(':', 1)[1].strip()
            prompt_lines = lines[1:]
            # 去掉名称行后的空行
            while prompt_lines and not prompt_lines[0].strip():
                prompt_lines.pop(0)

        prompt_text = '\n'.join(prompt_lines)
        clean_name = sanitize_filename(char_name)
        output_path = os.path.join(save_location, f"{clean_name}_system_prompt.txt")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(prompt_text)

        print(f"\n系统提示词已保存到 {output_path}")
        return output_path

    except Exception as e:
        print(f"\n保存系统提示词时出错：{e}")
        return None
