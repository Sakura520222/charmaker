import json
import base64
import re
import os
from PIL import Image
import piexif

def sanitize_filename(name):
    """接受一个字符串并返回一个有效的文件名。"""
    if not name:
        return "unnamed_character"
    name = name.strip().replace('**', '').replace('*', '')
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name[:100]

def save_character_card(character_data, image_path, save_location):
    """
    将角色数据保存到 PNG 图片的元数据中。

    参数：
        character_data (dict): 角色数据。
        image_path (str): 源 PNG 图片的路径。
        save_location (str): 保存新图片的目录。
    """
    try:
        char_name = character_data.get("NAME", "character")[:100]
        # 构建详细的角色卡结构
        card = {
            "name": char_name,
            "description": character_data.get("DESCRIPTION", ""),
            "personality": character_data.get("PERSONALITY_SUMMARY", ""),
            "scenario": character_data.get("SCENARIO", ""),
            "first_mes": character_data.get("GREETING_MESSAGE", ""),
            "mes_example": character_data.get("EXAMPLE_MESSAGES", ""),
            "creatorcomment": "",
            "avatar": "none",
            "talkativeness": "0.5",
            "fav": False,
            "tags": [],
            "spec": "chara_card_v2",
            "spec_version": "2.0",
            "data": {
                "name": char_name,
                "description": character_data.get("DESCRIPTION", ""),
                "personality": character_data.get("PERSONALITY_SUMMARY", ""),
                "scenario": character_data.get("SCENARIO", ""),
                "first_mes": character_data.get("GREETING_MESSAGE", ""),
                "mes_example": character_data.get("EXAMPLE_MESSAGES", ""),
                "creator_notes": "",
                "system_prompt": "",
                "post_history_instructions": "",
                "tags": [],
                "creator": "",
                "character_version": "",
                "alternate_greetings": [],
                "extensions": {
                    "talkativeness": "0.5",
                    "fav": False,
                    "world": "",
                    "depth_prompt": {
                        "prompt": "",
                        "depth": 4,
                        "role": "system"
                    }
                },
                "group_only_greetings": []
            },
            "create_date": "2025-07-27 @18:16:41.697"  # 占位日期
        }

        # 使用 base64 编码数据
        chara_data_str = json.dumps(card)
        chara_data_base64 = base64.b64encode(chara_data_str.encode('utf-8')).decode('utf-8')

        # 打开图片并插入元数据
        img = Image.open(image_path)
        exif_dict = {"Exif": {piexif.ImageIFD.MakerNote: chara_data_base64.encode('utf-8')}}
        exif_bytes = piexif.dump(exif_dict)

        # 保存新图片
        clean_name = sanitize_filename(char_name)
        output_path = os.path.join(save_location, f"{clean_name}.png")
        img.save(output_path, "png", exif=exif_bytes)
        print(f"角色卡已保存到 {output_path}")

    except Exception as e:
        print(f"保存角色卡时出错：{e}")

def save_as_json(character_data, save_location):
    """
    将角色数据保存为 JSON 文件。

    参数：
        character_data (dict): 要保存的角色数据。
        save_location (str): 保存 JSON 文件的目录。
    """
    try:
        char_name = character_data.get("NAME", "character")[:100]
        clean_name = sanitize_filename(char_name)
        file_path = os.path.join(save_location, f"{clean_name}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(character_data, f, indent=4)
        print(f"角色数据已保存到 {file_path}")
    except IOError as e:
        print(f"保存 JSON 文件时出错：{e}")
