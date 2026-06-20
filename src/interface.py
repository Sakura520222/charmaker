import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import sys
import os
import requests
import io
from PIL import Image, ImageTk

# interface.py 位于 src/，需同时能 import src 下同级模块与项目根的 main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))                               # src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))           # 项目根/

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
        self.root.geometry("1120x800")
        self.root.minsize(800, 680)

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

        # ── 现代化配色方案 ──────────────────────────────────
        if self.is_dark_mode:
            self.bg_color = "#0d1117"
            self.card_bg = "#161b22"
            self.card_bg_alt = "#1c2333"
            self.primary = "#818cf8"
            self.primary_hover = "#6366f1"
            self.primary_active = "#4f46e5"
            self.text_color = "#e6edf3"
            self.text_secondary = "#8b949e"
            self.text_widget_bg = "#0d1117"
            self.text_widget_fg = "#c9d1d9"
            self.header_color = "#f0f6fc"
            self.entry_bg = "#0d1117"
            self.entry_fg = "#e6edf3"
            self.border_color = "#30363d"
            self.border_focus = "#818cf8"
            self.success_color = "#3fb950"
            self.button_bg = "#21262d"
            self.button_hover = "#30363d"
            self.button_fg = "#c9d1d9"
            self.separator_color = "#21262d"
            self.preview_bg = "#0d1117"
            self.preview_border = "#30363d"
        else:
            self.bg_color = "#f6f8fa"
            self.card_bg = "#ffffff"
            self.card_bg_alt = "#f0f4f8"
            self.primary = "#5b6abf"
            self.primary_hover = "#4c59a6"
            self.primary_active = "#3d4a8f"
            self.text_color = "#1f2937"
            self.text_secondary = "#6b7280"
            self.text_widget_bg = "#ffffff"
            self.text_widget_fg = "#1f2937"
            self.header_color = "#111827"
            self.entry_bg = "#ffffff"
            self.entry_fg = "#1f2937"
            self.border_color = "#d1d9e0"
            self.border_focus = "#5b6abf"
            self.success_color = "#10b981"
            self.button_bg = "#eaeef2"
            self.button_hover = "#dde3e9"
            self.button_fg = "#374151"
            self.separator_color = "#d1d9e0"
            self.preview_bg = "#f9fafb"
            self.preview_border = "#d1d9e0"

        self.root.configure(bg=self.bg_color)

        # ── 全局默认 ──
        style.configure('.', background=self.bg_color, foreground=self.text_color,
                        font=('Segoe UI', 10))
        style.configure('TFrame', background=self.bg_color)
        style.configure('Card.TFrame', background=self.card_bg)

        # ── LabelFrame（卡片容器） ──
        style.configure('TLabelframe', background=self.card_bg,
                        borderwidth=1, relief="groove",
                        bordercolor=self.border_color)
        style.configure('TLabelframe.Label', background=self.card_bg,
                        font=('Segoe UI', 11, 'bold'), foreground=self.primary,
                        padding=(8, 0, 0, 2))

        # ── 标签 ──
        style.configure('TLabel', background=self.card_bg,
                        foreground=self.text_color, font=('Segoe UI', 10))
        style.configure('Header.TLabel', background=self.bg_color,
                        font=('Segoe UI', 22, 'bold'), foreground=self.header_color)
        style.configure('SubHeader.TLabel', background=self.bg_color,
                        font=('Segoe UI', 10), foreground=self.text_secondary)
        style.configure('Status.TLabel', background=self.bg_color,
                        font=('Segoe UI', 10), foreground=self.text_secondary)
        style.configure('Section.TLabel', background=self.card_bg,
                        font=('Segoe UI', 9, 'bold'), foreground=self.text_secondary)

        # ── 按钮 ──
        style.configure('TButton', font=('Segoe UI', 10),
                        background=self.button_bg, foreground=self.button_fg,
                        borderwidth=0, padding=(10, 5), anchor='center')
        style.map('TButton',
                  background=[('active', self.button_hover), ('disabled', self.bg_color)],
                  foreground=[('disabled', self.text_secondary)])

        style.configure('Theme.TButton', font=('Segoe UI Emoji', 16),
                        background=self.bg_color, foreground=self.text_color,
                        borderwidth=0, padding=4, anchor='center')
        style.map('Theme.TButton',
                  background=[('active', self.card_bg)])

        style.configure('Action.TButton', font=('Segoe UI', 13, 'bold'),
                        foreground='white', background=self.primary,
                        padding=(20, 12), anchor='center')
        style.map('Action.TButton',
                  background=[('active', self.primary_active),
                              ('disabled', self.text_secondary)],
                  foreground=[('disabled', '#ffffff')])

        style.configure('Small.TButton', font=('Segoe UI', 9),
                        background=self.button_bg, foreground=self.button_fg,
                        borderwidth=0, padding=(6, 3))
        style.map('Small.TButton',
                  background=[('active', self.button_hover)])

        # ── Combobox ──
        style.configure('TCombobox', fieldbackground=self.entry_bg,
                        background=self.button_bg, foreground=self.entry_fg,
                        padding=(8, 5), arrowcolor=self.text_color)
        style.map('TCombobox',
                  fieldbackground=[('readonly', self.entry_bg)],
                  selectbackground=[('readonly', self.primary)],
                  selectforeground=[('readonly', 'white')])

        # ── Entry ──
        style.configure('TEntry', fieldbackground=self.entry_bg,
                        foreground=self.entry_fg, padding=(8, 5))
        style.map('TEntry',
                  fieldbackground=[('disabled', self.card_bg_alt)])

        # ── Checkbutton / Radiobutton ──
        style.configure('TCheckbutton', background=self.card_bg,
                        foreground=self.text_color, font=('Segoe UI', 10))
        style.map('TCheckbutton', background=[('active', self.card_bg)])
        style.configure('TRadiobutton', background=self.card_bg,
                        foreground=self.text_color)

        # ── Progressbar ──
        style.configure('Horizontal.TProgressbar', background=self.primary,
                        troughcolor=self.card_bg_alt, borderwidth=0, thickness=3)

        # ── Notebook（选项卡） ──
        style.configure('TNotebook', background=self.bg_color, borderwidth=0, padding=0)
        style.configure('TNotebook.Tab', background=self.button_bg,
                        foreground=self.text_secondary, padding=[16, 7],
                        font=('Segoe UI', 10))
        style.map('TNotebook.Tab',
                  background=[('selected', self.card_bg), ('active', self.button_hover)],
                  foreground=[('selected', self.primary), ('active', self.text_color)])

        # ── Separator ──
        style.configure('TSeparator', background=self.separator_color)

        # ── 更新已有的 Text 控件颜色 ──
        if hasattr(self, 'urls_text'):
            self.urls_text.configure(
                bg=self.text_widget_bg, fg=self.text_widget_fg,
                insertbackground=self.primary,
                highlightbackground=self.border_color,
                highlightcolor=self.border_focus)
            self.instructions_text.configure(
                bg=self.text_widget_bg, fg=self.text_widget_fg,
                insertbackground=self.primary,
                highlightbackground=self.border_color,
                highlightcolor=self.border_focus)

    def toggle_dark_mode(self):
        self.is_dark_mode = not self.is_dark_mode
        self.dark_mode_btn.config(text="☀️" if self.is_dark_mode else "🌙")
        self.config['dark_mode'] = self.is_dark_mode
        config_manager.save_config(self.config)
        self.setup_styles()
        # 强制刷新预览框边框色
        self.preview_frame.configure(style='Card.TFrame')

    def setup_ui(self):
        # ══════════════════════════════════════════════════════
        #  Header
        # ══════════════════════════════════════════════════════
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill="x", padx=20, pady=(16, 0))

        self.dark_mode_btn = ttk.Button(
            header_frame, text="☀️" if self.is_dark_mode else "🌙",
            style='Theme.TButton', command=self.toggle_dark_mode, width=3)
        self.dark_mode_btn.pack(side="right", anchor="n", padx=(0, 2))

        titles_frame = ttk.Frame(header_frame)
        titles_frame.pack(side="left", fill="x", expand=True)
        ttk.Label(titles_frame, text="CharMaker", style='Header.TLabel').pack(anchor="w")
        ttk.Label(titles_frame, text="提供 URL 和参数，全自动构建并生成角色卡。",
                  style='SubHeader.TLabel').pack(anchor="w", pady=(2, 0))

        # Header 分隔线
        ttk.Separator(self.root, orient="horizontal").pack(
            fill="x", padx=20, pady=(12, 0))

        # ══════════════════════════════════════════════════════
        #  主体两栏
        # ══════════════════════════════════════════════════════
        self.main_paned = ttk.Frame(self.root)
        self.main_paned.pack(fill="both", expand=True, padx=20, pady=12)
        self.main_paned.columnconfigure(0, weight=1, uniform="col")
        self.main_paned.columnconfigure(1, weight=1, uniform="col")
        self.main_paned.rowconfigure(0, weight=1)
        self.main_paned.rowconfigure(1, weight=1)

        # ── 左栏：内容来源 ──
        self.left_frame = ttk.Frame(self.main_paned)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        content_frame = ttk.LabelFrame(self.left_frame, text="  📋 内容来源", padding=(14, 10))
        content_frame.pack(fill="both", expand=True)

        ttk.Label(content_frame, text="目标 URL / 图片（每行一个）：",
                  style='Section.TLabel').pack(anchor="w", pady=(0, 4))
        self.urls_text = tk.Text(
            content_frame, height=6, font=('Cascadia Code', 10),
            relief="flat", padx=10, pady=8,
            spacing1=4, spacing3=4, highlightthickness=1,
            wrap="word")
        self.urls_text.pack(fill="both", expand=True, pady=(0, 10))

        ttk.Label(content_frame, text="附加自定义指令（提示词）：",
                  style='Section.TLabel').pack(anchor="w", pady=(0, 4))
        self.instructions_text = tk.Text(
            content_frame, height=4, font=('Segoe UI', 10),
            relief="flat", padx=10, pady=8,
            spacing1=2, spacing3=2, highlightthickness=1,
            wrap="word")
        self.instructions_text.pack(fill="both", expand=True)

        # 初始化 Text 控件颜色
        self.urls_text.configure(
            bg=self.text_widget_bg, fg=self.text_widget_fg,
            insertbackground=self.primary,
            highlightbackground=self.border_color,
            highlightcolor=self.border_focus)
        self.instructions_text.configure(
            bg=self.text_widget_bg, fg=self.text_widget_fg,
            insertbackground=self.primary,
            highlightbackground=self.border_color,
            highlightcolor=self.border_focus)

        # ── 右栏 ──
        self.right_frame = ttk.Frame(self.main_paned)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # ── AI 配置 + 抓取设置选项卡 ──
        self.config_notebook = ttk.Notebook(self.right_frame)
        self.config_notebook.pack(fill="x", pady=(0, 8))

        # ─ Tab 1：AI 配置 ─
        api_frame = ttk.Frame(self.config_notebook, padding=(14, 12))
        self.config_notebook.add(api_frame, text="  🤖 AI 配置  ")

        # 提供商
        row = 0
        ttk.Label(api_frame, text="平台提供商：").grid(
            row=row, column=0, sticky="w", pady=(0, 8))

        provider_box_frame = ttk.Frame(api_frame)
        provider_box_frame.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=(0, 8))

        self.provider_var = tk.StringVar(value=self.config.get('api_provider', 'groq'))
        self.provider_cb = ttk.Combobox(
            provider_box_frame, textvariable=self.provider_var,
            values=["groq", "openrouter", "gemini", "openai"],
            state="readonly", width=18)
        self.provider_cb.pack(side="left")
        self.provider_cb.bind("<<ComboboxSelected>>", self.on_provider_change)

        self.gemini_grounding_var = tk.BooleanVar(value=self.config.get('gemini_grounding', False))
        self.gemini_grounding_chk = ttk.Checkbutton(
            provider_box_frame, text="Google 搜索增强",
            variable=self.gemini_grounding_var, command=self.on_grounding_toggle)
        if self.provider_var.get() == "gemini":
            self.gemini_grounding_chk.pack(side="left", padx=(10, 0))

        # API 密钥
        row = 1
        ttk.Label(api_frame, text="API 密钥：").grid(
            row=row, column=0, sticky="w", pady=(0, 8))
        self.api_key_var = tk.StringVar(
            value=self.config.get(f"{self.provider_var.get()}_api_key", ""))
        self.api_key_var.trace_add("write", self.on_api_key_change)
        self.api_key_entry = ttk.Entry(
            api_frame, textvariable=self.api_key_var, width=28, show="•")
        self.api_key_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=(0, 8))

        # 模型
        row = 2
        ttk.Label(api_frame, text="LLM 模型：").grid(
            row=row, column=0, sticky="w", pady=(0, 8))
        self.model_var = tk.StringVar(value=config_manager.get_current_model(self.config))
        self.model_var.trace_add("write", self.on_model_change)
        self.model_entry = ttk.Entry(api_frame, textvariable=self.model_var, width=28)
        self.model_entry.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=(0, 8))

        # OpenAI Base URL
        row = 3
        self.base_url_row = row
        ttk.Label(api_frame, text="自定义 Base URL：").grid(
            row=row, column=0, sticky="w", pady=(0, 8))
        base_url_frame = ttk.Frame(api_frame)
        base_url_frame.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=(0, 8))
        self.openai_base_url_var = tk.StringVar(value=self.config.get('openai_base_url', ''))
        self.openai_base_url_entry = ttk.Entry(
            base_url_frame, textvariable=self.openai_base_url_var, width=28)
        self.openai_base_url_entry.pack(side="left")
        self.openai_base_url_var.trace_add("write", self.on_base_url_change)
        self.openai_base_url_label = api_frame.grid_slaves(row=self.base_url_row, column=0)
        self.openai_base_url_frame = base_url_frame

        # 预设方案
        row = 4
        ttk.Label(api_frame, text="预设方案：").grid(
            row=row, column=0, sticky="w", pady=(0, 8))
        preset_frame = ttk.Frame(api_frame)
        preset_frame.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=(0, 8))
        self.preset_var = tk.StringVar(value=self.config.get('preset', 'Preset 3'))
        self.preset_cb = ttk.Combobox(
            preset_frame, textvariable=self.preset_var,
            values=["Preset 1", "Preset 2", "Preset 3"],
            state="readonly", width=19)
        self.preset_cb.pack(side="left")
        self.preset_cb.bind("<<ComboboxSelected>>", self.on_preset_change)
        self.preset_help_btn = ttk.Button(
            preset_frame, text="❓", width=3, style='Small.TButton',
            command=self.show_preset_help)
        self.preset_help_btn.pack(side="left", padx=(6, 0))

        # 复选框
        row = 5
        self.sep_sys_msg_var = tk.BooleanVar(value=self.config.get('separate_system_messages', False))
        ttk.Checkbutton(api_frame, text="分离系统消息",
                        variable=self.sep_sys_msg_var,
                        command=self.on_sys_msg_toggle).grid(
            row=row, column=0, columnspan=2, sticky="w")

        row = 6
        self.check_tokens_var = tk.BooleanVar(value=self.config.get('check_token_count', True))
        ttk.Checkbutton(api_frame, text="生成前检查 token 数量",
                        variable=self.check_tokens_var,
                        command=self.on_check_tokens_toggle).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # 输出模式
        row = 7
        ttk.Label(api_frame, text="输出模式：").grid(
            row=row, column=0, sticky="w", pady=(8, 8))
        output_mode_frame = ttk.Frame(api_frame)
        output_mode_frame.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=(8, 8))
        self.output_mode_var = tk.StringVar(value="角色卡")
        self.output_mode_cb = ttk.Combobox(
            output_mode_frame, textvariable=self.output_mode_var,
            values=["角色卡", "系统提示词"], state="readonly", width=19)
        self.output_mode_cb.pack(side="left")
        self.output_mode_cb.bind("<<ComboboxSelected>>", self.on_output_mode_change)

        # 输出语言
        row = 8
        ttk.Label(api_frame, text="输出语言：").grid(
            row=row, column=0, sticky="w", pady=(0, 8))
        lang_frame = ttk.Frame(api_frame)
        lang_frame.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=(0, 8))
        self.output_lang_var = tk.StringVar(value=self.config.get('output_language', '与来源相同'))
        self.output_lang_cb = ttk.Combobox(
            lang_frame, textvariable=self.output_lang_var,
            values=["与来源相同", "中文", "English", "日本語", "한국어",
                    "Español", "Français", "Deutsch", "Português", "Русский"],
            state="readonly", width=19)
        self.output_lang_cb.pack(side="left")
        self.output_lang_cb.bind("<<ComboboxSelected>>", self.on_output_lang_change)

        # ─ Tab 2：抓取设置 ─
        scraping_frame = ttk.Frame(self.config_notebook, padding=(14, 12))
        self.config_notebook.add(scraping_frame, text="  🌐 抓取设置  ")

        ttk.Label(scraping_frame, text="抓取引擎：").grid(
            row=0, column=0, sticky="w", pady=(0, 10))
        self.scraper_engine_var = tk.StringVar(value=self.config.get('scraper_engine', 'legacy'))
        self.scraper_engine_cb = ttk.Combobox(
            scraping_frame, textvariable=self.scraper_engine_var,
            values=["legacy (scraper.py)", "crawl4ai"],
            state="readonly", width=18)
        self.scraper_engine_cb.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 10))
        self.scraper_engine_cb.bind("<<ComboboxSelected>>", self.on_scraper_engine_change)

        self.crawl4ai_headless_var = tk.BooleanVar(value=self.config.get('crawl4ai_headless', True))
        self.crawl4ai_headless_chk = ttk.Checkbutton(
            scraping_frame, text="使用无头模式（建议关闭）",
            variable=self.crawl4ai_headless_var, command=self.on_headless_mode_toggle)

        self.update_scraper_options()

        # ── 图片设置卡片 ──
        self.img_frame = ttk.LabelFrame(self.right_frame, text="  🖼️ 图片设置", padding=(14, 10))
        self.img_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(self.img_frame, text="最终头像图片来源：",
                  style='Section.TLabel').pack(anchor="w", pady=(0, 6))

        img_opt_frame = ttk.Frame(self.img_frame, style='Card.TFrame')
        img_opt_frame.pack(fill="x")

        self.final_img_type_var = tk.StringVar(value="default")
        self.final_img_cb = ttk.Combobox(
            img_opt_frame, textvariable=self.final_img_type_var,
            values=["default", "local", "url"], state="readonly", width=12)
        self.final_img_cb.pack(side="left", padx=(0, 10))
        self.final_img_cb.bind("<<ComboboxSelected>>", self.on_final_img_opt_change)

        self.final_img_val_var = tk.StringVar()
        self.final_img_val_var.trace_add("write", self.queue_preview_update)

        self.final_img_entry = ttk.Entry(img_opt_frame, textvariable=self.final_img_val_var)
        self.final_img_entry.pack(side="left", fill="x", expand=True)
        self.final_img_entry.config(state="disabled")

        self.final_img_btn = ttk.Button(
            img_opt_frame, text="浏览...", width=8, command=self.browse_image)

        # 图片预览
        self.preview_frame = ttk.Frame(self.img_frame, style='Card.TFrame', height=110)
        self.preview_frame.pack(fill="x", pady=(10, 0))
        self.preview_frame.pack_propagate(False)

        self.thumb_label = ttk.Label(
            self.preview_frame, text="无预览", style='Status.TLabel', anchor="center")
        self.thumb_label.pack(fill="both", expand=True)

        # ── 输出目录卡片 ──
        self.out_frame = ttk.LabelFrame(self.right_frame, text="  📂 输出目录", padding=(14, 10))
        self.out_frame.pack(fill="x")

        out_inner = ttk.Frame(self.out_frame, style='Card.TFrame')
        out_inner.pack(fill="x")

        ttk.Label(out_inner, text="路径：", font=('Segoe UI', 9)).pack(side="left", padx=(0, 5))
        self.save_loc_var = tk.StringVar(value=self.config.get('save_location', 'saved_characters'))
        ttk.Entry(out_inner, textvariable=self.save_loc_var, state="readonly").pack(
            side="left", fill="x", expand=True)
        ttk.Button(out_inner, text="更改...", width=10,
                   command=self.change_save_location).pack(side="left", padx=(10, 0))

        # ══════════════════════════════════════════════════════
        #  底部操作栏
        # ══════════════════════════════════════════════════════
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 16))

        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(
            bottom_frame, mode='indeterminate', variable=self.progress_var,
            style="Horizontal.TProgressbar")

        self.start_btn = ttk.Button(
            bottom_frame, text="🚀  开始生成",
            style='Action.TButton', command=self.on_start)
        self.start_btn.pack(fill="x", pady=(0, 8), ipady=4)

        self.status_var = tk.StringVar(value="就绪，等待操作。")
        ttk.Label(bottom_frame, textvariable=self.status_var,
                  style='Status.TLabel', anchor="center").pack(fill="x")

        self.root.bind("<Configure>", self.on_window_resize)
        self.root.after(50, self.apply_responsive_layout)

    # ══════════════════════════════════════════════════════════
    #  响应式布局
    # ══════════════════════════════════════════════════════════

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

    # ══════════════════════════════════════════════════════════
    #  图片预览
    # ══════════════════════════════════════════════════════════

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

                img.thumbnail((96, 96))
                photo = ImageTk.PhotoImage(img)

                def set_img():
                    self.thumb_image = photo
                    self.thumb_label.config(image=photo, text="")

                self.root.after(0, set_img)
            except Exception:
                def set_err():
                    self.thumb_label.config(text="预览不可用", image="")
                    self.thumb_image = None
                self.root.after(0, set_err)

        self.thumb_label.config(text="正在加载预览...", image="")
        threading.Thread(target=load_img, daemon=True).start()

    # ══════════════════════════════════════════════════════════
    #  控件交互
    # ══════════════════════════════════════════════════════════

    def _update_openai_base_url_visibility(self):
        """根据当前提供商决定是否显示 OpenAI 自定义 Base URL 字段。"""
        provider = self.provider_var.get()
        if provider == "openai":
            for w in self.openai_base_url_frame.master.grid_slaves(row=self.base_url_row, column=0):
                if hasattr(w, 'grid'):
                    w.grid()
            self.openai_base_url_frame.grid()
        else:
            for w in self.openai_base_url_frame.master.grid_slaves(row=self.base_url_row, column=0):
                if hasattr(w, 'grid_remove'):
                    w.grid_remove()
            self.openai_base_url_frame.grid_remove()

    def on_base_url_change(self, *args):
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
            "评分表（准确度 + 角色扮演质量）：\n"
            "          描述        问候语      综合\n"
            "预设 1    88.3         88.0        88.2\n"
            "预设 2    78.0         84.3        81.2\n"
            "预设 3    82.0         78.0        80.0\n\n"
            "- 以下模型互联网来源的平均分析结果：\n"
            "  anthropic/claude-opus-4.6-search\n"
            "  google/gemini-3.1-pro-grounding\n"
            "  gpt-5.2-search\n\n"
            "使用相同的 3 个 URL + 1 张图片和 gemini-3-flash-preview 生成。\n\n"
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
            self.final_img_btn.pack(side="left", padx=(10, 0))
        elif opt == "url":
            self.final_img_entry.pack(side="left", fill="x", expand=True)
            self.final_img_entry.config(state="normal")

        self.queue_preview_update()

    def browse_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self.final_img_val_var.set(path)

    def on_scraper_engine_change(self, event=None):
        engine = self.scraper_engine_var.get()
        if engine == "crawl4ai":
            try:
                import crawl4ai
            except ImportError:
                messagebox.showwarning(
                    "缺少依赖库",
                    "crawl4ai 未安装。请使用 'pip install crawl4ai' 安装。将回退到旧版抓取器。")
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
                "**警告！**\n\n"
                "最近 Groq 因违反其服务条款开始限制多账户使用，"
                "使用该服务时请非常小心，因为可能会导致您的组织受到限制。")

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
            self.start_btn.config(text="📝  生成系统提示词")
        else:
            self.img_frame.pack(fill="x", pady=(0, 8), before=self.out_frame)
            self.start_btn.config(text="🚀  开始生成")

    def on_output_lang_change(self, event=None):
        self.config['output_language'] = self.output_lang_var.get()
        config_manager.save_config(self.config)

    def change_save_location(self):
        new_loc = filedialog.askdirectory(initialdir=self.save_loc_var.get())
        if new_loc:
            self.save_loc_var.set(new_loc)

    def update_status(self, text):
        self.status_var.set(text)
        self.root.update_idletasks()

    # ══════════════════════════════════════════════════════════
    #  生成工作流
    # ══════════════════════════════════════════════════════════

    def on_start(self):
        self.start_btn.config(state="disabled", text="⏳ 正在生成...")
        self.progress_bar.pack(fill="x", pady=(0, 8), before=self.start_btn)
        self.progress_bar.start(15)
        threading.Thread(target=self.run_generation_workflow, daemon=True).start()

    def end_loading(self):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        if self.output_mode_var.get() == "系统提示词":
            self.start_btn.config(state="normal", text="📝  生成系统提示词")
        else:
            self.start_btn.config(state="normal", text="🚀  开始生成")

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
                APIHandler.INSTRUCTIONS += (
                    f"\n\n<OUTPUT_LANGUAGE>\n你必须在输出中使用 {output_lang}（{output_lang}）。"
                    f"所有内容、描述、对话和文本都必须以 {output_lang}（{output_lang}）撰写。"
                    f"这是一项强制性要求。\n</OUTPUT_LANGUAGE>")

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
                        token_count += 350 * len(gen_image_objects)

                    k_tokens = token_count / 1000.0

                    proceed = messagebox.askyesno(
                        "Token 数量估算",
                        f"总内容约为 {k_tokens:.1f}K tokens。\n\n是否继续生成？")
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
                self.update_status("正在保存系统提示词...")
                os.makedirs(self.config['save_location'], exist_ok=True)
                output_path = save_system_prompt(response_text, self.config['save_location'])

                if output_path:
                    self.update_status(f"✅ 系统提示词已保存至 '{output_path}'。")
                    messagebox.showinfo("生成完成", f"系统提示词已成功生成并保存！\n\n保存路径：{output_path}")
                else:
                    raise ValueError("保存系统提示词失败。")
            else:
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
                "取消 = 使用默认模板图片")

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
                    filetypes=[("图片文件", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")])
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
