import requests
import json
import os
import sys
import importlib.util
from image_handler import ImageHandler

def load_instructions():
    """
    从可执行文件/脚本旁边的 prompt.py 外部文件加载 INSTRUCTIONS，
    如果不存在则回退到内部版本。
    """
    # 获取 EXE（如果已打包）或脚本所在的目录
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    prompt_path = os.path.join(base_path, 'prompt.py')

    # 尝试从外部文件加载（如果存在）
    if os.path.exists(prompt_path):
        try:
            # 使用 importlib 动态加载 Python 文件作为模块
            spec = importlib.util.spec_from_file_location("prompt_external", prompt_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'INSTRUCTIONS'):
                return module.INSTRUCTIONS
        except Exception as e:
            print(f" 警告：找到外部 prompt.py 但加载失败：{e}")
            print("  回退到内部提示词...")

    # 回退到内部提示词
    try:
        from prompt import INSTRUCTIONS
        return INSTRUCTIONS
    except ImportError:
        return "错误：找不到角色生成指令。"

try:
    from google import genai
    from google.genai.types import GoogleSearch
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

class APIHandler:
    """处理所有提供商的 API 通信"""

    INSTRUCTIONS = load_instructions()
    USER_PROMPT = "根据提供的内容和图片生成角色。"

    @staticmethod
    def _normalize_images(image_input):
        """将图片输入标准化为列表以支持多图片。"""
        if image_input is None:
            return []
        if isinstance(image_input, list):
            return [img for img in image_input if img is not None]
        return [image_input]

    @staticmethod
    def _combine_same_roles(messages):
        """合并具有相同角色（system-system、user-user）的相邻消息。"""
        if not messages:
            return messages

        combined = [messages[0]]
        for msg in messages[1:]:
            last = combined[-1]
            if msg.get("role") == last.get("role") and isinstance(msg.get("content"), str) and isinstance(last.get("content"), str):
                last["content"] = f"{last['content']}\n\n{msg['content']}"
            else:
                combined.append(msg)
        return combined

    @staticmethod
    def _build_openai_compatible_messages(config, instructions, content_text, images, provider):
        """
        构建兼容 OpenAI Chat Completions 格式的消息数组。
        适用于 OpenAI、Groq、OpenRouter 等使用 OpenAI 兼容 API 的提供商。
        """
        messages = []
        separate_system = config.get('separate_system_messages', False)
        content_role = 'system'

        # 预设/提示词消息必须作为第一个系统消息
        if instructions:
            messages.append({"role": "system", "content": instructions})

        # 将抓取/组装的内容添加为选定的角色
        if content_text and content_text.strip():
            messages.append({"role": content_role, "content": content_text.strip()})

        # 处理用户消息，支持多模态内容
        supports_vision = provider != "groq"

        if images and supports_vision:
            # 视觉模型的多模态内容
            user_content = [
                {"type": "text", "text": APIHandler.USER_PROMPT}
            ]

            added_images = 0
            for img in images:
                base64_image = ImageHandler.to_base64(img)
                if base64_image:
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    )
                    added_images += 1

            if added_images > 0:
                messages.append({"role": "user", "content": user_content})
            else:
                # 图片处理失败时的回退
                messages.append({"role": "user", "content": APIHandler.USER_PROMPT})
        else:
            # 仅文本内容
            messages.append({"role": "user", "content": APIHandler.USER_PROMPT})

        # 如果禁用了分离消息模式，合并相同角色的相邻消息
        if not separate_system:
            messages = APIHandler._combine_same_roles(messages)

        return messages

    @staticmethod
    def call_openai_style(config, content_text, instructions, image_objects):
        """处理 Groq/OpenRouter API 调用（OpenAI 兼容格式）"""
        provider = config['api_provider']
        api_key = config.get(f"{provider}_api_key")

        if not api_key or "YOUR_" in api_key:
            raise ValueError(f"{provider.title()} API 密钥未设置")

        # 获取当前提供商的正确模型
        provider_models = config.get('provider_models', {})
        model_name = provider_models.get(provider)
        if not model_name:
            # 如果未找到 provider_models 则回退到旧版 model_name
            model_name = config.get('model_name')

        if not model_name:
            raise ValueError(f"{provider} 的模型名称未指定")

        images = APIHandler._normalize_images(image_objects)
        messages = APIHandler._build_openai_compatible_messages(config, instructions, content_text, images, provider)

        # API 配置
        api_urls = {
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions"
        }

        api_url = api_urls.get(provider)
        if not api_url:
            raise ValueError(f"提供商 '{provider}' 没有 API URL")

        # 请求头 - OpenRouter 特定要求
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        if provider == "openrouter":
            headers.update({
                "HTTP-Referer": "http://localhost:3000",  # OpenRouter 要求
                "X-Title": "AI 角色创建器"  # 可选但推荐
            })

        # 负载，使用 OpenRouter 兼容的参数
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.7
        }

        # 调试输出
        print(f"API URL：{api_url}")
        print(f"模型：{model_name}")
        print(f"消息数量：{len(messages)}")

        try:
            # 发起 API 调用
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=600
            )
            if response.status_code != 200:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = f" - {error_data.get('error', {}).get('message', '未知错误')}"
                except:
                    error_detail = f" - {response.text[:200]}"

                raise ValueError(f"API 请求失败（HTTP {response.status_code}）{error_detail}")

            response.raise_for_status()
            data = response.json()

            # 验证响应结构
            if 'choices' not in data or not data['choices']:
                raise ValueError("API 响应中没有选项")

            if 'message' not in data['choices'][0]:
                raise ValueError("API 响应选项中没有消息")

            return data['choices'][0]['message']['content']

        except requests.exceptions.RequestException as e:
            raise ValueError(f"网络错误：{str(e)}")
        except json.JSONDecodeError as e:
            raise ValueError(f"无效的 JSON 响应：{str(e)}")

    @staticmethod
    def call_openai(config, content_text, instructions, image_objects):
        """处理 OpenAI API 调用，支持自定义 base_url 以兼容第三方服务"""
        api_key = config.get('openai_api_key')

        if not api_key or "YOUR_" in api_key:
            raise ValueError("OpenAI API 密钥未设置")

        provider_models = config.get('provider_models', {})
        model_name = provider_models.get('openai')
        if not model_name:
            model_name = config.get('model_name')

        if not model_name:
            raise ValueError("OpenAI 的模型名称未指定")

        images = APIHandler._normalize_images(image_objects)
        messages = APIHandler._build_openai_compatible_messages(config, instructions, content_text, images, "openai")

        # 支持 custom base_url，方便接入兼容 OpenAI 的第三方服务
        base_url = config.get('openai_base_url', '').strip()
        if base_url:
            # 确保 base_url 格式正确
            base_url = base_url.rstrip('/')
            if not base_url.endswith('/v1/chat/completions'):
                if base_url.endswith('/v1'):
                    api_url = f"{base_url}/chat/completions"
                elif base_url.endswith('/chat/completions'):
                    api_url = base_url
                else:
                    api_url = f"{base_url}/v1/chat/completions"
            else:
                api_url = base_url
        else:
            api_url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.7
        }

        # 调试输出
        print(f"API URL：{api_url}")
        print(f"模型：{model_name}")
        print(f"消息数量：{len(messages)}")

        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=600
            )

            if response.status_code != 200:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = f" - {error_data.get('error', {}).get('message', '未知错误')}"
                except:
                    error_detail = f" - {response.text[:200]}"

                raise ValueError(f"API 请求失败（HTTP {response.status_code}）{error_detail}")

            response.raise_for_status()
            data = response.json()

            if 'choices' not in data or not data['choices']:
                raise ValueError("API 响应中没有选项")

            if 'message' not in data['choices'][0]:
                raise ValueError("API 响应选项中没有消息")

            return data['choices'][0]['message']['content']

        except requests.exceptions.RequestException as e:
            raise ValueError(f"网络错误：{str(e)}")
        except json.JSONDecodeError as e:
            raise ValueError(f"无效的 JSON 响应：{str(e)}")

    @staticmethod
    def call_gemini(config, content_text, instructions, image_objects):
        """处理 Gemini API 调用"""
        if not genai:
            raise ImportError("'google-genai' 库未安装")

        api_key = config.get('gemini_api_key') or os.environ.get("GEMINI_API_KEY")
        if not api_key or "YOUR_" in api_key:
            raise ValueError("Gemini API 密钥未设置")

        client = genai.Client(api_key=api_key)
        content_role = 'system'

        provider_models = config.get('provider_models', {})
        model_name = provider_models.get('gemini')
        # 预设/提示词必须作为第一个系统内容。
        system_chunks = [instructions] if instructions else []
        user_content = []

        if content_text and content_text.strip():
            if content_role == 'system':
                system_chunks.append(content_text.strip())
            else:
                user_content.append(content_text.strip())

        images = APIHandler._normalize_images(image_objects)

        if images:
            user_content.append(APIHandler.USER_PROMPT)
            user_content.extend(images)
        else:
            user_content.append(APIHandler.USER_PROMPT)

        use_grounding = config.get('gemini_grounding', False)
        tools = [GoogleSearch] if use_grounding else None

        response = client.models.generate_content(
            model=model_name,
            config=genai_types.GenerateContentConfig(
                system_instruction="\n\n".join([chunk for chunk in system_chunks if chunk]),
                tools=tools
            ),
            contents=user_content
        )

        return response.text

    @staticmethod
    def build_content(base_content, additional_instructions):
        """构建 API 调用的内容负载和预设指令。"""
        content_chunks = []

        if base_content and base_content.strip():
            content_chunks.append(base_content.strip())

        if additional_instructions and additional_instructions.strip():
            content_chunks.append(f"附加指令：\n{additional_instructions.strip()}")

        content_text = "\n\n".join(content_chunks)
        return content_text, APIHandler.INSTRUCTIONS

    @staticmethod
    def generate_character(config, base_content, image_object=None, additional_instructions=None):
        """主要角色生成函数"""
        provider = config['api_provider']
        images = APIHandler._normalize_images(image_object)

        if not provider:
            raise ValueError("未配置 API 提供商")

        if images and provider == 'groq':
            print("警告：Groq 不支持图片输入。图片将被忽略。")
            images = []

        if not base_content and not images:
            raise ValueError("未提供内容")

        content_text, instructions = APIHandler.build_content(base_content, additional_instructions)

        print(f"正在向 {provider.title()} 发送请求...")

        if provider == "gemini":
            return APIHandler.call_gemini(config, content_text, instructions, images)
        elif provider == "openai":
            return APIHandler.call_openai(config, content_text, instructions, images)
        elif provider in ["groq", "openrouter"]:
            return APIHandler.call_openai_style(config, content_text, instructions, images)
        else:
            raise ValueError(f"未知的提供商 '{provider}'")
