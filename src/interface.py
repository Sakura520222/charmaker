import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import sys
import os
import requests
import io
from PIL import Image, ImageTk

# Add the src directory to sys.path if not running from there
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from image_handler import ImageHandler
from api_handler import APIHandler
from scraper import scrape_with_selenium, scrape_with_crawl4ai
from character_card import save_character_card, save_system_prompt
import config_manager
from main import parse_ai_response


class CharMakerTkinterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CharMaker")
        self.root.geometry("1020x720")
        self.root.minsize(760, 640)

        self.compact_breakpoint = 980
        self.is_compact_layout = False

        self.config = config_manager.load_config()
        self.is_dark_mode = self.config.get('dark_mode', False)
        self.thumb_image = None
        self.preview_timer = None

        self.setup_styles()
        self.setup_ui()
        self.queue_preview_update()

    def setup_styles(self):
        style = ttk.Style(self.root)
        if 'clam' in style.theme_names():
            style.theme_use('clam')

        if self.is_dark_mode:
            self.bg_color = "#1e1e1e"
            self.card_bg = "#2d2d30"
            self.primary = "#4a90e2"
            self.text_color = "#f0f0f0"
            self.text_widget_bg = "#1e1e1e"
            self.text_widget_fg = "#f0f0f0"
            self.header_color = "#ffffff"
            self.entry_bg = "#333333"
            self.entry_fg = "#ffffff"
        else:
            self.bg_color = "#f0f3f5"
            self.card_bg = "#ffffff"
            self.primary = "#2b579a"
            self.text_color = "#202124"
            self.text_widget_bg = "#f9fafd"
            self.text_widget_fg = "#333333"
            self.header_color = "#1a1a1a"
            self.entry_bg = "#ffffff"
            self.entry_fg = "#000000"

        self.root.configure(bg=self.bg_color)

        style.configure('.', background=self.bg_color, foreground=self.text_color, font=('Segoe UI', 10))
        style.configure('TFrame', background=self.bg_color)
        style.configure('Card.TFrame', background=self.card_bg)

        style.configure('TLabelframe', background=self.card_bg, borderwidth=1, bordercolor="#e1e1e1" if not self.is_dark_mode else "#444", relief="flat")
        style.configure('TLabelframe.Label', background=self.card_bg, font=('Segoe UI', 11, 'bold'), foreground=self.primary)

        style.configure('TLabel', background=self.card_bg, foreground=self.text_color, font=('Segoe UI', 10))
        style.configure('Header.TLabel', background=self.bg_color, font=('Segoe UI', 20, 'bold'), foreground=self.header_color)
        style.configure('SubHeader.TLabel', background=self.bg_color, font=('Segoe UI', 10), foreground="#888" if self.is_dark_mode else "#5f6368")
        style.configure('Status.TLabel', background=self.bg_color, font=('Segoe UI', 10, 'italic'), foreground="#888" if self.is_dark_mode else "#5f6368")

        btn_bg = "#444" if self.is_dark_mode else "#e1dfdd"
        btn_fg = "#f0f0f0" if self.is_dark_mode else "#000"

        style.configure('TCombobox', fieldbackground=self.entry_bg, background=btn_bg, foreground=self.entry_fg, padding=4)
        style.map('TCombobox', fieldbackground=[('readonly', self.entry_bg)], selectbackground=[('readonly', self.primary)], selectforeground=[('readonly', 'white')])

        style.configure('TEntry', fieldbackground=self.entry_bg, foreground=self.entry_fg, padding=4)
        style.map('TEntry', fieldbackground=[('disabled', '#222' if self.is_dark_mode else '#f0f0f0')])
        style.configure('TCheckbutton', background=self.card_bg, foreground=self.text_color, font=('Segoe UI', 10))
        style.map('TCheckbutton', background=[('active', self.card_bg)])
        style.configure('TRadiobutton', background=self.card_bg, foreground=self.text_color)

        style.configure('TButton', font=('Segoe UI', 10), background=btn_bg, foreground=btn_fg, borderwidth=0, padding=6)
        style.map('TButton', background=[('active', '#555' if self.is_dark_mode else '#d0d0d0'), ('disabled', '#333' if self.is_dark_mode else '#f3f2f1')])

        style.configure('Theme.TButton', font=('Segoe UI Emoji', 14), background=self.bg_color, foreground=self.text_color, borderwidth=0, padding=2, anchor='center')
        style.map('Theme.TButton', background=[('active', '#333' if self.is_dark_mode else '#e0e0e0')])

        style.configure('Action.TButton', font=('Segoe UI', 12, 'bold'), foreground='white', background=self.primary, padding=10)
        style.map('Action.TButton',
                  background=[('active', '#357abd' if self.is_dark_mode else '#1e3e6d'), ('disabled', '#555' if self.is_dark_mode else '#a5b5c9')],
                  foreground=[('disabled', '#888' if self.is_dark_mode else '#f0f0f0')])

        style.configure('Horizontal.TProgressbar', background=self.primary, troughcolor=btn_bg, borderwidth=0, thickness=4)

        style.configure('TNotebook', background=self.bg_color, borderwidth=0)
        style.configure('TNotebook.Tab', background=btn_bg, foreground=btn_fg, padding=[10, 5], font=('Segoe UI', 10))
        style.map('TNotebook.Tab',
                  background=[('selected', self.card_bg), ('active', '#555' if self.is_dark_mode else '#d0d0d0')],
                  foreground=[('selected', self.primary)])

        if hasattr(self, 'urls_text'):
            self.urls_text.configure(bg=self.text_widget_bg, fg=self.text_widget_fg, insertbackground=self.text_color, highlightbackground="#444" if self.is_dark_mode else "#d1d5db")
            self.instructions_text.configure(bg=self.text_widget_bg, fg=self.text_widget_fg, insertbackground=self.text_color, highlightbackground="#444" if self.is_dark_mode else "#d1d5db")

    def toggle_dark_mode(self):
        self.is_dark_mode = not self.is_dark_mode
        self.dark_mode_btn.config(text="☀️" if self.is_dark_mode else "🌒")
        self.config['dark_mode'] = self.is_dark_mode
        config_manager.save_config(self.config)
        self.setup_styles()

    def setup_ui(self):
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill="x", padx=14, pady=(8, 4))

        self.dark_mode_btn = ttk.Button(header_frame, text="☀️" if self.is_dark_mode else "🌒", style='Theme.TButton', command=self.toggle_dark_mode, width=3)
        self.dark_mode_btn.pack(side="right", anchor="n", padx=(0, 6))

        titles_frame = ttk.Frame(header_frame)
        titles_frame.pack(side="left", fill="x", expand=True)
        ttk.Label(titles_frame, text="CharMaker", style='Header.TLabel').pack(anchor="w")
        ttk.Label(titles_frame, text="提供 URL 和参数，全自动构建并生成角色卡。", style='SubHeader.TLabel').pack(anchor="w")

        self.main_paned = ttk.Frame(self.root)
        self.main_paned.pack(fill="both", expand=True, padx=14, pady=4)
        self.main_paned.columnconfigure(0, weight=1, uniform="col")
        self.main_paned.columnconfigure(1, weight=1, uniform="col")
        self.main_paned.rowconfigure(0, weight=1)
        self.main_paned.rowconfigure(1, weight=1)

        self.left_frame = ttk.Frame(self.main_paned)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        content_frame = ttk.LabelFrame(self.left_frame, text="内容来源", padding=10)
        content_frame.pack(fill="both", expand=True, pady=(0, 8))

        ttk.Label(content_frame, text="目标 URL / 图片（每行一个）：", font=('Segoe UI', 9, 'bold')).pack(anchor="w", pady=(0, 5))
        self.urls_text = tk.Text(content_frame, height=6, font=('Consolas', 10), relief="flat", padx=8, pady=7, spacing1=5, spacing3=5, highlightthickness=1)
        self.urls_text.pack(fill="both", expand=True, pady=(0, 8))

        ttk.Label(content_frame, text="附加自定义指令（提示词）：", font=('Segoe UI', 9, 'bold')).pack(anchor="w", pady=(0, 5))
        self.instructions_text = tk.Text(content_frame, height=4, font=('Segoe UI', 10), relief="flat", padx=8, pady=7, spacing1=2, spacing3=2, highlightthickness=1)
        self.instructions_text.pack(fill="both", expand=True)

        self.urls_text.configure(bg=self.text_widget_bg, fg=self.text_widget_fg, insertbackground=self.text_color, highlightbackground="#d1d5db")
        self.instructions_text.configure(bg=self.text_widget_bg, fg=self.text_widget_fg, insertbackground=self.text_color, highlightbackground="#d1d5db")

        self.right_frame = ttk.Frame(self.main_paned)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # Split AI configuration into two tabs
        self.config_notebook = ttk.Notebook(self.right_frame)
        self.config_notebook.pack(fill="x", pady=(0, 8))

        api_frame = ttk.Frame(self.config_notebook, padding=10)
        self.config_notebook.add(api_frame, text="AI 配置")

        ttk.Label(api_frame, text="平台提供商：").grid(row=0, column=0, sticky="w", pady=(0, 10))

        provider_box_frame = ttk.Frame(api_frame)
        provider_box_frame.grid(row=0, column=1, sticky="w", padx=10, pady=(0, 10))

        self.provider_var = tk.StringVar(value=self.config.get('api_provider', 'groq'))
        self.provider_cb = ttk.Combobox(provider_box_frame, textvariable=self.provider_var, values=["groq", "openrouter", "gemini", "openai"], state="readonly", width=18)
        self.provider_cb.pack(side="left")
        self.provider_cb.bind("<<ComboboxSelected>>", self.on_provider_change)

        self.gemini_grounding_var = tk.BooleanVar(value=self.config.get('gemini_grounding', False))
        self.gemini_grounding_chk = ttk.Checkbutton(provider_box_frame, text="Google 搜索增强", variable=self.gemini_grounding_var, command=self.on_grounding_toggle)
        if self.provider_var.get() == "gemini":
            self.gemini_grounding_chk.pack(side="left", padx=(10, 0))

        ttk.Label(api_frame, text="API 密钥：").grid(row=1, column=0, sticky="w", pady=(0, 10))
        self.api_key_var = tk.StringVar(value=self.config.get(f"{self.provider_var.get()}_api_key", ""))
        self.api_key_var.trace_add("write", self.on_api_key_change)
        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=28, show="*")
        self.api_key_entry.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 10))

        ttk.Label(api_frame, text="LLM 模型：").grid(row=2, column=0, sticky="w", pady=(0, 10))
        self.model_var = tk.StringVar(value=config_manager.get_current_model(self.config))
        self.model_var.trace_add("write", self.on_model_change)
        self.model_entry = ttk.Entry(api_frame, textvariable=self.model_var, width=28)
        self.model_entry.grid(row=2, column=1, sticky="w", padx=10, pady=(0, 10))

        # OpenAI 自定义 Base URL（仅当选择 openai 时显示）
        self.base_url_row = 3
        ttk.Label(api_frame, text="自定义 Base URL：").grid(row=self.base_url_row, column=0, sticky="w", pady=(0, 10))
        base_url_frame = ttk.Frame(api_frame)
        base_url_frame.grid(row=self.base_url_row, column=1, sticky="w", padx=10, pady=(0, 10))
        self.openai_base_url_var = tk.StringVar(value=self.config.get('openai_base_url', ''))
        self.openai_base_url_entry = ttk.Entry(base_url_frame, textvariable=self.openai_base_url_var, width=28)
        self.openai_base_url_entry.pack(side="left")
        self.openai_base_url_var.trace_add("write", self.on_base_url_change)
        self.openai_base_url_label = api_frame.grid_slaves(row=self.base_url_row, column=0)
        self.openai_base_url_frame = base_url_frame

        # 根据当前提供商决定是否显示 base URL
        self._update_openai_base_url_visibility()

        preset_row = self.base_url_row + 1
        ttk.Label(api_frame, text="预设方案：").grid(row=preset_row, column=0, sticky="w", pady=(0, 10))
        preset_frame = ttk.Frame(api_frame)
        preset_frame.grid(row=preset_row, column=1, sticky="w", padx=10, pady=(0, 10))
        self.preset_var = tk.StringVar(value=self.config.get('preset', 'Preset 3'))
        self.preset_cb = ttk.Combobox(preset_frame, textvariable=self.preset_var, values=["Preset 1", "Preset 2", "Preset 3"], state="readonly", width=19)
        self.preset_cb.pack(side="left")
        self.preset_cb.bind("<<ComboboxSelected>>", self.on_preset_change)
        self.preset_help_btn = ttk.Button(preset_frame, text="❓", width=3, command=self.show_preset_help)
        self.preset_help_btn.pack(side="left", padx=(5, 0))

        check_row = preset_row + 1
        self.sep_sys_msg_var = tk.BooleanVar(value=self.config.get('separate_system_messages', False))
        ttk.Checkbutton(api_frame, text="分离系统消息", variable=self.sep_sys_msg_var, command=self.on_sys_msg_toggle).grid(row=check_row, column=0, columnspan=2, sticky="w")

        self.check_tokens_var = tk.BooleanVar(value=self.config.get('check_token_count', True))
        ttk.Checkbutton(api_frame, text="生成前检查 token 数量", variable=self.check_tokens_var, command=self.on_check_tokens_toggle).grid(row=check_row + 1, column=0, columnspan=2, sticky="w", pady=(5, 0))

        output_mode_row = check_row + 2
        ttk.Label(api_frame, text="输出模式：").grid(row=output_mode_row, column=0, sticky="w", pady=(0, 10))
        output_mode_frame = ttk.Frame(api_frame)
        output_mode_frame.grid(row=output_mode_row, column=1, sticky="w", padx=10, pady=(0, 10))
        self.output_mode_var = tk.StringVar(value="角色卡")
        self.output_mode_cb = ttk.Combobox(output_mode_frame, textvariable=self.output_mode_var, values=["角色卡", "系统提示词"], state="readonly", width=19)
        self.output_mode_cb.pack(side="left")
        self.output_mode_cb.bind("<<ComboboxSelected>>", self.on_output_mode_change)

        lang_row = output_mode_row + 1
        ttk.Label(api_frame, text="输出语言：").grid(row=lang_row, column=0, sticky="w", pady=(0, 10))
        lang_frame = ttk.Frame(api_frame)
        lang_frame.grid(row=lang_row, column=1, sticky="w", padx=10, pady=(0, 10))
        self.output_lang_var = tk.StringVar(value=self.config.get('output_language', '与来源相同'))
        self.output_lang_cb = ttk.Combobox(lang_frame, textvariable=self.output_lang_var,
                                           values=["与来源相同", "中文", "English", "日本語", "한국어", "Español", "Français", "Deutsch", "Português", "Русский"],
                                           state="readonly", width=19)
        self.output_lang_cb.pack(side="left")
        self.output_lang_cb.bind("<<ComboboxSelected>>", self.on_output_lang_change)

        scraping_frame = ttk.Frame(self.config_notebook, padding=10)
        self.config_notebook.add(scraping_frame, text="抓取设置")

        ttk.Label(scraping_frame, text="抓取引擎：").grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.scraper_engine_var = tk.StringVar(value=self.config.get('scraper_engine', 'legacy'))

        self.scraper_engine_cb = ttk.Combobox(scraping_frame, textvariable=self.scraper_engine_var, values=["legacy (scraper.py)", "crawl4ai"], state="readonly", width=18)
        self.scraper_engine_cb.grid(row=0, column=1, sticky="w", padx=10, pady=(0, 10))
        self.scraper_engine_cb.bind("<<ComboboxSelected>>", self.on_scraper_engine_change)

        self.crawl4ai_headless_var = tk.BooleanVar(value=self.config.get('crawl4ai_headless', True))
        self.crawl4ai_headless_chk = ttk.Checkbutton(scraping_frame, text="使用无头模式（建议关闭）", variable=self.crawl4ai_headless_var, command=self.on_headless_mode_toggle)

        self.update_scraper_options()

        self.img_frame = ttk.LabelFrame(self.right_frame, text="图片设置", padding=10)
        self.img_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(self.img_frame, text="最终头像图片来源：", font=('Segoe UI', 9)).pack(anchor="w", pady=(0, 5))

        img_opt_frame = ttk.Frame(self.img_frame, style='Card.TFrame')
        img_opt_frame.pack(fill="x")

        self.final_img_type_var = tk.StringVar(value="default")
        self.final_img_cb = ttk.Combobox(img_opt_frame, textvariable=self.final_img_type_var,
                                         values=["default", "local", "url"], state="readonly", width=12)
        self.final_img_cb.pack(side="left", padx=(0, 10))
        self.final_img_cb.bind("<<ComboboxSelected>>", self.on_final_img_opt_change)

        self.final_img_val_var = tk.StringVar()
        self.final_img_val_var.trace_add("write", self.queue_preview_update)

        self.final_img_entry = ttk.Entry(img_opt_frame, textvariable=self.final_img_val_var)
        self.final_img_entry.pack(side="left", fill="x", expand=True)
        self.final_img_entry.config(state="disabled")

        self.final_img_btn = ttk.Button(img_opt_frame, text="浏览...", width=8, command=self.browse_image)

        self.preview_frame = ttk.Frame(self.img_frame, style='Card.TFrame', height=98)
        self.preview_frame.pack(fill="x", pady=(8, 0))
        self.preview_frame.pack_propagate(False)

        self.thumb_label = ttk.Label(self.preview_frame, text="无预览", style='Status.TLabel', anchor="center")
        self.thumb_label.pack(fill="both", expand=True)

        self.out_frame = ttk.LabelFrame(self.right_frame, text="输出目录", padding=10)
        self.out_frame.pack(fill="x")

        out_inner = ttk.Frame(self.out_frame, style='Card.TFrame')
        out_inner.pack(fill="x")

        ttk.Label(out_inner, text="路径：", font=('Segoe UI', 9)).pack(side="left", padx=(0, 5))
        self.save_loc_var = tk.StringVar(value=self.config.get('save_location', 'saved_characters'))
        ttk.Entry(out_inner, textvariable=self.save_loc_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(out_inner, text="更改...", width=10, command=self.change_save_location).pack(side="left", padx=(10, 0))

        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill="x", side="bottom", padx=14, pady=(0, 10))

        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(bottom_frame, mode='indeterminate', variable=self.progress_var, style="Horizontal.TProgressbar")

        self.start_btn = ttk.Button(bottom_frame, text="🚀 开始生成", style='Action.TButton', command=self.on_start)
        self.start_btn.pack(fill="x", pady=(0, 10))

        self.status_var = tk.StringVar(value="就绪，等待操作。")
        ttk.Label(bottom_frame, textvariable=self.status_var, style='Status.TLabel', anchor="center").pack(fill="x")

        self.root.bind("<Configure>", self.on_window_resize)
        self.root.after(50, self.apply_responsive_layout)

    def apply_responsive_layout(self):
        width = self.root.winfo_width()
        compact = width < self.compact_breakpoint

        if compact == self.is_compact_layout:
            return

        self.is_compact_layout = compact

        self.left_frame.grid_forget()
        self.right_frame.grid_forget()

        if compact:
            self.left_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 6))
            self.right_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 0))
            self.main_paned.columnconfigure(1, weight=0)
        else:
            self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
            self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)
            self.main_paned.columnconfigure(1, weight=1, uniform="col")

    def on_window_resize(self, event):
        if event.widget is self.root:
            self.apply_responsive_layout()

    def queue_preview_update(self, *args):
        if self.preview_timer:
            self.root.after_cancel(self.preview_timer)
        self.preview_timer = self.root.after(800, self.update_thumbnail_preview)

    def update_thumbnail_preview(self):
        path = self.get_final_image_path()
        if not path:
            self.thumb_label.config(text="无预览", image="")
            self.thumb_image = None
            return

        def load_img():
            try:
                if path.startswith("http"):
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    resp = requests.get(path, headers=headers, stream=True, timeout=5)
                    resp.raise_for_status()
                    img = Image.open(io.BytesIO(resp.content))
                else:
                    if not os.path.exists(path):
                        raise Exception("File not found")
                    img = Image.open(path)

                img.thumbnail((90, 90))
                photo = ImageTk.PhotoImage(img)

                def set_img():
                    self.thumb_image = photo
                    self.thumb_label.config(image=photo, text="")

                self.root.after(0, set_img)
            except Exception as e:
                def set_err():
                    self.thumb_label.config(text="预览不可用", image="")
                    self.thumb_image = None
                self.root.after(0, set_err)

        self.thumb_label.config(text="正在加载预览...", image="")
        threading.Thread(target=load_img, daemon=True).start()

    def _update_openai_base_url_visibility(self):
        """根据当前提供商决定是否显示 OpenAI 自定义 Base URL 字段。"""
        provider = self.provider_var.get()
        if provider == "openai":
            # 显示 base URL 行的标签和输入框
            for w in self.openai_base_url_frame.master.grid_slaves(row=self.base_url_row, column=0):
                if hasattr(w, 'grid'):
                    w.grid()
            self.openai_base_url_frame.grid()
        else:
            # 隐藏 base URL 行
            for w in self.openai_base_url_frame.master.grid_slaves(row=self.base_url_row, column=0):
                if hasattr(w, 'grid_remove'):
                    w.grid_remove()
            self.openai_base_url_frame.grid_remove()

    def on_base_url_change(self, *args):
        """保存 OpenAI 自定义 Base URL。"""
        self.config['openai_base_url'] = self.openai_base_url_var.get()
        config_manager.save_config(self.config)

    def on_api_key_change(self, *args):
        provider = self.provider_var.get()
        self.config[f'{provider}_api_key'] = self.api_key_var.get()
        config_manager.save_config(self.config)

    def on_model_change(self, *args):
        provider = self.provider_var.get()
        config_manager.set_provider_model(self.config, provider, self.model_var.get())

    def on_preset_change(self, event=None):
        self.config['preset'] = self.preset_var.get()
        config_manager.save_config(self.config)

    def show_preset_help(self):
        help_text = (
            "预设方案控制 AI 如何格式化和生成角色。\n\n"
            "• 预设 1：实验性，效果优秀。\n"
            "• 预设 2：倾向于较短的描述（1300 - 2100 tokens）。\n"
            "• 预设 3：倾向于较长的描述（2000 - 3500 tokens）。平均一致性较低，但最佳生成有时可超越预设 1。\n\n"
            """评分表（准确度 + 角色扮演质量）：
              描述        问候语      综合
预设 1    88.3         88.0        88.2
预设 2    78.0         84.3        81.2
预设 3    82.0         78.0        80.0

- 以下模型互联网来源的平均分析结果：
anthropic/claude-opus-4.6-search
google/gemini-3.1-pro-grounding,
gpt-5.2-search

使用相同的 3 个 URL + 1 张图片和 gemini-3-flash-preview 生成。\n\n"""
            "你可以通过编辑 'presets.py' 文件来自定义这些预设。"
        )
        messagebox.showinfo("预设方案说明", help_text)

    def on_sys_msg_toggle(self, event=None):
        self.config['separate_system_messages'] = self.sep_sys_msg_var.get()
        config_manager.save_config(self.config)

    def on_check_tokens_toggle(self, event=None):
        self.config['check_token_count'] = self.check_tokens_var.get()
        config_manager.save_config(self.config)

    def on_final_img_opt_change(self, event=None):
        opt = self.final_img_type_var.get()
        self.final_img_btn.pack_forget()
        self.final_img_entry.pack_forget()

        if opt == "default":
            self.final_img_entry.pack(side="left", fill="x", expand=True)
            self.final_img_entry.delete(0, tk.END)
            self.final_img_entry.config(state="disabled")
        elif opt == "local":
            self.final_img_entry.pack(side="left", fill="x", expand=True)
            self.final_img_entry.config(state="normal")
            self.final_img_btn.pack(side="left", padx=(10,0))
        elif opt == "url":
            self.final_img_entry.pack(side="left", fill="x", expand=True)
            self.final_img_entry.config(state="normal")

        self.queue_preview_update()

    def browse_image(self):
        path = filedialog.askopenfilename(filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self.final_img_val_var.set(path)

    def on_scraper_engine_change(self, event=None):
        engine = self.scraper_engine_var.get()
        if engine == "crawl4ai":
            try:
                import crawl4ai
            except ImportError:
                messagebox.showwarning("缺少依赖库", "crawl4ai 未安装。请使用 'pip install crawl4ai' 安装。将回退到旧版抓取器。")
                self.scraper_engine_var.set("legacy (scraper.py)")
                engine = "legacy (scraper.py)"

        self.config['scraper_engine'] = engine
        config_manager.save_config(self.config)
        self.update_scraper_options()

    def on_headless_mode_toggle(self, event=None):
        self.config['crawl4ai_headless'] = self.crawl4ai_headless_var.get()
        config_manager.save_config(self.config)

    def update_scraper_options(self):
        if self.scraper_engine_var.get() == "crawl4ai":
            self.crawl4ai_headless_chk.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))
        else:
            self.crawl4ai_headless_chk.grid_forget()

    def on_provider_change(self, event=None):
        provider = self.provider_var.get()
        self.config['api_provider'] = provider

        if provider == 'groq':
            messagebox.showwarning(
                "⚠️ Groq API 警告",
                "**警告！**\n\n最近 Groq 因违反其服务条款开始限制多账户使用，使用该服务时请非常小心，因为可能会导致您的组织受到限制。"
            )

        model = config_manager.get_current_model(self.config)
        self.model_var.set(model)

        api_key = self.config.get(f"{provider}_api_key", "")
        self.api_key_var.set(api_key)

        if provider == "gemini":
            self.gemini_grounding_chk.pack(side="left", padx=(10, 0))
        else:
            self.gemini_grounding_chk.pack_forget()

        self._update_openai_base_url_visibility()

        config_manager.save_config(self.config)

    def on_grounding_toggle(self, event=None):
        self.config['gemini_grounding'] = self.gemini_grounding_var.get()
        config_manager.save_config(self.config)

    def on_output_mode_change(self, event=None):
        """切换输出模式时，显示/隐藏图片设置并更新按钮文本。"""
        if self.output_mode_var.get() == "系统提示词":
            self.img_frame.pack_forget()
            self.start_btn.config(text="📝 生成系统提示词")
        else:
            self.img_frame.pack(fill="x", pady=(0, 8), before=self.out_frame)
            self.start_btn.config(text="🚀 开始生成")

    def on_output_lang_change(self, event=None):
        """保存输出语言设置。"""
        self.config['output_language'] = self.output_lang_var.get()
        config_manager.save_config(self.config)

    def change_save_location(self):
        new_loc = filedialog.askdirectory(initialdir=self.save_loc_var.get())
        if new_loc:
            self.save_loc_var.set(new_loc)

    def update_status(self, text):
        self.status_var.set(text)
        self.root.update_idletasks()

    def on_start(self):
        self.start_btn.config(state="disabled", text="正在生成...")
        self.progress_bar.pack(fill="x", pady=(0, 10), before=self.start_btn)
        self.progress_bar.start(15)
        threading.Thread(target=self.run_generation_workflow, daemon=True).start()

    def end_loading(self):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        if self.output_mode_var.get() == "系统提示词":
            self.start_btn.config(state="normal", text="📝 生成系统提示词")
        else:
            self.start_btn.config(state="normal", text="🚀 开始生成")

    def run_generation_workflow(self):
        is_system_prompt = self.output_mode_var.get() == "系统提示词"

        try:
            provider = self.provider_var.get()
            self.config['api_provider'] = provider
            config_manager.set_provider_model(self.config, provider, self.model_var.get())
            self.config['separate_system_messages'] = self.sep_sys_msg_var.get()
            self.config['save_location'] = self.save_loc_var.get()

            # 根据输出模式选择预设和用户提示词
            try:
                from presets import PRESET1, PRESET2, PRESET3, PRESET_SYSTEM_PROMPT
                if is_system_prompt:
                    APIHandler.INSTRUCTIONS = PRESET_SYSTEM_PROMPT
                    APIHandler.USER_PROMPT = "根据提供的内容生成系统提示词。"
                else:
                    preset_map = {"Preset 1": PRESET1, "Preset 2": PRESET2, "Preset 3": PRESET3}
                    APIHandler.INSTRUCTIONS = preset_map.get(self.preset_var.get(), PRESET3)
                    APIHandler.USER_PROMPT = "根据提供的内容和图片生成角色。"
            except Exception as e:
                print(f"警告：无法直接加载预设 ({e})")

            # 注入输出语言指令
            output_lang = self.output_lang_var.get()
            if output_lang and output_lang != "与来源相同":
                APIHandler.INSTRUCTIONS += f"\n\n<OUTPUT_LANGUAGE>\n你必须在输出中使用 {output_lang}（{output_lang}）。所有内容、描述、对话和文本都必须以 {output_lang}（{output_lang}）撰写。这是一项强制性要求。\n</OUTPUT_LANGUAGE>"

            raw_urls = [line.strip() for line in self.urls_text.get("1.0", tk.END).split('\n') if line.strip()]
            instructions = self.instructions_text.get("1.0", tk.END).strip()

            urls_to_scrape = []
            gen_image_objects = []

            for url in raw_urls:
                if ImageHandler.is_image_url(url):
                    self.update_status("正在加载视觉参考...")
                    loaded_img = ImageHandler.load_image(url)
                    if loaded_img:
                        gen_image_objects.append(loaded_img)
                    else:
                        self.update_status("加载视觉参考失败... 继续执行。")
                else:
                    urls_to_scrape.append(url)

            scraped_content = ""
            if urls_to_scrape:
                self.update_status(f"正在抓取 URL（从 {len(urls_to_scrape)} 个来源获取网页内容）...")
                engine = self.config.get('scraper_engine', 'legacy (scraper.py)')
                if engine == 'crawl4ai':
                    headless = self.config.get('crawl4ai_headless', True)
                    scraped_content = scrape_with_crawl4ai(urls_to_scrape, headless=headless)
                    if scraped_content is None:
                        # Fallback
                        scraped_content = scrape_with_selenium(urls_to_scrape)
                else:
                    scraped_content = scrape_with_selenium(urls_to_scrape)

            if not scraped_content and not gen_image_objects:
                self.end_loading()
                self.update_status("已中止：未提供有效内容或图片。")
                messagebox.showerror("验证错误", "未提供有效内容或图片来生成。请提供 URL 或图片参考。")
                return

            if gen_image_objects:
                self.update_status(f"已加载 {len(gen_image_objects)} 张图片 + 文本内容。准备生成。")

            if self.check_tokens_var.get():
                try:
                    import tiktoken
                    system_text = APIHandler.INSTRUCTIONS
                    full_text = f"{system_text}\n\n{scraped_content}\n\n{instructions}"
                    enc = tiktoken.get_encoding("cl100k_base")
                    token_count = len(enc.encode(full_text))

                    if gen_image_objects:
                        token_count += 350 * len(gen_image_objects) # rough estimate per image input

                    k_tokens = token_count / 1000.0

                    proceed = messagebox.askyesno(
                        "Token 数量估算",
                        f"总内容约为 {k_tokens:.1f}K tokens。\n\n是否继续生成？"
                    )
                    if not proceed:
                        self.update_status("用户在 token 检查后取消了操作。")
                        return
                except ImportError:
                    print("tiktoken 未安装，跳过精确 token 计数检查。")

            gen_label = "系统提示词" if is_system_prompt else "角色"
            self.update_status(f"正在通过 {provider.title()} API 生成{gen_label}...")
            response_text = APIHandler.generate_character(
                self.config,
                scraped_content,
                gen_image_objects,
                instructions
            )

            if is_system_prompt:
                # 系统提示词模式：直接保存原始响应为 .txt 文件
                self.update_status("正在保存系统提示词...")
                os.makedirs(self.config['save_location'], exist_ok=True)
                output_path = save_system_prompt(response_text, self.config['save_location'])

                if output_path:
                    self.update_status(f"✅ 系统提示词已保存至 '{output_path}'。")
                    messagebox.showinfo("生成完成", f"系统提示词已成功生成并保存！\n\n保存路径：{output_path}")
                else:
                    raise ValueError("保存系统提示词失败。")
            else:
                # 角色卡模式（原有逻辑）
                character_details = parse_ai_response(response_text)
                if not character_details or not character_details.get("NAME"):
                    raise ValueError("响应中未找到角色数据。AI 输出格式可能有误。")

                self.update_status("正在处理最终角色头像...")
                final_img_path = self.get_final_image_path()
                if not final_img_path or not os.path.exists(final_img_path):
                    self.update_status("最终图片缺失/无效。等待用户选择...")
                    final_img_path = self.prompt_for_final_image_choice()
                    if not final_img_path or not os.path.exists(final_img_path):
                        self.update_status("警告：最终图片无效。回退到默认 template.png。")
                        final_img_path = "./template.png"

                self.update_status("正在本地保存角色数据...")
                os.makedirs(self.config['save_location'], exist_ok=True)
                save_character_card(character_details, final_img_path, self.config['save_location'])
                ImageHandler.cleanup_temp_file(final_img_path)

                name = character_details.get('NAME', '未知')
                self.update_status(f"✅ 成功！角色 '{name}' 已创建并保存至 '{self.config['save_location']}'。")
                messagebox.showinfo("创建完成", f"角色 '{name}' 已成功生成并保存！")

        except Exception as e:
            self.update_status(f"❌ 生成过程中出错：{e}")
            messagebox.showerror("错误", str(e))
        finally:
            self.root.after(0, self.end_loading)

    def get_final_image_path(self):
        choice = self.final_img_type_var.get()
        if choice == "default":
            return "./template.png"
        elif choice == "local":
            local_path = self.final_img_val_var.get().strip()
            return local_path if local_path else None
        elif choice == "url":
            url = self.final_img_val_var.get().strip()
            if url:
                return self.download_image_to_temp(url)
        return None

    def download_image_to_temp(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, stream=True, timeout=10)
            response.raise_for_status()
            return ImageHandler.save_temp_image(response.content)
        except Exception:
            return None

    def prompt_for_final_image_choice(self):
        """当最终图片缺失/无效时，询问用户如何处理。"""
        while True:
            action = messagebox.askyesnocancel(
                "需要角色图片",
                "未设置有效的最终角色图片。\n\n"
                "是 = 输入图片 URL\n"
                "否 = 选择本地文件\n"
                "取消 = 使用默认模板图片"
            )

            if action is True:
                url = simpledialog.askstring("图片 URL", "输入角色图片的 URL：", parent=self.root)
                if not url:
                    continue
                img_path = self.download_image_to_temp(url.strip())
                if img_path and os.path.exists(img_path):
                    return img_path
                messagebox.showerror("URL 无效", "无法从该 URL 下载图片。")

            elif action is False:
                local_path = filedialog.askopenfilename(
                    title="选择角色图片",
                    filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")]
                )
                if local_path and os.path.exists(local_path):
                    return local_path
                if local_path:
                    messagebox.showerror("文件无效", "选择的文件路径无效。")

            else:
                return "./template.png"

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    app = CharMakerTkinterApp(root)
    root.mainloop()
