"""Tkinter desktop UI for the address geocoding tool."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import requests

from geo_coordinate_query.batch_convert import convert_coordinate_excel
from geo_coordinate_query.baidu_excel_processor import process_baidu_excel
from geo_coordinate_query.config import get_api_key, get_baidu_ak, update_config
from geo_coordinate_query.coordinates import (
    bd09_to_gcj02,
    gcj02_to_bd09,
    gcj02_to_wgs84,
    wgs84_to_gcj02,
)
from geo_coordinate_query.excel_processor import process_amap_excel
from geo_coordinate_query.map_services import baidu_smart_search, smart_search
from geo_coordinate_query.matching import address_similarity
from geo_coordinate_query.paths import get_app_dir


class GeoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("地址经纬度查询工具")
        self.root.geometry("750x720")
        self.root.resizable(False, False)
        self.root.configure(bg='#fafafa')
        self._build_ui()
        self._copy_tooltip = None  # 复制提示tooltip

    def _build_ui(self):
        style = ttk.Style()
        # B方案：简洁专业风 - 蓝色主色调 #2196f3
        BLUE = '#2196f3'
        DARK = '#212121'
        GREY = '#757575'

        style.configure('.', background='#fafafa', font=('微软雅黑', 10))
        style.configure('Title.TLabel', font=('微软雅黑', 14, 'bold'), background='#fafafa')
        style.configure('Section.TLabel', font=('微软雅黑', 10), foreground=GREY, background='#fafafa')
        style.configure('Info.TLabel', font=('微软雅黑', 9), background='#fafafa')
        style.configure('Result.TLabel', font=('微软雅黑', 10), foreground=DARK, background='#fafafa')
        style.configure('ResultBold.TLabel', font=('Consolas', 12, 'bold'), foreground='#1a237e', background='#fafafa')
        style.configure('ResultRow.TLabel', font=('微软雅黑', 10), foreground=DARK, background='#f5f5f5')
        style.configure('ResultRowBold.TLabel', font=('Consolas', 12, 'bold'), foreground='#1a237e', background='#f5f5f5')
        style.configure('Accent.TButton', font=('微软雅黑', 10, 'bold'))
        style.configure('Tip.TLabel', font=('微软雅黑', 9), foreground='#555555', wraplength=620, background='#fafafa')
        style.configure('Step.TLabel', font=('微软雅黑', 9), foreground='#333333', wraplength=600, background='#fafafa')
        style.configure('Link.TLabel', font=('微软雅黑', 9, 'underline'), foreground='#0066cc', background='#fafafa')
        style.configure('KeyOk.TLabel', font=('Consolas', 9), foreground='#1565c0', background='#e3f2fd')
        style.configure('KeyNo.TLabel', font=('微软雅黑', 9), foreground='#e74c3c', background='#fafafa')
        style.configure('StatusOk.TLabel', font=('微软雅黑', 9), foreground='#388e3c', background='#e8f5e9')
        style.configure('StatusLow.TLabel', font=('微软雅黑', 9), foreground='#e65100', background='#fff3e0')
        style.configure('StatusFail.TLabel', font=('微软雅黑', 9), foreground='#c62828', background='#ffebee')
        style.configure('Method.TLabel', font=('Consolas', 9), foreground='#1565c0', background='#e3f2fd')
        style.configure('SimHigh.TLabel', font=('Consolas', 9), foreground='#2e7d32', background='#e8f5e9')
        style.configure('SimMid.TLabel', font=('Consolas', 9), foreground='#e65100', background='#fff3e0')
        style.configure('SimLow.TLabel', font=('Consolas', 9), foreground='#c62828', background='#ffebee')
        style.configure('CopyBtn.TLabel', font=('微软雅黑', 8), foreground='#5c6bc0', background='#e8eaf6')
        style.configure('CopyBtnRow.TLabel', font=('微软雅黑', 8), foreground='#5c6bc0', background='#f5f5f5')
        style.configure('FieldLabel.TLabel', font=('微软雅黑', 10), foreground=GREY, background='#fafafa')
        style.configure('FieldLabelRow.TLabel', font=('微软雅黑', 10), foreground=GREY, background='#f5f5f5')
        style.configure('TLabelframe', background='#fafafa')
        style.configure('TLabelframe.Label', font=('微软雅黑', 10, 'bold'), foreground='#424242', background='#fafafa')
        style.configure('TNotebook', background='#fafafa', borderwidth=0)
        style.configure('TNotebook.Tab', font=('微软雅黑', 11), padding=[10, 5])
        style.map('TNotebook.Tab', background=[('selected', '#fafafa'), ('!selected', '#f0f0f0')])

        # Notebook选项卡
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=8)

        # Tab 1: 查询
        query_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(query_tab, text="  地址查询  ")
        self._build_query_tab(query_tab)

        # 坐标转换工具标签页
        convert_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(convert_tab, text="  坐标转换工具  ")
        self._build_convert_tab(convert_tab)

        # 百度查询标签页
        baidu_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(baidu_tab, text="  百度查询  ")
        self._build_baidu_tab(baidu_tab)

        # Tab 2: 设置
        settings_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(settings_tab, text="  设置  ")
        self._build_settings_tab(settings_tab)

    # ===== 查询选项卡 =====
    def _build_query_tab(self, parent):
        # Key状态提示 - 仅在未设置时显示
        self.key_status_label = ttk.Label(parent, text="", style='KeyNo.TLabel')
        self.key_status_label.pack(pady=(0, 5))
        self._update_key_status()

        # 单地址查询
        addr_frame = ttk.LabelFrame(parent, text="  单地址查询  ", padding=10)
        addr_frame.pack(fill='x', pady=(0, 6))

        input_row = ttk.Frame(addr_frame)
        input_row.pack(fill='x')
        ttk.Label(input_row, text="地址/建筑名:", style='Section.TLabel').pack(side='left')
        self.addr_entry = ttk.Entry(input_row, width=45, font=('微软雅黑', 10))
        self.addr_entry.pack(side='left', padx=(5, 8), fill='x', expand=True)
        self.addr_entry.bind('<Return>', lambda e: self._do_single_query())
        ttk.Button(input_row, text="查询", style='Accent.TButton', command=self._do_single_query).pack(side='right')

        # 结果显示 - 表格式网格，可点击复制
        self.result_frame = ttk.Frame(addr_frame)
        self.result_frame.pack(fill='x', pady=(8, 0))
        self.result_labels = {}
        fields = [
            ('status', '状态'), ('method', '匹配方式'),
            ('lng', '经度(GCJ-02)'), ('lat', '纬度(GCJ-02)'),
            ('wgs_lng', 'WGS-84经度'), ('wgs_lat', 'WGS-84纬度'),
            ('similarity', '地址相似度'), ('coord_type', '坐标系'),
            ('province', '省份'), ('city', '城市'), ('district', '区县'),
            ('address', '地址'), ('name', 'POI名称'), ('type', '类型')
        ]
        for i, (key, label) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 3
            is_row_bg = (row % 2 == 0)
            field_style = 'FieldLabelRow.TLabel' if is_row_bg else 'FieldLabel.TLabel'
            val_style = 'ResultRow.TLabel' if is_row_bg else 'Result.TLabel'

            ttk.Label(self.result_frame, text=f"  {label}  ", style=field_style).grid(row=row, column=col, sticky='e', padx=(0, 2), pady=1)
            lbl = ttk.Label(self.result_frame, text="—", style=val_style, anchor='w', width=24, cursor='hand2')
            lbl.grid(row=row, column=col+1, sticky='w', padx=(0, 2), pady=1)
            # 绑定点击复制事件
            lbl.bind('<Button-1>', lambda e, k=key: self._copy_label(k))
            lbl.bind('<Enter>', lambda e, l=lbl: l.configure(foreground='#1565c0'))
            lbl.bind('<Leave>', lambda e, l=lbl, s=val_style: l.configure(foreground=ttk.Style().lookup(s, 'foreground')))
            self.result_labels[key] = lbl

        # 批量Excel处理
        excel_frame = ttk.LabelFrame(parent, text="  批量Excel处理  ", padding=10)
        excel_frame.pack(fill='x', pady=(0, 6))

        file_row = ttk.Frame(excel_frame)
        file_row.pack(fill='x')
        ttk.Label(file_row, text="Excel文件:", style='Section.TLabel').pack(side='left')
        self.file_var = tk.StringVar()
        ttk.Entry(file_row, textvariable=self.file_var, width=40, font=('微软雅黑', 9), state='readonly').pack(side='left', padx=(5, 8), fill='x', expand=True)
        ttk.Button(file_row, text="选择文件", command=self._pick_file).pack(side='right')

        btn_row = ttk.Frame(excel_frame)
        btn_row.pack(fill='x', pady=(8, 0))
        self.batch_btn = ttk.Button(btn_row, text="开始批量处理", style='Accent.TButton', command=self._do_batch)
        self.batch_btn.pack(side='left')
        self.batch_status = ttk.Label(btn_row, text="", style='Info.TLabel')
        self.batch_status.pack(side='left', padx=10)

        # 进度条和日志
        self.progress = ttk.Progressbar(parent, length=650, mode='determinate')
        self.progress.pack(fill='x', pady=(0, 4))

        log_frame = ttk.LabelFrame(parent, text="  处理日志  ", padding=5)
        log_frame.pack(fill='both', expand=True)
        self.log_text = tk.Text(log_frame, height=7, font=('Consolas', 8), state='disabled', wrap='word')
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    # ===== 坐标转换工具选项卡 =====
    def _build_convert_tab(self, parent):
        # 标题
        ttk.Label(parent, text="坐标转换工具", style='Title.TLabel').pack(pady=(0, 8))
        ttk.Label(parent, text="支持 GCJ-02 ↔ WGS-84 坐标系互相转换", style='Section.TLabel').pack(pady=(0, 8))

        # 单个经纬度转换
        single_frame = ttk.LabelFrame(parent, text="  单个经纬度转换  ", padding=10)
        single_frame.pack(fill='x', pady=(0, 6))

        # 转换方向选择
        dir_row = ttk.Frame(single_frame)
        dir_row.pack(fill='x', pady=(0, 6))
        ttk.Label(dir_row, text="转换方向:", style='Section.TLabel').pack(side='left')
        self.convert_dir_var = tk.StringVar(value='gcj_to_wgs')
        ttk.Radiobutton(dir_row, text='GCJ-02 → WGS-84', variable=self.convert_dir_var,
                        value='gcj_to_wgs').pack(side='left', padx=(10, 5))
        ttk.Radiobutton(dir_row, text='WGS-84 → GCJ-02', variable=self.convert_dir_var,
                        value='wgs_to_gcj').pack(side='left', padx=5)

        # 输入行
        input_row = ttk.Frame(single_frame)
        input_row.pack(fill='x', pady=(0, 4))
        ttk.Label(input_row, text="经度:", style='Section.TLabel').pack(side='left')
        self.convert_lng_entry = ttk.Entry(input_row, width=18, font=('Consolas', 10))
        self.convert_lng_entry.pack(side='left', padx=(4, 12))
        ttk.Label(input_row, text="纬度:", style='Section.TLabel').pack(side='left')
        self.convert_lat_entry = ttk.Entry(input_row, width=18, font=('Consolas', 10))
        self.convert_lat_entry.pack(side='left', padx=(4, 12))
        ttk.Button(input_row, text="转换", style='Accent.TButton',
                   command=self._do_single_convert).pack(side='right')

        # 结果行
        result_row = ttk.Frame(single_frame)
        result_row.pack(fill='x')
        ttk.Label(result_row, text="转换结果:", style='Section.TLabel').pack(side='left')
        self.convert_result_var = tk.StringVar(value="—")
        self.convert_result_lbl = ttk.Label(result_row, textvariable=self.convert_result_var,
                                            style='ResultBold.TLabel', cursor='hand2')
        self.convert_result_lbl.pack(side='left', padx=(6, 0))
        self.convert_result_lbl.bind('<Button-1>', lambda e: self._copy_convert_result())

        # 批量文件转换
        batch_frame = ttk.LabelFrame(parent, text="  批量文件转换  ", padding=10)
        batch_frame.pack(fill='x', pady=(0, 6))

        # 列名规范提示
        ttk.Label(batch_frame,
                  text="Excel要求: 必须包含 \"\u7ecf\u5ea6\" 和 \"\u7eac\u5ea6\" 列（GCJ-02坐标系）",
                  style='Tip.TLabel').pack(anchor='w', pady=(0, 6))

        file_row = ttk.Frame(batch_frame)
        file_row.pack(fill='x')
        ttk.Label(file_row, text="Excel文件:", style='Section.TLabel').pack(side='left')
        self.convert_file_var = tk.StringVar()
        ttk.Entry(file_row, textvariable=self.convert_file_var, width=38,
                  font=('微软雅黑', 9), state='readonly').pack(side='left', padx=(5, 8), fill='x', expand=True)
        ttk.Button(file_row, text="选择文件", command=self._pick_convert_file).pack(side='right')

        btn_row = ttk.Frame(batch_frame)
        btn_row.pack(fill='x', pady=(6, 0))
        self.convert_batch_btn = ttk.Button(btn_row, text="开始批量转换", style='Accent.TButton',
                                            command=self._do_batch_convert)
        self.convert_batch_btn.pack(side='left')
        self.convert_batch_status = ttk.Label(btn_row, text="", style='Info.TLabel')
        self.convert_batch_status.pack(side='left', padx=10)

        # 进度条
        self.convert_progress = ttk.Progressbar(parent, length=700, mode='determinate')
        self.convert_progress.pack(fill='x', pady=(0, 4))

        # 转换日志
        log_frame = ttk.LabelFrame(parent, text="  转换日志  ", padding=5)
        log_frame.pack(fill='both', expand=True, pady=(0, 6))
        self.convert_log_text = tk.Text(log_frame, height=5, font=('Consolas', 8), state='disabled', wrap='word')
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.convert_log_text.yview)
        self.convert_log_text.configure(yscrollcommand=scrollbar.set)
        self.convert_log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 操作说明
        guide_frame = ttk.LabelFrame(parent, text="  使用说明  ", padding=10)
        guide_frame.pack(fill='x')

        guide_text = (
            "坐标系说明:\n"
            "  • GCJ-02: 国测局坐标系，高德地图/腾讯地图等国内地图商使用的加密坐标系\n"
            "  • WGS-84: 世界大地坐标系，GPS原始坐标、Google Earth、国际通用坐标系\n\n"
            "单个转换: 直接输入经纬度，选择转换方向，点击转换按钮即可\n"
            "批量转换: 上传包含 \"\u7ecf\u5ea6\" 和 \"\u7eac\u5ea6\" 列的Excel文件，自动转换并生成新文件\n"
            "输出文件: 批量转换结果保存在原文件同目录下，文件名后缀为 _WGS84.xlsx\n"
            "点击结果: 转换结果可点击复制到剪贴板"
        )
        ttk.Label(guide_frame, text=guide_text, style='Step.TLabel',
                  justify='left').pack(anchor='w')

    def _do_single_convert(self):
        """单个经纬度转换"""
        lng_str = self.convert_lng_entry.get().strip()
        lat_str = self.convert_lat_entry.get().strip()
        if not lng_str or not lat_str:
            messagebox.showwarning("提示", "请输入经度和纬度")
            return
        try:
            lng = float(lng_str)
            lat = float(lat_str)
        except ValueError:
            messagebox.showerror("格式错误", "经纬度必须是数字，例如: 114.298572, 30.572815")
            return
        if not (-180 <= lng <= 180):
            messagebox.showerror("范围错误", f"经度必须在 -180 到 180 之间，当前: {lng}")
            return
        if not (-90 <= lat <= 90):
            messagebox.showerror("范围错误", f"纬度必须在 -90 到 90 之间，当前: {lat}")
            return

        direction = self.convert_dir_var.get()
        try:
            if direction == 'gcj_to_wgs':
                out_lng, out_lat = gcj02_to_wgs84(lng, lat)
                label = "WGS-84"
            else:
                out_lng, out_lat = wgs84_to_gcj02(lng, lat)
                label = "GCJ-02"
            result_text = f"{out_lng}, {out_lat}  ({label})"
            self.convert_result_var.set(result_text)
            self._convert_log(f"[{direction.upper()}] {lng},{lat} -> {out_lng},{out_lat}")
        except Exception as e:
            self.convert_result_var.set("转换失败")
            self._convert_log(f"转换失败: {str(e)}")

    def _copy_convert_result(self):
        """复制转换结果"""
        text = self.convert_result_var.get()
        if not text or text == '—':
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text.strip())

    def _pick_convert_file(self):
        path = filedialog.askopenfilename(
            title="选择Excel文件",
            filetypes=[("Excel文件", "*.xlsx *.xls")],
            initialdir=str(get_app_dir())
        )
        if path:
            self.convert_file_var.set(path)

    def _convert_log(self, msg):
        self.convert_log_text.configure(state='normal')
        self.convert_log_text.insert('end', msg + '\n')
        self.convert_log_text.see('end')
        self.convert_log_text.configure(state='disabled')
        self.root.update_idletasks()

    def _do_batch_convert(self):
        """Batch convert selected Excel coordinates."""
        file_path = self.convert_file_var.get().strip()
        if not file_path or not os.path.exists(file_path):
            messagebox.showwarning("提示", "请先选择有效的Excel文件")
            return

        self.convert_batch_btn.configure(state='disabled')
        self.convert_progress['value'] = 0

        def task():
            try:
                summary = convert_coordinate_excel(
                    file_path,
                    log=lambda msg: self.root.after(0, lambda m=msg: self._convert_log(m)),
                    status=lambda pct, text: self.root.after(
                        0,
                        lambda p=pct, t=text: (
                            self.convert_progress.configure(value=p),
                            self.convert_batch_status.configure(text=t),
                        ),
                    ),
                )
                self.root.after(0, lambda: self._convert_log(summary.message))
                self.root.after(0, lambda: self.convert_batch_status.configure(text=summary.message))
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "转换完成",
                        "结果已保存到:\n"
                        f"{summary.output_file}\n\n"
                        f"转换成功: {summary.converted}\n"
                        f"失败: {summary.failed}",
                    ),
                )
            except ValueError as err:
                error_message = str(err)
                self.root.after(0, lambda msg=error_message: messagebox.showerror("格式错误", msg))
            except Exception as err:
                error_message = str(err)
                self.root.after(0, lambda msg=error_message: messagebox.showerror("错误", f"处理失败:\n{msg}"))
                self.root.after(0, lambda msg=error_message: self._convert_log(f"错误: {msg}"))
            finally:
                self.root.after(0, lambda: self.convert_batch_btn.configure(state='normal'))

        threading.Thread(target=task, daemon=True).start()

    # ===== 百度查询选项卡 =====
    def _build_baidu_tab(self, parent):
        # AK状态提示
        self.baidu_ak_status = ttk.Label(parent, text="", style='KeyNo.TLabel')
        self.baidu_ak_status.pack(pady=(0, 5))
        self._update_baidu_ak_status()

        # 单地址查询
        addr_frame = ttk.LabelFrame(parent, text="  百度地图 - 单地址查询  ", padding=10)
        addr_frame.pack(fill='x', pady=(0, 6))

        input_row = ttk.Frame(addr_frame)
        input_row.pack(fill='x')
        ttk.Label(input_row, text="地址/建筑名:", style='Section.TLabel').pack(side='left')
        self.baidu_addr_entry = ttk.Entry(input_row, width=45, font=('微软雅黑', 10))
        self.baidu_addr_entry.pack(side='left', padx=(5, 8), fill='x', expand=True)
        self.baidu_addr_entry.bind('<Return>', lambda e: self._do_baidu_single())
        ttk.Button(input_row, text="查询", style='Accent.TButton', command=self._do_baidu_single).pack(side='right')

        # 结果显示
        self.baidu_result_frame = ttk.Frame(addr_frame)
        self.baidu_result_frame.pack(fill='x', pady=(8, 0))
        self.baidu_result_labels = {}
        fields = [
            ('status', '状态'), ('method', '匹配方式'),
            ('lng', '经度(GCJ-02)'), ('lat', '纬度(GCJ-02)'),
            ('bd_lng', '百度经度(BD-09)'), ('bd_lat', '百度纬度(BD-09)'),
            ('wgs_lng', 'WGS-84经度'), ('wgs_lat', 'WGS-84纬度'),
            ('similarity', '地址相似度'), ('coord_type', '坐标系'),
            ('province', '省份'), ('city', '城市'), ('district', '区县'),
            ('address', '地址'), ('name', 'POI名称'), ('type', '类型')
        ]
        for i, (key, label) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 3
            is_row_bg = (row % 2 == 0)
            field_style = 'FieldLabelRow.TLabel' if is_row_bg else 'FieldLabel.TLabel'
            val_style = 'ResultRow.TLabel' if is_row_bg else 'Result.TLabel'
            ttk.Label(self.baidu_result_frame, text=f"  {label}  ", style=field_style).grid(row=row, column=col, sticky='e', padx=(0, 2), pady=1)
            lbl = ttk.Label(self.baidu_result_frame, text="—", style=val_style, anchor='w', width=24, cursor='hand2')
            lbl.grid(row=row, column=col+1, sticky='w', padx=(0, 2), pady=1)
            lbl.bind('<Button-1>', lambda e, k=key: self._copy_baidu_label(k))
            lbl.bind('<Enter>', lambda e, l=lbl: l.configure(foreground='#1565c0'))
            lbl.bind('<Leave>', lambda e, l=lbl, s=val_style: l.configure(foreground=ttk.Style().lookup(s, 'foreground')))
            self.baidu_result_labels[key] = lbl

        # 批量Excel处理
        excel_frame = ttk.LabelFrame(parent, text="  百度地图 - 批量Excel处理  ", padding=10)
        excel_frame.pack(fill='x', pady=(0, 6))

        file_row = ttk.Frame(excel_frame)
        file_row.pack(fill='x')
        ttk.Label(file_row, text="Excel文件:", style='Section.TLabel').pack(side='left')
        self.baidu_file_var = tk.StringVar()
        ttk.Entry(file_row, textvariable=self.baidu_file_var, width=40, font=('微软雅黑', 9), state='readonly').pack(side='left', padx=(5, 8), fill='x', expand=True)
        ttk.Button(file_row, text="选择文件", command=self._pick_baidu_file).pack(side='right')

        btn_row = ttk.Frame(excel_frame)
        btn_row.pack(fill='x', pady=(8, 0))
        self.baidu_batch_btn = ttk.Button(btn_row, text="开始批量处理", style='Accent.TButton', command=self._do_baidu_batch)
        self.baidu_batch_btn.pack(side='left')
        self.baidu_batch_status = ttk.Label(btn_row, text="", style='Info.TLabel')
        self.baidu_batch_status.pack(side='left', padx=10)

        # 进度条和日志
        self.baidu_progress = ttk.Progressbar(parent, length=650, mode='determinate')
        self.baidu_progress.pack(fill='x', pady=(0, 4))

        log_frame = ttk.LabelFrame(parent, text="  百度查询日志  ", padding=5)
        log_frame.pack(fill='both', expand=True)
        self.baidu_log_text = tk.Text(log_frame, height=7, font=('Consolas', 8), state='disabled', wrap='word')
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.baidu_log_text.yview)
        self.baidu_log_text.configure(yscrollcommand=scrollbar.set)
        self.baidu_log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 使用说明
        guide_frame = ttk.LabelFrame(parent, text="  使用说明  ", padding=8)
        guide_frame.pack(fill='x', pady=(6, 0))
        guide_text = (
            "• 百度地图API返回BD-09坐标系，已自动转换为GCJ-02（与高德一致）和WGS-84\n"
            "• 百度地图POI数据丰富，适合地标建筑、商铺、景点等查询\n"
            "• 需要先在「设置」选项卡配置百度地图AK（免费申请）"
        )
        ttk.Label(guide_frame, text=guide_text, style='Step.TLabel', justify='left').pack(anchor='w')

    def _update_baidu_ak_status(self):
        ak = get_baidu_ak()
        if ak:
            self.baidu_ak_status.pack_forget()
        else:
            self.baidu_ak_status.configure(text="未设置百度地图 AK，请前往「设置」选项卡配置！", style='KeyNo.TLabel')
            self.baidu_ak_status.pack(pady=(0, 5))

    def _set_baidu_result(self, data, input_keyword=''):
        for key, lbl in self.baidu_result_labels.items():
            lbl.configure(text="—")
        if data is None:
            self.baidu_result_labels['status'].configure(text="未找到")
            return
        if data.get('accurate'):
            self.baidu_result_labels['status'].configure(text="  查询成功  ")
        else:
            self.baidu_result_labels['status'].configure(text="  精度较低  ")
        self.baidu_result_labels['method'].configure(text=f"  {data.get('method', '—')}  ")
        self.baidu_result_labels['coord_type'].configure(text=f"  {data.get('coord_type', 'BD-09')}  ")
        lng = data.get('lng', '—')
        lat = data.get('lat', '—')
        self.baidu_result_labels['lng'].configure(text=str(lng))
        self.baidu_result_labels['lat'].configure(text=str(lat))
        bd_lng = data.get('bd_lng', '—')
        bd_lat = data.get('bd_lat', '—')
        self.baidu_result_labels['bd_lng'].configure(text=str(bd_lng))
        self.baidu_result_labels['bd_lat'].configure(text=str(bd_lat))
        # 计算WGS-84
        if lng != '—' and lat != '—':
            try:
                wgs_lng, wgs_lat = gcj02_to_wgs84(float(lng), float(lat))
                self.baidu_result_labels['wgs_lng'].configure(text=str(wgs_lng))
                self.baidu_result_labels['wgs_lat'].configure(text=str(wgs_lat))
            except Exception:
                self.baidu_result_labels['wgs_lng'].configure(text='转换失败')
                self.baidu_result_labels['wgs_lat'].configure(text='转换失败')
        # 地址相似度
        sim = address_similarity(input_keyword, data) if input_keyword else 0.0
        sim_lbl = self.baidu_result_labels.get('similarity')
        if sim_lbl:
            sim_text = f"{sim:.0%}" if sim > 0 else "—"
            sim_lbl.configure(text=f"  {sim_text}  ")
            if sim >= 0.6:
                sim_lbl.configure(style='SimHigh.TLabel')
            elif sim >= 0.4:
                sim_lbl.configure(style='SimMid.TLabel')
            else:
                sim_lbl.configure(style='SimLow.TLabel')
        self.baidu_result_labels['province'].configure(text=data.get('province', '—'))
        self.baidu_result_labels['city'].configure(text=data.get('city', '—'))
        self.baidu_result_labels['district'].configure(text=data.get('district', '—'))
        self.baidu_result_labels['address'].configure(text=data.get('address', '—'))
        self.baidu_result_labels['name'].configure(text=data.get('name', '—'))
        self.baidu_result_labels['type'].configure(text=data.get('type', '—'))

    def _copy_baidu_label(self, key):
        text = self.baidu_result_labels[key].cget('text')
        if not text or text == '—':
            return
        text = text.strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._show_copy_tooltip(key, text)

    def _check_baidu_ak(self):
        if not get_baidu_ak():
            messagebox.showwarning("提示", "请先在「设置」选项卡中配置百度地图 AK！")
            self.notebook.select(3)  # 切换到设置tab
            return False
        return True

    def _pick_baidu_file(self):
        path = filedialog.askopenfilename(
            title="选择Excel文件",
            filetypes=[("Excel文件", "*.xlsx *.xls")],
            initialdir=str(get_app_dir())
        )
        if path:
            self.baidu_file_var.set(path)

    def _baidu_log(self, msg):
        self.baidu_log_text.configure(state='normal')
        self.baidu_log_text.insert('end', msg + '\n')
        self.baidu_log_text.see('end')
        self.baidu_log_text.configure(state='disabled')
        self.root.update_idletasks()

    def _do_baidu_single(self):
        if not self._check_baidu_ak():
            return
        keyword = self.baidu_addr_entry.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "请输入地址或建筑名称")
            return
        self._set_baidu_result(None)
        self.baidu_result_labels['status'].configure(text="查询中...")
        self.root.update_idletasks()

        def task():
            result = baidu_smart_search(keyword)
            self.root.after(0, lambda: self._set_baidu_result(result, input_keyword=keyword))
            if result:
                sim = address_similarity(keyword, result)
                warn = " [相似度低]" if sim < 0.4 else ""
                self.root.after(0, lambda: self._baidu_log(
                    f"[百度单地址] {keyword} -> {result['lng']},{result['lat']} ({result.get('address','')}){warn} (相似度:{sim:.0%})"))
            else:
                self.root.after(0, lambda: self._baidu_log(f"[百度单地址] {keyword} -> 未找到"))

        threading.Thread(target=task, daemon=True).start()

    def _do_baidu_batch(self):
        if not self._check_baidu_ak():
            return
        file_path = self.baidu_file_var.get().strip()
        if not file_path or not os.path.exists(file_path):
            messagebox.showwarning("提示", "请先选择有效的Excel文件")
            return
        self.baidu_batch_btn.configure(state='disabled')
        self.baidu_progress['value'] = 0

        def task():
            try:
                summary = process_baidu_excel(
                    file_path,
                    log=lambda msg: self.root.after(0, lambda m=msg: self._baidu_log(m)),
                    status=lambda pct, text: self.root.after(
                        0,
                        lambda p=pct, t=text: (
                            self.baidu_progress.configure(value=p),
                            self.baidu_batch_status.configure(text=t),
                        ),
                    ),
                )
                self.root.after(0, lambda: self._baidu_log(summary.message))
                self.root.after(0, lambda: self.baidu_batch_status.configure(text=summary.message))
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "处理完成",
                        "结果已保存到:\n"
                        f"{summary.output_file}\n\n"
                        f"精确匹配: {summary.accurate}\n"
                        f"粗略匹配: {summary.low}\n"
                        f"失败: {summary.fail}",
                    ),
                )

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"处理失败:\n{str(e)}"))
                self.root.after(0, lambda: self._baidu_log(f"错误: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.baidu_batch_btn.configure(state='normal'))

        threading.Thread(target=task, daemon=True).start()

    # ===== 设置选项卡 =====
    def _build_settings_tab(self, parent):
        # 创建可滚动区域
        canvas = tk.Canvas(parent, highlightthickness=0, bg='#fafafa')
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, padding=4)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        _canvas_win = canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        # 内部Frame宽度跟随Canvas
        def _on_canvas_resize(event):
            canvas.itemconfig(_canvas_win, width=event.width)
        canvas.bind('<Configure>', _on_canvas_resize)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 鼠标滚轮支持（仅在Canvas区域内生效）
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        def _bind_mousewheel(event):
            canvas.bind_all('<MouseWheel>', _on_mousewheel)
        def _unbind_mousewheel(event):
            canvas.unbind_all('<MouseWheel>')
        canvas.bind('<Enter>', _bind_mousewheel)
        canvas.bind('<Leave>', _unbind_mousewheel)

        # 标题
        ttk.Label(scroll_frame, text="API Key 设置", style='Title.TLabel').pack(pady=(0, 10))

        # 高德Key输入区域
        key_frame = ttk.LabelFrame(scroll_frame, text="  高德地图 API Key  ", padding=12)
        key_frame.pack(fill='x', pady=(0, 10))

        input_row = ttk.Frame(key_frame)
        input_row.pack(fill='x')
        ttk.Label(input_row, text="API Key:", style='Section.TLabel').pack(side='left')
        self.key_entry = ttk.Entry(input_row, width=50, font=('Consolas', 10))
        self.key_entry.pack(side='left', padx=(5, 8), fill='x', expand=True)
        self.key_entry.insert(0, get_api_key())

        save_btn = ttk.Button(input_row, text="保存", style='Accent.TButton', command=self._save_key)
        save_btn.pack(side='right')

        self.key_save_status = ttk.Label(key_frame, text="", style='Info.TLabel')
        self.key_save_status.pack(pady=(5, 0))

        test_row = ttk.Frame(key_frame)
        test_row.pack(fill='x', pady=(8, 0))
        ttk.Button(test_row, text="测试 Key 是否可用", command=self._test_key).pack(side='left')
        self.test_result_label = ttk.Label(test_row, text="", style='Info.TLabel')
        self.test_result_label.pack(side='left', padx=10)

        # 高德创建说明
        guide_frame = ttk.LabelFrame(scroll_frame, text="  如何获取高德地图 API Key（免费）  ", padding=12)
        guide_frame.pack(fill='x', pady=(0, 10))

        steps = [
            ("步骤 1：注册账号",
             "打开高德开放平台官网：https://lbs.amap.com/\n"
             "点击右上角「注册」，使用手机号或邮箱完成注册，并进行实名认证。"),

            ("步骤 2：创建应用",
             "登录后进入「控制台」->「应用管理」->「我的应用」\n"
             "点击右上角「创建新应用」\n"
             "  - 应用名称：随意填写，如「地址查询工具」\n"
             "  - 应用类型：选择「其他」"),

            ("步骤 3：添加 Key",
             "在创建的应用下方，点击「添加 Key」\n"
             "  - Key 名称：随意填写\n"
             "  - 服务平台：选择「Web服务」\n"
             "  - 提交后即可获得 Key（一串32位字母数字）"),

            ("步骤 4：使用 Key",
             "将获取到的 Key 粘贴到上方的输入框中，点击「保存」即可。\n"
             "免费额度：每日 5,000 次地理编码调用，足够日常使用。"),
        ]

        for i, (title, desc) in enumerate(steps):
            step_frame = ttk.Frame(guide_frame)
            step_frame.pack(fill='x', pady=(0 if i == 0 else 8, 0))
            ttk.Label(step_frame, text=title, style='Section.TLabel').pack(anchor='w')
            ttk.Label(step_frame, text=desc, style='Step.TLabel').pack(anchor='w', padx=(10, 0))

        link_frame = ttk.Frame(guide_frame)
        link_frame.pack(fill='x', pady=(12, 0))
        link_label = ttk.Label(link_frame, text="打开高德开放平台: https://lbs.amap.com/dev/key/app", style='Link.TLabel')
        link_label.pack(anchor='w')
        link_label.bind('<Button-1>', lambda e: self._open_url("https://lbs.amap.com/dev/key/app"))
        link_label.configure(cursor='hand2')

        # ============ 百度地图 AK 设置 ============
        baidu_frame = ttk.LabelFrame(scroll_frame, text="  百度地图 AK (Access Key)  ", padding=12)
        baidu_frame.pack(fill='x', pady=(0, 10))

        baidu_input_row = ttk.Frame(baidu_frame)
        baidu_input_row.pack(fill='x')
        ttk.Label(baidu_input_row, text="百度 AK:", style='Section.TLabel').pack(side='left')
        self.baidu_ak_entry = ttk.Entry(baidu_input_row, width=50, font=('Consolas', 10))
        self.baidu_ak_entry.pack(side='left', padx=(5, 8), fill='x', expand=True)
        self.baidu_ak_entry.insert(0, get_baidu_ak())

        baidu_save_btn = ttk.Button(baidu_input_row, text="保存", style='Accent.TButton', command=self._save_baidu_ak)
        baidu_save_btn.pack(side='right')

        self.baidu_ak_save_status = ttk.Label(baidu_frame, text="", style='Info.TLabel')
        self.baidu_ak_save_status.pack(pady=(5, 0))

        baidu_test_row = ttk.Frame(baidu_frame)
        baidu_test_row.pack(fill='x', pady=(8, 0))
        ttk.Button(baidu_test_row, text="测试 AK 是否可用", command=self._test_baidu_ak).pack(side='left')
        self.baidu_test_result_label = ttk.Label(baidu_test_row, text="", style='Info.TLabel')
        self.baidu_test_result_label.pack(side='left', padx=10)

        # 百度创建说明
        baidu_guide = ttk.LabelFrame(scroll_frame, text="  如何获取百度地图 AK（免费）  ", padding=12)
        baidu_guide.pack(fill='x', pady=(0, 6))

        baidu_steps = [
            ("步骤 1：注册账号",
             "打开百度地图开放平台：https://lbsyun.baidu.com/\n"
             "点击右上角「注册」，使用手机号完成注册。"),
            ("步骤 2：创建应用",
             "登录后进入「控制台」->「应用管理」->「我的应用」\n"
             "点击「创建应用」，应用名称随意，应用类型选「其他」。"),
            ("步骤 3：获取 AK",
             "在应用下方点击「添加 Key」，应用类型选「服务端」，\n"
             "提交后即可获得 AK。"),
            ("步骤 4：使用 AK",
             "将 AK 粘贴到上方输入框，点击「保存」即可。\n"
             "免费额度：每日 30,000 次地理编码调用，足够日常使用。"),
        ]
        for i, (title, desc) in enumerate(baidu_steps):
            step_frame = ttk.Frame(baidu_guide)
            step_frame.pack(fill='x', pady=(0 if i == 0 else 8, 0))
            ttk.Label(step_frame, text=title, style='Section.TLabel').pack(anchor='w')
            ttk.Label(step_frame, text=desc, style='Step.TLabel').pack(anchor='w', padx=(10, 0))

        baidu_link_frame = ttk.Frame(baidu_guide)
        baidu_link_frame.pack(fill='x', pady=(12, 0))
        baidu_link_label = ttk.Label(baidu_link_frame, text="打开百度地图开放平台: https://lbsyun.baidu.com/apiconsole/key", style='Link.TLabel')
        baidu_link_label.pack(anchor='w')
        baidu_link_label.bind('<Button-1>', lambda e: self._open_url("https://lbsyun.baidu.com/apiconsole/key"))
        baidu_link_label.configure(cursor='hand2')

        # 底部说明
        ttk.Label(scroll_frame, text="提示：Key 保存在程序同目录下的 config.json 文件中，修改后自动生效。",
                  style='Tip.TLabel').pack(anchor='w', pady=(6, 0))

    def _update_key_status(self):
        key = get_api_key()
        if key:
            self.key_status_label.pack_forget()  # 已设置则隐藏提示
        else:
            self.key_status_label.configure(text="未设置 API Key，请前往「设置」选项卡配置！", style='KeyNo.TLabel')
            self.key_status_label.pack(pady=(0, 5))

    def _save_key(self):
        new_key = self.key_entry.get().strip()
        if not new_key:
            messagebox.showwarning("提示", "请输入 API Key")
            return
        update_config(api_key=new_key)
        self.key_save_status.configure(text="已保存!")
        self._update_key_status()
        # 2秒后清除保存提示
        self.root.after(2000, lambda: self.key_save_status.configure(text=""))

    def _test_key(self):
        key = self.key_entry.get().strip()
        if not key:
            messagebox.showwarning("提示", "请先输入 API Key")
            return

        self.test_result_label.configure(text="测试中...")
        self.root.update_idletasks()

        def task():
            # 用一个简单的geocode请求测试
            url = f"https://restapi.amap.com/v3/geocode/geo?address=%E5%8C%97%E4%BA%AC&key={key}"
            try:
                resp = requests.get(url, timeout=10)
                data = resp.json()
                if data.get('status') == '1':
                    self.root.after(0, lambda: self.test_result_label.configure(
                        text="Key 有效!", foreground='#27ae60'))
                else:
                    info = data.get('info', '未知错误')
                    self.root.after(0, lambda: self.test_result_label.configure(
                        text=f"Key 无效: {info}", foreground='#e74c3c'))
            except Exception as e:
                error_message = str(e)[:30]
                self.root.after(0, lambda msg=error_message: self.test_result_label.configure(
                    text=f"网络错误: {msg}", foreground='#e74c3c'))

        threading.Thread(target=task, daemon=True).start()

    def _open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def _save_baidu_ak(self):
        new_ak = self.baidu_ak_entry.get().strip()
        if not new_ak:
            messagebox.showwarning("提示", "请输入百度地图 AK")
            return
        update_config(baidu_ak=new_ak)
        self.baidu_ak_save_status.configure(text="已保存!")
        self._update_baidu_ak_status()
        self.root.after(2000, lambda: self.baidu_ak_save_status.configure(text=""))

    def _test_baidu_ak(self):
        ak = self.baidu_ak_entry.get().strip()
        if not ak:
            messagebox.showwarning("提示", "请先输入百度地图 AK")
            return
        self.baidu_test_result_label.configure(text="测试中...")
        self.root.update_idletasks()

        def task():
            url = f"https://api.map.baidu.com/geocoding/v3/?address=%E5%8C%97%E4%BA%AC&ak={ak}&output=json"
            try:
                resp = requests.get(url, timeout=10)
                data = resp.json()
                if data.get('status') == 0:
                    self.root.after(0, lambda: self.baidu_test_result_label.configure(
                        text="AK 有效!", foreground='#27ae60'))
                else:
                    msg = data.get('message', '未知错误')
                    self.root.after(0, lambda: self.baidu_test_result_label.configure(
                        text=f"AK 无效: {msg}", foreground='#e74c3c'))
            except Exception as e:
                error_message = str(e)[:30]
                self.root.after(0, lambda msg=error_message: self.baidu_test_result_label.configure(
                    text=f"网络错误: {msg}", foreground='#e74c3c'))

        threading.Thread(target=task, daemon=True).start()

    # ===== 查询功能 =====
    def _log(self, msg):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')
        self.root.update_idletasks()

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="选择Excel文件",
            filetypes=[("Excel文件", "*.xlsx *.xls")],
            initialdir=str(get_app_dir())
        )
        if path:
            self.file_var.set(path)

    def _set_result(self, data, input_keyword=''):
        for key, lbl in self.result_labels.items():
            lbl.configure(text="—")
        if data is None:
            self.result_labels['status'].configure(text="未找到")
            return
        if data.get('accurate'):
            self.result_labels['status'].configure(text="  查询成功  ")
        else:
            self.result_labels['status'].configure(text="  精度较低  ")
        self.result_labels['method'].configure(text=f"  {data.get('method', '—')}  ")
        self.result_labels['coord_type'].configure(text=f"  {data.get('coord_type', 'GCJ-02')}  ")
        lng = data.get('lng', '—')
        lat = data.get('lat', '—')
        self.result_labels['lng'].configure(text=str(lng))
        self.result_labels['lat'].configure(text=str(lat))
        # 计算并显示 WGS-84 坐标
        if lng != '—' and lat != '—':
            try:
                wgs_lng, wgs_lat = gcj02_to_wgs84(float(lng), float(lat))
                self.result_labels['wgs_lng'].configure(text=str(wgs_lng))
                self.result_labels['wgs_lat'].configure(text=str(wgs_lat))
            except Exception:
                self.result_labels['wgs_lng'].configure(text='转换失败')
                self.result_labels['wgs_lat'].configure(text='转换失败')
        # 计算并显示地址相似度
        sim = address_similarity(input_keyword, data) if input_keyword else 0.0
        sim_lbl = self.result_labels.get('similarity')
        if sim_lbl:
            sim_text = f"{sim:.0%}" if sim > 0 else "—"
            sim_lbl.configure(text=f"  {sim_text}  ")
            if sim >= 0.6:
                sim_lbl.configure(style='SimHigh.TLabel')
            elif sim >= 0.4:
                sim_lbl.configure(style='SimMid.TLabel')
            else:
                sim_lbl.configure(style='SimLow.TLabel')
        self.result_labels['province'].configure(text=data.get('province', '—'))
        self.result_labels['city'].configure(text=data.get('city', '—'))
        self.result_labels['district'].configure(text=data.get('district', '—'))
        self.result_labels['address'].configure(text=data.get('address', '—'))
        self.result_labels['name'].configure(text=data.get('name', '—'))
        self.result_labels['type'].configure(text=data.get('type', '—'))

    def _copy_label(self, key):
        """点击label复制内容到剪贴板"""
        text = self.result_labels[key].cget('text')
        if not text or text == '—':
            return
        text = text.strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        # 显示tooltip提示
        self._show_copy_tooltip(key, text)

    def _show_copy_tooltip(self, key, text):
        """在label旁显示"已复制"提示"""
        if self._copy_tooltip:
            try:
                self._copy_tooltip.destroy()
            except:
                pass
        lbl = self.result_labels[key]
        x = lbl.winfo_rootx() + lbl.winfo_width() + 4
        y = lbl.winfo_rooty() - 2
        self._copy_tooltip = tk.Toplevel(self.root)
        self._copy_tooltip.overrideredirect(True)
        self._copy_tooltip.geometry(f'+{x}+{y}')
        self._copy_tooltip.attributes('-topmost', True)
        tip = tk.Label(self._copy_tooltip, text='  已复制  ', bg='#323232', fg='white',
                       font=('微软雅黑', 9), padx=8, pady=3, borderwidth=0)
        tip.pack()
        self.root.after(1200, self._hide_copy_tooltip)

    def _hide_copy_tooltip(self):
        if self._copy_tooltip:
            try:
                self._copy_tooltip.destroy()
            except:
                pass
            self._copy_tooltip = None

    def _check_key(self):
        if not get_api_key():
            messagebox.showwarning("提示", "请先在「设置」选项卡中配置 API Key！")
            self.notebook.select(3)  # 切换到设置tab
            return False
        return True

    def _do_single_query(self):
        if not self._check_key():
            return
        keyword = self.addr_entry.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "请输入地址或建筑名称")
            return

        self._set_result(None)
        self.result_labels['status'].configure(text="查询中...")
        self.root.update_idletasks()

        def task():
            result = smart_search(keyword)
            self.root.after(0, lambda: self._set_result(result, input_keyword=keyword))
            if result:
                sim = address_similarity(keyword, result)
                warn = " [相似度低]" if sim < 0.4 else ""
                self.root.after(0, lambda: self._log(f"[单地址] {keyword} -> {result['lng']},{result['lat']} ({result.get('address','')}){warn} (相似度:{sim:.0%})"))
            else:
                self.root.after(0, lambda: self._log(f"[单地址] {keyword} -> 未找到"))

        threading.Thread(target=task, daemon=True).start()

    def _do_batch(self):
        if not self._check_key():
            return
        file_path = self.file_var.get().strip()
        if not file_path or not os.path.exists(file_path):
            messagebox.showwarning("提示", "请先选择有效的Excel文件")
            return

        self.batch_btn.configure(state='disabled')
        self.progress['value'] = 0

        def task():
            try:
                summary = process_amap_excel(
                    file_path,
                    log=lambda msg: self.root.after(0, lambda m=msg: self._log(m)),
                    status=lambda pct, text: self.root.after(
                        0,
                        lambda p=pct, t=text: (
                            self.progress.configure(value=p),
                            self.batch_status.configure(text=t),
                        ),
                    ),
                )
                self.root.after(0, lambda: self._log(summary.message))
                self.root.after(0, lambda: self.batch_status.configure(text=summary.message))
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "处理完成",
                        "结果已保存到:\n"
                        f"{summary.output_file}\n\n"
                        f"精确匹配: {summary.accurate}\n"
                        f"粗略匹配: {summary.low}\n"
                        f"失败: {summary.fail}",
                    ),
                )
            except Exception as err:
                error_message = str(err)
                self.root.after(0, lambda msg=error_message: messagebox.showerror("错误", f"处理失败:\n{msg}"))
                self.root.after(0, lambda msg=error_message: self._log(f"错误: {msg}"))
            finally:
                self.root.after(0, lambda: self.batch_btn.configure(state='normal'))

        threading.Thread(target=task, daemon=True).start()



def main() -> None:
    root = tk.Tk()
    GeoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
