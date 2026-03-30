# 🌍 NCVO

**NCVO** 是一款基于 Python 和 CustomTkinter 构建的现代化、交互式 NetCDF 数据查看与分析工具，功能仿照ncview进行设计。
它不仅拥有高颜值的暗黑系 UI，还专为气象学、海洋学及流体力学研究人员（特别是 WRF 模式用户）设计，提供了从**多维数据切片**、**交互式探针**到**出版级图像导出**的一站式工作流。

## ✨ 核心特性 (Key Features)

- 🎨 **现代化 UI 界面**：摒弃传统 Tkinter 的简陋外观，采用深色/浅色自适应的现代卡片式设计。
- 🔪 **多维空间切片**：支持 X-Y（水平面）、X-Z（垂直剖面）、Y-Z（垂直剖面）快速切换，并可通过滑块轻松浏览时间轴与高度层。
- 🏔️ **WRF 模式深度兼容**：自动解析真实经纬度 (REAL) 与理想网格 (IDEAL)，支持利用 `PH`, `PHB`, `HGT` 变量进行真实物理高度 (m) 的智能插值。
- 🔍 **交互式数据探针 (Probe)**：在主云图上点击任意位置，即可弹出独立窗口，一键绘制该点的**时间序列 (T-axis)** 或 **垂直/水平剖面 (1D Profile)**。
- 🛠️ **极客级绘图自定义**：
  - 动态渲染 Colormap 预览，支持反转与自定义刻度范围。
  - 坐标轴刻度支持**直接输入数学运算**（如 `*1000`, `-273.15`，轻松完成单位换算）。
  - 支持 Latex 语法渲染标题与坐标轴标签（如 `$T_{2m}$`）。
  - 自由调整长宽比例 (Aspect Ratio)、刻度朝向、刻度间距与图表字体。
  - Colorbar 全维度控制（水平/垂直、长度、宽度、间距、自定义刻度步长）。
- 💾 **科研级一键导出**：
  - **图像导出**：支持导出 PNG, JPG, 高清 TIFF 及矢量图 SVG。导出时后台智能切换至白底黑字，完美适配论文与 PPT。
  - **数据导出**：支持将当前云图的 2D 矩阵或探针曲线的 1D 序列一键展平并导出为 `.csv` 文件。

---

## 📸 界面截图 (Screenshots)

![Image](https://github.com/abestapple/NCVO/blob/main/mainwindow.png)
![Image](https://github.com/abestapple/NCVO/blob/main/probe_window.png)
---
## 🚀 安装指南 (Installation)

确保你已经安装了 Python 3.8 或更高版本。
   ```bash
   pip install NCVO
安装成功之后，直接在cmd/powershell 输入 ncvo 回车即可使用

## 📚 详细使用教程 (User Guide)

软件主界面分为左侧的**控制侧边栏 (Sidebar)** 和右侧的**主绘图区 (Main Canvas)**。

以下是侧边栏从上到下 6 个功能模块的详细说明：

### 1. Data & Import (数据与导入区)
此处用于加载 NetCDF 数据文件并选择要分析的变量。
* **📂 Open Main NC File**: 点击导入主数据文件。导入后后台会自动解析空间坐标 (经纬度或理想网格)。
* **🔗 Import Spatial Ref (可选)**: 如果你的主文件是被裁剪过的（丢失了完整的坐标数组），可导入包含完整地理信息的原始参考文件，软件会自动进行匹配。
* **Select Variable**: 软件会自动过滤出维度 $\ge 2$ 的有效变量供你选择。

### 2. Navigation & Slicing (维度切片与导航区)
用于在多维数据中穿梭，选择观察切面。
* **Slice Plane**: 选择切面投影方式（水平面 `X-Y`、纬向剖面 `X-Z`、经向剖面 `Y-Z`）。
* **Time Axis (< >)**: 拖动滑块或点击左右箭头，在不同的时间步 (Time Step) 之间切换。
* **Level Axis (< >)**: 空间层级滑动。在 X-Y 切面下控制 Z 轴（高度层）；在 X-Z 切面下控制 Y 轴（纬度切片位置）。

### 3. Plot Settings (绘图基础设置)
控制云图的颜色、值域及物理高度映射。
* **Use Physical Height (Y-axis)**: 针对垂直剖面，Y 轴将通过公式 `(PH+PHB)/9.81 - HGT` 自动映射为**真实的物理高度 (AGL, 单位: 米)**。
* **Enable Height Interp (m)**: 针对 X-Y 切面。输入目标高度（如 `500`），自动在垂直方向三维插值，画出**绝对物理高度处**的水平切面图。
* **Colormap**: 选择颜色渐变方案（附带实时颜色条预览）。
* **Min / Max / Lvls**: 强制设定云图的极值与等值线填充层数。
* **Lock / Auto**: 锁定当前极值，或根据当前切片数据自动缩放 (Auto Scale)。

### 4. Display & Axes (显示与坐标轴)
精准控制图表的坐标轴范围、长宽比和文字标签。
* **Aspect Ratio**: 图像长宽比例拉伸（`auto`, `equal` 或 自定义数字）。
* **Tick Dir & Step**: `Dir` 为刻度线朝向；`dX / dY` 可强制指定 X/Y 轴相邻刻度的间隔。
* **Axis Limits (X/Y)**: 截取显示的坐标轴范围（局部放大）。
* **Custom Text (Title, X Lbl, Y Lbl)**: 自定义标题与轴标签，**原生支持 LaTeX 语法**（如 `$T_{2m}\ (\mu V)$`）。

### 5. Plot Styling & CBar (高级样式与色条控制)
提供像素级的图表微调，满足 Publication-Ready 需求。
* **Font & Size**: 全局设定图表字体及基础字号。
* **Tick Math (X/Y)**: **坐标轴刻度数学运算**！例如输入 `* 3.6` 或 `- 273.15`，一键完成单位换算。
* **Colorbar Layout**: 
  * 控制放置方向 (`horizontal`/`vertical`)、间距 (`Pad`)、长度 (`Length`) 和 粗细 (`Aspect`)。
* **CB Lbl**: Colorbar 自定义标签（支持 LaTeX）。
* **Ticks (Min/Max/Step)**: 强制设定 Colorbar 旁边显示的具体刻度值（最值与步长）。

### 6. Export, Save & Styles (导出、保存与模板)
* **💾 Save / Load Style**: 将当前所有参数配置保存为 `.json` 模板文件，或一键加载复原。
* **🖼️ Export Plot Image**: 导出高清图片（支持 `.png`, `.jpg`, `.tiff`, `.svg`）。**后台自动智能去黑底，输出白底黑字的论文级图片**。
* **📊 Export Map Data (CSV)**: 将当前主图中绘制的云图数据展平为 `[X, Y, Value]` 三列结构，并导出为 `.csv`。

---

### 🎯 附：交互式数据探针 (Interactive Probe)
在右侧主绘图区，**鼠标左键点击任意位置**，即可唤出“多维数据探针”窗口。

1. 自动逆向寻址，显示点击处的物理坐标与网格索引 (Index)。
2. **Select Plot Dimension**: 沿不同维度展开，快速绘制 1D 曲线（如时间序列、垂直风速廓线等）。
3. **💾 Export Curve (CSV)**: 将当前 1D 曲线的 `[X, Y]` 数据导出为 CSV。



