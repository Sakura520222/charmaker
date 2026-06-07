import requests
import io
import base64
import tempfile
import os
from PIL import Image
from urllib.parse import urlparse, parse_qs
import file_dialogs

class ImageHandler:
    """处理图片加载、处理和验证"""

    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
    MAX_SIZE_MB = 11

    @staticmethod
    def is_image_url(url):
        """检查 URL 是否指向图片，处理复杂 URL"""
        if not url.lower().startswith('http'):
            return False

        # 解析 URL 并检查扩展名
        parsed = urlparse(url.lower())
        path = parsed.path

        # 在路径的任何位置查找扩展名，忽略扩展名后的内容
        # 例如，wiki/images/Alectra.png/revision/latest 会在此触发
        if any(f"{ext}/" in path or path.endswith(ext) for ext in ImageHandler.SUPPORTED_FORMATS):
            return True

        # 后备路径正则查找，用于带有查询参数或更深路径的图片
        import re
        if re.search(r'\.(jpg|jpeg|png|gif|webp|bmp)(/|\?|$)', url.lower()):
            return True

        image_indicators = ['image', 'img', 'photo', 'pic', 'thumb', 'avatar', 'banner']
        url_parts = url.lower().replace('/', ' ').replace('-', ' ').replace('_', ' ').split()

        # 仅当指标是独立的单词/段时才匹配
        if any(indicator in url_parts for indicator in image_indicators):
            return True

        image_domains = [
            'imgur.com', 'i.imgur.com',
            'images.unsplash.com', 'unsplash.com',
            'pixabay.com', 'pexels.com',
            'flickr.com', 'staticflickr.com',
            'googleusercontent.com',
            'amazonaws.com',
            'cloudfront.net',
            'cdn.discordapp.com',
            'media.discordapp.net'
        ]

        domain = parsed.netloc.lower()
        if any(img_domain in domain for img_domain in image_domains):
            return True

        query_params = parse_qs(parsed.query)
        image_format_params = ['f', 'format', 'type', 'ext']
        for param in image_format_params:
            if param in query_params:
                param_value = query_params[param][0].lower() if query_params[param] else ''
                if any(fmt.strip('.') in param_value for fmt in ImageHandler.SUPPORTED_FORMATS):
                    return True

        import re
        if re.search(r'/(images?|img|photos?|pics?|media)/.*\.(jpg|jpeg|png|gif|webp|bmp)$', path):
            return True

        return False

    @staticmethod
    def load_from_url(url, timeout=10):
        """从 URL 加载图片，带有健壮的错误处理"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, stream=True, timeout=timeout)
            response.raise_for_status()

            # 检查内容类型
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                print(f"警告：Content-Type 是 '{content_type}'，不是图片")

            # 检查文件大小
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > ImageHandler.MAX_SIZE_MB * 1024 * 1024:
                raise ValueError(f"图片过大：{int(content_length) / (1024*1024):.1f}MB")

            # 加载并验证图片
            image_data = response.content
            image = Image.open(io.BytesIO(image_data))
            image.verify()  # 验证是否为有效图片

            # 重新加载以供实际使用（verify() 会关闭文件）
            image = Image.open(io.BytesIO(image_data))
            print(f"✓ 图片已加载：{image.size[0]}x{image.size[1]} {image.format}")
            return image

        except requests.RequestException as e:
            print(f"✗ 加载图片时网络错误：{e}")
        except Exception as e:
            print(f"✗ 处理图片时出错：{e}")
        return None

    @staticmethod
    def load_from_file(filepath):
        """从本地文件加载图片"""
        try:
            if not os.path.exists(filepath):
                print(f"✗ 文件未找到：{filepath}")
                return None

            image = Image.open(filepath)
            print(f"✓ 图片已加载：{image.size[0]}x{image.size[1]} {image.format}")
            return image

        except Exception as e:
            print(f"✗ 打开图片文件时出错：{e}")
            return None

    @staticmethod
    def load_image(source):
        """通用图片加载器 - 处理 URL、文件路径或对话框"""
        if source == '!':
            filepath = file_dialogs.open_image_dialog()
            return ImageHandler.load_from_file(filepath) if filepath else None
        elif ImageHandler.is_image_url(source):
            return ImageHandler.load_from_url(source)
        elif os.path.exists(source):
            return ImageHandler.load_from_file(source)
        else:
            print(f"✗ 无效的图片来源：{source}")
            return None

    @staticmethod
    def to_base64(image, format='JPEG', quality=85):
        """将 PIL 图片转换为 base64 字符串"""
        try:
            # 将 RGBA/P 转换为 RGB 以用于 JPEG
            if format.upper() == 'JPEG' and image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')

            buffered = io.BytesIO()
            save_kwargs = {'format': format}
            if format.upper() == 'JPEG':
                save_kwargs['quality'] = quality

            image.save(buffered, **save_kwargs)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')

        except Exception as e:
            print(f"✗ 将图片转换为 base64 时出错：{e}")
            return None

    @staticmethod
    def save_temp_image(image_data, suffix='.png'):
        """将图片数据保存到临时文件"""
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temp_file.write(image_data)
            temp_file.close()
            return temp_file.name
        except Exception as e:
            print(f"✗ 保存临时图片时出错：{e}")
            return None

    @staticmethod
    def cleanup_temp_file(filepath):
        """清理临时文件"""
        if filepath and filepath.startswith(tempfile.gettempdir()):
            try:
                os.unlink(filepath)
            except OSError:
                pass
