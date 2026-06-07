# CharMaker 汉化版
基于网络搜索的 AI 角色卡创建器

**通过发送多个 URL 甚至图片给 AI 来创建角色卡！**

> 📌 本仓库是 [CharMaker](https://github.com/gusta01010/charmaker) 的中文汉化版本，由原作者 [Gustavo Lima (gusta01010)](https://github.com/gusta01010) 开发。在此感谢原作者的出色工作！
>
> 如需查看原版项目，请访问：https://github.com/gusta01010/charmaker

这个开源工具帮助你创建所需的角色，方法是将网站抓取的内容和插入的图片附加到 AI，生成其：
- 名称
- 详细描述
- 简要性格
- 场景设定
- 问候消息
- 示例消息

## 主要功能

- **多提供商 AI 支持**：OpenAI、Gemini、Groq 和 OpenRouter API，每个提供商可独立配置模型
- **多种抓取引擎**：Selenium、Crawl4AI 和 Requests 三种抓取方式，支持自动回退
- **系统提示词生成**：基于抓取内容自动生成可用于 LLM 角色扮演的系统提示词
- **高级图片处理**：本地文件、URL 和默认模板
- **输出语言选择**：支持中文、English、日本語等多种输出语言
- **Token 计数**：在生成前监控 API 使用量
- **可自定义预设**：多种预定义的角色生成模板（含高级预设）
- **外部提示词加载**：支持通过外部 `prompt.py` 文件自定义 AI 指令
- **多浏览器支持**：Chrome、Firefox 和 Microsoft Edge，自动检测系统已安装的浏览器
- **Gemini Grounding**：支持 Gemini 搜索接地功能
- **图形界面**：基于 Tkinter 的美观桌面应用，支持暗色模式
- **V3 角色卡格式**：输出兼容 `chara_card_v3` 规范的 PNG 角色卡

## 界面选项

CharMaker 提供两种交互方式：

1. **图形界面应用** (`interface.py`) — 功能齐全的图形界面：
   - 暗色/亮色模式支持
   - 响应式、自适应布局
   - 实时图片预览
   - 交互式配置管理
   - 快速访问所有功能

2. **命令行界面** (`main.py`) — 用于自动化和脚本：
   - 批量角色创建
   - 系统提示词生成模式
   - 与其他工具集成
   - 可脚本化的工作流

## 使用方法

1. 运行 `main.py` 进入终端模式，或运行 `interface.py` 进入图形界面模式

2. 设置你想要的保存文件夹、提供商以及你自己的 API 密钥：
    - 选择 API 提供商（OpenAI、Gemini、Groq 或 OpenRouter）
    - 分离系统消息：切换是否将抓取的内容合并到单个系统提示中
    - 选择抓取引擎（Selenium、Crawl4AI 或 Requests）
    - 选择输出语言

3. 开始角色创建 - 你可以：
    - **添加** 来自 Wiki 或数据库的角色 URL
    - **添加图片 URL** 作为视觉参考
    - （仅限终端）使用 `!` 从**本地电脑加载图片**
    - （仅限终端）在空输入框中按 `回车` 发送已添加的信息

4. 抓取其内容并在 AI 返回角色的元数据后，你可以：
    - （仅限终端）使用 **SillyTavern 的默认 .png 模板**、**本地电脑的图片**或 **URL 图片**保存角色卡图片
    - （仅限终端）重试（你可以作为用户发送额外的指令给 AI 进行反馈）
    - （仅限终端）丢弃（丢弃该角色）
    - （仅限图形界面）角色会自动保存

角色卡将保存在设置的保存路径文件夹中。

## 分支

* `main`：设计用于处理有互联网信息的已知角色，支持多个 AI 提供商（包括 OpenAI、Gemini、Groq、OpenRouter）
* `cftf`（Card for this feeling）：设计用于**仅使用图片**，根据给定的图片生成角色卡

## 截图
### 图形界面模式
![](https://files.catbox.moe/yfmyyx.png)

### 终端模式
![](https://files.catbox.moe/rk3bce.png)

## 更新日志

### 汉化版新增（2026.06）
- 全界面及文档中文汉化
- 新增系统提示词生成模式（`PRESET_SYSTEM_PROMPT`），可基于抓取内容生成完整的 LLM 角色扮演系统提示词
- 新增输出语言选择功能，支持中文、英语、日语等多种语言
- API 超时时间增加，提升长文本生成的稳定性
- 增强浏览器自动检测逻辑

### v2.0 — GUI 与多提供商支持（2026.03）
- 引入 Tkinter 图形界面应用（暗色模式、响应式布局）
- 新增 Groq 和 OpenRouter API 提供商支持
- 新增 Crawl4AI 抓取引擎选项
- 增强 API 提示词处理和多引擎回退机制

### v1.5 — 多浏览器与预设系统（2026.01 — 2026.02）
- 新增 Chrome、Firefox、Edge 多浏览器支持，自动检测系统浏览器
- 提取 AI 指令预设为独立的 `presets.py` 文件
- 支持通过外部 `prompt.py` 动态加载自定义指令
- 新增高级角色生成预设

### v1.0 — Gemini 集成与核心功能（2025.08 — 2025.12）
- 初始版本发布，基于 Selenium 的网页抓取 + OpenAI/Gemini API
- CFTF 版本：纯图片驱动的角色卡生成
- 角色卡保存格式升级至 `chara_card_v3`
- 抓取可靠性增强：重试机制与回退策略

## 许可证
本项目基于 [MIT 许可证](./LICENSE) 授权 - 详情请参见 `LICENSE` 文件。

## 致谢
- 原作者：[Gustavo Lima (gusta01010)](https://github.com/gusta01010) — [原版仓库](https://github.com/gusta01010/charmaker)
- 使用 [Selenium](https://www.selenium.dev) 和 [Crawl4AI](https://crawl4ai.com) 构建

示例中的图片来自：
- [Seeklogo](https://seeklogo.com/)
- [TYPE-MOON Fandom](https://typemoon.fandom.com/)
- [Pinclipart](https://www.pinclipart.com/)
