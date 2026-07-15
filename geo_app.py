"""Tkinter UI for place resolution, nearby POI lookup, and Excel workflows."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

import pandas as pd

from geo_coordinate_query.batch_convert import convert_coordinate_excel
from geo_coordinate_query.config import get_api_key, get_baidu_ak, update_config
from geo_coordinate_query.coordinates import gcj02_to_wgs84, wgs84_to_gcj02
from geo_coordinate_query.excel_processor import BatchSummary, process_excel
from geo_coordinate_query.map_services import nearby_poi_search
from geo_coordinate_query.paths import get_app_dir
from geo_coordinate_query.query_service import PlaceCandidate, PlaceQueryService, ProviderName

PROVIDER_OPTIONS = {
    "自动对比": "auto",
    "高德地图": "amap",
    "百度地图": "baidu",
}


class GeoApp:
    """Coordinate the unified desktop workflows without map-provider duplication."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("地点与周边 POI 查询工具")
        self.root.geometry("1040x760")
        self.root.minsize(900, 620)
        self._query_service = PlaceQueryService()
        self._candidates: list[PlaceCandidate] = []
        self._nearby_records: list[dict[str, Any]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self._configure_styles()
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        place_tab = ttk.Frame(notebook, padding=12)
        batch_tab = ttk.Frame(notebook, padding=12)
        convert_tab = ttk.Frame(notebook, padding=12)
        settings_tab = ttk.Frame(notebook, padding=12)
        notebook.add(place_tab, text="地点与周边 POI")
        notebook.add(batch_tab, text="批量导入导出")
        notebook.add(convert_tab, text="坐标转换")
        notebook.add(settings_tab, text="设置")
        self._settings_tab = settings_tab

        self._build_place_tab(place_tab)
        self._build_batch_tab(batch_tab)
        self._build_convert_tab(convert_tab)
        self._build_settings_tab(settings_tab)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.configure("TNotebook.Tab", font=("微软雅黑", 10), padding=(12, 6))
        style.configure("Title.TLabel", font=("微软雅黑", 13, "bold"))
        style.configure("Muted.TLabel", foreground="#606770")
        style.configure("Accent.TButton", font=("微软雅黑", 10, "bold"))

    def _build_place_tab(self, parent: ttk.Frame) -> None:
        query_frame = ttk.LabelFrame(parent, text="地点查询", padding=10)
        query_frame.pack(fill="x", pady=(0, 8))

        row = ttk.Frame(query_frame)
        row.pack(fill="x")
        ttk.Label(row, text="地点/地址:").pack(side="left")
        self._place_entry = ttk.Entry(row, font=("微软雅黑", 10))
        self._place_entry.pack(side="left", fill="x", expand=True, padx=(6, 12))
        self._place_entry.bind("<Return>", lambda _: self._search_places())
        ttk.Label(row, text="城市:").pack(side="left")
        self._city_entry = ttk.Entry(row, width=12)
        self._city_entry.insert(0, "武汉市")
        self._city_entry.pack(side="left", padx=(6, 12))
        ttk.Label(row, text="服务:").pack(side="left")
        self._provider_var = tk.StringVar(value="自动对比")
        ttk.Combobox(
            row,
            textvariable=self._provider_var,
            values=tuple(PROVIDER_OPTIONS),
            width=10,
            state="readonly",
        ).pack(side="left", padx=(6, 12))
        self._place_search_button = ttk.Button(
            row,
            text="查询候选",
            style="Accent.TButton",
            command=self._search_places,
        )
        self._place_search_button.pack(side="right")

        candidate_bar = ttk.Frame(parent)
        candidate_bar.pack(fill="x", pady=(0, 4))
        self._candidate_status = tk.StringVar(value="输入地点后查询，选择准确的中心点再检索 POI。")
        ttk.Label(candidate_bar, textvariable=self._candidate_status, style="Muted.TLabel").pack(side="left")
        self._export_candidates_button = ttk.Button(
            candidate_bar,
            text="导出候选",
            command=self._export_candidates,
            state="disabled",
        )
        self._export_candidates_button.pack(side="right")

        candidate_frame = ttk.Frame(parent)
        candidate_frame.pack(fill="both", expand=True)
        candidate_columns = ("服务", "相似度", "匹配方式", "名称", "地址", "坐标(GCJ-02)")
        self._candidate_tree = self._make_tree(candidate_frame, candidate_columns, (70, 70, 105, 180, 300, 160), 8)
        self._candidate_tree.bind("<<TreeviewSelect>>", lambda _: self._update_selected_center())

        poi_frame = ttk.LabelFrame(parent, text="周边公共服务设施与商业 POI", padding=10)
        poi_frame.pack(fill="both", expand=True, pady=(8, 0))
        poi_controls = ttk.Frame(poi_frame)
        poi_controls.pack(fill="x", pady=(0, 5))
        ttk.Label(poi_controls, text="半径(米):").pack(side="left")
        self._radius_var = tk.StringVar(value="2000")
        ttk.Entry(poi_controls, textvariable=self._radius_var, width=10).pack(side="left", padx=(6, 12))
        self._selected_center_var = tk.StringVar(value="请先选择一个地点候选。")
        ttk.Label(poi_controls, textvariable=self._selected_center_var, style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        self._nearby_button = ttk.Button(
            poi_controls,
            text="查询周边 POI",
            style="Accent.TButton",
            command=self._search_nearby_pois,
            state="disabled",
        )
        self._nearby_button.pack(side="right")
        self._export_poi_button = ttk.Button(
            poi_controls,
            text="导出 POI",
            command=self._export_nearby_pois,
            state="disabled",
        )
        self._export_poi_button.pack(side="right", padx=(0, 6))

        poi_columns = ("类别", "名称", "地址", "类型", "距离(米)", "坐标(GCJ-02)", "坐标(WGS-84)")
        self._poi_tree = self._make_tree(poi_frame, poi_columns, (80, 180, 300, 150, 85, 160, 160), 8)

    def _build_batch_tab(self, parent: ttk.Frame) -> None:
        input_frame = ttk.LabelFrame(parent, text="Excel 批量地点查询", padding=10)
        input_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(
            input_frame,
            text="输入表可包含“地址”“名称”“原名称”列。处理后会新增坐标、地图服务、匹配方式和相似度列。",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(input_frame)
        row.pack(fill="x")
        self._batch_file_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._batch_file_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="选择 Excel", command=self._pick_batch_file).pack(side="left", padx=(8, 0))

        controls = ttk.Frame(input_frame)
        controls.pack(fill="x", pady=(8, 0))
        ttk.Label(controls, text="地图服务:").pack(side="left")
        self._batch_provider_var = tk.StringVar(value="自动对比")
        ttk.Combobox(
            controls,
            textvariable=self._batch_provider_var,
            values=tuple(PROVIDER_OPTIONS),
            width=10,
            state="readonly",
        ).pack(side="left", padx=(6, 12))
        ttk.Label(controls, text="城市:").pack(side="left")
        self._batch_city_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self._batch_city_var, width=12).pack(side="left", padx=(6, 12))
        self._batch_button = ttk.Button(
            controls,
            text="开始处理",
            style="Accent.TButton",
            command=self._process_batch,
        )
        self._batch_button.pack(side="left")
        self._batch_status = tk.StringVar(value="")
        ttk.Label(controls, textvariable=self._batch_status, style="Muted.TLabel").pack(side="left", padx=12)

        self._batch_progress = ttk.Progressbar(parent, mode="determinate")
        self._batch_progress.pack(fill="x", pady=(0, 6))
        self._batch_log = tk.Text(parent, height=22, state="disabled", font=("Consolas", 9), wrap="word")
        self._batch_log.pack(fill="both", expand=True)

    def _build_convert_tab(self, parent: ttk.Frame) -> None:
        point_frame = ttk.LabelFrame(parent, text="单点坐标转换", padding=10)
        point_frame.pack(fill="x", pady=(0, 8))
        row = ttk.Frame(point_frame)
        row.pack(fill="x")
        self._convert_direction = tk.StringVar(value="gcj_to_wgs")
        ttk.Radiobutton(row, text="GCJ-02 → WGS-84", variable=self._convert_direction, value="gcj_to_wgs").pack(side="left")
        ttk.Radiobutton(row, text="WGS-84 → GCJ-02", variable=self._convert_direction, value="wgs_to_gcj").pack(side="left", padx=12)
        ttk.Label(row, text="经度:").pack(side="left")
        self._convert_lng = ttk.Entry(row, width=16)
        self._convert_lng.pack(side="left", padx=(6, 12))
        ttk.Label(row, text="纬度:").pack(side="left")
        self._convert_lat = ttk.Entry(row, width=16)
        self._convert_lat.pack(side="left", padx=(6, 12))
        ttk.Button(row, text="转换", command=self._convert_point).pack(side="left")
        self._convert_result = tk.StringVar(value="")
        ttk.Label(point_frame, textvariable=self._convert_result).pack(anchor="w", pady=(8, 0))

        excel_frame = ttk.LabelFrame(parent, text="Excel 坐标转换", padding=10)
        excel_frame.pack(fill="x")
        ttk.Label(excel_frame, text="输入表需包含“经度”“纬度”列，处理后输出 WGS-84 坐标列。", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        row = ttk.Frame(excel_frame)
        row.pack(fill="x")
        self._convert_file_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._convert_file_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="选择 Excel", command=self._pick_convert_file).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="开始转换", command=self._convert_excel).pack(side="left", padx=(8, 0))
        self._convert_status = tk.StringVar(value="")
        ttk.Label(excel_frame, textvariable=self._convert_status, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="地图服务设置", style="Title.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(parent, text="地点自动对比会使用已配置的服务；仅配置一个 Key 时可选择对应服务。", style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        amap_frame = ttk.LabelFrame(parent, text="高德 Web 服务 Key", padding=10)
        amap_frame.pack(fill="x", pady=(0, 8))
        self._amap_key_entry = ttk.Entry(amap_frame, show="*", font=("Consolas", 10))
        self._amap_key_entry.insert(0, get_api_key())
        self._amap_key_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(amap_frame, text="保存", command=self._save_keys).pack(side="left", padx=(8, 0))

        baidu_frame = ttk.LabelFrame(parent, text="百度地图服务端 AK", padding=10)
        baidu_frame.pack(fill="x", pady=(0, 8))
        self._baidu_key_entry = ttk.Entry(baidu_frame, show="*", font=("Consolas", 10))
        self._baidu_key_entry.insert(0, get_baidu_ak())
        self._baidu_key_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(baidu_frame, text="保存", command=self._save_keys).pack(side="left", padx=(8, 0))

        self._settings_status = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._settings_status, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

    def _make_tree(
        self,
        parent: ttk.Frame,
        columns: tuple[str, ...],
        widths: tuple[int, ...],
        height: int,
    ) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        for column, width in zip(columns, widths):
            tree.heading(column, text=column)
            tree.column(column, width=width, stretch=True, anchor="w")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        return tree

    def _search_places(self) -> None:
        keyword = self._place_entry.get().strip()
        city = self._city_entry.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "请输入地点名称或详细地址")
            return
        provider = self._provider_code(self._provider_var.get())
        self._place_search_button.configure(state="disabled")
        self._candidate_status.set("正在查询候选地点...")
        self._clear_tree(self._candidate_tree)
        self._clear_tree(self._poi_tree)
        self._nearby_records = []
        self._export_poi_button.configure(state="disabled")

        def action() -> list[PlaceCandidate]:
            return self._query_service.search(keyword, city, provider)

        self._run_background(action, self._show_candidates, self._place_search_button)

    def _show_candidates(self, candidates: list[PlaceCandidate]) -> None:
        self._candidates = candidates
        if not candidates:
            self._candidate_status.set("未找到候选。请补充城市、街道或切换地图服务。")
            self._nearby_button.configure(state="disabled")
            return
        for index, candidate in enumerate(candidates):
            data = candidate.data
            self._candidate_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    self._provider_label(candidate.provider),
                    f"{candidate.score:.0%}",
                    data.get("method", ""),
                    candidate.label,
                    data.get("address", ""),
                    f"{data.get('lng', '')}, {data.get('lat', '')}",
                ),
            )
        self._candidate_tree.selection_set("0")
        self._candidate_status.set(f"找到 {len(candidates)} 个候选。请确认选中的中心点。")
        self._export_candidates_button.configure(state="normal")
        self._update_selected_center()

    def _update_selected_center(self) -> None:
        selected = self._selected_candidate()
        if not selected:
            self._nearby_button.configure(state="disabled")
            self._selected_center_var.set("请先选择一个地点候选。")
            return
        data = selected.data
        self._selected_center_var.set(
            f"当前中心：{selected.label} | {data.get('lng')}, {data.get('lat')} | {self._provider_label(selected.provider)}"
        )
        self._nearby_button.configure(state="normal")

    def _search_nearby_pois(self) -> None:
        candidate = self._selected_candidate()
        if not candidate:
            return
        try:
            radius = int(self._radius_var.get())
            if not 1 <= radius <= 50000:
                raise ValueError
        except ValueError:
            messagebox.showerror("半径错误", "请输入 1 到 50000 米之间的整数。")
            return
        self._nearby_button.configure(state="disabled")
        self._clear_tree(self._poi_tree)
        self._selected_center_var.set("正在查询公共服务设施和商业 POI...")

        def action() -> list[dict[str, Any]]:
            data = candidate.data
            return nearby_poi_search(
                candidate.provider,
                float(data["lng"]),
                float(data["lat"]),
                radius,
            )

        self._run_background(action, self._show_nearby_pois, self._nearby_button)

    def _show_nearby_pois(self, records: list[dict[str, Any]]) -> None:
        self._nearby_records = records
        for record in records:
            self._poi_tree.insert(
                "",
                "end",
                values=(
                    record.get("类别", ""),
                    record.get("名称", ""),
                    record.get("地址", ""),
                    record.get("类型", ""),
                    record.get("距中心距离(米)", ""),
                    f"{record.get('经度(GCJ-02)', '')}, {record.get('纬度(GCJ-02)', '')}",
                    f"{record.get('WGS84经度', '')}, {record.get('WGS84纬度', '')}",
                ),
            )
        self._selected_center_var.set(f"已查询到 {len(records)} 条周边 POI。")
        self._export_poi_button.configure(state="normal" if records else "disabled")

    def _process_batch(self) -> None:
        file_path = self._batch_file_var.get()
        if not file_path:
            messagebox.showwarning("提示", "请选择待处理的 Excel 文件。")
            return
        provider = self._provider_code(self._batch_provider_var.get())
        self._batch_button.configure(state="disabled")
        self._batch_progress.configure(value=0)
        self._batch_status.set("正在处理...")
        self._set_log("")

        def log(message: str) -> None:
            self.root.after(0, lambda: self._append_log(message))

        def status(percent: float, message: str) -> None:
            self.root.after(0, lambda: self._set_batch_status(percent, message))

        def action() -> BatchSummary:
            return process_excel(
                file_path,
                provider,
                log=log,
                status=status,
                city=self._batch_city_var.get().strip(),
            )

        self._run_background(action, self._show_batch_summary, self._batch_button)

    def _show_batch_summary(self, summary: BatchSummary) -> None:
        self._batch_status.set(summary.message)
        self._append_log(f"输出文件: {summary.output_file}")
        messagebox.showinfo("处理完成", f"{summary.message}\n\n结果已保存到:\n{summary.output_file}")

    def _convert_point(self) -> None:
        try:
            lng = float(self._convert_lng.get())
            lat = float(self._convert_lat.get())
            if self._convert_direction.get() == "gcj_to_wgs":
                result = gcj02_to_wgs84(lng, lat)
                name = "WGS-84"
            else:
                result = wgs84_to_gcj02(lng, lat)
                name = "GCJ-02"
        except ValueError:
            messagebox.showerror("格式错误", "经纬度必须是有效数字。")
            return
        self._convert_result.set(f"{name}: {result[0]}, {result[1]}")

    def _convert_excel(self) -> None:
        file_path = self._convert_file_var.get()
        if not file_path:
            messagebox.showwarning("提示", "请选择待转换的 Excel 文件。")
            return
        self._convert_status.set("正在转换...")

        def action() -> Any:
            return convert_coordinate_excel(file_path)

        self._run_background(action, self._show_convert_summary)

    def _show_convert_summary(self, summary: Any) -> None:
        self._convert_status.set(summary.message)
        messagebox.showinfo("转换完成", f"{summary.message}\n\n结果已保存到:\n{summary.output_file}")

    def _export_candidates(self) -> None:
        records = [candidate.as_dict() for candidate in self._candidates]
        self._export_records(records, "地点候选.xlsx", "地点候选")

    def _export_nearby_pois(self) -> None:
        self._export_records(self._nearby_records, "周边POI.xlsx", "周边 POI")

    def _export_records(self, records: list[dict[str, Any]], file_name: str, title: str) -> None:
        if not records:
            return
        output = filedialog.asksaveasfilename(
            title=f"导出{title}",
            initialdir=str(get_app_dir()),
            initialfile=file_name,
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx")],
        )
        if not output:
            return
        try:
            pd.DataFrame(records).to_excel(output, index=False)
        except OSError as err:
            messagebox.showerror("导出失败", str(err))
            return
        messagebox.showinfo("导出完成", f"已导出 {len(records)} 条{title}。")

    def _pick_batch_file(self) -> None:
        path = filedialog.askopenfilename(
            title="选择待查询的 Excel 文件",
            initialdir=str(get_app_dir()),
            filetypes=[("Excel 文件", "*.xlsx *.xls")],
        )
        if path:
            self._batch_file_var.set(path)

    def _pick_convert_file(self) -> None:
        path = filedialog.askopenfilename(
            title="选择待转换的 Excel 文件",
            initialdir=str(get_app_dir()),
            filetypes=[("Excel 文件", "*.xlsx *.xls")],
        )
        if path:
            self._convert_file_var.set(path)

    def _save_keys(self) -> None:
        update_config(
            api_key=self._amap_key_entry.get().strip(),
            baidu_ak=self._baidu_key_entry.get().strip(),
        )
        self._settings_status.set("已保存地图服务 Key。")

    def _selected_candidate(self) -> PlaceCandidate | None:
        selected = self._candidate_tree.selection()
        if not selected:
            return None
        return self._candidates[int(selected[0])]

    def _run_background(
        self,
        action: Callable[[], Any],
        on_success: Callable[[Any], None],
        button: ttk.Button | None = None,
    ) -> None:
        def task() -> None:
            try:
                result = action()
            except Exception as err:
                message = str(err)
                self.root.after(0, lambda: messagebox.showerror("操作失败", message))
            else:
                self.root.after(0, lambda: on_success(result))
            finally:
                if button:
                    self.root.after(0, lambda: button.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    def _set_batch_status(self, percent: float, message: str) -> None:
        self._batch_progress.configure(value=percent)
        self._batch_status.set(message)

    def _set_log(self, text: str) -> None:
        self._batch_log.configure(state="normal")
        self._batch_log.delete("1.0", "end")
        self._batch_log.insert("end", text)
        self._batch_log.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self._batch_log.configure(state="normal")
        self._batch_log.insert("end", text + "\n")
        self._batch_log.see("end")
        self._batch_log.configure(state="disabled")

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        tree.delete(*tree.get_children())

    @staticmethod
    def _provider_code(label: str) -> ProviderName:
        return PROVIDER_OPTIONS[label]  # type: ignore[return-value]

    @staticmethod
    def _provider_label(provider: str) -> str:
        return {"amap": "高德", "baidu": "百度"}.get(provider, provider)


def main() -> None:
    root = tk.Tk()
    GeoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
