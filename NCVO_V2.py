import customtkinter as ctk
import netCDF4 as nc
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter, MultipleLocator
from tkinter import filedialog, messagebox
import os
import warnings
import json
from PIL import Image

# 忽略 numpy 计算全 NaN 切片时的警告
warnings.filterwarnings("ignore", category=RuntimeWarning)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class ModernNcView(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Modern NcView - Ultimate Spatial & Cross-Section Pro")
        self.geometry("1250x950") 

        # --- 核心数据状态 ---
        self.ds, self.da = None, None
        self.ref_ds = None 
        self.var_name = ""
        
        # 空间阵列
        self.lon_arr, self.lat_arr = None, None
        self.x_arr, self.y_arr = None, None
        self.z_arr, self.time_arr = None, None
        self.height_3d = None 
        
        self.img = None
        self.cbar = None
        
        self.sim_type = "UNKNOWN" 
        self.current_t = 0
        self.slider2_val = 0 
        self.slice_plane = "X-Y (Horizontal)"
        
        self.auto_scale = True 
        self.vmin_val, self.vmax_val = 0.0, 1.0
        self.levels_val = 30 
        self.cmap_name = 'jet'
        
        self.data_ndim, self.nt, self.nz, self.ny, self.nx = 0, 0, 0, 0, 0
        self.has_time, self.has_z = False, False

        # --- 绘图缓存数据（用于导出） ---
        self.current_plot_x = None
        self.current_plot_y = None
        self.current_data_slice = None

        # --- UI自定义锁定状态 ---
        self.user_set_axes = False
        self.user_set_labels = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_sidebar()
        self.create_main_canvas()
        self.bind_shortcuts()

    def create_sidebar(self):
        self.sidebar = ctk.CTkScrollableFrame(self, width=380, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        title_lbl = ctk.CTkLabel(self.sidebar, text="WRF Spatial Probe", font=ctk.CTkFont(size=22, weight="bold"))
        title_lbl.pack(pady=(20, 15))

        # ==========================================
        # 1. Data & Variables (数据导入与变量选择区)
        # ==========================================
        sec1 = ctk.CTkFrame(self.sidebar, corner_radius=8)
        sec1.pack(fill="x", padx=10, pady=(0, 15))
        ctk.CTkLabel(sec1, text="1. Data & Import", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.open_btn = ctk.CTkButton(sec1, text="📂 Open Main NC File", command=self.open_file, fg_color="#2b8a3e", hover_color="#237032")
        self.open_btn.pack(fill="x", padx=10, pady=5)
        self.ref_btn = ctk.CTkButton(sec1, text="🔗 Import Spatial Ref", command=self.open_ref_file, fg_color="#1f538d")
        self.ref_btn.pack(fill="x", padx=10, pady=5)

        self.sim_label = ctk.CTkLabel(sec1, text="Case: Waiting...", text_color="#f39c12", font=ctk.CTkFont(weight="bold"))
        self.sim_label.pack(anchor="w", padx=10, pady=5)

        ctk.CTkLabel(sec1, text="Select Variable:").pack(anchor="w", padx=10, pady=(5,0))
        self.var_dropdown = ctk.CTkComboBox(sec1, values=["Open file first"], command=self.change_var)
        self.var_dropdown.pack(fill="x", padx=10, pady=(0, 15))

        # ==========================================
        # 2. Navigation & Slicing (维度切片与导航区)
        # ==========================================
        sec2 = ctk.CTkFrame(self.sidebar, corner_radius=8)
        sec2.pack(fill="x", padx=10, pady=(0, 15))
        ctk.CTkLabel(sec2, text="2. Navigation & Slicing", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(sec2, text="Slice Plane:").pack(anchor="w", padx=10)
        self.slice_dropdown = ctk.CTkComboBox(sec2, values=["X-Y (Horizontal)", "X-Z (Cross-section)", "Y-Z (Cross-section)"], command=self.change_slice_plane)
        self.slice_dropdown.set(self.slice_plane)
        self.slice_dropdown.pack(fill="x", padx=10, pady=(0, 10))

        self.time_label = ctk.CTkLabel(sec2, text="Time Axis: 0", cursor="hand2")
        self.time_label.pack(anchor="w", padx=10)
        t_frame = ctk.CTkFrame(sec2, fg_color="transparent")
        t_frame.pack(fill="x", padx=10, pady=(0, 10))
        t_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(t_frame, text="<", width=28, command=lambda: self.step_time(-1)).grid(row=0, column=0, padx=(0, 5))
        self.time_slider = ctk.CTkSlider(t_frame, from_=0, to=1, number_of_steps=1, command=self.change_time)
        self.time_slider.set(0); self.time_slider.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(t_frame, text=">", width=28, command=lambda: self.step_time(1)).grid(row=0, column=2, padx=(5, 0))

        self.dim2_label = ctk.CTkLabel(sec2, text="Level Axis: 0", cursor="hand2")
        self.dim2_label.pack(anchor="w", padx=10)
        d2_frame = ctk.CTkFrame(sec2, fg_color="transparent")
        d2_frame.pack(fill="x", padx=10, pady=(0, 15))
        d2_frame.grid_columnconfigure(1, weight=1)
        self.btn_dim2_prev = ctk.CTkButton(d2_frame, text="<", width=28, command=lambda: self.step_dim2(-1))
        self.btn_dim2_prev.grid(row=0, column=0, padx=(0, 5))
        self.dim2_slider = ctk.CTkSlider(d2_frame, from_=0, to=1, number_of_steps=1, command=self.change_dim2)
        self.dim2_slider.set(0); self.dim2_slider.grid(row=0, column=1, sticky="ew")
        self.btn_dim2_next = ctk.CTkButton(d2_frame, text=">", width=28, command=lambda: self.step_dim2(1))
        self.btn_dim2_next.grid(row=0, column=2, padx=(5, 0))

        # ==========================================
        # 3. Plot Settings (绘图颜色与高度设置区)
        # ==========================================
        sec3 = ctk.CTkFrame(self.sidebar, corner_radius=8)
        sec3.pack(fill="x", padx=10, pady=(0, 15))
        ctk.CTkLabel(sec3, text="3. Plot Settings", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))

        self.use_phys_height_var = ctk.BooleanVar(value=True)
        self.phys_height_cb = ctk.CTkCheckBox(sec3, text="Use Physical Height (Y-axis)", variable=self.use_phys_height_var, command=self.update_plot)
        self.phys_height_cb.pack(anchor="w", padx=10, pady=5)

        self.interp_var = ctk.BooleanVar(value=False)
        self.interp_checkbox = ctk.CTkCheckBox(sec3, text="Enable Height Interp (m)", variable=self.interp_var, command=self.update_plot)
        self.interp_checkbox.pack(anchor="w", padx=10, pady=5)
        self.target_height_entry = ctk.CTkEntry(sec3, placeholder_text="e.g.: 500")
        self.target_height_entry.insert(0, "500")
        self.target_height_entry.pack(fill="x", padx=10, pady=(0, 5))
        self.target_height_entry.bind("<Return>", lambda e: self.update_plot())

        cmap_header_frame = ctk.CTkFrame(sec3, fg_color="transparent")
        cmap_header_frame.pack(fill="x", padx=10, pady=(5, 2))
        
        ctk.CTkLabel(cmap_header_frame, text="Colormap:").pack(side="left")
        
        self.cmap_preview_label = ctk.CTkLabel(cmap_header_frame, text="")
        self.cmap_preview_label.pack(side="left", padx=(10, 0))
        
        self.cmap_dropdown = ctk.CTkComboBox(sec3, values=['jet', 'viridis', 'plasma', 'coolwarm', 'RdBu_r', 'magma', 'terrain','temp_diff_18lev','MPL_RdYlGn_r','MPL_RdYlBu_r','MPL_Reds','MPL_rainbow','MPL_ocean_r','MPL_YlGnBu'], command=self.change_cmap)
        self.cmap_dropdown.set(self.cmap_name)
        self.cmap_dropdown.pack(fill="x", padx=10, pady=(0, 10))
        
        self.update_cmap_preview(self.cmap_name)

        val_frame = ctk.CTkFrame(sec3, fg_color="transparent")
        val_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(val_frame, text="Min:").grid(row=0, column=0, padx=(5,2))
        self.vmin_entry = ctk.CTkEntry(val_frame, width=45); self.vmin_entry.grid(row=0, column=1)
        ctk.CTkLabel(val_frame, text="Max:").grid(row=0, column=2, padx=(5,2))
        self.vmax_entry = ctk.CTkEntry(val_frame, width=45); self.vmax_entry.grid(row=0, column=3)
        ctk.CTkLabel(val_frame, text="Lvls:").grid(row=0, column=4, padx=(5,2))
        self.levels_entry = ctk.CTkEntry(val_frame, width=40); self.levels_entry.insert(0, str(self.levels_val)); self.levels_entry.grid(row=0, column=5)
        self.levels_entry.bind("<Return>", self.on_levels_enter)

        btn_frame = ctk.CTkFrame(sec3, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(10, 15))
        btn_frame.grid_columnconfigure(0, weight=1); btn_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(btn_frame, text="Lock Limits", command=self.apply_clim).grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(btn_frame, text="Auto Scale", command=self.reset_clim, fg_color="#555555", hover_color="#333333").grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # ==========================================
        # 4. Display & Axes (显示数据设置区)
        # ==========================================
        sec4 = ctk.CTkFrame(self.sidebar, corner_radius=8)
        sec4.pack(fill="x", padx=10, pady=(0, 15))
        ctk.CTkLabel(sec4, text="4. Display & Axes", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))

        ctk.CTkLabel(sec4, text="Aspect Ratio (Y/X stretch):").pack(anchor="w", padx=10)
        self.aspect_dropdown = ctk.CTkComboBox(sec4, values=['auto', 'equal', '0.5', '1.0', '2.0', '5.0'], command=lambda e: self.update_plot())
        self.aspect_dropdown.set('auto')
        self.aspect_dropdown.pack(fill="x", padx=10, pady=(0, 5))

        # 刻度方向与步长
        ctk.CTkLabel(sec4, text="Tick Dir & Step (Empty=Auto):").pack(anchor="w", padx=10, pady=(5,0))
        tick_opt_frame = ctk.CTkFrame(sec4, fg_color="transparent")
        tick_opt_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(tick_opt_frame, text="Dir:").pack(side="left")
        self.tick_dir_dropdown = ctk.CTkComboBox(tick_opt_frame, values=['out', 'in', 'inout'], width=70, command=lambda e: self.update_plot())
        self.tick_dir_dropdown.set('out')
        self.tick_dir_dropdown.pack(side="left", padx=(2, 10))
        
        ctk.CTkLabel(tick_opt_frame, text="dX:").pack(side="left")
        self.x_step_entry = ctk.CTkEntry(tick_opt_frame, width=45)
        self.x_step_entry.pack(side="left", padx=2)
        self.x_step_entry.bind("<Return>", lambda e: self.update_plot())
        
        ctk.CTkLabel(tick_opt_frame, text="dY:").pack(side="left")
        self.y_step_entry = ctk.CTkEntry(tick_opt_frame, width=45)
        self.y_step_entry.pack(side="left", padx=2)
        self.y_step_entry.bind("<Return>", lambda e: self.update_plot())

        ctk.CTkLabel(sec4, text="Axis Limits:").pack(anchor="w", padx=10, pady=(5,0))
        r1 = ctk.CTkFrame(sec4, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(r1, text="X:").pack(side="left")
        self.main_xmin = ctk.CTkEntry(r1, width=60); self.main_xmin.pack(side="left", padx=2, expand=True)
        self.main_xmax = ctk.CTkEntry(r1, width=60); self.main_xmax.pack(side="left", padx=2, expand=True)

        r2 = ctk.CTkFrame(sec4, fg_color="transparent")
        r2.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(r2, text="Y:").pack(side="left")
        self.main_ymin = ctk.CTkEntry(r2, width=60); self.main_ymin.pack(side="left", padx=2, expand=True)
        self.main_ymax = ctk.CTkEntry(r2, width=60); self.main_ymax.pack(side="left", padx=2, expand=True)

        r3 = ctk.CTkFrame(sec4, fg_color="transparent")
        r3.pack(fill="x", padx=10, pady=(5, 5))
        ctk.CTkButton(r3, text="Apply Limits", command=self.apply_axis_limits).pack(side="left", padx=(0,5), expand=True, fill="x")
        ctk.CTkButton(r3, text="Auto Reset", fg_color="#555555", hover_color="#333333", command=self.reset_display_settings).pack(side="left", expand=True, fill="x")

        # 主图标题定义
        ctk.CTkLabel(sec4, text="Custom Text (LaTeX: $...$):").pack(anchor="w", padx=10, pady=(5,0))
        
        t_frame = ctk.CTkFrame(sec4, fg_color="transparent")
        t_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(t_frame, text="Title:").pack(side="left")
        self.title_entry = ctk.CTkEntry(t_frame, height=25)
        self.title_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.title_entry.bind("<Return>", self.apply_custom_labels)

        xl_frame = ctk.CTkFrame(sec4, fg_color="transparent")
        xl_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(xl_frame, text="X Lbl:").pack(side="left")
        self.xlabel_entry = ctk.CTkEntry(xl_frame, height=25)
        self.xlabel_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.xlabel_entry.bind("<Return>", self.apply_custom_labels)
        
        yl_frame = ctk.CTkFrame(sec4, fg_color="transparent")
        yl_frame.pack(fill="x", padx=10, pady=(2, 10))
        ctk.CTkLabel(yl_frame, text="Y Lbl:").pack(side="left")
        self.ylabel_entry = ctk.CTkEntry(yl_frame, height=25)
        self.ylabel_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.ylabel_entry.bind("<Return>", self.apply_custom_labels)

        # ==========================================
        # 5. Advanced Plot Styling (高级字体、色条与刻度运算)
        # ==========================================
        sec5 = ctk.CTkFrame(self.sidebar, corner_radius=8)
        sec5.pack(fill="x", padx=10, pady=(0, 15))
        ctk.CTkLabel(sec5, text="5. Plot Styling & CBar", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))

        # 字体与字号
        font_frame = ctk.CTkFrame(sec5, fg_color="transparent")
        font_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(font_frame, text="Font:").grid(row=0, column=0, sticky="w", pady=2)
        self.font_dropdown = ctk.CTkComboBox(font_frame, values=['Times New Roman','DejaVu Sans', 'Arial', 'Helvetica', 'Courier New', 'Consolas'], width=130)
        self.font_dropdown.set('Times New Roman')
        self.font_dropdown.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        ctk.CTkLabel(font_frame, text="Size:").grid(row=0, column=2, sticky="w", pady=2, padx=(5,0))
        self.fontsize_entry = ctk.CTkEntry(font_frame, width=45)
        self.fontsize_entry.insert(0, "11")
        self.fontsize_entry.grid(row=0, column=3, sticky="w", padx=5, pady=2)

        # 刻度线运算
        ctk.CTkLabel(sec5, text="Tick Math (e.g. *1000, -273.15):").pack(anchor="w", padx=10, pady=(5,0))
        tick_frame = ctk.CTkFrame(sec5, fg_color="transparent")
        tick_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(tick_frame, text="X:").pack(side="left")
        self.xtick_math = ctk.CTkEntry(tick_frame, width=80)
        self.xtick_math.pack(side="left", padx=(2, 10), expand=True, fill="x")
        ctk.CTkLabel(tick_frame, text="Y:").pack(side="left")
        self.ytick_math = ctk.CTkEntry(tick_frame, width=80)
        self.ytick_math.pack(side="left", padx=(2, 0), expand=True, fill="x")

        # Colorbar 高级控制
        ctk.CTkLabel(sec5, text="Colorbar Layout:").pack(anchor="w", padx=10, pady=(10,0))
        cb_frame = ctk.CTkFrame(sec5, fg_color="transparent")
        cb_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(cb_frame, text="Orient:").grid(row=0, column=0, sticky="w", pady=2)
        self.cb_orient = ctk.CTkComboBox(cb_frame, values=['vertical', 'horizontal'], width=90, command=self.on_cbar_orient_change)
        self.cb_orient.set('vertical')
        self.cb_orient.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        ctk.CTkLabel(cb_frame, text="Pad:").grid(row=0, column=2, sticky="w", pady=2)
        self.cb_pad = ctk.CTkEntry(cb_frame, width=45)
        self.cb_pad.insert(0, "0.05") 
        self.cb_pad.grid(row=0, column=3, sticky="w", padx=5, pady=2)
        
        ctk.CTkLabel(cb_frame, text="Length:").grid(row=1, column=0, sticky="w", pady=2)
        self.cb_shrink = ctk.CTkEntry(cb_frame, width=90)
        self.cb_shrink.insert(0, "1.0")
        self.cb_shrink.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        ctk.CTkLabel(cb_frame, text="Aspect:").grid(row=1, column=2, sticky="w", pady=2)
        self.cb_aspect = ctk.CTkEntry(cb_frame, width=45)
        self.cb_aspect.insert(0, "20")
        self.cb_aspect.grid(row=1, column=3, sticky="w", padx=5, pady=2)

        cb_lbl_frame = ctk.CTkFrame(sec5, fg_color="transparent")
        cb_lbl_frame.pack(fill="x", padx=10, pady=(5,2))
        ctk.CTkLabel(cb_lbl_frame, text="CB Lbl:").pack(side="left")
        self.cb_label_entry = ctk.CTkEntry(cb_lbl_frame, height=25)
        self.cb_label_entry.pack(side="left", fill="x", expand=True, padx=(5,0))
        self.cb_label_entry.bind("<Return>", self.apply_custom_labels)

        # Colorbar 刻度最值与步长
        cb_step_frame = ctk.CTkFrame(sec5, fg_color="transparent")
        cb_step_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(cb_step_frame, text="Ticks:").pack(side="left")
        
        self.cb_tick_min = ctk.CTkEntry(cb_step_frame, width=45, placeholder_text="Min")
        self.cb_tick_min.pack(side="left", padx=2)
        self.cb_tick_min.bind("<Return>", lambda e: self.update_plot())
        
        self.cb_tick_max = ctk.CTkEntry(cb_step_frame, width=45, placeholder_text="Max")
        self.cb_tick_max.pack(side="left", padx=2)
        self.cb_tick_max.bind("<Return>", lambda e: self.update_plot())

        self.cb_step_entry = ctk.CTkEntry(cb_step_frame, width=45, placeholder_text="Step")
        self.cb_step_entry.pack(side="left", padx=2)
        self.cb_step_entry.bind("<Return>", lambda e: self.update_plot())

        ctk.CTkButton(sec5, text="Apply Global Styles", command=self.update_plot).pack(fill="x", padx=10, pady=(15, 15))

        # ==========================================
        # 6. Export, Save & Styles (导出与模板区)
        # ==========================================
        sec6 = ctk.CTkFrame(self.sidebar, corner_radius=8)
        sec6.pack(fill="x", padx=10, pady=(0, 20))
        ctk.CTkLabel(sec6, text="6. Export, Save & Styles", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))

        # 保存和加载样式模板的按钮
        style_btn_frame = ctk.CTkFrame(sec6, fg_color="transparent")
        style_btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        style_btn_frame.grid_columnconfigure(0, weight=1)
        style_btn_frame.grid_columnconfigure(1, weight=1)
        
        self.btn_save_style = ctk.CTkButton(style_btn_frame, text="💾 Save Style", command=self.save_style, fg_color="#2c3e50", hover_color="#1a252f")
        self.btn_save_style.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.btn_load_style = ctk.CTkButton(style_btn_frame, text="📂 Load Style", command=self.load_style, fg_color="#2980b9", hover_color="#1f618d")
        self.btn_load_style.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.btn_export_img = ctk.CTkButton(sec6, text="🖼️ Export Plot Image", command=self.export_image, fg_color="#8e44ad", hover_color="#732d91")
        self.btn_export_img.pack(fill="x", padx=10, pady=(0, 5))
        
        self.btn_export_csv = ctk.CTkButton(sec6, text="📊 Export Map Data (CSV)", command=self.export_csv, fg_color="#d35400", hover_color="#a93226")
        self.btn_export_csv.pack(fill="x", padx=10, pady=(0, 15))

    def create_main_canvas(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.fig, self.ax = plt.subplots(figsize=(8, 6))
        self.fig.patch.set_facecolor('#2b2b2b'); self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('white'); self.ax.yaxis.label.set_color('white')

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.ax.text(0.5, 0.5, 'Please import main data or reference file', color='white', ha='center', va='center', transform=self.ax.transAxes)
        
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)

    # ================= 颜色条预览生成 (修复AttributeError) =================

    def generate_cmap_preview(self, cmap_name, width=180, height=16):
        """生成 Colormap 的渐变预览图"""
        cmap = plt.get_cmap(cmap_name) 
        gradient = np.linspace(0, 1, width)
        rgba = cmap(gradient)
        rgba = (rgba * 255).astype(np.uint8)
        rgba_2d = np.tile(rgba, (height, 1, 1))
        img = Image.fromarray(rgba_2d, 'RGBA')
        return ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))

    def update_cmap_preview(self, cmap_name):
        """更新 UI 上的预览标签"""
        try:
            img_ctk = self.generate_cmap_preview(cmap_name)
            self.cmap_preview_label.configure(image=img_ctk)
        except Exception:
            pass

    # ================= 样式模板保存与加载 =================
    
    def save_style(self):
        """将当前绘图参数保存为 JSON 文件"""
        style_config = {
            "slice_plane": self.slice_dropdown.get(),
            "use_phys_height": self.use_phys_height_var.get(),
            "interp_var": self.interp_var.get(),
            "target_height": self.target_height_entry.get(),
            "cmap_name": self.cmap_dropdown.get(),
            "auto_scale": self.auto_scale,
            "vmin": self.vmin_entry.get(),
            "vmax": self.vmax_entry.get(),
            "levels": self.levels_entry.get(),
            "aspect": self.aspect_dropdown.get(),
            "tick_dir": self.tick_dir_dropdown.get(),
            "x_step": self.x_step_entry.get(),
            "y_step": self.y_step_entry.get(),
            "user_set_axes": self.user_set_axes,
            "xmin": self.main_xmin.get(),
            "xmax": self.main_xmax.get(),
            "ymin": self.main_ymin.get(),
            "ymax": self.main_ymax.get(),
            "user_set_labels": self.user_set_labels,
            "title": self.title_entry.get(),
            "xlabel": self.xlabel_entry.get(),
            "ylabel": self.ylabel_entry.get(),
            "font_family": self.font_dropdown.get(),
            "font_size": self.fontsize_entry.get(),
            "x_math": self.xtick_math.get(),
            "y_math": self.ytick_math.get(),
            "cb_orient": self.cb_orient.get(),
            "cb_pad": self.cb_pad.get(),
            "cb_shrink": self.cb_shrink.get(),
            "cb_aspect": self.cb_aspect.get(),
            "cb_label": self.cb_label_entry.get(),
            "cb_tick_min": self.cb_tick_min.get(),
            "cb_tick_max": self.cb_tick_max.get(),
            "cb_step": self.cb_step_entry.get()
        }
        
        filepath = filedialog.asksaveasfilename(
            title="Save Plot Style Profile",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not filepath: return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(style_config, f, indent=4)
            messagebox.showinfo("Success", f"Plot style successfully saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save style:\n{e}")

    def load_style(self):
        """从 JSON 文件读取并应用参数"""
        filepath = filedialog.askopenfilename(
            title="Load Plot Style Profile",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not filepath: return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                style = json.load(f)
            
            def set_entry(widget, value):
                widget.delete(0, 'end')
                widget.insert(0, str(value))
            
            if "slice_plane" in style: self.slice_dropdown.set(style["slice_plane"]); self.slice_plane = style["slice_plane"]
            if "use_phys_height" in style: self.use_phys_height_var.set(style["use_phys_height"])
            if "interp_var" in style: self.interp_var.set(style["interp_var"])
            if "target_height" in style: set_entry(self.target_height_entry, style["target_height"])
            
            if "cmap_name" in style: 
                self.cmap_dropdown.set(style["cmap_name"])
                self.cmap_name = style["cmap_name"]
                self.update_cmap_preview(self.cmap_name)
                
            if "auto_scale" in style: self.auto_scale = style["auto_scale"]
            if "vmin" in style: set_entry(self.vmin_entry, style["vmin"])
            if "vmax" in style: set_entry(self.vmax_entry, style["vmax"])
            if "levels" in style: set_entry(self.levels_entry, style["levels"])
            
            if "aspect" in style: self.aspect_dropdown.set(style["aspect"])
            if "tick_dir" in style: self.tick_dir_dropdown.set(style["tick_dir"])
            
            if "x_step" in style: set_entry(self.x_step_entry, style["x_step"])
            if "y_step" in style: set_entry(self.y_step_entry, style["y_step"])
            
            if "user_set_axes" in style: self.user_set_axes = style["user_set_axes"]
            if "xmin" in style: set_entry(self.main_xmin, style["xmin"])
            if "xmax" in style: set_entry(self.main_xmax, style["xmax"])
            if "ymin" in style: set_entry(self.main_ymin, style["ymin"])
            if "ymax" in style: set_entry(self.main_ymax, style["ymax"])
            
            if "user_set_labels" in style: self.user_set_labels = style["user_set_labels"]
            if "title" in style: set_entry(self.title_entry, style["title"])
            if "xlabel" in style: set_entry(self.xlabel_entry, style["xlabel"])
            if "ylabel" in style: set_entry(self.ylabel_entry, style["ylabel"])
            
            if "font_family" in style: self.font_dropdown.set(style["font_family"])
            if "font_size" in style: set_entry(self.fontsize_entry, style["font_size"])
            
            if "x_math" in style: set_entry(self.xtick_math, style["x_math"])
            if "y_math" in style: set_entry(self.ytick_math, style["y_math"])
            
            if "cb_orient" in style: self.cb_orient.set(style["cb_orient"])
            if "cb_pad" in style: set_entry(self.cb_pad, style["cb_pad"])
            if "cb_shrink" in style: set_entry(self.cb_shrink, style["cb_shrink"])
            if "cb_aspect" in style: set_entry(self.cb_aspect, style["cb_aspect"])
            if "cb_label" in style: set_entry(self.cb_label_entry, style["cb_label"])
            if "cb_tick_min" in style: set_entry(self.cb_tick_min, style["cb_tick_min"])
            if "cb_tick_max" in style: set_entry(self.cb_tick_max, style["cb_tick_max"])
            if "cb_step" in style: set_entry(self.cb_step_entry, style["cb_step"])
            
            if not self.auto_scale:
                try:
                    self.vmin_val = float(self.vmin_entry.get())
                    self.vmax_val = float(self.vmax_entry.get())
                    self.levels_val = int(self.levels_entry.get())
                except ValueError:
                    pass

            messagebox.showinfo("Success", "Style template successfully loaded and applied!")
            self.update_plot()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load style:\n{e}")

    # ================= 导出功能核心逻辑 =================
    
    def _set_plot_theme(self, theme='dark'):
        """静默切换绘图主题，用于导出高清白底论文图"""
        bg_color = '#2b2b2b' if theme == 'dark' else 'white'
        fg_color = 'white' if theme == 'dark' else 'black'
        
        self.fig.patch.set_facecolor(bg_color)
        self.ax.set_facecolor(bg_color)
        self.ax.tick_params(colors=fg_color)
        self.ax.xaxis.label.set_color(fg_color)
        self.ax.yaxis.label.set_color(fg_color)
        self.ax.title.set_color(fg_color)
        
        for spine in self.ax.spines.values():
            spine.set_edgecolor(fg_color)
            
        if self.cbar is not None:
            self.cbar.ax.yaxis.set_tick_params(color=fg_color, labelcolor=fg_color)
            self.cbar.ax.xaxis.set_tick_params(color=fg_color, labelcolor=fg_color)
            self.cbar.outline.set_edgecolor(fg_color)
            
            cbl = self.cbar.ax.get_xlabel() if self.cb_orient.get() == 'horizontal' else self.cbar.ax.get_ylabel()
            self.cbar.set_label(cbl, color=fg_color)

    def export_image(self):
        if self.ds is None or self.da is None:
            messagebox.showwarning("Warning", "No plot available to export!")
            return
            
        filepath = filedialog.asksaveasfilename(
            title="Save Plot Image",
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("JPEG Image", "*.jpg"),
                ("SVG Image", "*.svg"),
                ("TIFF Image", "*.tiff"),
                ("All Files", "*.*")
            ]
        )
        if not filepath: return
        
        try:
            self._set_plot_theme('light')
            self.fig.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            messagebox.showinfo("Success", f"Plot image successfully saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save image:\n{e}")
        finally:
            self._set_plot_theme('dark')
            self.canvas.draw()

    def export_csv(self):
        if self.current_plot_x is None or self.current_data_slice is None:
            messagebox.showwarning("Warning", "No map data available to export!")
            return
            
        filepath = filedialog.asksaveasfilename(
            title="Save Map Data to CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not filepath: return
        
        try:
            x_flat = np.array(self.current_plot_x).flatten()
            y_flat = np.array(self.current_plot_y).flatten()
            val_flat = np.array(self.current_data_slice).flatten()
            
            if len(x_flat) == len(val_flat) and len(y_flat) == len(val_flat):
                data = np.column_stack((x_flat, y_flat, val_flat))
                header = "X,Y,Value"
            else:
                data = np.column_stack((x_flat, val_flat))
                header = "X,Value"
                
            np.savetxt(filepath, data, delimiter=',', header=header, comments='', fmt='%g')
            messagebox.showinfo("Success", f"Map data successfully saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save CSV:\n{e}")

    # ================= 动态修改 UI 回调 =================
    
    def on_cbar_orient_change(self, choice):
        self.cb_pad.delete(0, 'end')
        if choice == 'horizontal':
            self.cb_pad.insert(0, "0.15")
        else:
            self.cb_pad.insert(0, "0.05")
        self.update_plot()

    def apply_custom_labels(self, event=None):
        self.user_set_labels = True
        self.update_plot()

    def apply_axis_limits(self):
        self.user_set_axes = True
        self.update_plot()

    def reset_display_settings(self, refresh=True):
        self.user_set_axes = False
        self.user_set_labels = False
        self.main_xmin.delete(0, 'end'); self.main_xmax.delete(0, 'end')
        self.main_ymin.delete(0, 'end'); self.main_ymax.delete(0, 'end')
        self.xlabel_entry.delete(0, 'end'); self.ylabel_entry.delete(0, 'end')
        self.title_entry.delete(0, 'end'); self.cb_label_entry.delete(0, 'end')
        self.x_step_entry.delete(0, 'end'); self.y_step_entry.delete(0, 'end')
        self.cb_tick_min.delete(0, 'end'); self.cb_tick_max.delete(0, 'end')
        self.cb_step_entry.delete(0, 'end')
        if refresh: 
            self.update_plot()


    # ================= 空间阵列与解析 =================

    def open_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("NetCDF Files", "*.nc;*.nc4"), ("All Files", "*.*")])
        if not filepath: return
        if self.ds is not None: self.ds.close() 
        try:
            self.ds = nc.Dataset(filepath, 'r')
            self.title(f"Modern NcView - {os.path.basename(filepath)}")
            if self.ref_ds is None:
                self.extract_spatial_info(self.ds)
            self.parse_dataset()
        except Exception as e: messagebox.showerror("Error", f"Failed to open file: {e}")

    def open_ref_file(self):
        filepath = filedialog.askopenfilename(title="Select Spatial Reference File", filetypes=[("NetCDF Files", "*.nc;*.nc4"), ("All Files", "*.*")])
        if not filepath: return
        try:
            temp_ref = nc.Dataset(filepath, 'r')
            if self.ds is not None:
                dims_main = {k: v.size for k,v in self.ds.dimensions.items() if 'west_east' in k or 'south_north' in k or 'bottom_top' in k}
                dims_ref = {k: v.size for k,v in temp_ref.dimensions.items() if 'west_east' in k or 'south_north' in k or 'bottom_top' in k}
                mismatch = any(dims_main.get(k) != v for k, v in dims_ref.items() if k in dims_main)
                if mismatch:
                    proceed = messagebox.askyesno("Dimension Warning", f"Reference dimensions {dims_ref} do not match main data {dims_main}. Force import?")
                    if not proceed:
                        temp_ref.close(); return

            if self.ref_ds is not None: self.ref_ds.close()
            self.ref_ds = temp_ref
            
            success = self.extract_spatial_info(self.ref_ds)
            if success:
                messagebox.showinfo("Success", f"Spatial reference info imported!\nDetected: {self.sim_type} case")
            else:
                messagebox.showwarning("Warning", "Imported, but failed to extract full coordinate/height info.")
            
            if self.ds is not None and self.var_name:
                self.update_plot()
                
        except Exception as e: messagebox.showerror("Error", f"Failed to parse reference file: {e}")

    def extract_spatial_info(self, source_ds):
        def find_var(names):
            for n in names:
                if n in source_ds.variables: return source_ds.variables[n][:]
            return None

        lon = find_var(['XLONG', 'XLONG_M', 'lon', 'longitude'])
        lat = find_var(['XLAT', 'XLAT_M', 'lat', 'latitude'])
        if lon is not None and lon.ndim > 2: lon = lon[0]
        if lat is not None and lat.ndim > 2: lat = lat[0]
        self.lon_arr, self.lat_arr = lon, lat
        
        dx, dy = getattr(source_ds, 'DX', 1000), getattr(source_ds, 'DY', 1000)
        
        if self.lon_arr is not None and self.lat_arr is not None:
            if np.max(np.abs(self.lon_arr)) > 0.001:
                self.sim_type = "REAL"
                self.sim_label.configure(text="Case Type: REAL (Coordinates)", text_color="#2ecc71")
            else:
                self.sim_type = "IDEAL"
                self.sim_label.configure(text="Case Type: IDEAL (Grid)", text_color="#3498db")
                ny, nx = self.lon_arr.shape if self.lon_arr.ndim == 2 else (len(self.lat_arr), len(self.lon_arr))
                self.x_arr = np.arange(nx) * dx
                self.y_arr = np.arange(ny) * dy
        else:
            self.sim_type = "UNKNOWN"
            self.sim_label.configure(text="Case Type: Array (No spatial info)", text_color="#e74c3c")

        self.height_3d = None
        try:
            if all(v in source_ds.variables for v in ['PH', 'PHB', 'HGT']):
                ph = source_ds.variables['PH'][0] 
                phb = source_ds.variables['PHB'][0]
                hgt = source_ds.variables['HGT'][0]
                z_stag = (ph + phb) / 9.81
                z_mass = 0.5 * (z_stag[:-1, :, :] + z_stag[1:, :, :])
                self.height_3d = z_mass - hgt
        except Exception: pass

        self.z_arr = find_var(['z', 'level', 'bottom_top', 'height'])
        self.time_arr = find_var(['time', 't', 'XTIME'])
        
        if self.height_3d is not None or self.z_arr is not None:
            self.interp_checkbox.configure(state="normal")
            self.phys_height_cb.configure(state="normal")
        else:
            self.interp_var.set(False); self.use_phys_height_var.set(False)
            self.interp_checkbox.configure(state="disabled")
            self.phys_height_cb.configure(state="disabled")

        return True

    def parse_dataset(self):
        data_vars = [name for name, var in self.ds.variables.items() if len(var.shape) >= 2 and name not in var.dimensions]
        if not data_vars: return
        self.var_dropdown.configure(values=data_vars)
        self.var_dropdown.set(data_vars[0])
        self.change_var(data_vars[0])

    # ================= UI 联动 =================

    def change_var(self, var_name):
        self.reset_display_settings(refresh=False) 
        self.var_name = var_name
        self.da = self.ds.variables[self.var_name]
        shape = self.da.shape
        self.data_ndim = len(shape)
        self.current_t, self.slider2_val = 0, 0
        self.auto_scale = True

        if self.data_ndim >= 4:
            self.has_time, self.has_z = True, True
            self.nt, self.nz, self.ny, self.nx = shape[0], shape[1], shape[2], shape[3]
        elif self.data_ndim == 3:
            dims = self.da.dimensions
            if len(dims) > 0 and 'time' in dims[0].lower():
                self.has_time, self.has_z = True, False
                self.nt, self.nz, self.ny, self.nx = shape[0], 0, shape[1], shape[2]
            else:
                self.has_time, self.has_z = False, True
                self.nt, self.nz, self.ny, self.nx = 0, shape[0], shape[1], shape[2]
        else:
            self.has_time, self.has_z, self.nt, self.nz, self.ny, self.nx = False, False, 0, 0, shape[-2], shape[-1] if len(shape)>=2 else 0

        if self.has_time and self.nt > 1:
            self.time_slider.configure(from_=0, to=self.nt-1, number_of_steps=self.nt-1, state="normal")
            self.time_label.configure(text=f"Time Axis: {0} / {self.nt-1}")
        else:
            self.time_slider.configure(state="disabled"); self.time_label.configure(text="Time Axis (None)")
        self.time_slider.set(0)

        if self.has_z:
            self.slice_dropdown.configure(state="normal")
        else:
            self.slice_dropdown.set("X-Y (Horizontal)")
            self.slice_plane = "X-Y (Horizontal)"
            self.slice_dropdown.configure(state="disabled")

        self.update_slider2_ui()
        self.update_plot()

    def change_slice_plane(self, choice):
        self.slice_plane = choice
        self.slider2_val = 0 
        self.reset_display_settings(refresh=False) 
        self.update_slider2_ui()
        self.update_plot()

    def update_slider2_ui(self):
        plane = self.slice_plane
        if "X-Y" in plane:
            max_val = self.nz - 1 if self.has_z else 0
            label_text = "Z-Level"
            if self.height_3d is not None: self.interp_checkbox.configure(state="normal")
        elif "X-Z" in plane:
            max_val = self.ny - 1
            label_text = "Y-Level"
            self.interp_checkbox.configure(state="disabled")
        elif "Y-Z" in plane:
            max_val = self.nx - 1
            label_text = "X-Level"
            self.interp_checkbox.configure(state="disabled")
        else:
            max_val, label_text = 0, "None"

        if self.slider2_val > max_val: self.slider2_val = 0
        if max_val > 0:
            self.dim2_slider.configure(from_=0, to=max_val, number_of_steps=max_val, state="normal")
            self.dim2_label.configure(text=f"{label_text}: {self.slider2_val} / {max_val}")
        else:
            self.dim2_slider.configure(state="disabled")
            self.dim2_label.configure(text=f"{label_text} (None)")
        self.dim2_slider.set(self.slider2_val)

    # ================= 核心切片绘图算法 =================

    def interp_target_height(self, t_idx):
        try: target_h = float(self.target_height_entry.get())
        except ValueError: target_h = 500.0
        var_3d = self.da[t_idx, :, :, :] if self.has_time else self.da[:, :, :]
        h_3d = self.height_3d
        
        mask_above = h_3d >= target_h
        k_above = np.argmax(mask_above, axis=0)
        k_below = np.maximum(k_above - 1, 0)
        
        Y, X = np.indices(k_above.shape)
        h_above = h_3d[k_above, Y, X]
        h_below = h_3d[k_below, Y, X]
        v_above = var_3d[k_above, Y, X]
        v_below = var_3d[k_below, Y, X]
        
        with np.errstate(divide='ignore', invalid='ignore'):
            weights = (target_h - h_below) / (h_above - h_below)
            weights = np.clip(weights, 0, 1)
            out_2d = v_below + weights * (v_above - v_below)
        
        valid_mask = (target_h >= h_3d[0, Y, X]) & (target_h <= h_3d[-1, Y, X])
        out_2d[~valid_mask] = np.nan
        return out_2d

    def _get_data_slice(self, t_idx, s2_idx):
        plane = self.slice_plane
        if self.interp_var.get() and "X-Y" in plane and self.height_3d is not None and self.has_z:
            return self.interp_target_height(t_idx)
            
        if self.data_ndim >= 4:
            if "X-Y" in plane: return self.da[t_idx, s2_idx, :, :]
            elif "X-Z" in plane: return self.da[t_idx, :, s2_idx, :]
            elif "Y-Z" in plane: return self.da[t_idx, :, :, s2_idx]
        elif self.data_ndim == 3:
            if self.has_time: return self.da[t_idx, :, :] 
            else:
                if "X-Y" in plane: return self.da[s2_idx, :, :]
                elif "X-Z" in plane: return self.da[:, s2_idx, :]
                elif "Y-Z" in plane: return self.da[:, :, s2_idx]
        elif self.data_ndim == 2:
            return self.da[t_idx, :] if self.has_time else self.da[:, :]
        return self.da[:]

    def _create_tick_formatter(self, math_str):
        def formatter(x, pos):
            try:
                clean_str = ''.join(c for c in math_str if c in '0123456789.+-*/() ')
                val = eval(f"{x} {clean_str}")
                return f"{val:g}"
            except Exception:
                return f"{x:g}"
        return FuncFormatter(formatter)

    def update_plot(self):
        if self.ds is None or self.da is None: return
        
        # --- 1. 应用全局字体与字号 ---
        plt.rcParams['font.family'] = self.font_dropdown.get()
        try: font_size = int(self.fontsize_entry.get())
        except ValueError: font_size = 11
        plt.rcParams['font.size'] = font_size

        self.ax.clear()
        
        data_slice = self._get_data_slice(self.current_t, self.slider2_val)

        if self.auto_scale and data_slice.ndim >= 2:
            try:
                v_min_auto, v_max_auto = float(np.nanmin(data_slice)), float(np.nanmax(data_slice))
                if np.isnan(v_min_auto): v_min_auto, v_max_auto = 0.0, 1.0
            except Exception: v_min_auto, v_max_auto = 0.0, 1.0
            self.vmin_val, self.vmax_val = v_min_auto, v_max_auto
            self.vmin_entry.delete(0, 'end'); self.vmin_entry.insert(0, f"{self.vmin_val:.2f}")
            self.vmax_entry.delete(0, 'end'); self.vmax_entry.insert(0, f"{self.vmax_val:.2f}")

        # --- 2. 刻度线运算解析 ---
        x_math = self.xtick_math.get().strip()
        y_math = self.ytick_math.get().strip()
        
        if x_math: self.ax.xaxis.set_major_formatter(self._create_tick_formatter(x_math))
        else: self.ax.xaxis.set_major_formatter(plt.ScalarFormatter())
            
        if y_math: self.ax.yaxis.set_major_formatter(self._create_tick_formatter(y_math))
        else: self.ax.yaxis.set_major_formatter(plt.ScalarFormatter())

        # ================== 1D 绘制逻辑 ==================
        data_sq = np.squeeze(data_slice)
        if data_sq.ndim <= 1:
            if data_sq.ndim == 0: 
                x_data, y_data = [0], [data_sq]
                self.ax.plot(x_data, y_data, marker='o', color='cyan')
            else: 
                x_data, y_data = np.arange(len(data_sq)), data_sq
                self.ax.plot(x_data, y_data, color='cyan')
                
            self.current_plot_x = np.array(x_data)
            self.current_plot_y = np.zeros_like(x_data)
            self.current_data_slice = np.array(y_data)
            
            auto_title = f"1D Series - {self.var_name} | T: {self.current_t}"
            auto_xl, auto_yl = "Index", f"{self.var_name}"
            
            if not self.user_set_labels:
                self.title_entry.delete(0, 'end'); self.title_entry.insert(0, auto_title)
                self.xlabel_entry.delete(0, 'end'); self.xlabel_entry.insert(0, auto_xl)
                self.ylabel_entry.delete(0, 'end'); self.ylabel_entry.insert(0, auto_yl)
                final_title, final_xl, final_yl = auto_title, auto_xl, auto_yl
            else:
                final_title = self.title_entry.get().strip() or auto_title
                final_xl = self.xlabel_entry.get().strip() or auto_xl
                final_yl = self.ylabel_entry.get().strip() or auto_yl
                
            if not self.user_set_axes:
                self.main_xmin.delete(0, 'end'); self.main_xmin.insert(0, str(round(float(np.nanmin(x_data)), 4)))
                self.main_xmax.delete(0, 'end'); self.main_xmax.insert(0, str(round(float(np.nanmax(x_data)), 4)))
                self.main_ymin.delete(0, 'end'); self.main_ymin.insert(0, str(round(float(np.nanmin(y_data)), 4)))
                self.main_ymax.delete(0, 'end'); self.main_ymax.insert(0, str(round(float(np.nanmax(y_data)), 4)))

            self.ax.set_title(final_title, color='white', fontsize=font_size+2)
            if self.cbar is not None: self.cbar.remove(); self.cbar = None
            
            self.ax.set_xlabel(final_xl, color='white', fontsize=font_size)
            self.ax.set_ylabel(final_yl, color='white', fontsize=font_size)
            
            tick_dir = self.tick_dir_dropdown.get()
            self.ax.tick_params(axis='both', direction=tick_dir, labelsize=font_size)
            
            x_step_str, y_step_str = self.x_step_entry.get().strip(), self.y_step_entry.get().strip()
            if x_step_str:
                try: val = float(x_step_str); self.ax.xaxis.set_major_locator(MultipleLocator(val))
                except ValueError: pass
            if y_step_str:
                try: val = float(y_step_str); self.ax.yaxis.set_major_locator(MultipleLocator(val))
                except ValueError: pass
            
            try:
                xmin, xmax = float(self.main_xmin.get()), float(self.main_xmax.get())
                if xmin != xmax: self.ax.set_xlim(xmin, xmax)
            except ValueError: pass
            try:
                ymin, ymax = float(self.main_ymin.get()), float(self.main_ymax.get())
                if ymin != ymax: self.ax.set_ylim(ymin, ymax)
            except ValueError: pass
            
            self.canvas.draw(); return

        # ================== 2D 绘制逻辑 ==================
        plane = self.slice_plane
        plot_x, plot_y = None, None
        auto_xl, auto_yl = "Index X", "Index Y"
        use_height = self.use_phys_height_var.get()

        if "X-Y" in plane:
            if self.sim_type == "REAL":
                plot_x, plot_y = self.lon_arr, self.lat_arr
                auto_xl, auto_yl = "Longitude", "Latitude"
            elif self.sim_type == "IDEAL":
                plot_x, plot_y = np.meshgrid(self.x_arr, self.y_arr)
                auto_xl, auto_yl = "X (m)", "Y (m)"

        elif "X-Z" in plane:
            nz_plot, nx_plot = data_slice.shape
            if self.sim_type == "REAL" and self.lon_arr is not None:
                x_1d = self.lon_arr[min(self.slider2_val, self.lon_arr.shape[0]-1), :] if self.lon_arr.ndim == 2 else self.lon_arr
                auto_xl = "Longitude"
            elif self.sim_type == "IDEAL" and self.x_arr is not None:
                x_1d = self.x_arr
                auto_xl = "X (m)"
            else:
                x_1d = np.arange(nx_plot)
            plot_x = np.tile(x_1d, (nz_plot, 1))

            if use_height and self.height_3d is not None:
                safe_y = min(self.slider2_val, self.height_3d.shape[1]-1)
                plot_y = self.height_3d[:, safe_y, :]
                auto_yl = "Height AGL (m)"
            elif use_height and self.z_arr is not None:
                plot_y = np.tile(self.z_arr[:, None], (1, len(x_1d)))
                auto_yl = "Z-Coordinate"
            else:
                plot_y = np.tile(np.arange(nz_plot)[:, None], (1, len(x_1d)))
                auto_yl = "Z-Level (Layer Index)"

        elif "Y-Z" in plane:
            nz_plot, ny_plot = data_slice.shape
            if self.sim_type == "REAL" and self.lat_arr is not None:
                x_1d = self.lat_arr[:, min(self.slider2_val, self.lat_arr.shape[1]-1)] if self.lat_arr.ndim == 2 else self.lat_arr
                auto_xl = "Latitude"
            elif self.sim_type == "IDEAL" and self.y_arr is not None:
                x_1d = self.y_arr
                auto_xl = "Y (m)"
            else:
                x_1d = np.arange(ny_plot)
            plot_x = np.tile(x_1d, (nz_plot, 1))

            if use_height and self.height_3d is not None:
                safe_x = min(self.slider2_val, self.height_3d.shape[2]-1)
                plot_y = self.height_3d[:, :, safe_x]
                auto_yl = "Height AGL (m)"
            elif use_height and self.z_arr is not None:
                plot_y = np.tile(self.z_arr[:, None], (1, len(x_1d)))
                auto_yl = "Z-Coordinate"
            else:
                plot_y = np.tile(np.arange(nz_plot)[:, None], (1, len(x_1d)))
                auto_yl = "Z-Level (Layer Index)"

        if plot_x is not None and plot_y is not None:
            if plot_x.ndim == 1 and plot_y.ndim == 1:
                plot_x, plot_y = np.meshgrid(plot_x, plot_y)
            if plot_x.shape != data_slice.shape or plot_y.shape != data_slice.shape:
                min_y = min(plot_x.shape[0], plot_y.shape[0], data_slice.shape[0])
                min_x = min(plot_x.shape[1], plot_y.shape[1], data_slice.shape[1])
                plot_x = plot_x[:min_y, :min_x]
                plot_y = plot_y[:min_y, :min_x]
                data_slice = data_slice[:min_y, :min_x]

        ny, nx = data_slice.shape
        if plot_x is None or plot_y is None or plot_x.shape != data_slice.shape:
            plot_x, plot_y = np.meshgrid(np.arange(nx), np.arange(ny))

        self.current_plot_x = plot_x
        self.current_plot_y = plot_y
        self.current_data_slice = data_slice

        auto_title = f"Var: {self.var_name} | {self.sim_type} | "
        if self.interp_var.get() and "X-Y" in plane:
            auto_title += f"Target H: {self.target_height_entry.get()}m"
        else:
            auto_title += f"Slice: {plane}"
        if self.has_time: auto_title += f" | T: {self.current_t}"
        
        auto_cb_label = f"{self.var_name} [{getattr(self.da, 'units', '')}]"

        if not self.user_set_labels:
            self.title_entry.delete(0, 'end'); self.title_entry.insert(0, auto_title)
            self.xlabel_entry.delete(0, 'end'); self.xlabel_entry.insert(0, auto_xl)
            self.ylabel_entry.delete(0, 'end'); self.ylabel_entry.insert(0, auto_yl)
            self.cb_label_entry.delete(0, 'end'); self.cb_label_entry.insert(0, auto_cb_label)
            final_title, final_xl, final_yl, final_cbl = auto_title, auto_xl, auto_yl, auto_cb_label
        else:
            final_title = self.title_entry.get() or auto_title
            final_xl = self.xlabel_entry.get() or auto_xl
            final_yl = self.ylabel_entry.get() or auto_yl
            final_cbl = self.cb_label_entry.get().strip() or auto_cb_label

        if not self.user_set_axes:
            x_min_auto = round(float(np.nanmin(plot_x)), 4)
            x_max_auto = round(float(np.nanmax(plot_x)), 4)
            y_min_auto = round(float(np.nanmin(plot_y)), 4)
            y_max_auto = round(float(np.nanmax(plot_y)), 4)
            
            self.main_xmin.delete(0, 'end'); self.main_xmin.insert(0, str(x_min_auto))
            self.main_xmax.delete(0, 'end'); self.main_xmax.insert(0, str(x_max_auto))
            self.main_ymin.delete(0, 'end'); self.main_ymin.insert(0, str(y_min_auto))
            self.main_ymax.delete(0, 'end'); self.main_ymax.insert(0, str(y_max_auto))

        v_min, v_max = self.vmin_val, self.vmax_val
        if np.isclose(v_min, v_max): v_min -= 0.1; v_max += 0.1
        levels = np.linspace(v_min, v_max, max(2, int(self.levels_val))) 

        if ny < 2 or nx < 2:
            self.img = self.ax.pcolormesh(plot_x, plot_y, data_slice, cmap=self.cmap_name, vmin=v_min, vmax=v_max, shading='auto')
        else:
            # 移除了 extend='both' 参数，使得两头变平
            self.img = self.ax.contourf(plot_x, plot_y, data_slice, levels=levels, cmap=self.cmap_name, extend='neither')

        # --- 3. 应用 Colorbar 高级设置 ---
        if self.cbar is not None: self.cbar.remove()
        
        cbar_orient = self.cb_orient.get()
        try: c_shrink = float(self.cb_shrink.get())
        except ValueError: c_shrink = 1.0
        try: c_aspect = float(self.cb_aspect.get())
        except ValueError: c_aspect = 20
        try: c_pad = float(self.cb_pad.get())
        except ValueError: c_pad = 0.05
        
        self.cbar = self.fig.colorbar(self.img, ax=self.ax, orientation=cbar_orient, 
                                      shrink=c_shrink, aspect=c_aspect, pad=c_pad)
                                      
        tick_dir = self.tick_dir_dropdown.get()
        self.cbar.ax.tick_params(direction=tick_dir)
        
        cb_tmin_str = self.cb_tick_min.get().strip()
        cb_tmax_str = self.cb_tick_max.get().strip()
        cb_step_str = self.cb_step_entry.get().strip()

        if cb_tmin_str or cb_tmax_str or cb_step_str:
            try:
                t_min = float(cb_tmin_str) if cb_tmin_str else v_min
                t_max = float(cb_tmax_str) if cb_tmax_str else v_max
                
                if cb_step_str:
                    c_step = float(cb_step_str)
                    if c_step > 0:
                        ticks = np.arange(t_min, t_max + c_step * 0.001, c_step)
                        self.cbar.set_ticks(ticks)
                else:
                    ticks = np.linspace(t_min, t_max, 6)
                    self.cbar.set_ticks(ticks)
            except ValueError:
                pass

        self.cbar.ax.yaxis.set_tick_params(color='white')
        self.cbar.ax.xaxis.set_tick_params(color='white') 
        
        if cbar_orient == 'vertical':
            plt.setp(plt.getp(self.cbar.ax.axes, 'yticklabels'), color='white', fontsize=font_size)
        else:
            plt.setp(plt.getp(self.cbar.ax.axes, 'xticklabels'), color='white', fontsize=font_size)
            
        self.cbar.set_label(final_cbl, color='white', fontsize=font_size)
        self.ax.set_title(final_title, color='white', fontsize=font_size+2)
        
        self.ax.set_xlabel(final_xl, color='white', fontsize=font_size)
        self.ax.set_ylabel(final_yl, color='white', fontsize=font_size)
        
        self.ax.tick_params(axis='both', direction=tick_dir, labelsize=font_size)
        
        x_step_str, y_step_str = self.x_step_entry.get().strip(), self.y_step_entry.get().strip()
        if x_step_str:
            try: val = float(x_step_str); self.ax.xaxis.set_major_locator(MultipleLocator(val))
            except ValueError: pass
        if y_step_str:
            try: val = float(y_step_str); self.ax.yaxis.set_major_locator(MultipleLocator(val))
            except ValueError: pass
        
        aspect_val = self.aspect_dropdown.get().strip().lower()
        try:
            if aspect_val in ['auto', 'equal']: self.ax.set_aspect(aspect_val)
            else: self.ax.set_aspect(float(aspect_val))
        except ValueError:
            self.ax.set_aspect('auto')
            
        try:
            xmin, xmax = float(self.main_xmin.get()), float(self.main_xmax.get())
            if xmin != xmax: self.ax.set_xlim(xmin, xmax)
        except ValueError: pass
        try:
            ymin, ymax = float(self.main_ymin.get()), float(self.main_ymax.get())
            if ymin != ymax: self.ax.set_ylim(ymin, ymax)
        except ValueError: pass

        self.canvas.draw()

    # ================= 交互回调 =================

    def change_time(self, val):
        self.current_t = int(val)
        if self.has_time: self.time_label.configure(text=f"Time Axis: {self.current_t} / {self.nt-1}")
        self.update_plot()

    def change_dim2(self, val):
        self.slider2_val = int(val)
        self.update_slider2_ui()
        self.update_plot()

    def step_time(self, delta):
        if not self.has_time: return
        new_t = self.current_t + delta
        if 0 <= new_t <= self.nt - 1:
            self.time_slider.set(new_t); self.change_time(new_t)

    def step_dim2(self, delta):
        if self.dim2_slider.cget("state") == "disabled": return
        new_val = self.slider2_val + delta
        if 0 <= new_val <= self.dim2_slider.cget("to"):
            self.dim2_slider.set(new_val); self.change_dim2(new_val)

    def bind_shortcuts(self):
        def on_key(event, dim, delta):
            if isinstance(self.focus_get(), ctk.CTkEntry): return
            if dim == 't': self.step_time(delta)
            elif dim == 'z': self.step_dim2(delta)
        self.bind("<Left>", lambda e: on_key(e, 't', -1)); self.bind("<Right>", lambda e: on_key(e, 't', 1))
        self.bind("<Down>", lambda e: on_key(e, 'z', -1)); self.bind("<Up>", lambda e: on_key(e, 'z', 1))

    def change_cmap(self, choice):
        try:
            self.cmap_name = getattr(cmaps, choice)
        except:
            self.cmap_name = choice
        self.update_cmap_preview(choice) 
        self.update_plot()

    def apply_clim(self):
        try:
            self.vmin_val, self.vmax_val = float(self.vmin_entry.get()), float(self.vmax_entry.get())
            self.levels_val = max(2, int(self.levels_entry.get())) 
            self.auto_scale = False  
            self.update_plot()
        except ValueError: pass
        
    def on_levels_enter(self, event=None):
        try:
            self.levels_val = max(2, int(self.levels_entry.get())) 
            self.update_plot()
        except ValueError: pass
            
    def reset_clim(self):
        self.auto_scale = True  
        self.levels_val = 30
        self.levels_entry.delete(0, 'end'); self.levels_entry.insert(0, str(self.levels_val))
        self.update_plot()

    def on_click(self, event):
        if event.inaxes != self.ax or self.ds is None: return 
        
        click_x, click_y = event.xdata, event.ydata
        idx_x, idx_y, idx_z = 0, 0, 0
        plane = self.slice_plane

        if "X-Y" in plane:
            idx_z = self.slider2_val
            if self.sim_type == "REAL" and self.lon_arr is not None and self.lat_arr is not None:
                if abs(self.lon_arr.shape[0] - self.ny) <= 1 and abs(self.lon_arr.shape[1] - self.nx) <= 1:
                    dist = (self.lon_arr - click_x)**2 + (self.lat_arr - click_y)**2
                    idx_y, idx_x = np.unravel_index(dist.argmin(), dist.shape)
                else:
                    idx_x, idx_y = int(click_x), int(click_y)
            elif self.sim_type == "IDEAL" and self.x_arr is not None and self.y_arr is not None:
                idx_x = (np.abs(self.x_arr - click_x)).argmin()
                idx_y = (np.abs(self.y_arr - click_y)).argmin()
            else:
                idx_x, idx_y = int(click_x), int(click_y)
                
        elif "X-Z" in plane:
            idx_y = self.slider2_val
            if self.sim_type == "REAL" and self.lon_arr is not None:
                x_1d = self.lon_arr[min(self.slider2_val, self.lon_arr.shape[0]-1), :] if self.lon_arr.ndim == 2 else self.lon_arr
                idx_x = (np.abs(x_1d - click_x)).argmin()
            elif self.sim_type == "IDEAL" and self.x_arr is not None:
                idx_x = (np.abs(self.x_arr - click_x)).argmin()
            else:
                idx_x = int(click_x)
                
            if self.use_phys_height_var.get() and self.height_3d is not None:
                safe_x = min(idx_x, self.height_3d.shape[2]-1)
                safe_y = min(idx_y, self.height_3d.shape[1]-1)
                idx_z = (np.abs(self.height_3d[:, safe_y, safe_x] - click_y)).argmin()
            elif self.use_phys_height_var.get() and self.z_arr is not None:
                idx_z = (np.abs(self.z_arr - click_y)).argmin()
            else:
                idx_z = int(click_y)

        elif "Y-Z" in plane:
            idx_x = self.slider2_val
            if self.sim_type == "REAL" and self.lat_arr is not None:
                y_1d = self.lat_arr[:, min(self.slider2_val, self.lat_arr.shape[1]-1)] if self.lat_arr.ndim == 2 else self.lat_arr
                idx_y = (np.abs(y_1d - click_x)).argmin()
            elif self.sim_type == "IDEAL" and self.y_arr is not None:
                idx_y = (np.abs(self.y_arr - click_x)).argmin()
            else:
                idx_y = int(click_x)

            if self.use_phys_height_var.get() and self.height_3d is not None:
                safe_x = min(idx_x, self.height_3d.shape[2]-1)
                safe_y = min(idx_y, self.height_3d.shape[1]-1)
                idx_z = (np.abs(self.height_3d[:, safe_y, safe_x] - click_y)).argmin()
            elif self.use_phys_height_var.get() and self.z_arr is not None:
                idx_z = (np.abs(self.z_arr - click_y)).argmin()
            else:
                idx_z = int(click_y)

        idx_x = max(0, min(idx_x, self.nx - 1))
        idx_y = max(0, min(idx_y, self.ny - 1))
        idx_z = max(0, min(idx_z, self.nz - 1))

        AdvancedProbeWindow(self, idx_x, idx_y, idx_z, click_x, click_y)

# =====================================================================
# 多维数据探针窗口 (Multi-dimensional Probe)
# =====================================================================
class AdvancedProbeWindow(ctk.CTkToplevel):
    def __init__(self, app, idx_x, idx_y, idx_z, actual_x, actual_y):
        super().__init__()
        self.app = app 
        self.idx_x, self.idx_y, self.idx_z = idx_x, idx_y, idx_z

        self.title(f"Multi-dim Probe - {app.var_name}")
        self.geometry("900x550")

        self.current_x_data = None
        self.current_y_data = None

        self.setup_ui(actual_x, actual_y)
        if self.plot_types:
            self.change_dim(self.plot_types[0])

    def setup_ui(self, actual_x, actual_y):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.panel = ctk.CTkFrame(self, width=280)
        self.panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(self.panel, text="Probe Dimension", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 15))

        info_text = f"X-Index: {self.idx_x}\nY-Index: {self.idx_y}"
        if self.app.has_z: info_text += f"\nZ-Index: {self.idx_z}"
        if self.app.has_time: info_text += f"\nT-Index: {self.app.current_t}"
        ctk.CTkLabel(self.panel, text=info_text, justify="left", text_color="#1f77b4").pack(pady=(0, 20), padx=15, anchor="w")

        ctk.CTkLabel(self.panel, text="Select Plot Dimension:").pack(anchor="w", padx=15)
        self.plot_types = []
        if self.app.has_time: self.plot_types.append("Time Series (T-axis)")
        if self.app.has_z: self.plot_types.append("Vertical Profile (Z-axis)")
        self.plot_types.append("Zonal Profile (X-axis)")
        self.plot_types.append("Meridional Profile (Y-axis)")

        self.dim_var = ctk.StringVar(value=self.plot_types[0] if self.plot_types else "")
        self.dim_dropdown = ctk.CTkComboBox(self.panel, values=self.plot_types, variable=self.dim_var, command=self.change_dim)
        self.dim_dropdown.pack(fill="x", padx=15, pady=(5, 20))

        ctk.CTkLabel(self.panel, text="X-Axis Range:").pack(anchor="w", padx=15)
        frame_x = ctk.CTkFrame(self.panel, fg_color="transparent")
        frame_x.pack(fill="x", padx=15, pady=(0, 10))
        self.entry_x_min = ctk.CTkEntry(frame_x, width=80); self.entry_x_min.pack(side="left")
        ctk.CTkLabel(frame_x, text="-").pack(side="left", padx=5)
        self.entry_x_max = ctk.CTkEntry(frame_x, width=80); self.entry_x_max.pack(side="left")

        ctk.CTkLabel(self.panel, text="Y-Axis Range (Data Value):").pack(anchor="w", padx=15)
        frame_y = ctk.CTkFrame(self.panel, fg_color="transparent")
        frame_y.pack(fill="x", padx=15, pady=(0, 20))
        self.entry_y_min = ctk.CTkEntry(frame_y, width=80); self.entry_y_min.pack(side="left")
        ctk.CTkLabel(frame_y, text="-").pack(side="left", padx=5)
        self.entry_y_max = ctk.CTkEntry(frame_y, width=80); self.entry_y_max.pack(side="left")

        self.btn_apply = ctk.CTkButton(self.panel, text="Apply Custom Range", command=self.apply_limits)
        self.btn_apply.pack(fill="x", padx=15, pady=5)
        self.btn_reset = ctk.CTkButton(self.panel, text="Reset to Auto Range", command=lambda: self.change_dim(self.dim_var.get()), fg_color="#555555", hover_color="#333333")
        self.btn_reset.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(self.panel, text="Export:").pack(anchor="w", padx=15, pady=(15, 0))
        self.btn_export_csv = ctk.CTkButton(self.panel, text="💾 Export Curve (CSV)", command=self.export_csv, fg_color="#27ae60", hover_color="#1e8449")
        self.btn_export_csv.pack(fill="x", padx=15, pady=(5, 10))

        self.plot_frame = ctk.CTkFrame(self, corner_radius=0)
        self.plot_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.fig.patch.set_facecolor('#2b2b2b'); self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('white'); self.ax.yaxis.label.set_color('white')

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def export_csv(self):
        if self.current_x_data is None or self.current_y_data is None:
            messagebox.showwarning("Warning", "No curve data available to export!")
            return
            
        filepath = filedialog.asksaveasfilename(
            title="Save Curve Data to CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not filepath: return
        
        try:
            x_arr = np.array(self.current_x_data).flatten()
            y_arr = np.array(self.current_y_data).flatten()
            
            if len(x_arr) != len(y_arr):
                messagebox.showerror("Error", "X and Y data lengths do not match.")
                return
                
            data = np.column_stack((x_arr, y_arr))
            
            x_lbl = self.dim_var.get().replace(',', ' ')
            y_lbl = self.app.var_name.replace(',', ' ')
            header = f"{x_lbl},{y_lbl}"
            
            np.savetxt(filepath, data, delimiter=',', header=header, comments='', fmt='%g')
            messagebox.showinfo("Success", f"Curve data successfully saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save CSV:\n{e}")

    def extract_data(self, dim_type):
        da, ndim = self.app.da, self.app.data_ndim
        ct, cz, cy, cx = self.app.current_t, self.idx_z, self.idx_y, self.idx_x
        try:
            if "T-axis" in dim_type:
                if ndim >= 4: return da[:, cz, cy, cx]
                if ndim == 3: return da[:, cy, cx]
                if ndim == 2 and self.app.has_time: return da[:, cx]
            elif "Z-axis" in dim_type:
                if ndim >= 4: return da[ct, :, cy, cx]
            elif "Y-axis" in dim_type:
                if ndim >= 4: return da[ct, cz, :, cx]
                if ndim == 3: return da[ct, :, cx]
                if ndim == 2 and not self.app.has_time: return da[:, cx]
            elif "X-axis" in dim_type:
                if ndim >= 4: return da[ct, cz, cy, :]
                if ndim == 3: return da[ct, cy, :]
                if ndim == 2: return da[ct, :] if self.app.has_time else da[cy, :]
        except Exception as e: print(f"Extraction failed: {e}")
        return np.array([])

    def get_x_axis_data(self, dim_type, data_len):
        cx, cy = self.idx_x, self.idx_y
        if "T-axis" in dim_type: return self.app.time_arr if self.app.time_arr is not None and len(self.app.time_arr) == data_len else np.arange(data_len)
        elif "Z-axis" in dim_type:
            if self.app.use_phys_height_var.get() and self.app.height_3d is not None:
                return self.app.height_3d[:, min(cy, self.app.height_3d.shape[1]-1), min(cx, self.app.height_3d.shape[2]-1)]
            return self.app.z_arr if self.app.z_arr is not None and len(self.app.z_arr) == data_len else np.arange(data_len)
        elif "X-axis" in dim_type:
            arr = self.app.lon_arr
            if arr is not None:
                if arr.ndim == 1 and len(arr) == data_len: return arr
                if arr.ndim == 2 and arr.shape[1] == data_len: return arr[min(cy, arr.shape[0]-1), :]
            return self.app.x_arr if self.app.x_arr is not None and len(self.app.x_arr) == data_len else np.arange(data_len)
        elif "Y-axis" in dim_type:
            arr = self.app.lat_arr
            if arr is not None:
                if arr.ndim == 1 and len(arr) == data_len: return arr
                if arr.ndim == 2 and arr.shape[1] == data_len: return arr[:, min(cx, arr.shape[1]-1)]
            return self.app.y_arr if self.app.y_arr is not None and len(self.app.y_arr) == data_len else np.arange(data_len)
        return np.arange(data_len)

    def change_dim(self, choice):
        y_data = self.extract_data(choice)
        if len(y_data) == 0:
            self.ax.clear(); self.ax.text(0.5, 0.5, "Cannot extract data for this dimension", color="red", ha="center", transform=self.ax.transAxes); self.canvas.draw(); return
            
        x_data = self.get_x_axis_data(choice, len(y_data))
        self.current_x_data, self.current_y_data = np.squeeze(x_data), np.squeeze(y_data)
        
        x_min, x_max = np.nanmin(x_data), np.nanmax(x_data)
        y_min, y_max = np.nanmin(y_data), np.nanmax(y_data)
        x_pad = (x_max - x_min) * 0.05 if x_max != x_min else 1
        y_pad = (y_max - y_min) * 0.05 if y_max != y_min else 1

        self.entry_x_min.delete(0, 'end'); self.entry_x_min.insert(0, f"{x_min - x_pad:.2f}")
        self.entry_x_max.delete(0, 'end'); self.entry_x_max.insert(0, f"{x_max + x_pad:.2f}")
        self.entry_y_min.delete(0, 'end'); self.entry_y_min.insert(0, f"{y_min - y_pad:.2f}")
        self.entry_y_max.delete(0, 'end'); self.entry_y_max.insert(0, f"{y_max + y_pad:.2f}")

        self.draw_plot()

    def apply_limits(self): self.draw_plot()

    def draw_plot(self):
        if self.current_x_data is None or self.current_y_data is None: return
        self.ax.clear()
        
        cx = self.current_x_data if self.current_x_data.ndim > 0 else np.array([self.current_x_data])
        cy = self.current_y_data if self.current_y_data.ndim > 0 else np.array([self.current_y_data])
        
        self.ax.plot(cx, cy, color='#00d2ff', marker='.', markersize=4, linewidth=1.5)
        try:
            self.ax.set_xlim(float(self.entry_x_min.get()), float(self.entry_x_max.get()))
            self.ax.set_ylim(float(self.entry_y_min.get()), float(self.entry_y_max.get()))
        except ValueError: pass 

        font_size = plt.rcParams.get('font.size', 10)
        
        self.ax.set_title(f"Probe: {self.app.var_name} | {self.dim_var.get()}", color='white', fontsize=font_size+2)
        self.ax.set_xlabel(f"Coordinate / Index ({self.dim_var.get()})", color='white', fontsize=font_size)
        self.ax.set_ylabel(f"{self.app.var_name} [{getattr(self.app.da, 'units', '')}]", color='white', fontsize=font_size)
        
        tick_dir = self.app.tick_dir_dropdown.get()
        self.ax.tick_params(axis='both', direction=tick_dir, labelsize=font_size)
        
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.fig.tight_layout()
        self.canvas.draw()

if __name__ == "__main__":
    app = ModernNcView()
    app.mainloop()
