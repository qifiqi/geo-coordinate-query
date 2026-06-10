"""
地址经纬度查询工具
支持单个地址/建筑名查询，也支持xlsx批量导入导出
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import requests
import threading
import time
import os
import sys
import json
from urllib.parse import quote
from convert_to_wgs84 import gcj02_to_wgs84

# ========== 配置管理 ==========

def _get_app_dir():
    """获取程序真实所在目录（兼容PyInstaller打包后的exe）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后的exe
        return os.path.dirname(sys.executable)
    else:
        # 正常Python脚本运行
        return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(_get_app_dir(), 'config.json')

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'api_key': ''}

def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 全局配置
_config = load_config()

def get_api_key():
    return _config.get('api_key', '')

# ========== API查询函数 ==========

def geocode_search(keyword, api_key=None):
    """地理编码搜索"""
    key = api_key or get_api_key()
    if not key:
        return None
    encoded = quote(keyword.strip())
    url = f"https://restapi.amap.com/v3/geocode/geo?address={encoded}&key={key}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == '1' and data.get('count') != '0':
            geo = data['geocodes'][0]
            lng, lat = geo['location'].split(',')
            district = geo.get('district', '')
            city = geo.get('city', '')
            province = geo.get('province', '')
            formatted = geo.get('formatted_address', '')
            level = geo.get('level', '')
            is_accurate = bool(district)
            return {
                'lng': float(lng), 'lat': float(lat),
                'province': province, 'city': city, 'district': district,
                'address': formatted, 'level': level,
                'accurate': is_accurate, 'method': 'geocode'
            }
    except:
        pass
    return None

def poi_search(keyword, city='', api_key=None):
    """POI搜索"""
    key = api_key or get_api_key()
    if not key:
        return None
    encoded = quote(keyword.strip())
    url = f"https://restapi.amap.com/v3/place/text?keywords={encoded}&city={quote(city)}&key={key}&offset=3"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == '1' and int(data.get('count', 0)) > 0:
            poi = data['pois'][0]
            lng, lat = poi['location'].split(',')
            return {
                'lng': float(lng), 'lat': float(lat),
                'province': poi.get('pname', ''),
                'city': poi.get('cityname', ''),
                'district': poi.get('adname', ''),
                'address': poi.get('address', ''),
                'name': poi.get('name', ''),
                'tel': poi.get('tel', ''),
                'type': poi.get('type', ''),
                'accurate': True, 'method': 'POI'
            }
    except:
        pass
    return None

def smart_search(keyword):
    """多策略智能搜索，返回最佳结果"""
    if not keyword or not keyword.strip():
        return None
    keyword = keyword.strip()
    candidates = []

    result = geocode_search(keyword)
    if result:
        candidates.append(result)
        if result['accurate']:
            return result

    result = poi_search(keyword)
    if result:
        candidates.append(result)
        if result['accurate']:
            return result

    return candidates[0] if candidates else None

# ========== Excel处理函数 ==========

def build_search_address(row):
    address = str(row.get('地址', '')).strip() if pd.notna(row.get('地址')) else ''
    name = str(row.get('名称', '')).strip() if pd.notna(row.get('名称')) else ''
    old_name = str(row.get('原名称', '')).strip() if pd.notna(row.get('原名称')) else ''
    if address and len(address) > 3:
        return address
    if name and name != 'nan' and len(name) > 2:
        return f"武汉市{name}"
    if old_name and old_name != 'nan' and len(old_name) > 2:
        return f"武汉市{old_name}"
    return address if address else name

def smart_search_excel(row):
    address = str(row.get('地址', '')).strip() if pd.notna(row.get('地址')) else ''
    name = str(row.get('名称', '')).strip() if pd.notna(row.get('名称')) else ''
    old_name = str(row.get('原名称', '')).strip() if pd.notna(row.get('原名称')) else ''
    candidates = []

    if address and len(address) > 3:
        result = geocode_search(address)
        if result:
            candidates.append((result, address))
            if result['accurate']:
                return result, address

    if name and name != 'nan' and len(name) > 2 and name not in ['居民住宅', '幼儿园']:
        result = poi_search(name)
        if result:
            candidates.append((result, name))
            if result['accurate']:
                return result, name

    if old_name and old_name != 'nan' and len(old_name) > 2:
        result = poi_search(old_name)
        if result:
            candidates.append((result, old_name))
            if result['accurate']:
                return result, old_name

    if name and address and name != 'nan':
        combined = f"{name}({address})"
        result = poi_search(combined)
        if result:
            candidates.append((result, combined))

    for c, kw in candidates:
        if c.get('accurate'):
            return c, kw
    if candidates:
        return candidates[0]
    return None, ""

# ========== GUI应用 ==========

class GeoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("地址经纬度查询工具")
        self.root.geometry("700x660")
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

    # ===== 设置选项卡 =====
    def _build_settings_tab(self, parent):
        # 标题
        ttk.Label(parent, text="API Key 设置", style='Title.TLabel').pack(pady=(0, 10))

        # Key输入区域
        key_frame = ttk.LabelFrame(parent, text="  高德地图 API Key  ", padding=12)
        key_frame.pack(fill='x', pady=(0, 10))

        input_row = ttk.Frame(key_frame)
        input_row.pack(fill='x')
        ttk.Label(input_row, text="API Key:", style='Section.TLabel').pack(side='left')
        self.key_entry = ttk.Entry(input_row, width=50, font=('Consolas', 10))
        self.key_entry.pack(side='left', padx=(5, 8), fill='x', expand=True)
        # 加载已保存的key
        self.key_entry.insert(0, get_api_key())

        save_btn = ttk.Button(input_row, text="保存", style='Accent.TButton', command=self._save_key)
        save_btn.pack(side='right')

        self.key_save_status = ttk.Label(key_frame, text="", style='Info.TLabel')
        self.key_save_status.pack(pady=(5, 0))

        # 测试按钮
        test_row = ttk.Frame(key_frame)
        test_row.pack(fill='x', pady=(8, 0))
        ttk.Button(test_row, text="测试 Key 是否可用", command=self._test_key).pack(side='left')
        self.test_result_label = ttk.Label(test_row, text="", style='Info.TLabel')
        self.test_result_label.pack(side='left', padx=10)

        # 创建说明
        guide_frame = ttk.LabelFrame(parent, text="  如何获取高德地图 API Key（免费）  ", padding=12)
        guide_frame.pack(fill='both', expand=True)

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

        # 底部链接
        link_frame = ttk.Frame(guide_frame)
        link_frame.pack(fill='x', pady=(12, 0))
        link_label = ttk.Label(link_frame, text="打开高德开放平台: https://lbs.amap.com/dev/key/app", style='Link.TLabel')
        link_label.pack(anchor='w')
        link_label.bind('<Button-1>', lambda e: self._open_url("https://lbs.amap.com/dev/key/app"))
        link_label.configure(cursor='hand2')

        # 底部说明
        ttk.Label(guide_frame, text="提示：Key 保存在程序同目录下的 config.json 文件中，修改后自动生效。",
                  style='Tip.TLabel').pack(anchor='w', pady=(10, 0))

    def _update_key_status(self):
        key = get_api_key()
        if key:
            self.key_status_label.pack_forget()  # 已设置则隐藏提示
        else:
            self.key_status_label.configure(text="未设置 API Key，请前往「设置」选项卡配置！", style='KeyNo.TLabel')
            self.key_status_label.pack(pady=(0, 5))

    def _save_key(self):
        global _config
        new_key = self.key_entry.get().strip()
        if not new_key:
            messagebox.showwarning("提示", "请输入 API Key")
            return
        _config['api_key'] = new_key
        save_config(_config)
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
                self.root.after(0, lambda: self.test_result_label.configure(
                    text=f"网络错误: {str(e)[:30]}", foreground='#e74c3c'))

        threading.Thread(target=task, daemon=True).start()

    def _open_url(self, url):
        import webbrowser
        webbrowser.open(url)

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
            initialdir=_get_app_dir()
        )
        if path:
            self.file_var.set(path)

    def _set_result(self, data):
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
            self.notebook.select(1)  # 切换到设置tab
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
            self.root.after(0, lambda: self._set_result(result))
            if result:
                self.root.after(0, lambda: self._log(f"[单地址] {keyword} -> {result['lng']},{result['lat']} ({result.get('address','')})"))
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
                df = pd.read_excel(file_path)
                total = len(df)
                self.root.after(0, lambda: self._log(f"读取文件: {os.path.basename(file_path)}，共{total}行"))

                df['经度'] = None
                df['纬度'] = None
                df['WGS84经度'] = None
                df['WGS84纬度'] = None
                df['省份'] = None
                df['城市'] = None
                df['区县'] = None
                df['API返回地址'] = None
                df['匹配方式'] = None
                df['精度'] = None

                accurate = 0
                low = 0
                fail = 0

                for idx, row in df.iterrows():
                    search_kw = build_search_address(row)
                    result, kw_used = smart_search_excel(row)

                    if result:
                        df.at[idx, '经度'] = result['lng']
                        df.at[idx, '纬度'] = result['lat']
                        # 计算 WGS-84 坐标
                        try:
                            wgs_lng, wgs_lat = gcj02_to_wgs84(float(result['lng']), float(result['lat']))
                            df.at[idx, 'WGS84经度'] = wgs_lng
                            df.at[idx, 'WGS84纬度'] = wgs_lat
                        except Exception:
                            pass
                        df.at[idx, '省份'] = result.get('province', '')
                        df.at[idx, '城市'] = result.get('city', '')
                        df.at[idx, '区县'] = result.get('district', '')
                        df.at[idx, 'API返回地址'] = result.get('address', '') or result.get('name', '')
                        df.at[idx, '匹配方式'] = result.get('method', '')

                        if result.get('accurate'):
                            df.at[idx, '精度'] = '精确'
                            accurate += 1
                        else:
                            df.at[idx, '精度'] = '粗略'
                            low += 1

                        status = "OK" if result.get('accurate') else "LOW"
                        self.root.after(0, lambda i=idx, t=total, s=status, r=result:
                            self._log(f"[{i+1}/{t}] {s} {r['lng']},{r['lat']} ({r.get('address','')})"))
                    else:
                        fail += 1
                        df.at[idx, '精度'] = '失败'
                        self.root.after(0, lambda i=idx, t=total:
                            self._log(f"[{i+1}/{t}] FAIL"))

                    pct = (idx + 1) / total * 100
                    self.root.after(0, lambda p=pct: self.progress.configure(value=p))
                    self.root.after(0, lambda i=idx, t=total: self.batch_status.configure(text=f"处理中 {i+1}/{t}"))
                    time.sleep(0.15)

                dir_path = os.path.dirname(file_path)
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_file = os.path.join(dir_path, f"{base_name}_经纬度.xlsx")
                df.to_excel(output_file, index=False, engine='openpyxl')

                summary = f"完成! 精确:{accurate} 粗略:{low} 失败:{fail} 共:{total}"
                self.root.after(0, lambda: self._log(summary))
                self.root.after(0, lambda: self.batch_status.configure(text=summary))
                self.root.after(0, lambda: messagebox.showinfo("处理完成",
                    f"结果已保存到:\n{output_file}\n\n精确匹配: {accurate}\n粗略匹配: {low}\n失败: {fail}"))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"处理失败:\n{str(e)}"))
                self.root.after(0, lambda: self._log(f"错误: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.batch_btn.configure(state='normal'))

        threading.Thread(target=task, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = GeoApp(root)
    root.mainloop()
