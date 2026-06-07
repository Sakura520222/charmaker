"""
评分表（准确度 + 角色扮演质量）：
              描述        问候语      综合
预设 1    88.3         88.0        88.2
预设 2    78.0         84.3        81.2
预设 3    82.0         78.0        80.0

- 以下模型互联网来源的平均分析结果：
    anthropic/claude-opus-4.6-search
    google/gemini-3.1-pro-preview-grounding,
    gpt-5.2-search

使用相同的 2 个 URL + 2 张图片和 gemini-3-flash-preview + crawl4ai 生成。

预设 1：实验性，效果优秀。
预设 2：倾向于较短的描述（1300 - 2100）
预设 3：倾向于较长的描述（2000 - 3500），效果优秀。平均一致性较低，但最佳生成有时可超越预设 1。
"""

from presets import PRESET1, PRESET2, PRESET3

INSTRUCTIONS = PRESET1
