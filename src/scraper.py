import time
import re
import ssl
import os
import urllib3
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup, NavigableString, Tag, Comment
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import config_manager
except ImportError:
    # 后备模拟，以防某些环境缺少该模块
    class _MockConfig:
        def load_config(self): return {}
        def save_config(self, cfg): pass
    config_manager = _MockConfig()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TLSAdapter(HTTPAdapter):
    """自定义适配器，用于稳健地处理各种 TLS/SSL 配置。"""
    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        if self.ssl_context:
            kwargs['ssl_context'] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)


def create_session_with_retries(retries=3, backoff_factor=0.5, verify_ssl=True):
    """创建一个高度稳健的请求会话，带有现代反爬虫请求头和 SSL 回退。"""
    session = requests.Session()

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )

    if not verify_ssl:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        ssl_context.set_ciphers('DEFAULT:@SECLEVEL=1')
        adapter = TLSAdapter(ssl_context=ssl_context, max_retries=retry_strategy)
    else:
        adapter = HTTPAdapter(max_retries=retry_strategy)

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 现代化请求头，模拟真实 Chromium 浏览器以绕过基本 WAF
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Connection': 'keep-alive',
    })

    return session


def is_valid_url_format(url):
    """快速 URL 格式验证。"""
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme in ['http', 'https'] and parsed.netloc and '.' in parsed.netloc)
    except Exception:
        return False


def is_valid_url(url):
    """检查 URL 是否可访问，智能处理 SSL 和超时。"""
    if not is_valid_url_format(url):
        return False, "URL 格式无效"

    try:
        session = create_session_with_retries(retries=1, verify_ssl=True)
        response = session.head(url, timeout=10, allow_redirects=True)

        if response.status_code >= 400:
            return False, f"HTTP {response.status_code} 错误"
        return True, "有效"

    except (requests.exceptions.SSLError, ssl.SSLError):
        try:
            session = create_session_with_retries(retries=1, verify_ssl=False)
            response = session.head(url, timeout=10, allow_redirects=True, verify=False)
            if response.status_code >= 400:
                return False, f"HTTP {response.status_code} 错误"
            return True, "有效（已绕过 SSL）"
        except Exception as e:
            return False, f"SSL 绕过失败：{e}"

    except requests.exceptions.ConnectionError:
        return False, "连接失败 - 网站可能已关闭或需要 JavaScript/浏览器"
    except requests.exceptions.Timeout:
        return False, "连接超时 - 需要浏览器渲染"
    except Exception as e:
        return False, f"错误：{str(e)}"


def get_urls():
    """交互式 URL 收集器。"""
    urls = []
    print("输入要抓取的 URL。输入 'done' 完成。")

    while True:
        url = input("URL：").strip()
        if url.lower() == 'done' or not url:
            break

        if not re.match(r'^https?:\/\/', url):
            url = 'https://' + url

        if not is_valid_url_format(url):
            print(f"✗ 无效的 URL 格式：{url}")
            continue

        print(f"正在验证 {url}...")
        is_valid, message = is_valid_url(url)

        if is_valid:
            urls.append(url)
            print(f"✓ 已添加：{url}")
        else:
            print(f"⚠ {message}")
            force = input("仍然添加？该网站可能严格要求真实浏览器 (y/N)：").lower().strip()
            if force in ['y', 'yes', '1']:
                urls.append(url)
                print(f"✓ 已添加（强制）：{url}")

    return urls


def clean_and_format_text(soup):
    """
    高级可读性内容提取器和 Markdown 生成器。
    大幅改进，忽略噪音并完美格式化表格/列表。
    """
    # 1. 清除完全无关的 DOM 元素
    for element in soup(['script', 'style', 'noscript', 'meta', 'link', 'iframe', 'svg',
                         'canvas', 'form', 'nav', 'footer', 'aside', 'header', 'button', 'input']):
        element.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Wiki 导航框的积极过滤器
    for selector in[
        ".comment", "#comments", ".advertisement", ".sidebar", ".menu", ".cookie-banner",
        ".navbox", ".infobox", ".metadata", ".toc", "#toc",
        "table[class*='navbox']", "div[class*='navbox']", "table[class*='infobox']"
    ]:
        for el in soup.select(selector):
            el.decompose()

    # 2. 启发式内容检测
    main_content = None
    for selector in ['article', 'main', '[role="main"]', '#main-content', '.main-content']:
        main_content = soup.select_one(selector)
        if main_content: break

    if not main_content:
        candidates = soup.find_all(['div', 'section'])
        best_candidate = soup.body if soup.body else soup
        highest_score = -1

        for candidate in candidates:
            p_tags = candidate.find_all('p')
            score = len(p_tags)
            class_id_text = (candidate.get('class', [''])[0] + " " + candidate.get('id', '')).lower()
            if any(bad in class_id_text for bad in['wrap', 'page', 'container', 'body']):
                score -= 2

            if score > highest_score and score > 2:
                highest_score = score
                best_candidate = candidate

        main_content = best_candidate

    # 3. 健壮的 HTML 转 Markdown 递归解析器
    def to_markdown(node, list_depth=0):
        if isinstance(node, NavigableString):
            text = str(node)
            return re.sub(r'\s+', ' ', text)

        if not isinstance(node, Tag):
            return ""

        tag = node.name
        children_md = "".join(to_markdown(c, list_depth) for c in node.children)

        # 块级元素
        if tag in['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = tag[1]
            return f"\n\n{'#' * int(level)} {children_md.strip()}\n\n"

        elif tag == 'p':
            return f"\n\n{children_md.strip()}\n\n"

        elif tag in ['ul', 'ol']:
            return f"\n{children_md}\n"

        elif tag == 'li':
            indent = "  " * list_depth
            prefix = "- " if node.parent and node.parent.name == 'ul' else "1. "
            inner = "".join(to_markdown(c, list_depth + 1) for c in node.children).strip()
            return f"\n{indent}{prefix}{inner}"

        elif tag == 'blockquote':
            return "\n\n" + "\n".join(f"> {line}" for line in children_md.strip().split("\n")) + "\n\n"

        elif tag in ['pre', 'code']:
            if tag == 'code' and node.parent.name != 'pre':
                return f"`{children_md.strip()}`"
            text = node.get_text()
            return f"\n\n```\n{text}\n```\n\n"

        # 表格逻辑（GitHub 风格 Markdown）
        elif tag == 'table':
            # 如果是嵌套表格，仅作为纯文本处理
            if node.find_parent('table'):
                return f" {children_md.strip()} "

            rows =[]
            for child in node.children:
                if child.name in ['thead', 'tbody', 'tfoot']:
                    rows.extend(child.find_all('tr', recursive=False))
                elif child.name == 'tr':
                    rows.append(child)

            if not rows: return ""

            table_md = "\n\n"
            valid_rows = 0

            for i, row in enumerate(rows):
                cells = row.find_all(['td', 'th'], recursive=False)
                if not cells: continue

                cell_text =[" ".join(to_markdown(c).strip().split()) for c in cells]
                table_md += "| " + " | ".join(cell_text) + " |\n"

                if valid_rows == 0:
                    table_md += "| " + " | ".join(["---"] * len(cells)) + " |\n"

                valid_rows += 1

            return table_md + "\n"

        # 行内元素
        elif tag in ['strong', 'b']:
            return f" **{children_md.strip()}** "

        elif tag in ['em', 'i']:
            return f" *{children_md.strip()}* "

        elif tag == 'a':
            href = node.get('href', '')
            text = children_md.strip()
            if not text: return ""
            if href.startswith('http'):
                return f" [{text}]({href}) "
            return f" [{text}] "

        elif tag in ['br', 'hr']:
            return "\n" if tag == 'br' else "\n\n---\n\n"

        else:
            return children_md

    # 处理并清理最终 Markdown
    raw_md = to_markdown(main_content)

    # 清理正则表达式
    cleaned_md = re.sub(r'\n{3,}', '\n\n', raw_md)          # 最多 2 个换行
    cleaned_md = re.sub(r' +(\n|$)', r'\1', cleaned_md)     # 尾部空格
    cleaned_md = re.sub(r'( \*\*|\*\* )', '**', cleaned_md) # 粗体间距
    cleaned_md = re.sub(r'( \*|\* )', '*', cleaned_md)      # 斜体间距
    # 移除复杂表格中残留的过多空管道符
    cleaned_md = re.sub(r'\|\s+\|\s+\|', '| |', cleaned_md)

    return cleaned_md.strip()


def scrape_with_requests(url, verify_ssl=True):
    """使用 requests 抓取 URL。优化了速度和编码回退。"""
    try:
        session = create_session_with_retries(retries=2, verify_ssl=verify_ssl)
        response = session.get(url, timeout=20, verify=verify_ssl)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            return None, None, False

        # 让 BeautifulSoup 从 response.content 原生处理字符集解析
        soup = BeautifulSoup(response.content, 'html.parser')
        page_title = soup.title.string.strip() if soup.title and soup.title.string else "无标题页面"

        formatted_text = clean_and_format_text(soup)

        if formatted_text and len(formatted_text.strip()) > 50:
            return formatted_text, page_title, True
        return None, None, False

    except (requests.exceptions.SSLError, ssl.SSLError):
        if verify_ssl:
            return scrape_with_requests(url, verify_ssl=False)
        return None, None, False
    except Exception:
        return None, None, False


def scrape_with_selenium(urls, use_requests_fallback=True):
    """
    大幅改进的 Selenium 实现。
    使用 Selenium 4 内置管理器（不再使用硬编码的 executable_paths）。
    融合高级隐身机制以绕过机器人防护。
    """
    if not urls:
        print("未提供要抓取的 URL。")
        return ""

    all_text = ""
    driver = None
    config = config_manager.load_config() if hasattr(config_manager, 'load_config') else {}
    browser_cfg = config.get("browser_config", {})
    preferred_browser = browser_cfg.get("browser_name", "Chrome")

    def get_stealth_chrome_options(is_edge=False):
        options = EdgeOptions() if is_edge else ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        options.add_experimental_option('useAutomationExtension', False)
        # 忽略安全错误以确保页面成功加载
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--log-level=3')
        options.add_argument('--silent')
        return options

    # 要尝试的浏览器，将配置首选的浏览器放在前面
    browsers = [("Chrome", "chrome"), ("Edge", "edge"), ("Firefox", "firefox")]
    browsers.sort(key=lambda x: x[0] != preferred_browser)

    for browser_name, browser_type in browsers:
        try:
            print(f"正在通过 Selenium 4 自动管理器设置 {browser_name}...")

            if browser_type == "chrome":
                driver = webdriver.Chrome(options=get_stealth_chrome_options(is_edge=False))
            elif browser_type == "edge":
                driver = webdriver.Edge(options=get_stealth_chrome_options(is_edge=True))
            elif browser_type == "firefox":
                options = FirefoxOptions()
                options.add_argument('--headless')
                driver = webdriver.Firefox(options=options)

            if driver:
                print(f"✓ {browser_name} 初始化成功。")

                # 通过 CDP 应用反爬虫隐身脚本
                if browser_type in ["chrome", "edge"]:
                    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                        "source": """
                            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                            window.navigator.chrome = {runtime: {}};
                        """
                    })

                # 保存可用浏览器到配置
                if browser_name != preferred_browser and hasattr(config_manager, 'save_config'):
                    config["browser_config"] = {"browser_name": browser_name, "browser_type": browser_type}
                    config_manager.save_config(config)

                driver.set_page_load_timeout(45)
                break

        except Exception as e:
            # 静默失败并尝试下一个浏览器
            driver = None
            continue

    if not driver:
        print("⚠ 所有浏览器初始化失败。回退到 Requests 引擎。")

    successful_scrapes = 0
    total_urls = len(urls)

    for i, url in enumerate(urls, 1):
        scraped = False
        formatted_text = None
        page_title = "无标题页面"

        if driver:
            try:
                print(f"[{i}/{total_urls}] 正在使用 Selenium 加载 {url}...")
                driver.get(url)

                # 智能动态等待 - 等到网络基本空闲或 body 加载完成
                WebDriverWait(driver, 15).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )

                # 滚动以触发懒加载的文本/图片
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                time.sleep(1.5)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

                page_source = driver.page_source
                page_title = driver.title or "无标题页面"

                if page_source and len(page_source) > 500:
                    soup = BeautifulSoup(page_source, 'html.parser')
                    formatted_text = clean_and_format_text(soup)

                    if formatted_text and len(formatted_text.strip()) > 50:
                        scraped = True
                        print(f"  ✓ Selenium 提取成功")
                    else:
                        print(f"  ⚠ 提取的内容过短。尝试回退方案。")

            except TimeoutException:
                print(f"  ⚠ 页面加载超时。")
            except WebDriverException as e:
                print(f"  ⚠ Selenium 导航错误：{str(e).splitlines()[0]}")
            except Exception as e:
                print(f"  ⚠ 未预期的 Selenium 错误：{e}")

        # 如果 Selenium 不起作用或内容被阻止，则回退到 requests
        if not scraped and use_requests_fallback:
            print(f"  → 正在尝试对 {url} 进行基于 Requests 的提取...")
            content, req_title, success = scrape_with_requests(url)
            if success and content:
                formatted_text = content
                page_title = req_title
                scraped = True
                print(f"  ✓ Requests 提取成功")

        if scraped and formatted_text:
            all_text += f"\n# {page_title}\n\n{formatted_text}\n\n---\n"
            successful_scrapes += 1
            print(f"✓ 已抓取：{url}")
        else:
            print(f"✗ 失败：{url} - 未提取到可读内容")

    if driver:
        try:
            driver.quit()
        except:
            pass

    print(f"\n{'='*50}")
    print(f"抓取完成：{successful_scrapes}/{total_urls} 个 URL 成功")

    if not all_text.strip():
        print("⚠ 警告：未从任何 URL 抓取到内容")

    return all_text


def save_to_file(text, filename="scraped_content.txt"):
    """安全地将文本保存到文件。"""
    if not text.strip():
        print("没有内容可保存。")
        return

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"✓ 内容已成功保存到 '{filename}'")
    except IOError as e:
        print(f"✗ 保存文件时出错：{e}")


if __name__ == "__main__":
    # 确保 BeautifulSoup 可用于自测
    urls_to_scrape = get_urls()
    if urls_to_scrape:
        scraped_content = scrape_with_selenium(urls_to_scrape)
        if scraped_content.strip():
            save_to_file(scraped_content)
            print("\n--- 抓取内容预览 ---")
            print(scraped_content[:1500] + "\n\n... [已截断] ...")

import asyncio
import os

def _detect_system_browser_channel():
    """
    检测系统中已安装的 Chromium 内核浏览器，返回 (channel_name, executable_path)。
    优先级：Chrome > Edge。
    如果都未找到则返回 (None, None)。
    """
    import shutil
    import platform

    if platform.system() == "Windows":
        chrome_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for p in chrome_paths:
            if os.path.isfile(p):
                return "chrome", p

        edge_paths = [
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        ]
        for p in edge_paths:
            if os.path.isfile(p):
                return "msedge", p

    else:
        if shutil.which("google-chrome") or shutil.which("google-chrome-stable"):
            path = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
            return "chrome", path
        if shutil.which("microsoft-edge") or shutil.which("microsoft-edge-stable"):
            path = shutil.which("microsoft-edge") or shutil.which("microsoft-edge-stable")
            return "msedge", path
        if platform.system() == "Darwin":
            chrome_mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            edge_mac = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
            if os.path.isfile(chrome_mac):
                return "chrome", chrome_mac
            if os.path.isfile(edge_mac):
                return "msedge", edge_mac

    return None, None


def _get_crawl4ai_home_folder():
    """获取 crawl4ai 的主目录（用于写入路径缓存）。"""
    try:
        from crawl4ai.utils import get_home_folder
        return get_home_folder()
    except Exception:
        # 回退：使用默认路径
        return os.path.join(os.path.expanduser("~"), ".crawl4ai")


def _write_browser_path_cache(browser_exe_path):
    """
    将系统浏览器路径写入 crawl4ai 的路径缓存文件。
    crawl4ai 的 get_chromium_path() 会优先读取这个缓存，
    这样它就会用系统浏览器而不是 Playwright 自带的 Chromium。
    """
    home_folder = _get_crawl4ai_home_folder()
    os.makedirs(home_folder, exist_ok=True)
    path_file = os.path.join(home_folder, "chromium.path")
    with open(path_file, "w") as f:
        f.write(browser_exe_path)
    print(f"  已写入浏览器路径缓存：{browser_exe_path}")


def _patch_browser_manager_get_page():
    """
    修复 crawl4ai 0.6.3 在 use_managed_browser=True（托管浏览器）模式下连续抓取
    多个 URL 时的 IndexError（browser_manager.py:967，context.pages[0] 越界）。

    托管模式下所有抓取共用同一个 default_context：抓完第一个 URL 后该 page
    会被关闭，context.pages 变空，随后 context.pages[0] 直接越界（首个 URL 因
    复用初始 about:blank 页而成功，故表现为「第一个成功、其后全崩」）。

    做法：调用原 get_page 前，若 default_context 没有任何 page 就先新建一个，
    保证 pages[0] 不越界。保留托管浏览器 + 系统浏览器链路，不修改第三方库源码。
    """
    from crawl4ai.browser_manager import BrowserManager

    if getattr(BrowserManager.get_page, "_charmaker_patched", False):
        return  # 已打过补丁，避免重复包装

    _orig_get_page = BrowserManager.get_page

    async def _patched_get_page(self, crawlerRunConfig):
        # 托管模式下，确保 default_context 至少有一个可用 page，
        # 否则 crawl4ai 内部的 context.pages[0] 会因列表为空而越界。
        if (
            getattr(self.config, "use_managed_browser", False)
            and self.default_context is not None
            and not self.default_context.pages
        ):
            await self.default_context.new_page()
        return await _orig_get_page(self, crawlerRunConfig)

    _patched_get_page._charmaker_patched = True
    BrowserManager.get_page = _patched_get_page


def scrape_with_crawl4ai(urls, headless=True):
    try:
        from crawl4ai import BrowserConfig, CrawlerRunConfig, AsyncWebCrawler, DefaultMarkdownGenerator
    except ImportError:
        print("crawl4ai 未安装，回退到旧版抓取器。")
        return None

    # 应用托管浏览器多 URL 抓取的 IndexError 补丁
    _patch_browser_manager_get_page()

    async def _crawl():
        os.environ["NODE_OPTIONS"] = "--no-deprecation"

        # 检测系统浏览器并将路径写入 crawl4ai 缓存
        sys_channel, sys_browser_path = _detect_system_browser_channel()

        if sys_browser_path:
            _write_browser_path_cache(sys_browser_path)
            print(f"  使用系统浏览器：{sys_channel} ({sys_browser_path})")
        else:
            print("  未检测到系统浏览器，将使用 Playwright 内置 Chromium")

        browser_config = BrowserConfig(
            headless=headless,
            verbose=False,
            use_managed_browser=True,
        )

        wait_for_loading = """js:() => {
            const text = document.body ? document.body.innerText : '';
            return !text.includes('Loading page resources.') && !text.includes('The site isn\\'t loading');
        }"""

        config = CrawlerRunConfig(
            wait_for=wait_for_loading,
            delay_before_return_html=3.0,
            css_selector="body",
            excluded_selector=".toc, .wds-global-footer, #catlinks, .printfooter, .global-top-navigation, .notifications-placeholder, #community-navigation, .community-header-wrapper, .global-explore-navigation, .global-footer, .global-footer__content, .global-footer__bottom, .fandom-community-header, #navigator, #header, .full_hr, .menubar, #toolbar, #lastmodified, #footer, #cosmos-footer, #cosmos-toolbar, .cosmos-header, #cosmos-banner, .mw-header, #mw-head, #mw-panel, #mw-page-base, #mw-head-base, .mw-footer, .mw-footer-container, .vector-column-end, .vector-sticky-pinned-container, .azltable, .page__rioque ght-rail, #google_translate_element, #onetrust-banner-sdk, #onetrust-consent-sdk, #top_leaderboard-odyssey-wrapper, .mw-cookiewarning-container, .nv-view, .nv-talk, .nv-edit, .navibox, .pcomment, #google_translate_element, #goog-gt-tt, #goog-gt-vt, .adthrive-comscore, .adthrive-footer-message, .adthrive-ad, .adthrive-footer, .raptive-content-terms-modal, .adthrive-ccpa-modal, #adt-ii, #adthrive-mcmp",
            markdown_generator=DefaultMarkdownGenerator(
                options={"ignore_links": True, "skip_internal_links": True}
            )
        )

        all_text = ""
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for url in urls:
                try:
                    result = await crawler.arun(url=url, config=config)
                    if result.success:
                        all_text += f"\n--- 来自 {url} 的内容 ---\n"
                        all_text += str(result.markdown)
                    else:
                        print(f"抓取 {url} 失败：{result.error_message}")
                except Exception as e:
                    print(f"抓取 {url} 时出错：{e}")
        return all_text

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            pass
    except RuntimeError:
        pass

    return asyncio.run(_crawl())
