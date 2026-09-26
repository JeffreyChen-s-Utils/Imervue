# Puppet 指南 — 直播与动画制作

从"我想做 VTuber 风直播或短动画"走到"我已经在 OBS 上直播 / 我手上有一个 MP4 文件"的完整流程，用 Imervue 的 **Puppet** 标签完成。

两条路：

1. **直播** — 用鼠标 / 麦克风 / 摄像头驱动 puppet rig，把结果送进 OBS 推流或录制。
2. **动画制作** — 录一段 take、编辑动作时间轴、输出 GIF / MP4 / WebM。

两者共用同一个 rig 跟参数系统，差别只在输出端是直播虚拟镜头还是磁盘上的文件。

---

## 目录

- [快速开始](#快速开始)
- [Part 1 — OBS 直播整合](#part-1--obs-直播整合)
- [Part 2 — 制作动画](#part-2--制作动画)
- [导入 rig](#导入-rig)
- [进阶功能](#进阶功能)
- [可选依赖](#可选依赖)
- [键盘快捷键](#键盘快捷键)
- [疑难排解](#疑难排解)

---

## 快速开始

1. 启动 Imervue（从源码跑就 `python -m Imervue`）。
2. 点窗口顶端的 **Puppet** 标签。
3. **File > Examples > March 7th**（或工具栏的 **Examples ▾** 下拉）。内置的 307-drawable Cubism rig 居中加载。
4. 在底部 **Motions** 停靠栏点任一个动作 — rig 立刻动起来。
5. 工具栏的 **Reset to rest** 按钮把 rig 拉回静止姿势。

这是基本款。下面解释怎么把这个 idle rig 变成直播或视频文件。

---

## Part 1 — OBS 直播整合

目标：在 OBS 上有一个 webcam 风窗口显示你的 puppet，被你的脸 / 麦克风 / 鼠标驱动，准备好放进直播。

### 1.1 输入端（什么驱动 rig）

Puppet 工具栏有 6 个实时输入 toggle（**Live** 菜单里也有同样 6 个），可以同时开（彼此不冲突、只要驱动不同参数）。

| Toggle | 驱动 | 可选依赖 |
|---|---|---|
| **Drag-track head** | `ParamAngleX/Y`、`ParamEyeBallX/Y` 跟着在 canvas 上移动的鼠标光标 | 无 |
| **Auto-blink** | `ParamEyeLOpen/ROpen` 每 ~4.5 秒眨一次眼 | 无 |
| **Mic lip-sync** | `ParamMouthOpenY` 跟着麦克风音量、`ParamMouthForm` 跟着元音音色 | `sounddevice` |
| **Webcam tracking** | 脸部 landmark 驱动头部 yaw/pitch/roll、眼睛开合、视线与嘴巴开合 | `opencv-python` + `mediapipe` |
| **Auto idle** | 呼吸循环 + 头 / 身体轻微 drift | 无 |
| **Idle motions** | 每 8 秒从 `Idle` 组随机播一个动作 | 无 |

典型脸部追踪 VTuber 设置：开 **Webcam tracking** + **Auto-blink** + **Mic lip-sync**。打开 *Webcam tracking* 时会弹出预览窗口，显示摄像头画面 + 检测到的 landmark — 用来确认 tracker 真的有看到你。

> **首次使用注意** — webcam tracking 需要 `mediapipe` 的 face-landmark 模型。Imervue 第一次启用会自动下载（~3.7 MB，从 Google Cloud Storage）到 `<app_dir>/models/face_landmarker.task`，之后直接用缓存。

**Output > VTS API** 是另一种输入：它在 `ws://127.0.0.1:8001`（仅限本机）开一个精简版 VTube Studio Public API 服务器，支持该协议的面部追踪程序连上后，可以列出 rig 的参数并写入数值。服务器会自动发放并接受 token。

### 1.2 输出端（OBS 怎么看到 rig）

三条路。新手用 **A**，要 pixel-perfect alpha 合成用 **B**；**C** 完全不用设置。

#### Path A — Virtual Camera

Puppet canvas 变成 OBS"视频捕获设备"源列表里的一台 webcam。

```bash
pip install pyvirtualcam
```

加上平台对应的虚拟摄像头驱动：

- **Windows**：装 OBS Studio 26+，自带 *OBS Virtual Camera* 驱动。第一次打开 OBS、右下角点 **Start Virtual Camera** 注册驱动，之后 `pyvirtualcam` 才找得到。
- **macOS**：OBS for Mac 自带 system extension，首次运行会要求在"系统设置 → 隐私与安全性"启用。
- **Linux**：`sudo apt install v4l2loopback-dkms` 然后 `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"`。

接线：

1. Puppet 标签打开 rig，工具栏 / **Output > Virtual camera** 打勾。状态栏会告诉你实际设备名（通常是 *OBS Virtual Camera*）。
2. OBS：**Sources > + > Video Capture Device**，下拉选步骤 1 打印的设备名。

**为什么背景是洋红色？**

虚拟摄像头走 DirectShow / AVFoundation / v4l2loopback，三个传输层**只有 RGB、没有 alpha 通道**。OBS 把进来的图像当不透明 RGB 处理，所以 Imervue 在角色以外填什么颜色，OBS 就显示什么颜色。挑 `#FF00FF` 是业界标准 chroma-key 色 — 几乎不会出现在自然肤色 / 发色 / 瞳色里，去背容差可以开很宽。

**OBS 端去背：**

1. *Video Capture Device* 源右键 → **Filters**
2. **Effect Filters → + → Color Key**
3. 设置：
   - **Key Color Type**：`Custom Color`
   - **Custom Color**：HEX `FF00FF`
   - **Similarity**：从 `80` 起跳，边缘有残留洋红色就拉到 `200–300`
   - **Smoothness**：`30–50`，边缘不会太硬
4. 关闭对话框 — 滤镜会跟着源，之后重启虚拟摄像头都自动套用

#### Path B — NDI（专业、真实 alpha）

NDI 在 LAN 上以 < 50 ms 延迟传 RGBA。不用色键 — alpha 通道整条传过去。

```bash
pip install ndi-python
```

加上：

1. 从 <https://ndi.video/tools/> 下载 **NDI Tools** — installer 包含 runtime DLL，`ndi-python` 会 link 进去。
2. OBS 端装 **obs-ndi** 插件：<https://github.com/obs-ndi/obs-ndi/releases>

接线：

1. Puppet 标签工具栏 / **Output > NDI output** 打勾。状态栏显示源名（默认 *Imervue Puppet*）。
2. OBS：**Sources > + > NDI Source**，下拉选步骤 1 的源名。

角色直接合成到 OBS 场景，零色键滤镜。Off-screen render 把角色外的区域填成完全透明。

**`ndi-python` Windows 编译前置**

`ndi-python` 只 ship source distribution，pip 拿到后从 C++ 编。Windows 上要：

- **Visual Studio Build Tools 2022** 勾"**使用 C++ 的桌面开发**"工作负载
- **CMake**（安装时勾 *Add to system PATH*）
- **NDI SDK**（跟 NDI Tools 不同，去 <https://ndi.video/for-developers/ndi-sdk/> 拿）装在默认 `C:\Program Files\NDI\NDI 6 SDK\`
- 环境变量 `NDI_SDK_DIR` 指向 SDK 安装路径

嫌麻烦就走 Path A。

#### Path C — Window Capture（零安装）

OBS **Sources > + > Window Capture** 可以直接抓 Imervue 窗口。没有虚拟摄像头驱动、没有 SDK。Trade-off：

- 抓整个 Imervue 窗口（含外壳），要加 OBS *Crop/Pad* filter 裁到只剩 puppet 区。
- Puppet 工作区的棋盘格背景也会跟着推。
- 受 Imervue 窗口大小限制。

只适合临时 demo。要正式直播用 A 或 B。

### 1.3 角色独立渲染路径

Virtual Camera 与 NDI 都用 off-screen framebuffer 重画，**不含棋盘格背景跟任何编辑器外壳**。Imervue 窗口里的工具栏 / 停靠栏 / 状态栏纯粹是给你编辑用的，推流只有角色 drawable 本身。输出长边上限 1080 px（避免 3503×7777 的 Cubism canvas 把 DirectShow 驱动搞挂）。

### 1.4 两段 take 之间重置

**Loop** 关闭时动作会停在最后一帧，**Pause** 会停在当前姿势，实时输入也会把参数留在最后写入的值。点工具栏 **Reset to rest**（或 **Edit > Reset to rest**）一键归零：

- Motion player 直接停（不走淡出）
- 所有实时输入 toggle 取消勾，**Record motion** 也会停止（录到的 take 会保留）
- Active expressions 清空
- Pose groups 还原第一个 member
- 物理链弹回静止姿势
- 参数值还原到 authored defaults

状态栏确认："*Rig reset to neutral pose.*"

---

## Part 2 — 制作动画

目标：磁盘上有一个 `.mp4` / `.webm` / `.gif` / `.png` 文件。

### 2.1 从实时 take 录制动作

最简单的路径：用脸 / 麦克风 / 鼠标驱动 rig、实时录下参数值，Imervue 烘焙成一个之后可以播 / 循环 / 保存的 `Motion`。

1. 打开 rig。
2. 启用想驱动 rig 的实时输入（webcam / drag / blink / lip-sync / idle），或准备自己拖 **Parameters** 停靠栏的滑块。
3. **Output > Record motion**。对话框问你动作名称（默认 `user_motion`），确认后开始录制。
4. 表演 — 动脸 / 讲话 / 移动鼠标 — 持续多久都可以。
5. 再选一次 **Output > Record motion** 停止录制。
6. 新动作出现在 **Motions** 停靠栏（与已有动作同名的 take 会替换它）。加入动作会重新加载 rig，参数、表情和物理都回到默认值。点它播放，或 **File > Save As…** 把它存进 `.puppet` 文件。

录制速率 30 Hz。没变动的轨（整段都不变的参数）自动丢掉。每个保留的轨在每两个相邻采样之间产生一个 linear segment。录制器读取的是参数本身的值（滑块、动作、实时输入），所以表情叠加和物理输出不会录进 take。录出来的动作不属于任何组。

### 2.2 编辑录好的动作

**Motion Timeline** 对话框可以事后微调动作的关键点。

1. 在 **Motions** 停靠栏点击动作让播放器载入它，再选 **Edit > Edit motion…**。
2. 从 **Track** 列表选一个参数。图表显示该轨的关键点：X 轴是动作时长内的时间，Y 轴固定为 −1 到 1。
3. 拖动黄色的点来移动关键点的时间和数值。`cubic-bezier` segment 可以拖动紫色控制手柄来塑形。每个 segment 都画成两个关键点之间的直线。
4. 对话框不能新增或删除关键点，也不能改 segment 类型；四种类型（`linear`、`stepped`、`inverse-stepped`、`cubic-bezier`）来自动作文件本身。
5. 每次拖动都会更新内存中的动作，并把 canvas 重新摆到播放器当前的时间点。**File > Save As…** 才会把修改写进 `.puppet` 文件。

### 2.3 手动 keyframe 编辑（不录 take）

Puppet 标签没有用来新建动作的 keyframe 编辑器。不靠实时表演也想做出动作：

1. 打开 **Output > Record motion**，自己拖 **Parameters** 停靠栏的滑块 — 滑块变化和其他实时输入一样会被录下。
2. 停止录制，再用 **Edit > Edit motion…** 调整关键点（见 2.2）。
3. 要精确的 keyframe，就直接手写 `.puppet` zip 里的 `motions/<name>.json`，并把名称加进 `puppet.json` 的 `motions`（见 [`FORMAT.md`](Imervue/puppet/FORMAT.md)）。

每个滑块旁的 **Set key** 按钮是绑骨用的工具，不是动作 keyframe：它把每个变形器当前的 form 存成该参数在滑块当前值的 key。**Edit > Add Parameter** 会新增一个 `ParamN` 滑块（−1 到 1）供你打 key。

Parameter blends — 在两个以上参数构成的网格上给变形器 form 打 key，例如用 `ParamAngleX × ParamAngleY` 在 2D 网格上控制头部方向 — 从 `puppet.json` 的 `parameter_blends` 读取；Puppet 标签没有编辑它的界面。

### 2.4 输出

| 动作 | 输出 |
|---|---|
| **Output > Capture frame…** | 把当前 frame 存成透明背景的单张 PNG。适合做缩图 / 静态头像。 |
| **Output > Record…** | 先选 GIF / WebM / MP4 文件，接着用 `imageio` 以 30 fps 写入帧，直到你再次切换关闭；codec 由扩展名决定。工具栏按钮就是同一个 toggle。 |
| **Output > Export all motions…** | 选文件夹和容器格式（`.mp4`、`.gif` 或 `.webm`）；每个动作从头播放并录满它的时长，存成 `<motion-name>.<ext>`。适合批量产出反应 clip、idle loop 等。 |

录制用跟推流一样的**角色独立 off-screen render**，所以你不用事后 crop 掉外壳。GIF / WebM / MP4 的帧按文档长宽比缩进长边 1080 px，背景为白色（这些格式不带 alpha），每边取 16 的倍数。PNG 截取保留文档尺寸，长边上限 4096 px。

### 2.5 动作配音

一个动作可以携带 `sound_path` — 一个 WAV 文件的绝对路径。动作开始播放时通过 `QSoundEffect` 播一次 WAV；**Pause** 和 **Stop** 会停止声音。把 Cubism `.model3.json` 叠加到已打开的 rig（见*导入 rig*）时，会从动作条目的 `Sound` 字段填入；其他动作要编辑 `.puppet` zip 内的 `motions/<name>.json` — Puppet 标签没有设置它的字段。WAV 文件本身不会存进 `.puppet`，文件不存在时直接跳过。

如果没装 `PySide6.QtMultimedia`，音频优雅停用，动作的视觉轨仍然会播。

---

## 导入 rig

### 从 PNG

**File > Import PNG…** 先询问网格的格子大小（默认 64 px；越小网格越密），再对图像跑 `auto_mesh`：

- 用正方形格子铺满图像，完全透明的格子全部丢掉
- 预先设置 Cubism 标准参数目录（`ParamAngleX/Y/Z`、`ParamEyeLOpen/ROpen`、`ParamMouthOpenY`、`ParamBreath` …）
- 产生单一 drawable、还没有变形器的 rig — 从 **Edit** 菜单加入变形器

适合：快速 prototype、单张无分层的角色图。

### 从 PSD

**File > Import PSD…** 把每个可见、非空的图层变成独立 drawable — 一个裁到图层不透明范围的四边形，按图层顺序叠放 — 每个图层组变成一个 Part。接着预先设置标准参数目录，再按图层名称自动绑骨：

- 名称含左右和开闭状态的眼睛图层（`eye_l_open`、`EyeRClose` …）跟着 `ParamEyeLOpen` / `ParamEyeROpen` 淡入淡出，所以 Auto-blink 会切换它们
- 嘴巴图层（`mouth_open`、`mouth_close`、`mouth_a` … `mouth_o`）跟着 `ParamMouthOpenY` 和 `ParamMouthForm` 淡入淡出，所以 Mic lip-sync 会切换它们
- `head` / `face` 图层共用一个以 `ParamAngleZ` 打 key（±15°）的旋转变形器
- `hair` / `bang` / `fringe` 图层共用一个 warp 变形器，外加一条从 `ParamAngleX` 到 `ParamHairFront` 的物理链；warp 目前在 `ParamHairFront` 上还没有 key

其他图层（身体、手臂、衣服）不会加任何变形器。

适合：美术提供的多图层角色文件。

### 从 Cubism `.moc3`

**File > Import Cubism…** 会先显示导入模式说明（勾选 *Don't show this again* 以后就跳过）。它同时接受 `.moc3` 和对应的 `.model3.json` manifest — 不论选哪个、只要工作区还没开 rig，导入器都会跑完整 sample-and-reconstruct 转换：

1. 通过 Cubism Native SDK 加载 `.moc3`（用户自备 — 把 SDK 解压到 `<cwd>/sdk/` 或设 `CUBISM_CORE_DLL` 环境变量指向 DLL）。直接选 `.moc3` 也可以，只要旁边有同名 `.model3.json`，工作区会自动定位到 manifest。
2. 把每个 Cubism 参数从 min 扫到 max，记录每个 drawable 的形变顶点。
3. 同时抓取参数驱动的 *visibility* 切换 — 比耶 / 捂脸 / 哭等手势切换都能完整保留。
4. 把 `.model3.json` bundle 里既有的 motion / expression / physics / hit-area / display-name 全部 fold 进 puppet。bundle 的 `motions/` 文件夹里、manifest 没列到的动作会归入 `Idle` 组。

转换好的 rig 会在 canvas 上打开；用 **File > Save As…** 写成自包含的 `.puppet` zip，不需要附 Cubism SDK 就能散布（SDK 永不打包 — Live2D 的 Free Material License 规定）。

> **叠加到既有 rig**：如果已经开了一个 `.puppet`，此时选 `.model3.json` 会把它的 JSON 部分叠加到当前文档上：名称或 id 还不存在的 motions、expressions、physics、hit areas、pose groups，再加上 display names — 适合把 Cubism 动作库嫁接到自己手绘的 PSD rig。`.moc3` 路径始终新建文档；要往既有 rig 加动作，请选 `.model3.json` 或单独的 `.motion3.json` / `.exp3.json` / `.physics3.json` / `.pose3.json` / `.cdi3.json`。

---

## 进阶功能

### 参数

每个会动的值都是 *parameter*，有 min、max、default。参数的每个 `key` 存的是某个参数值下的变形器 form；runtime 在当前值两侧的两个 key 之间线性插值，超出首尾就保持端点 key。Cubism 标准 id 参考 `Imervue/puppet/standard_params.py`。

### 变形器

- **Rotation** — 锚点 + 角度，作用于变形器自己 `drawables` 列表里的 drawable。`parent` 只决定顺序：父节点先于子节点执行，但父节点的旋转只移动它自己列出的 drawable，子节点的锚点也不会跟着父节点动。要让 body lean 带着 head + arms 一起动，就把它们也列进身体的变形器。
- **Warp** — 覆盖在 `bounds` 矩形上的 `rows × cols` 双线性网格；范围内的顶点跟着网格走，范围外的不动。用于脸颊挤压、衣服褶皱、头发摆动。
- **Bone rotation** — `bone_rotation` 变形器（骨骼 id + 锚点 + 角度）给带有 `bone_weights` 的 drawable 做蒙皮：每个顶点按权重混合各骨骼的旋转。骨骼之间同样不会继承旋转。
- **Vertex morphs** — Cubism 式每 drawable 的 delta 数组，在参数默认值跟极值之间做线性混合。`.moc3` 转换器产生这个。

### Pose groups

互斥的 drawable 可见度。同时只显示组里一个成员：在 **Pose** 停靠栏挑要显示的成员，其他成员隐藏。用于武器切换、嘴型变体、costume 切换。默认显示组里的第一个成员；成员本身的 `visible` 标志不起作用。

### 物理

Verlet pendulum 链用于头发 / 衣物 / 缎带。*输入参数*（例如 `ParamAngleX`）让链锚点横向移动；重力 + 阻尼 + per-particle 弹簧把链拉回静止；尖端横向位移映射回 *输出参数*（例如 `ParamHairFront`），限制在 −1…1。静止时输出等于输入，所以输入一变化，链就会延迟跟上并甩过头，看起来就是摆动。

Puppet 标签显示中且 rig 有物理链时，canvas 用自己的时钟每秒推进约 60 次，所以输入停下后链还会继续摆。物理链的输出会覆盖滑块、动作或表情在该参数上的值。**Reset to rest** 会把所有链弹回静止。

物理链来自 Cubism 导入（`.physics3.json`）、PSD 自动绑骨的头发规则，或 `.puppet` 文件里的 `physics.json`；Puppet 标签没有物理编辑器。

### 表情

参数覆写堆栈，叠在滑块 / 动作值上。模式：`additive`（最终 = base + value）、`multiply`（最终 = base × value）、`overwrite`（最终 = value）。从 **Expressions** 停靠栏切换；启用中的表情按开启顺序应用。

用于瞬时情绪：*smile*、*surprised*、*angry*。March 7th rig 内置 8 个表情（`捂脸` / `比耶` / `照相` / `脸红` / `黑脸` / `哭` / `流汗` / `星星`）。

### Hit areas

命名的点击区域。hit area 的范围是它所列 drawable 在当前（已变形）位置的外框；在范围内按左键（**Edit mesh** 关闭时）会执行它的动作。它的 `motion` 指定动作组 — 从该组随机播一个动作（`TapHead` 会挑一个 `TapHead` 动作）；没有动作属于该组时，会在 **Motions** 停靠栏选中同名动作并停住，等你按 **Play**。它的 `expression` 会切换该表情（点 body → 切换 `surprised`）。范围重叠时，含最前面 drawable 的那个胜出。

内置的 March 7th rig 没有定义任何 hit area，点击它不会有反应。用 **File > Import Cubism…** 转换的 rig 会带入模型的 `HitAreas`，但只有范围、没有动作；在 `puppet.json` 的 `hit_areas` 列表里给它们加上 `motion` 或 `expression` 才会有反应。Puppet 标签没有 hit area 编辑器。

---

## 可选依赖

Puppet 标签的核心（渲染、参数系统、动作播放、PNG / PSD / Cubism 导入）跑在默认 `requirements.txt` 上。更重的依赖用 `try / except` 包起来，缺了也不会坏其他功能。

| 功能 | 可选依赖 | 安装 |
|---|---|---|
| Webcam 脸部追踪 | `opencv-python` + `mediapipe` | `pip install opencv-python mediapipe` |
| 麦克风对嘴 | `sounddevice` | `pip install sounddevice` |
| 虚拟摄像头输出 | `pyvirtualcam` + 平台驱动 | `pip install pyvirtualcam`，见上面 Path A |
| NDI 输出 | `ndi-python` + NDI runtime + NDI SDK（编译时用） | 见上面 Path B |
| Cubism `.moc3` 导入 | 用户自备 Cubism Native SDK DLL | <https://www.live2d.com/sdk/about/> |
| 动作音频播放 | `PySide6.QtMultimedia` | 通常跟着 PySide6；缺的话从平台的 QtMultimedia 包补 |

切换一个缺少 Python 包的功能时，会打开该包的安装程序，装好后自动开启功能。包已安装但设备或 runtime 失败（没有麦克风、没有虚拟摄像头驱动、没有 NDI runtime）时，toggle 会自动取消勾，状态栏会说明原因。**File > Install dependencies…** 可以一次装齐所有 Python 可选包；Cubism SDK 跟 NDI runtime 因为授权需要手动装。

---

## 键盘快捷键

Puppet 标签没有自己的键盘快捷键 — 所有命令都在它的菜单和工具栏上。Canvas 接受这些鼠标操作：

| 操作 | 动作 |
|---|---|
| **中键拖动** | 平移 |
| **鼠标滚轮** | 缩放（以光标为中心）；**Tools > Fit to Window** 重新适应窗口 |
| **左键** | 触发光标下的 hit area；**Edit mesh** 开启时改为抓住光标 8 px 内的顶点（最前面的 drawable 优先）拖动 |
| **右键** | 清除 bone 选取 overlay |

---

## 疑难排解

### "Webcam tracking 开了什么都没发生"

预览窗口会弹出显示摄像头画面；如果画面里没有脸，没有参数会被驱动。预览窗口的状态栏显示 *"No face in frame"*。移到镜头前或改善光线。

如果预览是黑的：摄像头被其他 app 占用、或 OS 拒绝了摄像头存取。macOS 首次使用会要求权限 — 检查"系统设置 → 隐私与安全性 → 摄像头"。

### "OBS 看到洋红色背景"

设计使然 — 见上面 Path A。在 OBS 的 *Video Capture Device* 源加 Color Key filter、`Custom Color = #FF00FF`。

### "ndi-python 安装失败、找不到 cmake"

`ndi-python` 从源码编。装 CMake、Visual Studio C++ Build Tools、NDI SDK — 见 Path B 前置。不需要 NDI 的话用 Path A。

### "动作播完 rig 卡在最后一个姿势"

Motions 停靠栏的 **Loop** 关闭时，播到结尾的动作会停在最后一帧，**Pause** 也会停在当前姿势。**Stop** 会按动作的淡出时间（动作没设置时为 0.5 秒）把动作的参数缓缓带回默认值。工具栏的 **Reset to rest** 一次把所有参数、表情、pose group 和物理链还原。

### Cubism 转换器把相机显示成"多一只手"

March 7th 之类 rig 的比耶 / 拍照 / 捂脸手势是用 Cubism 动态可见度旗标驱动的。转换器把这些切换存成 `opacity_keys` 曲线，所以每个道具只在对应参数拉起时出现。如果转换出来的 `.puppet` 一直显示这些道具，说明它的 drawable 缺少这些曲线 — 从 **File > Import Cubism…** 重新转换并保存结果。

---

## 文件格式参考

`.puppet` 是 zip 容器、含 JSON manifest 跟 PNG 纹理。完整规格见 [`Imervue/puppet/FORMAT.md`](Imervue/puppet/FORMAT.md)。

内置 demo rig：[`examples/puppet/march_7th.puppet`](examples/puppet/march_7th.puppet) 与 [`examples/puppet/vivian.puppet`](examples/puppet/vivian.puppet)（见 [`examples/puppet/README.md`](examples/puppet/README.md)）。
