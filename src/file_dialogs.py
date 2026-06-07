import tkinter as tk
from tkinter import filedialog

def open_image_dialog():
    """打开文件对话框选择图片文件。"""
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    filepath = filedialog.askopenfilename(
        title="选择图片",
        filetypes=(
            ("图片文件", "*.png *.jpg *.jpeg *.webp"),
            ("所有文件", "*.*")
        )
    )
    return filepath

def open_folder_dialog(initial_dir="."):
    """打开文件夹选择对话框。"""
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    folder_path = filedialog.askdirectory(
        title="选择保存角色的文件夹",
        initialdir=initial_dir
    )
    return folder_path
