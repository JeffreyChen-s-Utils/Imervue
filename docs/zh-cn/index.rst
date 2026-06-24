Imervue 使用手册
================

GPU 加速图像工作站，提供 **四个顶层标签**。本手册大部分内容围绕这四个标签组织。

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - 标签
     - 功能
   * - **Imervue**
     - 浏览、查看、整理、搜索、批处理图库。见"Imervue 标签 — 图片浏览与图库"。
   * - **Modify**
     - 非破坏显影管线 — 滑块、曲线、LUT、蒙版、修图、多图合成。见"Modify 标签 — 非破坏显影"。
   * - **Paint**
     - 本格的なラスター描画 风格的栅格绘图工作室，含笔刷、图层、动画、漫画工具、PSD I/O。见"Paint 标签 — 本格的なラスター描画 风格绘图"。
   * - **Puppet**
     - 从零打造的 2D 绑骨偶动画器 — 网格、变形器、参数、动作、物理。见"Puppet 标签 — 2D 绑骨偶动画"。

接下来的"快速开始"、"参考"、"插件系统"、"MCP 服务器"属于跨标签的章节，所有标签通用。

.. contents:: 目录
   :depth: 2
   :local:

----

快速开始
--------

打开 Imervue 后，你会看到三个区域：

::

   ┌──────────┬──────────────────────┬──────────┐
   │  文件夹  │                      │  EXIF    │
   │  树状图  │     图片浏览区       │  信息栏  │
   │          │                      │          │
   └──────────┴──────────────────────┴──────────┘

- **左边**：文件夹目录，点选文件夹就能浏览里面的图片
- **中间**：图片显示区，会以缩略图网格展示所有图片
- **右边**：EXIF 信息栏，显示图片的拍摄信息

----

打开图片
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 方法
     - 操作
   * - 打开文件夹
     - ``文件`` > ``打开文件夹``，选择你要浏览的目录
   * - 打开单张图片
     - ``文件`` > ``打开图片``，选择一张图片
   * - 拖拽打开
     - 直接把图片或文件夹拖进窗口
   * - 从资源管理器打开
     - 右键图片 > ``Open with Imervue``（需先注册文件关联）
   * - 最近打开
     - ``文件`` > ``最近打开``，快速回到之前看过的文件夹

支持的图片格式
^^^^^^^^^^^^^^

- **常见格式**：PNG、JPEG、BMP、TIFF、WebP、GIF、APNG、SVG
- **RAW 格式**：CR2（Canon）、NEF（Nikon）、ARW（Sony）、DNG（Adobe）、RAF（Fujifilm）、ORF（Olympus）

----

浏览图片
--------

缩略图网格模式
^^^^^^^^^^^^^^

打开文件夹后，所有图片会以缩略图网格排列。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 方法
   * - 浏览图片
     - 鼠标滚轮上下滚动
   * - 移动画面
     - 按住鼠标中键拖拽
   * - 进入大图模式
     - 左键点击任一张缩略图
   * - 调整缩略图大小
     - 上方菜单 ``缩略图大小`` > 选择 128 / 256 / 512 / 1024
   * - 缩略图排列密度
     - ``缩略图大小`` > ``缩略图排列密度`` > 紧凑 / 标准 / 宽松
   * - Hover 预览弹窗
     - 鼠标悬停缩略图 500 ms 显示放大预览
   * - 框选多张图片
     - 左键拖拽框选
   * - 方向键移动
     - ``↑`` ``↓`` ``←`` ``→`` 平移画面，按住 ``Shift`` 可微调

缩略图会显示状态徽章：左缘色条（颜色标签）、左上 ❤（收藏）、右上 ★（书签）、左下评分星。
尚未加载完成的缩略图以旋转点阵占位符显示。

列表（详细）模式
^^^^^^^^^^^^^^^^

按 ``Ctrl + L`` 可在缩略图格与可排序的列表视图之间切换，列为：预览 · 标签 · 名称 · 分辨率 · 大小 · 类型 · 修改时间 · 星级评分（可直接点击设置 0 – 5 星）。
双击行（或按 ``Enter``）进入大图模式；按 ``Esc`` 返回列表。缩略图与元数据在后台线程懒加载，
面对大型文件夹仍保持流畅。

大图模式（Deep Zoom）
^^^^^^^^^^^^^^^^^^^^^

点击缩略图后进入大图模式，可以高画质浏览单张图片。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 方法
   * - 放大／缩小
     - 鼠标滚轮、或触控板捏合
   * - 拖拽平移
     - 按住鼠标中键
   * - 上一张图
     - ``←`` 左方向键（或触控板向右滑）
   * - 下一张图
     - ``→`` 右方向键（或触控板向左滑）
   * - 跨文件夹跳转
     - ``Ctrl + Shift + ←`` / ``→`` 跳至前／下一个含图片的同级文件夹
   * - 浏览历史
     - ``Alt + ←`` 返回、``Alt + →`` 前进（类似浏览器）
   * - 按编号跳转
     - ``Ctrl + G``
   * - 随机图片
     - ``X``
   * - 适应宽度
     - 按 ``W``
   * - 适应高度
     - 按 ``Shift + W``
   * - 重置缩放
     - 按 ``Home``
   * - 回到缩略图模式
     - 按 ``Esc``
   * - 全屏
     - 按 ``F``，再按一次退出
   * - 剧场模式
     - ``Shift + Tab`` 隐藏所有菜单／状态栏／文件树
   * - OSD 信息叠加
     - ``F8`` 显示文件名／尺寸／类型；``Ctrl + F8`` 显示 Debug HUD（显存／缓存／线程）
   * - 像素查看
     - ``Shift + P``：缩放 ≥ 400 % 显示像素网格与光标下 RGB／HEX
   * - 色彩模式
     - ``Shift + M`` 循环 正常／灰阶／反相／怀旧（GLSL，非破坏性）

分割视图与双页阅读
^^^^^^^^^^^^^^^^^^

无需打开 Compare Dialog 即可并排显示两张：

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 操作
     - 快捷键
   * - 分割视图（任意两张并排）
     - ``Shift + S``
   * - 双页阅读（当前 + 下一张）
     - ``Shift + D``
   * - 双页阅读（从右到左，漫画用）
     - ``Ctrl + Shift + D``
   * - 返回先前模式
     - ``Esc``

双页模式下方向键一次前进两张。RTL 变体会交换左右面板，让第 1 页显示在右侧。

多屏幕窗口
^^^^^^^^^^

按 ``Ctrl + Shift + M`` 会在副屏打开一个无边框的第二窗口，镜像显示主 viewer 当前的图片。
主窗口可以继续独立浏览——适合展览、双屏修图工作流、客户演示。再按一次 ``Ctrl + Shift + M`` 关闭，
或在第二窗口内按 ``Esc``。

----

整理图片
--------

评分与收藏
^^^^^^^^^^

在大图模式下，可以快速给图片打分：

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 按键
   * - 加入收藏 ❤
     - ``0``
   * - 评 1～5 星
     - ``1`` ``2`` ``3`` ``4`` ``5``（再按一次取消）

颜色标签 (F1 -- F5)
^^^^^^^^^^^^^^^^^^^

独立于星级之外的 旗标式颜色 flag，适合快速分类（例如：红=删除候选、绿=精选、蓝=待修）。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 按键
   * - 红 / 黄 / 绿 / 蓝 / 紫
     - ``F1`` / ``F2`` / ``F3`` / ``F4`` / ``F5``（再按同一键清除）
   * - 批量应用到选中
     - 框选多张缩略图后按对应 F 键
   * - 按颜色筛选
     - ``筛选`` > ``按颜色标签`` > 选择颜色／任一色／无标签

状态栏会显示当前图片的颜色 chip；缩略图左边缘显示对应色条；**列表模式**有独立的「标签」与「星级」列可排序，星级列可直接点击设置 0 – 5 星。

书签
^^^^

把常用的图片加入书签，方便日后快速找到。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 方法
   * - 加入／取消书签
     - 大图模式下按 ``B``
   * - 管理书签
     - ``文件`` > ``书签``

标签与相册
^^^^^^^^^^

用标签和相册分类管理你的图片。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 操作
     - 方法
   * - 打开管理界面
     - 按 ``T`` 或 ``文件`` > ``标签与相册``
   * - 给图片加标签
     - 右键图片 > ``加入标签``
   * - 加入相册
     - 右键图片 > ``加入相册``
   * - 按单一标签／相册筛选
     - ``筛选`` > ``按标签`` / ``按相册``
   * - 多标签过滤 (AND / OR)
     - ``筛选`` > ``多标签过滤…`` — 勾选多个标签或相册，选择「任一 (OR)」或「全部 (AND)」

排序与筛选
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 功能
     - 菜单位置
   * - 按名称排序
     - ``排序`` > ``按名称``
   * - 按修改日期排序
     - ``排序`` > ``按修改日期``
   * - 按文件大小排序
     - ``排序`` > ``按文件大小``
   * - 按分辨率排序
     - ``排序`` > ``按分辨率``
   * - 升序／降序
     - ``排序`` > ``升序`` / ``降序``
   * - 按扩展名筛选
     - ``筛选`` > ``JPEG`` / ``PNG`` / ``RAW`` 等
   * - 按评分筛选
     - ``筛选`` > ``按评分``
   * - 按颜色标签筛选
     - ``筛选`` > ``按颜色标签``（全部／任一色／无标签／红／黄／绿／蓝／紫）
   * - 高级过滤
     - ``筛选`` > ``高级过滤…`` — 分辨率范围、文件大小范围、方向（横／纵／正方）、修改日期区间
   * - 清除筛选
     - ``筛选`` > ``清除筛选``

浏览模式（缩略图格 / 列表）
^^^^^^^^^^^^^^^^^^^^^^^^^^^

在缩略图格与可排序的详细列表之间切换：

- ``Ctrl + L`` — 切换 缩略图格 ↔ 列表
- 菜单：``缩略图大小`` > ``浏览模式`` > 缩略图格 / 列表
- 列表模式下任一列（包含「标签」）皆可排序；双击行或按 ``Enter`` 打开大图模式。

----

编辑图片（修改选项卡）
----------------------

切换到上方的 **"修改"** 选项卡，就能进入编辑模式。也可以在大图模式下按 ``E`` 或右键 > ``修改`` 进入。

::

   ┌────────┬──────────────────────┬────────────┐
   │  工具  │                      │  绘图属性  │
   │  栏    │   画布（直接绘图）    │  调色、画笔 │
   │        │                      │  曝光调整  │
   └────────┴──────────────────────┴────────────┘

标注工具（左边）
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - 工具
     - 图标
     - 说明
   * - 选取
     - ⬚
     - 选取已画的标注，可拖拽移动
   * - 矩形
     - ▢
     - 画矩形框
   * - 椭圆
     - ◯
     - 画椭圆或圆形
   * - 直线
     - ╱
     - 画直线
   * - 箭头
     - →
     - 画箭头
   * - 手绘
     - ✎
     - 自由手绘线条
   * - 文字
     - T
     - 在图上加文字
   * - 马赛克
     - ▦
     - 框选区域打马赛克
   * - 模糊
     - ◌
     - 框选区域加模糊

.. tip::
   在修改选项卡中按 ``←`` ``→`` 可以切换上一张／下一张图片。

画笔类型（右边）
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 画笔
     - 效果
   * - 钢笔
     - 标准细线，最常用
   * - 马克笔
     - 较粗、半透明的笔触
   * - 铅笔
     - 细淡的线条
   * - 荧光笔
     - 宽大、高透明度，像真的荧光笔
   * - 喷雾
     - 喷点效果
   * - 书法
     - 粗细随笔画方向变化
   * - 水彩
     - 柔和晕染效果
   * - 炭笔
     - 粗糙质感笔触
   * - 蜡笔
     - 蜡质手感

绘图属性（右边）
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 属性
     - 说明
   * - 颜色
     - 点击色块选择绘图颜色
   * - 线宽
     - 拖动滑杆调整笔触粗细（1～40）
   * - 不透明度
     - 调整透明度（0%～100%）
   * - 字体
     - 选择文字工具使用的字体
   * - 字体大小
     - 调整文字大小（6～200 px）

图像调整（右边下方）
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 滑杆
     - 功能
   * - 曝光
     - 调整整体亮度
   * - 亮度
     - 微调明暗
   * - 对比度
     - 调整明暗对比
   * - 饱和度
     - 调整色彩鲜艳程度
   * - 白平衡 — 色温
     - 冷暖偏移（蓝 ↔ 黄）；适合混合光源或室内照片
   * - 白平衡 — 色调
     - 品红 / 绿偏移；修正日光灯偏色
   * - 阴影
     - 提亮或压暗暗部细节
   * - 中间调
     - 调整中间色调，不影响纯黑与纯白
   * - 高光
     - 救回过曝或进一步推亮
   * - 鲜艳度 (Vibrance)
     - 饱和度感知提升 — 保护肤色与已饱和色彩

这些调整是 **非破坏性** 的：每个滑杆均写入 per-image 的 Edit Recipe，随时可以按 ``重置`` 或
``Ctrl + Z`` 逐步还原。Recipe 在重启后保留，也可通过 XMP sidecar 导出 / 同步（见元数据章节）。

保存与撤销
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - 按钮
     - 说明
   * - 保存
     - 将标注和调整写入原始文件
   * - 撤销
     - 取消上一步操作
   * - 重做
     - 重做已撤销的操作
   * - 重置
     - 清除所有图像调整

----

绘图工作区（绘图标签）
----------------------

第三个顶层标签 — **绘图** — 是一个 本格的なラスター描画 风格的绘图工作区，支持多文档标签、
矢量与位图图层、漫画工具、动画帧，以及 PSD 导入/导出。从标签栏切换进入，或在
深度缩放模式下按 ``E`` 将当前图像直接送入新的绘图标签。

UX 体质升级：本格的なラスター描画 风格、会跟着 zoom 缩放的笔刷大小光标、每个工具独立
的光标图标、画布底层的透明格纹、拖放高亮覆盖、每个 tab 的"已修改"星号、
undo / redo toast 确认、状态栏的 autosave 状态段、启动时自动检测前次
会话的 autosave 并提示还原。

高级快捷键：``Tab`` 一键隐藏 / 恢复所有 docks 进入专注模式、``Ctrl+Tab``
切换标签、``,`` / ``.`` 循环笔刷种类、``0–9`` 数字键以 10 % 为单位设置
不透明度、``Alt+[`` / ``Alt+]`` 切换 active 图层、画布右键弹出 Undo /
Redo / Select All / Deselect / Fit / 100 % 快捷菜单。

颜色 dock 加入"透明 / 无颜色"槽（背景默认为透明），fill 与魔棒会尊重
alpha 边界，擦除后不再有残留 RGB 污染重画的软边。

::

   +------+----------------------+----------------+
   | 工具 |                      | 颜色 · 笔刷    |
   | 栏   |    画布（绘图）       | 图层 · 缩览    |
   |      |                      | 素材 · …       |
   +------+----------------------+----------------+

右侧停靠面板（颜色、笔刷、图层、缩览图、素材库、历史、色板、参考、直方图、动画）
全部并入同一列的标签组中，画布因此能保留完整可见高度。拖动任意 dock 标题可重
新排列或浮动，再通过 ``设置`` > ``工作区布局…`` 保存为命名版面。

工具栏（左侧）
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - 工具
     - 快捷键
     - 用途
   * - 笔刷
     - ``B``
     - 用当前笔刷类型绘画
   * - 橡皮擦
     - ``E``
     - 对当前图层做透明度擦除
   * - 油漆桶
     - ``G``
     - 容差 / 连续区域 / 取样所有图层 的填色
   * - 吸管
     - ``I``
     - 从画布吸取前景色
   * - 移动
     - ``V``
     - 平移当前图层或选区
   * - 矩形 / 套索 / 魔棒 / 快速选择
     - ``M`` / ``L`` / ``W``
     - 选区工具，含 替换 / 添加 / 减去 / 相交 模式
   * - 文字
     - ``T``
     - 内嵌文字编辑，可调字体 / 大小 / 粗体 / 斜体
   * - 渐变
     - ``U``
     - 线性 / 径向 / 角度 / 菱形 渐变填色
   * - 模糊 / 涂抹
     - ``R``
     - 局部像素操作
   * - 减淡 / 加深 / 海绵
     -
     - 暗房调色 — 按笔刷以及色调范围蒙版加权，对局部进行
       提亮、压暗或增 / 减饱和度
   * - 钢笔（贝塞尔）
     - ``P``
     - 矢量路径，可编辑锚点 / 控制柄
   * - 仿制图章
     - ``S``
     - Shift+点击设源点，点击盖章（含羽化）
   * - 对话框
     - ``Ctrl + B``
     - 漫画对话气泡，自动生成指向尾巴
   * - 矩形 / 椭圆 / 直线 / 多边形
     - ``Shift + R/E/I/P``
     - 矢量形状（含描边与填充）
   * - 裁切
     - ``C``
     - 含长宽比预设的交互式裁切
   * - 变换
     - ``Ctrl + T``
     - 自由 / 缩放 / 旋转 / 倾斜 变换控制
   * - 抓手
     - ``H``
     - 拖动平移画布
   * - 缩放
     - ``Z``
     - 点击放大，Alt+点击缩小

笔刷
^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 笔刷
     - 效果
   * - 钢笔
     - 锐利的抗锯齿线条，日常使用
   * - 马克笔 / 荧光笔
     - 半透明宽笔触，可叠加堆积
   * - 铅笔
     - 细而带纹理的铅笔线
   * - 喷雾
     - 由密度与流量驱动的散落点
   * - 书法
     - 笔触宽度随方向变化
   * - 水彩
     - 湿边渲染与柔和混合
   * - 炭笔 / 蜡笔
     - 粗糙纹理笔触（含压力倾斜）

每种笔刷都在 **笔刷 dock** 与上方 **选项栏** 中提供 大小 / 不透明度 / 硬度 /
密度 / 混合模式 控制。``设置`` > ``压力曲线…`` 可重映射数位板压力到宽度或不
透明度；``编辑`` > ``捕获笔刷尖端…`` 可把选区转为自定义笔刷尖端。

图层
^^^^

**图层 dock** 提供缩略图、可见性切换、原地重命名、拖拽排序，以及当前层的混合
模式与不透明度。``图层`` 菜单还有：

- **新建 / 矢量 / 复制 / 向下合并**（``Ctrl + Shift + N`` / ``Ctrl + Shift + V`` /
  ``Ctrl + J`` / ``Ctrl + E``）
- **蒙版** — 添加蒙版 / 由选区生成 / 反相 / 应用 / 删除
  （``Ctrl + Shift + M`` 添加；``Ctrl + Alt + Shift + M`` 由选区生成）
- **剪贴蒙版** — 将上方图层裁剪到当前 alpha（``Ctrl + Alt + G``）
- **图层效果** — 投影 / 外发光 / 描边；可清除全部效果
- **参考图层** — 将一个图层固定为吸管取色源
- **1-bit 图层** — 切换为线稿用的二值化图层
- **按颜色拆分图层** — 把平涂层拆成多层方便重填色
- **渐变映射** — 预设子菜单（怀旧 / 落日 / 蓝晒 …）

选区
^^^^

使用矩形 / 套索 / 魔棒 / 快速选择后，``编辑`` 菜单的 **描边选区…** 用当前
笔刷沿选区边缘绘制。``Q`` 切换 **快速蒙版模式** — 用任意笔刷以红色精修选区
边缘，再按 ``Q`` 转回选区。

动画
^^^^

**动画 dock** 把文档变成帧序列：

- ``添加帧`` 将当前图层状态存为一个关键帧。
- 点击缩略图跳到该帧。
- ``洋葱皮``（视图菜单）以低不透明度叠加相邻帧。
- 通过 **文件 > 导出页面** 导出（漫画阅读器用 CBZ；打印用 PDF），或
  **动画导出** 输出 MP4 / GIF。

漫画菜单
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 动作
     - 说明
   * - 分镜切割
     - ``Ctrl + Shift + P`` — 将画布按行 / 列 / 间距 / 边框 / 边距切成漫画格
   * - 切换网点图层
     - 把当前层转成网点（halftone）图层
   * - 加盖页码
     - 在多页文档上添加页码
   * - 集中线
     - 放射 / 平行 / 爆破 三种集中线生成器
   * - 动作闪光
     - 漫画风的爆裂 / 冲击闪光叠加
   * - 对话框工具
     - 拖出气泡，再放下指向说话者的尾巴

滤镜
^^^^

``滤镜`` 打开每个效果的实时预览对话框：

- **色阶** — 黑 / Gamma / 白 滑块（每通道）
- **曲线** — 可拖动节点（RGB / R / G / B），单调三次插值
- **色调分离** — 将颜色量化成 N 阶
- **阈值** — 按切点转为纯黑 / 白
- **自动色彩平衡** — 用灰色世界 / 白点算法消除色偏
- **胶片颗粒** — 可调尺寸与强度的亮度噪点
- **转为网点** — 报纸风的点状网点

视图辅助
^^^^^^^^

- **像素网格**（``Ctrl + Shift + '``）— 高倍率时显示一像素网格
- **吸附像素 / 边缘** — 将子像素位置锁到整数坐标
- **洋葱皮** — 动画相邻帧叠加
- **出血指示** — 印刷出血 / 安全区指示线
- **旋转画布**（``Ctrl + Shift + H``）— 不破坏像素的视角旋转

文件 I/O
^^^^^^^^

- **打开 PSD…**（``Ctrl + O``）与 **另存为 PSD…**（``Ctrl + S``）— Photoshop
  图层往返，含蒙版、混合模式、图层效果
- **导出图像…** — 拼合并保存为 PNG / JPEG / WebP / BMP / TIFF
- **导出页面 → CBZ** / **→ PDF** — 多帧漫画文档导出
- **导入 / 导出笔刷预设**、**导入调色板** — 在不同安装间共享资源
- **自动保存快照** — 后台周期快照，可从文件菜单恢复最新版

工作区布局
^^^^^^^^^^

``设置`` > ``工作区布局…`` 把 dock 排列、工具选项状态、可见面板存为一个
名称，再用一键切换 — 例如 "绘画" 布局突出笔刷与颜色 dock，"合成" 布局展开
图层与历史 dock。

----

旋转与翻转
----------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - 操作
     - 快捷键
     - 菜单
   * - 顺时针旋转 90°
     - ``R``
     - 右键 > 修改 > 顺时针旋转
   * - 逆时针旋转 90°
     - ``Shift + R``
     - 右键 > 修改 > 逆时针旋转
   * - 水平翻转
     - --
     - 右键 > 修改 > 水平翻转
   * - 垂直翻转
     - --
     - 右键 > 修改 > 垂直翻转
   * - 无损旋转（JPEG）
     - --
     - 右键 > 无损旋转

----

导出图片
--------

单张导出
^^^^^^^^

右键图片 > ``导出 / 另存为``

- 选择格式：PNG、JPEG、WebP、BMP、TIFF
- 调整质量（有损格式可调）
- 预览文件大小
- 选择保存位置

导出预设组合
^^^^^^^^^^^^

对于常见输出目标，``文件`` > ``以预设导出`` 可一键套用正确的缩放、格式与质量：

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - 预设
     - 流程
   * - **Web 1600**
     - 长边 1600 px、JPEG 质量 85、sRGB；适合博客 / 论坛上传。
   * - **Print 300 dpi**
     - 全分辨率 TIFF / 高质量 JPEG，附 300 dpi metadata 与色彩管理，送印专用。
   * - **Instagram 1080**
     - 方形（1080 × 1080）或竖式（1080 × 1350）裁剪，质量 90 JPEG。

预设可与下面的水印叠加搭配使用 — 启用水印后，所有预设导出都会自动附上。

水印叠加
^^^^^^^^

``文件`` > ``水印…`` 提供非破坏性叠加设置，仅在导出时应用，不会动到原始像素。

- **模式**：文字或图片。图片水印支持含 alpha 的 PNG。
- **位置**：9 格锚点（四角、四边、正中央）。
- **不透明度**：0 – 100 %。
- **缩放**：以导出长边百分比计算，会自动按预设尺寸缩放。

批量导出
^^^^^^^^

选取多张图片后，右键 > ``批量导出``

- 统一格式转换
- 设定最大宽度／高度（自动等比缩放）
- 质量控制
- 进度条实时显示

制作 GIF / 视频
^^^^^^^^^^^^^^^^

选取多张图片后，右键 > ``创建 GIF / 视频``

- 支持 GIF 和 MP4 格式
- 可拖拽排列顺序
- 设定每秒帧数（FPS）
- 自定义尺寸
- 循环播放选项

----

动画图片播放
------------

打开 GIF、APNG、动态 WebP 时，会自动播放动画。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按键
     - 操作
   * - ``空格键``
     - 播放／暂停
   * - ``,``
     - 上一帧
   * - ``.``
     - 下一帧
   * - ``]``
     - 加速播放
   * - ``[``
     - 减速播放

----

图片比较
--------

在缩略图模式下框选 2～4 张图片，右键 > ``比较图片``。

对话框共有四个标签页：

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 标签页
     - 用途
   * - **并排**
     - 同时显示 2 或 4 张图片，各自自适应缩放。
   * - **叠加**
     - 两张图以 α 滑块混合（0 → 只看 A、100 → 只看 B）。需选中 2 张。
   * - **差异**
     - 显示 ``|A − B|`` 的逐像素差异；增益滑块（0.10×–20×）可放大细微变化。
   * - **A | B 分割**
     - before / after 分割视图，可拖动垂直分割线扫动。适合展示 Develop 调整或导出差异。需选中 2 张。

尺寸不同时会自动以 Lanczos 将 B 重新采样为 A 的尺寸。超大图片内部会限制长边 ≤ 2048 px 以保持实时反应。

.. seealso::
   若想直接在主窗口并排而不打开对话框，请见 **分割视图**（``Shift + S``）与
   **双页阅读**（``Shift + D`` / ``Ctrl + Shift + D``）。

----

幻灯片
------

按 ``S`` 或右键 > ``幻灯片``，开始自动播放所有图片。

- 可调整每张停留时间
- 可开启淡入淡出效果

----

搜索图片
--------

按 ``Ctrl + F`` 或 ``/``，输入关键字即可搜索当前文件夹中的图片名称。

搜索支持 **模糊匹配**（前缀 > 子串 > 子序列 三级排名）与 **子串高亮**。
按 ``Enter`` 或双击结果跳至对应图片。

若想按 **编号** 跳转，改按 ``Ctrl + G`` 打开跳页对话框。

----

复制与粘贴
----------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 操作
     - 方法
   * - 复制图片到剪贴板
     - 大图模式下按 ``Ctrl + C``
   * - 粘贴剪贴板图片
     - ``文件`` > ``从剪贴板粘贴``，或按 ``Ctrl + V``
   * - 自动监控剪贴板
     - ``文件`` > ``自动标注剪贴板图片`` 打勾

.. note::
   自动监控功能开启后，每当剪贴板出现新图片（例如用截图工具），就会自动打开标注编辑。

----

删除图片
--------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 操作
     - 方法
   * - 删除当前图片
     - 按 ``Delete`` 键
   * - 删除选取的多张图片
     - 框选后按 ``Delete`` 或右键 > ``删除选取``

图片会移到系统回收站，可以从那边恢复。

----

批量操作
--------

在缩略图模式下框选多张图片后，右键可以进行：

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 功能
     - 说明
   * - 批量重命名
     - 使用模板 ``{name}`` ``{n}`` ``{ext}`` 自动命名
   * - 移动／复制
     - 把图片移动或复制到其他文件夹
   * - 全部旋转
     - 一次旋转所有选取的图片
   * - 批量导出
     - 统一转换格式和大小
   * - 加入标签
     - 给所有选取的图片加上同一个标签
   * - 加入相册
     - 把所有选取的图片放进相册

----

RGB 直方图
----------

在大图模式下按 ``H``，会在画面上显示 RGB 直方图，方便判断曝光状况。再按一次隐藏。

----

设为壁纸
--------

大图模式下右键 > ``设为壁纸``，一键将当前图片设为系统壁纸。

支持 Windows、macOS、Linux（GNOME）。

----

多窗口
------

``文件`` > ``新建窗口``，可以同时打开多个 Imervue 窗口，各自独立浏览不同文件夹。

触控板手势
----------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 手势
     - 动作
   * - 捏合
     - 在大图模式放大／缩小（以捏合中心为锚点）
   * - 水平滑动
     - 上一张 / 下一张图片

----

Windows 文件关联
-----------------

让你在资源管理器中直接用 Imervue 打开图片：

1. ``文件`` > ``文件关联`` > ``注册 Open with Imervue``
2. 需要系统管理员权限
3. 之后右键任意图片就能看到 ``Open with Imervue`` 选项

如果要移除：``文件`` > ``文件关联`` > ``移除文件关联``

----

插件系统
--------

Imervue 支持插件扩展功能。

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 操作
     - 菜单位置
   * - 查看已安装插件
     - ``插件`` > ``管理插件``
   * - 下载新插件
     - ``插件`` > ``下载插件``
   * - 打开插件文件夹
     - ``插件`` > ``打开插件文件夹``
   * - 重新加载
     - ``插件`` > ``重新加载插件``

----

语言切换
--------

``语言`` 菜单可以切换界面语言：

- English
- 繁体中文
- 简体中文
- 한국어
- 日本語

切换后需要重新启动才会生效。

----

所有快捷键一览
--------------

浏览
^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按键
     - 功能
   * - ``←`` / ``→``
     - 上一张／下一张图片
   * - 方向键
     - 缩略图模式下平移画面
   * - ``Shift + 方向键``
     - 微调平移
   * - ``Ctrl + Shift + ←`` / ``→``
     - 跨文件夹跳至前／下一个含图片的同级文件夹
   * - ``Alt + ←`` / ``Alt + →``
     - 浏览历史 返回 / 前进（类似浏览器）
   * - ``Ctrl + G``
     - 按编号跳至图片
   * - ``X``
     - 随机跳一张
   * - 鼠标滚轮 / 捏合
     - 放大缩小
   * - 水平滑动
     - 上／下一张图片
   * - 鼠标中键拖拽
     - 平移画面
   * - ``F``
     - 全屏
   * - ``Shift + Tab``
     - 剧场模式（隐藏所有外壳）
   * - ``Ctrl + L``
     - 切换 缩略图格 ↔ 列表（详细）
   * - ``Shift + S``
     - 分割视图（两张并排）
   * - ``Shift + D`` / ``Ctrl + Shift + D``
     - 双页阅读 / 从右到左（漫画）
   * - ``Ctrl + Shift + M``
     - 副屏镜像窗口
   * - ``Esc``
     - 回到缩略图模式／退出全屏／关闭双图或列表模式
   * - ``W``
     - 适应宽度
   * - ``Shift + W``
     - 适应高度
   * - ``Home``
     - 重置缩放

编辑
^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按键
     - 功能
   * - ``E``
     - 进入修改选项卡
   * - ``R``
     - 顺时针旋转
   * - ``Shift + R``
     - 逆时针旋转
   * - ``Ctrl + Z``
     - 撤销
   * - ``Ctrl + Shift + Z``
     - 重做
   * - ``Delete``
     - 删除图片

整理
^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按键
     - 功能
   * - ``0``
     - 加入／取消收藏
   * - ``1`` ～ ``5``
     - 评分（再按取消）
   * - ``F1`` ～ ``F5``
     - 颜色标签：红／黄／绿／蓝／紫（再按清除）
   * - ``P``
     - 分拣：Pick（标为保留）
   * - ``Shift + X``
     - 分拣：Reject（标为淘汰）
   * - ``U``
     - 分拣：取消标记
   * - ``B``
     - 加入／取消书签
   * - ``T``
     - 标签与相册管理

工具与叠加层
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按键
     - 功能
   * - ``Ctrl + F`` / ``/``
     - 模糊搜索（子串高亮）
   * - ``Ctrl + C``
     - 复制图片到剪贴板
   * - ``Ctrl + V``
     - 从剪贴板粘贴
   * - ``H``
     - RGB 直方图
   * - ``F8`` / ``Ctrl + F8``
     - OSD 信息 / Debug HUD（显存、缓存、线程）
   * - ``Shift + P``
     - 像素查看（≥ 400 % 显示网格与光标下 RGB 值）
   * - ``Shift + M``
     - 循环色彩模式（正常／灰阶／反相／怀旧）
   * - ``S``
     - 幻灯片

动画播放
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 按键
     - 功能
   * - ``空格键``
     - 播放／暂停
   * - ``,``
     - 上一帧
   * - ``.``
     - 下一帧
   * - ``[``
     - 减速
   * - ``]``
     - 加速

图库与元数据管理
----------------

Imervue 会在 ``%LOCALAPPDATA%/Imervue/library.db``（Windows）或
``~/.cache/imervue/library.db``（POSIX）维护 SQLite 索引，用于跨文件夹搜索、
分层标签、智能相册、感知哈希、笔记与分拣旗标。以下功能多数位于
``Extra Tools``（额外功能）菜单。为方便查找，该菜单按功能分为八个子菜单：
``Batch``（批量）、``Library & Metadata``（图库与元数据）、
``Views``（视图）、``Workflow``（工作流程）、``Export``（导出）、
``Develop (Non-Destructive)``（调整）、``Retouch & Transform``（修复与变形）、
``Multi-Image``（多张合成），以下路径均以
``Extra Tools`` > ``<子菜单>`` > ``<工具>`` 的形式呈现。

图库搜索
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Library Search`` 支持添加多个**根目录**并在后台建立索引，
之后可按扩展名、最小宽高、文件大小或文件名片段查询，并将结果作为虚拟
相册载入查看器。

智能相册
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Smart Albums`` 以友好名称保存一组过滤规则（扩展名、最小
尺寸、颜色标签、评分、收藏、分拣状态、分层标签、文件名片段），再次应用
时会按规则过滤当前文件夹。

相似图片搜索
^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Find Similar Images`` 会对当前深度缩放（或第一张选中）
的图片计算 64 位 DCT pHash，并按汉明距离由近到远列出索引中的近似图，可
通过 Max distance 调节宽严。

自动标记
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Auto-Tag Images`` 将启发式标签归入 ``auto/...``
（``photo`` / ``document`` / ``screenshot`` / ``landscape`` /
``portrait``）；若安装了 ``onnxruntime`` 且 ``models/clip_vit_b32.onnx``
存在，则额外添加 CLIP 内容标签。在工作线程中运行，带实时进度条。

分层标签
^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Hierarchical Tags`` 管理树状标签（如
``animal/cat/british``）。选择节点即显示该节点与全部子节点下的图片；可一
键为所选图片添加或移除标签。与右键菜单的扁平标签并行。

Token 批量重命名
^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Batch`` > ``Token Batch Rename`` 提供实时预览，输入
``{date:yyyymmdd}_{camera}_{counter:04}{ext}`` 等模板后立即显示每个文件的
新名称；冲突会被高亮。支持 tokens：``{name} {ext} {counter[:NN]}
{date[:fmt]} {width} {height} {wxh} {size_kb} {camera} {year} {month} {day}
{hour} {minute}``。

元数据导出
^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``Export Metadata (CSV / JSON)`` 会为当前视图中的每张图
片输出一行，包含 EXIF、尺寸、颜色标签、评分、收藏、分层标签、分拣状态
与笔记。方便接入电子表格或外部流程。

XMP Sidecar（other XMP-aware photo managers 互通）
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Imervue 支持读写 Adobe XMP sidecar 文件（``photo.jpg`` ↔ ``photo.xmp``），
让星级、标题、描述、关键字与颜色标签可与 other XMP-aware photo managers、other XMP-aware photo managers、Bridge
等 XMP 感知工具双向同步。

- **为当前图片导入 XMP** — 从 sidecar 读取星级 / 标题 / 关键字 / 颜色标签
  写入内部数据库。
- **为当前图片导出 XMP** — 将当前星级 / 标题 / 关键字 / 颜色标签写入
  图片旁的 sidecar 文件。
- **批量导入 / 导出** — 将同样操作应用至当前选择或整个文件夹。

XML 解析通过 ``defusedxml`` 进行，避免 XXE / billion-laughs 等攻击。
若未安装 ``defusedxml``，XMP 菜单项会自动隐藏，也不会写出 sidecar。

**EXIF 侧边栏** 亦提供可点击的 **星级快速条** — 设置的星级即为 XMP 导出的值。

分拣（Pick / Reject）
^^^^^^^^^^^^^^^^^^^^^

旗标式的三态旗标。``P`` 将当前或选中的所有 tile 标为 Pick；
``Shift + X`` 标为 Reject；``U`` 取消。``Filter`` > ``By Cull State`` 可只
显示某种状态；``Extra Tools`` > ``Workflow`` > ``Culling`` 提供对话框并带有
**Delete all rejects** 按钮，可从磁盘永久删除被淘汰文件。

暂存篮
^^^^^^

``Extra Tools`` > ``Workflow`` > ``Staging Tray`` 是跨文件夹的暂存篮。任意 tile 可加入篮中
（重启后保留），再一键将整篮移动或复制到目标文件夹。适合从多次拍摄中
汇总出精选再导出。

双窗格文件管理
^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Dual-Pane File Manager`` 提供 双窗格的双
树视图，可在两侧文件夹之间直接移动或复制选中项。

时间轴视图
^^^^^^^^^^

``Extra Tools`` > ``Views`` > ``Timeline View`` 按「日／月／年」分组当前图片集（Google
Photos 风格）。日期优先取 EXIF ``DateTimeOriginal``，否则使用文件修改时间。
双击图片可进入深度缩放。

拖拽至外部应用
^^^^^^^^^^^^^^

从**已选中** tile 按住拖拽，即可将文件丢入资源管理器、Chrome、Discord 等
支持 file URL 的应用；拖拽预览为 tile 缩略图。

单张图片笔记
^^^^^^^^^^^^

EXIF 侧栏包含 **Notes** 文本框，输入内容会经短暂去抖后自动写入索引；笔记
按图片路径保存，重新扫描也能保留。

----

高级 Develop 与合成
-------------------

色调曲线（Tone Curve）
^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Tone Curve`` 打开可拖拽控制点的曲线编辑器，提供 RGB、
R、G、B 四条通道。点击空白处新增控制点、拖拽移动、右键删除。点之间
以单调三次（monotone cubic）插值，曲线存在 recipe 中渲染时非破坏性生效。

应用 .cube LUT
^^^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Apply .cube LUT`` 可载入任意 Adobe ``.cube`` 文件
（1D / 3D，最高 64³）。LUT 以 ``lru_cache`` 按路径 + mtime 缓存，使用
三线性插值并通过强度滑块与原图混合，LUT 路径与强度存入 recipe。

虚拟副本（Virtual Copies）
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Workflow`` > ``Virtual Copies`` 为同一张图创建多组命名 recipe
快照。保存当前编辑后继续实验，之后随时切回任一版本；副本与主
recipe 同存，重置主 recipe 也不会消失。

HDR 合成
^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``HDR Merge`` 使用 OpenCV Mertens 曝光融合合并
多张不同曝光。可勾选 Align 先以 ``cv2.AlignMTB`` 对齐，输出写到
指定路径，不影响源文件。

全景拼接
^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Panorama Stitch`` 使用 OpenCV ``Stitcher`` 拼接
重叠影像，风景 / 城市用 **Panorama** 模式，平面文档用 **Scans**
模式，可自动裁掉黑边。

景深合成（Focus Stacking）
^^^^^^^^^^^^^^^^^^^^^^^^^^

``Extra Tools`` > ``Multi-Image`` > ``Focus Stacking`` 融合不同对焦距离的多张图像，
以 Laplacian 方差选取每像素最清晰的来源，并用高斯平滑避免接缝。
默认启用 ECC 对齐以补手持位移。

修复画笔
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Healing Brush`` 在最大 720 px 长边的预览中显示当前
图像。左键添加圆形修复区，右键移除，半径滑块控制新区域大小。应用
时使用 OpenCV inpainting（Telea 快 / Navier-Stokes 平滑），输出为
新文件。

镜头校正
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Lens Correction`` 提供四个纯 numpy 滑块：径向
畸变 ``k1``（桶形 / 枕形）、暗角补偿，以及红 / 蓝通道色差径向缩放。
因尺寸可能改变，结果输出为新文件而非写入 recipe。

地图视图
^^^^^^^^

``Extra Tools`` > ``Views`` > ``Map View`` 通过 Leaflet + OpenStreetMap（需
``PySide6.QtWebEngineWidgets``）显示所有含 GPS 的照片；未安装
WebEngine 时降级为坐标列表。

日历视图
^^^^^^^^

``Extra Tools`` > ``Views`` > ``Calendar View`` 用 ``QCalendarWidget`` 高亮有
照片的日期（依序 EXIF ``DateTimeOriginal`` → ``DateTimeDigitized``
→ 文件 mtime）。选中日期列出当日照片，双击在主视图中打开。

人脸检测
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Face Detection`` 使用 OpenCV Haar 正脸分类器检测
脸部并以矩形标注。在列表双击输入姓名，保存后写入 recipe 的
``extra['face_tags']``。此为经典算法，适合「找出脸的位置」，并
非现代 CNN 识别的替代。

局部调整蒙版
^^^^^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Local Adjustment Masks`` 支持画笔 / 放射 / 线性
渐变三种蒙版。每个蒙版都有独立的曝光、亮度、对比、饱和度、色温、
色调 delta 和羽化滑块，保存到 ``recipe.extra['masks']``，以非破坏
方式在加载时混合到原图。

色调分离
^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Split Toning`` 对阴影和高光分别应用不同色相与
饱和度，并通过平衡枢纽决定边界。保存在 ``recipe.extra`` 中，并在
develop pipeline 的 tone curve 之后应用。

仿制图章
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Clone Stamp`` 以羽化方式把源区块复制到目标，
是修复画笔的硬边版本。Shift+点击设定源点，单击盖章，右键撤销。
结果输出为新文件，不会影响原图。

裁剪 / 拉直
^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Crop / Straighten`` 结合 0..1 归一化裁剪矩形和
任意角度拉直。输出会自动裁剪到最大内接矩形，旋转后不会产生黑边。

自动拉直
^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Auto-Straighten`` 通过 Hough line 检测主要的地
平线或垂直线，给出建议旋转角度。应用前可以手动微调。

降噪 / 锐化
^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Noise Reduction / Sharpening`` 先用边缘保留的
bilateral 降噪，再用 unsharp mask 锐化。「仅亮度通道」会保留色噪，
但能压平明度噪声而不糊掉色彩边缘。

天空 / 背景
^^^^^^^^^^^

``Extra Tools`` > ``Retouch & Transform`` > ``Sky / Background`` 把检测到的天空替换成渐变，
或直接把背景去除成透明 / 白底。安装 ``rembg`` (U²-Net) 时会自动
启用神经网络前景分割。

屏幕校样
^^^^^^^^

``Extra Tools`` > ``Develop (Non-Destructive)`` > ``Soft Proof`` 加载 ICC 描述文件，将图像转入目标
色域再转回，并用洋红显示往返过程中被裁切的像素 — 打印前的快速
色域检查。

GPS 地理标记
^^^^^^^^^^^^

``Extra Tools`` > ``Library & Metadata`` > ``GPS Geotag`` 读取已有的 EXIF GPS 坐标并允许
编辑或设定新的十进制度数。需要安装 ``piexif``；直接写入 JPEG 文件。

打印排版
^^^^^^^^

``Extra Tools`` > ``Export`` > ``Print Layout`` 把多张图片排版为多页 PDF，可设
定页面大小、方向、网格、边距、间隔与裁切标记。需要 ``reportlab``。

----

Puppet 工作区（Puppet 标签）
----------------------------

第四个顶层标签 — **Puppet** — 是从零打造的 2D 绑骨偶动画系统。功能对标 Live2D（网格变形绑骨、参数、动作、物理、表情、姿势组、对嘴、摄像头追踪），但**不依赖任何专利 SDK**、**不使用** ``live2d-py``，采用完全开放的 ``.puppet`` 文件格式。

.. note::

   端到端教程 — 从全新安装到 OBS 直播或产出 MP4 — 在仓库根目录的
   ``puppet_guide.zh-CN.md``（英文版 ``puppet_guide.md``、繁体中文版 ``puppet_guide.zh-TW.md``）。
   本章是参考手册；那份是逐步走读。

端到端流程
^^^^^^^^^^

1. **导入 PNG** — 工具栏 ``Import PNG…`` 跑 ``puppet.auto_mesh.puppet_from_png``：依 alpha 三角化、单一 drawable、可立即渲染。
2. **加变形器** — ``Add Rotation Deformer``（锚点 + 角度）或 ``Add Warp Deformer``（rows × cols Bezier lattice；边界外顶点直通）。
3. **加参数** — ``Add Parameter`` 在右侧 **Parameters** 停靠栏加滑块（自动命名 ``Param1``、``Param2`` …）。
4. **设 keys** — 拖滑块到极端值、编辑 deformer form、按 **Set key**。对中立值跟另一端重复。Runtime 接着会在滑块移动时于相邻 keys 之间 lerp 各字段。
5. **保存** — ``Save As…`` 把 rig + 纹理 + 动作 + 表情 + 物理写成单一 ``.puppet`` zip，可分享或之后用 ``Open Puppet…`` 重开。

示例
^^^^

仓库内附完整 rig：``examples/puppet/march_7th.puppet`` — 307-drawable 的 Cubism Live2D 角色，仓库内转换好。纹理跟每参数顶点 morph 全烘进 ``.puppet`` zip，使用默认 ``requirements.txt`` 就能开，无需散布 Cubism SDK。

该 rig 带 203 个 Cubism 标准参数（``ParamAngleX/Y/Z``、``ParamEyeLOpen/ROpen``、``ParamBreath``、``ParamMouthOpenY`` …），所以所有标准输入驱动（摄像头、眨眼、对嘴、光标追踪）不用调整就能驱动。内置 18 个循环动作 — 作者转换的 Cubism idle 循环，加上 ``Idle`` 组和 ``Gesture`` 组的参考手势。

Puppet 标签工具栏 → **Examples ▾** 下拉直接选 March 7Th 或自己的 ``.puppet`` 打开。下方 **Motions** 停靠栏点任一个动作即播。

**执行内置示例 — 分步演示：**

1. **启动 Imervue**。源码运行：``python -m Imervue``；安装版：直接执行 ``Imervue`` 可执行文件 / app bundle。``examples/`` 目录已打包进 wheel 与 Nuitka EXE，rig 文件位于安装目录下。
2. 点窗口顶部的 **Puppet** 标签。
3. 工具栏 → **File > Examples > March 7Th**（或工具栏上的 **Examples ▾** 下拉）。307-drawable 的 rig 居中载入，参数栏填满 203 个 Cubism 标准参数滑块。
4. 在底部 **Motions** 停靠栏单击任一个动作条目（``zhaiyan``、``zhaoxiang``、``idle_breath``、``tap_head`` …）。立即开始播放；再点一次停止，或选别的动作交叉淡入。
5. 切换工具栏上的实时输入 toggle 让 rig 跟你动 — **Drag-track head**（头跟光标）、**Auto-blink**（自动眨眼）、**Auto idle** + **Idle motions**（呼吸 + 随机 idle 动作）、**Mic lip-sync**（麦克风 RMS 带动嘴型）、**Webcam tracking**（MediaPipe FaceLandmarker 驱动头 / 眼 / 嘴）。
6. 工具栏 **Reset to rest** 停掉所有动作、取消勾所有实时驱动、清掉 expressions / pose 覆盖，所有参数复位 — 标准的「从头开始」按钮。
7. 之后要打开别的 rig：**File > Open Puppet…** 从磁盘挑任何 ``.puppet`` zip；**File > Examples ▾** 始终连到内置清单。

OBS 直播整合
^^^^^^^^^^^^

两条输出，都把角色独立渲染到 off-screen framebuffer（不含棋盘格背景与编辑器外壳）再送到推流端。输出长边上限 1080 px，避免 Cubism 原生画布（March 7th 是 3503×7777）被 DirectShow 虚拟摄像头驱动拒绝。

**A. Virtual Camera** — 在 OBS"视频捕获设备"源列表里以 webcam 形式出现。``pip install pyvirtualcam`` 加上平台驱动：OBS Studio 26+（Windows/macOS）会附 *OBS Virtual Camera* 驱动，第一次打开 OBS 点 *Start Virtual Camera* 注册；Linux 用 ``v4l2loopback-dkms`` + ``modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"``。工具栏 **Output > Virtual camera** 开始推流。

DirectShow / AVFoundation / v4l2loopback 都**只有 RGB、没有 alpha 通道**，所以 Imervue 在角色以外的区域填**洋红色 `#FF00FF`** 当色键。OBS 端去背：

1. 视频捕获设备源右键 → **Filters**
2. **Effect Filters > + > Color Key**
3. 设置 **Key Color Type** = ``Custom Color``、**Custom Color** = HEX ``FF00FF``、**Similarity** = ``80–300``、**Smoothness** = ``30–50``

滤镜跟着源走，下次启用虚拟摄像头自动套用。

**B. NDI 输出** — LAN 上 < 50 ms 延迟、原生 RGBA，OBS / vMix 可以直接把角色叠到自己的场景上、不用色键。``pip install ndi-python``，加上 `NDI Tools <https://ndi.video/tools/>`_ runtime 与 `obs-ndi <https://github.com/obs-ndi/obs-ndi/releases>`_ 插件。工具栏 **Output > NDI output** 开始广播（默认源名 *Imervue Puppet*）。

``ndi-python`` 只 ship source distribution、pip 拿到后从 C++ 编。Windows 需要 Visual Studio Build Tools 2022（含 C++ 工作负载）、CMake 加到 PATH、NDI SDK（从 <https://ndi.video/for-developers/ndi-sdk/> 取得，跟 NDI Tools 不同）装在默认位置、环境变量 ``NDI_SDK_DIR`` 指向 SDK。

详细逐步与疑难排解见 ``puppet_guide.zh-CN.md`` § 1.2。

录制自定义动作
^^^^^^^^^^^^^^

不想手动编 keyframe？用实时 take 录：

1. 工具栏 **Record motion** 打勾，会弹出命名对话框。
2. 录制时拖滑块、开 **Webcam tracking**、让物理跑 — 任何会写参数值的事情都可以。
3. **Record motion** 取消勾 — 录制器把 30 Hz 串流烘焙成一个 ``Motion``：每个真的有变动的参数一条 linear-segment 轨（没变动的丢掉）。新动作立刻出现在底部 **Motions** 停靠栏。

存进 ``.puppet`` 的方式跟手写 keys 的动作完全相同。

工具栏参考
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 动作
     - 用途
   * - Open Puppet… / Examples ▾
     - 从磁盘加载 ``.puppet``，或从工具栏直接挑 ``examples/puppet/`` 下内置的 rig
   * - Import PNG… / Import PSD… / Import Cubism…
     - PNG 自动 mesh、PSD 分层拆 drawable、Cubism rig sample-and-reconstruct。Cubism 文件选择器同时接受 ``.moc3`` 和 ``.model3.json``；工作区还没开 rig 时两条路径都跑完整 ``.moc3 → .puppet`` 转换（SDK 用户自备）。已经开了 rig 时选 ``.model3.json`` 会把 JSON 部分（motions / expressions / physics）叠加到既有文档
   * - Save As…
     - 把当前 rig 写成 ``.puppet`` zip
   * - Add Rotation Deformer / Add Warp Deformer / Add Parameter
     - 从工具栏 author rig
   * - Drag-track head
     - 光标偏移 → ``ParamAngleX`` / ``ParamAngleY`` + ``ParamEyeBallX`` / ``ParamEyeBallY``
   * - Auto-blink
     - ``ParamEyeLOpen`` / ``ParamEyeROpen`` 上的 cosine close→open，每 ~4.5 秒一次（force-write 路径绕过 canvas 的 no-change-skip，避免被其他 driver 卡住）
   * - Mic lip-sync
     - 麦克风 RMS → ``ParamMouthOpenY``（需 ``sounddevice``）
   * - Webcam tracking
     - MediaPipe Tasks API FaceLandmarker → 头部 yaw / pitch / roll + 眼 + 嘴（需 ``opencv-python`` + ``mediapipe``；打开实时预览 dialog 显示检测到的 landmark）
   * - Auto idle / Idle motions
     - 标准参数上的呼吸 + 漂移，加上 Idle 组动作的随机循环
   * - Edit mesh
     - 拖曳 canvas 上的顶点微调 mesh
   * - Record motion
     - 把参数变化录成新的 ``Motion`` 加进文档 — take 烘焙、不用手动 author keys
   * - Capture frame… / Record… / Export all motions…
     - 存单张 PNG、开关 GIF / WebM / MP4 录制、或批量把每个动作各别 render 成文件（全部用跟推流相同的角色独立 off-screen render）
   * - Output > Virtual camera / NDI output
     - 直播输出 — 见上面的"OBS 直播整合"
   * - Reset to rest
     - Motion player 直接停、所有 live driver 取消勾、清空 expressions / pose groups、参数复位
   * - Fit to Window
     - Canvas 上重新居中 + 缩放 rig

可选依赖
^^^^^^^^

* ``sounddevice`` — 麦克风对嘴
* ``opencv-python`` + ``mediapipe`` — 摄像头脸部追踪
* ``imageio-ffmpeg`` — MP4 / WebM 录制（已随幻灯片视频功能附带）
* ``pyvirtualcam`` — 虚拟摄像头输出（见"OBS 直播整合"）
* ``ndi-python`` — NDI 输出（见"OBS 直播整合"）
* 用户自备 Cubism Native SDK DLL — ``.moc3 → .puppet`` 转换（Live2D Free Material License 禁止散布；放在 ``<cwd>/sdk/`` 或设 ``CUBISM_CORE_DLL`` 环境变量）

任何缺失都会优雅停用 — 对应工具栏 toggle 会自动弹回去并提示安装。**File > Install dependencies…** 可一次装齐所有 Python 可选包。

----

桌宠工作区（Desktop Pet 标签）
------------------------------

第五个标签 — **Desktop Pet**（桌宠） — 把任意 ``.puppet``
角色作为无边框、透明的浮层显示在桌面上。标签本身是控制面板；
真正的角色是一个独立的顶层窗口，与 Puppet 运行时共享全部能力
（动作、表情、物理、闲置驱动、麦克风 / 摄像头输入）。桌宠可以
响应点击、播放定时驱动的动画、跟随光标、在其它应用全屏时自动
隐藏，还能朗读你在 JSON 文件里写的台词。

本章是该标签的完整参考。组织结构如下：

#. **快速上手** — 从"刚打开 Imervue"到"桌面上出现一只桌宠"
   的五步路径。
#. **加载角色** — 文件选择器、内置示例、跨启动恢复。
#. **浮层窗口** — 所有窗口层级行为（拖曳移动、贴边吸附、穿透
   点击、锚点锁定、永远置底、全屏时隐藏、隐藏时暂停、透明度、
   尺寸、多显示器恢复）。
#. **交互模型** — 左键命中区域、完整右键菜单、系统托盘。
#. **实时驱动** — 六个可选的输入驱动及其可选依赖。
#. **Pet script（桌宠脚本）** — 用 JSON 文件替换桌宠的"嗓音"、
   排定提醒、为每个命中区域 / 每个动作绑定回应。
#. **持久化** — 跨启动会被记住的字段及完整设置 schema。
#. **创作新桌宠** — 指向 Puppet 标签与 ``.puppet`` 文件格式。
#. **疑难排查** — 常见意外和应对方式。

快速上手
^^^^^^^^

1. 切到 **Desktop Pet**（桌宠）标签。
2. 点击 **Load bundled March 7th**（载入内置 March 7th）使用
   内置角色，或 **Open Puppet…**（打开 Puppet 文件…）选择自己
   的 ``.puppet`` 文件。
3. 浮层会出现在桌面上，**Show pet on desktop**（在桌面显示
   桌宠）勾选框会被自动勾上。（如果想在不关闭 Imervue 的情况下
   隐藏桌宠，取消勾选或用系统托盘图标即可。）
4. 把角色拖到喜欢的位置。在屏幕边缘附近松开会贴边吸附。
5. 在标签页或桌宠的右键菜单里勾选想用的 **Live drivers**
   （实时驱动） — 闲置呼吸、眨眼、跟随光标、麦克风口型同步、
   摄像头追踪。

你设的所有项都会在下次启动时保留，所以第 5 步对每个角色 / 人设
只需做一次。

加载角色
^^^^^^^^

标签提供三种加载方式：

* **Open Puppet…**（打开 Puppet 文件…） — 从磁盘选择任意
  ``.puppet`` 文件。
* **Load bundled March 7th**（载入内置 March 7th） — 打开内置
  的 ``examples/puppet/march_7th.puppet``。解析器先查
  ``examples_dir()``（对打包的 Nuitka / pip 安装版本是
  frozen-safe 的），再回退到相对仓库根目录的查找，所以两种运行
  方式下按钮都能正常工作。
* **Last rig**（上一个角色） — 上次加载的角色会在 Imervue 启动
  时从设置字段 ``last_rig_path`` 自动恢复；Desktop Pet 标签会
  不可见地重新实例化浮层，让桌宠只差一次点击就回到你离开时
  的状态。

加载成功会自动勾上 **Show pet on desktop**，桌宠立刻出现。
失败路径会让勾选框保持原状，并把错误写到标签的状态栏。

浮层窗口
^^^^^^^^

角色生活在与 Imervue 主窗口分离的顶层窗口里。该窗口无边框、
不在任务栏出现，默认置于其它所有窗口之上。

.. list-table:: 窗口行为
   :header-rows: 1
   :widths: 28 72

   * - 行为
     - 说明
   * - 无边框浮层
     - 没有窗口边框，也没有最小化 / 关闭按钮，更不在任务栏
       出现。整个可见区域就是角色本身。
   * - 透明背景
     - 角色没遮住的地方完全透明。背后的桌面 / 应用会像素级
       精准地透出。
   * - 拖曳移动
     - 在身体上左键按下、拖动、松开。鼠标移动小于 6 像素时才
       会被识别为点击 — 移动更远就变成移动手势，不会触发点击
       处理器。
   * - 贴边吸附
     - 在屏幕边缘附近（默认 24 px 以内）松开，桌宠会"咔"地
       贴上去。阈值可在 0（关闭）到 200（很黏）之间配置。
       两个轴独立判断，所以拖到角落时会同时贴上两条边。
   * - 越界回拉
     - 拖到屏幕边缘外松开会被钳回屏幕内。桌宠不会被甩到你
       够不到的地方。
   * - 穿透点击模式
     - 开启后所有鼠标事件都会穿过桌宠传给背后的窗口。角色
       仍然可见，但无法被拖、无法右键、也无法用来触发动作。
       桌宠纯做装饰时打开它。
   * - 锁定位置
     - 在不影响穿透点击的前提下禁用拖曳。当你把桌宠放到精确
       位置后不希望被误拖时使用。
   * - 永远置底
     - 把桌宠从永远置顶翻成永远置底。它会像桌面挂件一样躺在
       所有窗口之后。同时取消接受焦点的标志，所以点击桌宠
       不会把它顶到前面。
   * - 全屏时隐藏
     - 一个 1 Hz 的后台轮询监视桌宠所在显示器的前台窗口。当
       该窗口覆盖屏幕的 ≥ 99 %、每边容差 ≤ 4 px（同时覆盖
       真正全屏与无边框窗口化的游戏）时，桌宠会自动隐藏。
       全屏结束后，桌宠会在原位置重新出现。检测器在 Windows
       上使用 Win32 ``GetWindowRect`` API；在 macOS / Linux
       上会优雅地 no-op（桌宠保持可见）。
   * - 隐藏时暂停
     - 在 ``hideEvent`` 时 ~30 FPS 的绘制 tick 和 1 Hz 的
       脚本 tick 都会停下，所以隐藏中的桌宠零 CPU 占用。下次
       ``showEvent`` 会重新启动。
   * - 尺寸预设
     - 小（200 × 300）、中（320 × 480）、大（480 × 720）。
       桌宠围绕当前中心点缩放，所以改尺寸时不会跑位。缩放
       后会重新跑一次吸附。
   * - 透明度滑块
     - 10 – 100 %。作用在窗口级（通过 ``setWindowOpacity``），
       所以是整个桌宠淡出，而不仅是贴图。最低 10 % 的下限
       是为了让你始终看得见、抓得到桌宠 — 完全透明会让你
       把它弄丢。
   * - 位置记忆
     - 每次松开后吸附之后的 ``(x, y)`` 都会被持久化。下次
       启动桌宠会回到那个屏幕坐标。如果保存的坐标已经不在
       任何连接的屏幕里（你拔掉了显示器），桌宠会回退到
       主屏的右下角。

交互模型
^^^^^^^^

桌宠通过三个独立通道响应鼠标输入。

**身体上左键**

点击位置会被映射回 puppet-canvas 坐标（撤销 canvas 的平移 /
缩放），交给现有的 ``hit_test`` 流水线。结果按以下方式驱动
行为：

#. 如果有一个 ``HitArea`` 覆盖了被点击的 drawable，且该区域
   绑定了动作，就播放该动作。
#. 不管动作是否播放，桌宠都可能弹出一个气泡 — 台词挑选优先级
   见 *Pet script*（桌宠脚本）一节。
#. 如果没有命中区域覆盖该点击，桌宠会回退到一句问候（从脚本
   的 ``greetings`` 列表或内置回退集里选）。

拖曳移动手势会抑制点击处理器，所以拖动桌宠不会触发动作 / 台词。

**身体上任意位置右键**

弹出一个结构如下的上下文菜单：

* **Hide pet**（隐藏桌宠） — 顶层动作，关闭浮层。
* **Live drivers**（实时驱动）子菜单 — 六个可勾选的开关
  （Auto idle、Idle motions、Auto-blink、Drag-track head、
  Mic lip-sync、Webcam tracking）。勾选状态镜像实时驱动的
  运行状态，所以菜单显示的就是当前在跑的。
* **Play motion**（播放动作）子菜单 — 从当前角色的
  ``document.motions`` 列表生成。选中一项会播放该动作（如果
  脚本为它绑定了台词，还会触发桌宠的声音）。
* **Apply expression**（应用表情）子菜单 — 从角色的
  ``document.expressions`` 生成。选中会切换该表情的参数 overlay。
* 五个顶层可勾选开关：**Lock position**（锁定位置）、
  **Click-through**（穿透点击）、**Always on bottom**
  （永远置底）、**Hide on fullscreen**（全屏时隐藏）、
  **Speech bubble**（气泡） — 与标签里同名开关的快捷入口。
* **Size**（尺寸）子菜单 — Small / Medium / Large；当前预设
  会被勾上。

没加载角色时，动作 / 表情子菜单会被禁用。

**系统托盘图标**

托盘图标（仅在报告支持托盘的平台上实例化）提供第四个入口，
覆盖最常用的操作：

* 左键切换桌宠显示。
* 右键打开菜单：**Show pet**（显示桌宠，可勾选）、
  **Click-through**（穿透点击）、**Open puppet…**（打开 puppet
  文件…）、**Hide pet**（隐藏桌宠）。
* 可勾选的 Show / Click-through 项通过 ``sync_visibility`` /
  ``sync_click_through`` 镜像标签的勾选状态，所以无论用户在哪
  切换对应开关，两边都会保持同步。

实时驱动
^^^^^^^^

每个实时驱动都是首次启用时才懒创建的，所以一只休眠中的桌宠
对你没开的驱动零 timer / 线程开销。每个驱动的状态都会被持久化；
打开它、关掉 Imervue、再启动，桌宠会带着同样的驱动复活。

.. list-table::
   :header-rows: 1
   :widths: 22 50 28

   * - 驱动
     - 作用
     - 可选依赖
   * - **Auto idle**
     - 在标准参数（``ParamBreath`` 等）上加呼吸 + 轻微漂移，
       让角色在什么都没动时也显得活着。
     - 无
   * - **Idle motions**
     - 每隔几秒从角色的 ``Idle`` 组里随机挑一个动作播放。
       如果当前已有动作在跑则跳过。
     - 无
   * - **Auto-blink**
     - 每 ~4.5 s 用平滑的余弦曲线闭眼再睁眼。该驱动会强制
       写入参数，避免其它触碰眼睛 open 值的驱动压制眨眼。
     - 无
   * - **Drag-track head**
     - 头 + 眼睛即便光标不在桌宠上也会转向全局光标位置。
       驱动 ``ParamAngleX`` / ``ParamAngleY`` /
       ``ParamEyeBallX`` / ``ParamEyeBallY``。
     - 无
   * - **Mic lip-sync**
     - 麦克风 RMS 振幅驱动 ``ParamMouthOpenY``。
     - ``sounddevice``
   * - **Webcam tracking**
     - MediaPipe FaceLandmarker 以 ~30 FPS 读取摄像头，驱动
       头部姿态 + 眼 open + 嘴 open 参数。会打开一个小的实时
       预览窗口让你确认摄像头看得见你的脸。
     - ``opencv-python`` + ``mediapipe``

两个带可选依赖的驱动会优雅降级：如果依赖没装，勾选会被弹回，
工作区状态栏会提示安装 ``sounddevice`` / ``opencv-python +
mediapipe``。

Pet script — 自定义嗓音与定时事件
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

桌宠的气泡从一个你可以自己写的 JSON 文件取台词，文件通过标签
里的 **Pet script**（桌宠脚本）面板加载。脚本控制四件事：

* **Greetings**（问候） — 没有更具体匹配时使用的默认点击台词。
* **Hit-area responses**（命中区域回应） — 按 ``HitArea.id``
  分桶的台词。
* **Motion lines**（动作台词） — 按动作名分桶的台词，在桌宠
  开始播放该动作时触发（无论来自命中区域还是上下文菜单）。
* **Scheduled chimes**（定时提醒） — 定时驱动的台词，每过
  ``every_seconds`` 秒（按 monotonic 墙钟）触发一次。

Schema（带版本号 — 新字段向前兼容）：

.. code-block:: json

   {
     "version": 1,
     "name": "March 7th — playful voice",
     "greetings": [
       "Hi!", "Hello hello!", "Need a break?"
     ],
     "hit_responses": {
       "HitAreaHead": ["Hey, my head!", "Stop poking!"],
       "HitAreaBody": ["Hehe~", "Pat pat?"]
     },
     "motion_lines": {
       "wave": ["Hi!", "Hello!"],
       "curtsy": ["Cheers!"]
     },
     "scheduled": [
       {"every_seconds": 1800, "messages": ["Stretch break!"]}
     ]
   }

加载规则：

* 每个桶内的列表按 round-robin 取样，用户不会连续看到同一句。
* 未知顶层 key 会被忽略（向前兼容 — 未来的 v2 文件仍能在 v1
  运行时上加载）。
* 列表里坏掉的条目（类型不对、scheduled 条目畸形、
  ``every_seconds`` ≤ 0）会被跳过 — 单条坏行不会让整个加载
  失败。只有彻底无法解析的 JSON 才会报错并把路径显示在状态栏。
* 命中区域 / 动作 / 问候按层级回退：一次左键先查
  ``hit_responses[area.id]``，然后 ``motion_lines[area.motion]``，
  然后 ``greetings``，最后兜底的内置默认问候集。
* 时间跟踪使用 ``time.monotonic``，所以挂起笔记本或调系统时钟
  也不会让排队事件批量爆发。

**Reset to default**（恢复默认）会丢掉用户脚本、回到内置问候集；
持久化的脚本路径会被清空，下次启动不再加载。

一个可用的示例位于
``examples/desktop_pet/march_7th.petscript.json`` — 六句问候、
两个命中区域桶（head / body）、三组动作台词（wave / curtsy /
cheer）、以及一个 30 分钟拉伸提醒。

持久化
^^^^^^

所有 Desktop Pet 状态都通过 ``user_setting_dict["desktop_pet"]``
（标准 Imervue 用户设置文件中的一个槽）round-trip。每个字段在
加载时都有默认值 + 范围钳制，所以坏掉的设置文件不会让启动崩溃。

.. list-table:: 持久化字段
   :header-rows: 1
   :widths: 28 18 54

   * - 字段
     - 默认值
     - 说明
   * - ``last_rig_path``
     - ``""``
     - 启动时若文件仍存在则自动恢复。
   * - ``script_path``
     - ``""``
     - 启动时若脚本仍能解析则自动恢复；不可读的脚本会静默
       回退到默认。
   * - ``position``
     - ``[-1, -1]``
     - 上次松手后的屏幕坐标 ``(x, y)``。``-1, -1`` 表示
       "使用主屏右下角"。两次会话之间拔掉显示器会用同样
       的方式回退。
   * - ``size_preset``
     - ``"medium"``
     - ``small`` / ``medium`` / ``large`` 之一。
   * - ``opacity``
     - ``1.0``
     - 钳制到 ``[0.1, 1.0]``。越界值重置为默认。
   * - ``click_through``
     - ``false``
     -
   * - ``anchor_locked``
     - ``false``
     -
   * - ``always_on_bottom``
     - ``false``
     - 与永远置顶互斥。
   * - ``hide_on_fullscreen``
     - ``true``
     - 设为 ``false`` 可在全屏时仍保持桌宠可见。
   * - ``snap_threshold``
     - ``24``
     - 钳制到 ``[0, 200]`` px。
   * - ``drivers``
     - 全部 ``false``
     - 按驱动 id 索引的子 dict（``auto_idle``、
       ``idle_motion``、``auto_blink``、``drag_track``、
       ``mic_lipsync``、``webcam_tracking``）。未知 key
       原样 round-trip 以便向前兼容。
   * - ``show_on_launch``
     - ``false``
     - Imervue 启动时自动显示浮层。
   * - ``speech_enabled``
     - ``true``
     - 为 false 时气泡永远不弹。

设置 dict 的合并行为是一层深的：缺少新 key 的旧设置文件加载
后仍会得到一个完整的状态 dict（默认值填空缺）；你已保存的新
key 也能在不认识它们的旧运行时上幸存。

创作新桌宠
^^^^^^^^^^

任何 ``.puppet`` 文件都能作为桌宠角色 — Desktop Pet 标签纯粹
是渲染 + 交互外壳；角色制作在 Puppet 标签里完成（见
*Puppet Workspace (Puppet Tab)*）。

创建自己的桌宠角色：

#. 切到 Puppet 标签，通过 **File > Import PNG…**
   （文件 > 导入 PNG…）或 **File > Import PSD…**
   （文件 > 导入 PSD…）导入画稿，或通过
   **File > Import Cubism…**（文件 > 导入 Cubism…）拉入
   Cubism 模型。
#. 制作 rotation / warp deformer、parameters、motions、
   expressions，以及（可选）绑到身体部位的 hit areas，让 Desktop
   Pet 的左键处理器可以触发动作。
#. 通过 **File > Save As…**（文件 > 另存为…）保存为 ``.puppet``
   zip。
#. 切回 Desktop Pet 标签，通过 **Open Puppet…** 加载新文件。

如果你的角色定义了 ``HitArea``，可以写一个 ``.petscript.json``，
让 ``hit_responses`` 的 key 匹配区域 id，即可为每个命中区域
单独写气泡台词。

疑难排查
^^^^^^^^

**桌宠出现在一个灰色矩形里，而不是完全透明。** OS 级别的半透明
背景属性需要带 alpha 的 GL surface 加上内嵌 GL widget 上的匹配
属性。确认没有第三方窗口管理工具覆盖浮层窗口上的
``WA_TranslucentBackground`` 属性（Linux 上的某些自定义窗口
管理器会这么做）。在 Windows / macOS 上应该 "开箱即用"。

**"Load bundled March 7th" 报告找不到文件。** 解析器先查
``examples_dir()``（打包构建使用的 frozen-safe 位置），再回退
到相对 CWD 的路径。如果两处都没有，状态栏会显示期望路径。
确认随安装一起发布的 ``examples/`` 目录存在 — 源代码 checkout
时请从仓库根目录启动 Imervue。

**点击桌宠没有说话。** 三处检查：

#. 确认 **Speech bubble on click**（点击时弹气泡）开关已开
   （在标签或右键菜单里）。
#. 如果加载了自定义脚本，确认 JSON 能解析 — 加载错误会显示在
   标签的状态栏。
#. 如果点击命中区域什么都没发生，说明该区域既没绑动作，脚本
   里也没有该区域 id 对应的 ``hit_responses`` 条目。要么在
   Puppet 标签里给该区域绑一个动作，要么在脚本的
   ``hit_responses`` 里加上该区域 id。

**摄像头追踪勾选会自动弹回。** Webcam tracking 需要在 Imervue
运行的同一个 Python 环境里装 ``opencv-python`` 与
``mediapipe``。安装命令 ``pip install opencv-python mediapipe``。
装好后再勾选应该会弹出一个显示检测到的人脸 landmark 的小预览
窗口。

**全屏应用时桌宠不自动隐藏。** 全屏检测器以 1 Hz 轮询前台
窗口。Windows 上用 ``GetWindowRect`` Win32 API；macOS / Linux
上没有可靠的跨平台等价物，会 no-op（桌宠保持可见）。在
Windows 上：确认 **Hide when other app is fullscreen**
（其它应用全屏时隐藏）已勾选，并确认全屏窗口确实覆盖了与桌宠
同一显示器的 ≥ 99 %。

**桌宠在两次启动之间漂到屏幕外。** 这发生在下次启动时桌宠
所在的屏幕已经不在连接的显示器里（笔记本脱坞、副屏被拔）。
这种情况下桌宠会自动回退到主屏右下角 — 拖到你想要的位置，
下次保存会覆盖掉过时的坐标。

----

命令行启动
----------

::

   imervue                        # 正常启动
   imervue 图片路径               # 直接打开指定图片
   imervue 文件夹路径             # 直接打开指定文件夹
   imervue --debug                # 启用调试模式
   imervue --software_opengl      # 使用软件渲染（显卡不支持时）

----

MCP 服务器
----------

Imervue 内置一个 `Model Context Protocol <https://modelcontextprotocol.io>`_
服务器，让 AI 助手（Claude Code、Claude Desktop、Cursor、Cline …）
可以直接调用项目的纯逻辑辅助函数，而无需启动 GUI。一行命令启动::

   python -m Imervue.mcp_server

服务器不依赖 Qt，各工具按需懒加载。

可用工具
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - 工具
     - 用途
   * - ``list_images``
     - 列出文件夹内的图片（路径、大小、修改时间）。传
       ``recursive=true`` 可递归遍历子目录。
   * - ``read_image_metadata``
     - 单张图片的尺寸、格式、EXIF、XMP sidecar。缺数据就回对应的
       空值，不会 raise。
   * - ``read_xmp_tags``
     - 仅读 XMP 的快速路径 — 评级、色标、关键字、标题、描述。
   * - ``convert_format``
     - 图片格式转换。目标格式由目标文件的后缀决定（``png`` /
       ``jpg`` / ``jpeg`` / ``webp`` / ``tiff`` / ``bmp``）。
       JPEG/WebP 可选择 ``quality``（1–100）。
   * - ``puppet_from_png``
     - 用 puppet 插件的 auto-mesh 从 PNG 建出 ``.puppet`` 动画文件。
       自动注入 Cubism 标准参数，导入后可直接被驱动。
   * - ``puppet_inspect``
     - 打开 ``.puppet`` 并返回结构化清单：drawables、deformers、
       parameters、motions、expressions、hit areas、parts、
       parameter blends、physics rigs。
   * - ``image_statistics`` / ``quality_metrics`` / ``read_histogram``
     - 每通道均值 / 最小 / 最大 / 标准差 / 中位数、无参考质量指标
       （色彩度、熵、对比度、边缘密度、噪点），以及 256 桶直方图与
       过曝 / 欠曝裁剪比例。
   * - ``sharpness_score`` / ``ocr_text`` / ``image_thumbnail``
     - Laplacian 方差模糊评分、Tesseract OCR 文字（缺失时优雅降级），
       以及有边界限制的 base64 PNG 预览。
   * - ``find_similar``
     - 按感知哈希（汉明阈值）将近重复图片分组。提供进度令牌时会
       逐文件汇报进度。
   * - ``apply_watermark`` / ``apply_frame``
     - 烧入文字水印，或为图片套上衬边 / 拍立得相框（可选说明文字）。
   * - ``build_collage``
     - 将多张图片合成为网格拼贴（可配置列数、单元尺寸、间距、边距、
       背景）。汇报进度。
   * - ``crop_image`` / ``resize_image`` / ``rotate_image``
     - 像素框裁切、保持长宽比的缩放，以及无损 90/180/270 旋转或
       水平 / 垂直翻转。
   * - ``collection_stats``
     - 汇总文件夹的评级、收藏、颜色标签与挑片状态（计数、0–5 星
       分布与平均值）。
   * - ``reverse_geocode`` / ``extract_video_frame``
     - 离线将 GPS 坐标解析到最近的城市，并把一帧视频解码成静态图。

每个工具都会公布 JSON ``outputSchema`` 以及只读 / 破坏性
``annotations``，并在文本信封之外以 ``structuredContent`` 返回结果
（遵循 MCP 2025-11-25），让客户端无需重新解析即可消费类型化载荷。
长时间运行的工具在调用方传入进度令牌时会流式发送
``notifications/progress``。

Prompts（提示词）
^^^^^^^^^^^^^^^^^^

服务器通过 ``prompts/list`` / ``prompts/get`` 公开四个提示词：
``caption_image``、``suggest_edits``、``analyze_composition``
（显著性驱动的构图评析）与 ``flag_issues``（锐度 + 质量 + 裁剪分流）。
提示词参数可通过 ``completion/complete`` 自动补全。

Claude Code（项目级）
^^^^^^^^^^^^^^^^^^^^^

repo 根目录已附项目级 ``.mcp.json``：

.. code-block:: json

   {
     "mcpServers": {
       "imervue": {
         "type": "stdio",
         "command": "python",
         "args": ["-m", "Imervue.mcp_server"]
       }
     }
   }

用 Claude Code 打开 repo 任何子目录都会自动发现这个服务器。
首次使用时 Claude Code 会询问是否启用项目 MCP 服务器，接受即可。

Claude Desktop
^^^^^^^^^^^^^^

把同样那段加进 Claude Desktop 的配置文件：

* macOS：``~/Library/Application Support/Claude/claude_desktop_config.json``
* Windows：``%APPDATA%\Claude\claude_desktop_config.json``

请使用绝对工作目录，或激活装了 Imervue 的 venv —
``python`` 必须能解析到能 ``import Imervue`` 的解释器。

通信协议
^^^^^^^^

服务器走 MCP ``2025-03-26`` 版的 stdio JSON-RPC 2.0:

* ``initialize`` — 握手，广告 ``capabilities.tools``。
* ``tools/list`` — 列出已注册工具与其 JSON-Schema 输入定义。
* ``tools/call`` — 用 ``{"name", "arguments"}`` 调用工具，结果回
  在 ``content`` 数组。
* ``notifications/*`` — 静默接受（不响应）。

实现在 ``Imervue/mcp_server/``：

* ``server.py`` — 协议循环 + 工具注册表
* ``tools.py`` — 各工具的 handler 与默认工具集
* ``__main__.py`` — ``python -m Imervue.mcp_server`` 入口

自定义工具可以直接 :class:`MCPServer` 然后 :meth:`MCPServer.register`，
通过 :meth:`MCPServer.handle_message` 喂消息（或直接调用
:func:`run` 跑 stdio 循环）。
