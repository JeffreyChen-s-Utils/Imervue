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
3. **File > Examples > March 7Th**（或工具栏的 **Examples ▾** 下拉）。内置的 307-drawable Cubism rig 居中加载。
4. 在底部 **Motions** 停靠栏点任一个动作 — rig 立刻动起来。
5. 工具栏的 **Reset to rest** 按钮把 rig 拉回静止姿势。

这是基本款。下面解释怎么把这个 idle rig 变成直播或视频文件。

---

## Part 1 — OBS 直播整合

目标：在 OBS 上有一个 webcam 风窗口显示你的 puppet，被你的脸 / 麦克风 / 鼠标驱动，准备好放进直播。

### 1.1 输入端（什么驱动 rig）

Puppet 工具栏有 5 个实时输入 toggle，可以同时开（彼此不冲突、只要驱动不同参数）。

| Toggle | 驱动 | 可选依赖 |
|---|---|---|
| **Drag-track head** | `ParamAngleX/Y`、`ParamEyeBallX/Y` 跟着鼠标光标 | 无 |
| **Auto-blink** | `ParamEyeLOpen/ROpen` 每 ~4.5 秒眨一次眼 | 无 |
| **Mic lip-sync** | `ParamMouthOpenY` 跟着麦克风 RMS | `sounddevice` |
| **Webcam tracking** | 脸部 landmark 驱动头部 yaw/pitch/roll + 眼 / 嘴开合 | `opencv-python` + `mediapipe` |
| **Auto idle** | 呼吸循环 + 头 / 身体轻微 drift | 无 |
| **Idle motions** | 随机循环播 Idle 组的动作 | 无 |

典型脸部追踪 VTuber 设置：开 **Webcam tracking** + **Auto-blink** + **Mic lip-sync**。打开 *Webcam tracking* 时会弹出预览窗口，显示摄像头画面 + 检测到的 landmark — 用来确认 tracker 真的有看到你。

> **首次使用注意** — webcam tracking 需要 `mediapipe` 的 face-landmark 模型。Imervue 第一次启用会自动下载（~3.7 MB，从 Google Cloud Storage）到 `<app_dir>/models/face_landmarker.task`，之后直接用缓存。

### 1.2 输出端（OBS 怎么看到 rig）

两条路。新手用 **A**，要 pixel-perfect alpha 合成用 **B**。

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

动作结束（或中途暂停）后 rig 会停在最后一个采样姿势。点工具栏 **Reset to rest**（或 **Edit > Reset to rest**）一键归零：

- Motion player 直接停（不走淡出）
- 所有实时输入 toggle 取消勾
- Active expressions 清空
- Pose groups 还原第一个 member
- 参数值还原到 authored defaults

状态栏确认："*Rig reset to neutral pose.*"

---

## Part 2 — 制作动画

目标：磁盘上有一个 `.mp4` / `.webm` / `.gif` / `.png` 文件。

### 2.1 从实时 take 录制动作

最简单的路径：用脸 / 麦克风 / 鼠标驱动 rig、实时录下参数值，Imervue 烘焙成一个之后可以播 / 循环 / 保存的 `Motion`。

1. 打开 rig。
2. 启用想驱动 rig 的实时输入（webcam / drag / blink / lip-sync / idle）。
3. **Output > Record motion** — 工具栏按钮打勾。
4. 表演 — 动脸 / 讲话 / 拖鼠标 — 持续多久都可以。
5. **Record motion** 取消勾。对话框问你动作名称跟可选的组标签（例如 *"wave"*、*"Idle"*）。
6. 新动作出现在 **Motions** 停靠栏。点它播放，或 **File > Save As…** 把它存进 `.puppet` 文件。

录制速率 30 Hz。没变动的轨（整段都不变的参数）自动丢掉，文件大小不会爆。每个保留的轨每个参数变动产生一个 linear segment。

### 2.2 编辑录好的动作

**Motion Timeline** 对话框可以事后微调已录制的动作。

1. Motions 停靠栏右键动作 → **Edit timeline…**（或 double-click）。
2. 对话框每个参数轨一条曲线。Y 轴是参数值范围，X 轴是时间。
3. 点关键点选取。拖曳移动。右键 *delete* / *insert key* / *change segment type*。
4. 支持的 segment 类型：`linear`、`stepped`、`inverse-stepped`、`cubic-bezier`（拖控制点塑形）。
5. 用时间轴 transport（play / loop / scrub）实时预览。

提示：脸部动作自然感的话，`ParamEyeLOpen/ROpen`（眨眼）跟 `ParamMouthOpenY`（说话）用 cubic-bezier 比较好，其他用 linear 就够了。

### 2.3 手动 keyframe 编辑（不录 take）

如果你心里有特定的 keyframe 序列：

1. **Edit > Add Parameter** 加入需要的新参数。
2. **Parameters** 停靠栏拖滑块到 t=0 时的值 → 按 **Set Key**。Imervue 在 t=0 标记当前参数快照。
3. 在 t=1.0、t=2.0… 重复。
4. Recipe 接 Motion Timeline 对话框 — 右键 → **New motion** 从你已 author 的 key 开始建新动作。

跨多参数的姿势，parameter-blends 功能可以把一个输入绑到 N 维 keyframe（例如 `ParamAngleX × ParamAngleY` 控制 2D 网格上的头部方向）。

### 2.4 输出

| 动作 | 输出 |
|---|---|
| **Output > Capture frame…** | 用 `glReadPixels` 存当前 frame 成单张 PNG。适合做缩图 / 静态头像。 |
| **Output > Record…** | 用 `imageio` 把帧序列写成 GIF / WebM / MP4。工具栏按钮是 toggle：开始 → 表演 → 结束 → 写盘。默认 30 fps；codec 从扩展名挑。 |
| **Output > Export all motions…** | 把 rig 里每个动作各别 render 成一个文件（例如 `<motion-name>.mp4`）。适合批量产出反应 clip、idle loop 等。 |

录制用跟推流一样的**角色独立 off-screen render**，所以你不用事后 crop 掉外壳。GIF / WebM / MP4 默认用文档长宽比、长边上限 1080。PNG 单帧保留文档原生尺寸。

### 2.5 动作配音

一个动作可以携带 `sound_path` — 一个 WAV 文件的绝对路径。动作播放时通过 `QSoundEffect` 同步播 WAV。手动在 Motion Timeline 对话框设置，或编辑 `.puppet` zip 内的 `motions/<name>.json`；v1 没有 GUI 设置这个。

如果没装 `PySide6.QtMultimedia`，音频优雅停用，动作的视觉轨仍然会播。

---

## 导入 rig

### 从 PNG

**File > Import PNG…** 对图像跑 `auto_mesh`：

- 三角化时尊重 alpha 通道 — 边缘不会有白边
- 预先设置 Cubism 标准参数目录（`ParamAngleX/Y/Z`、`ParamEyeLOpen/ROpen`、`ParamMouthOpenY`、`ParamBreath` …）
- 产生单一 drawable 的 rig，之后可以分割 / 变形

适合：快速 prototype、单张无分层的角色图。

### 从 PSD

**File > Import PSD…** 把每个 PSD 图层 parse 成独立 drawable。图层名符合 Live2D 惯例（`Head`、`Body`、`HairFront` 等）自动绑到标准 deformer。

适合：美术提供的多图层角色文件。

### 从 Cubism `.moc3`

**File > Import Cubism…** 同时接受 `.moc3` 和对应的 `.model3.json` manifest — 不论选哪个、只要工作区还没开 rig，导入器都会跑完整 sample-and-reconstruct 转换：

1. 通过 Cubism Native SDK 加载 `.moc3`（用户自备 — 把 SDK 解压到 `<cwd>/sdk/` 或设 `CUBISM_CORE_DLL` 环境变量指向 DLL）。直接选 `.moc3` 也可以，只要旁边有同名 `.model3.json`，工作区会自动定位到 manifest。
2. 把每个 Cubism 参数从 min 扫到 max，记录每个 drawable 的形变顶点。
3. 同时抓取参数驱动的 *visibility* 切换 — 比耶 / 捂脸 / 哭等手势切换都能完整保留。
4. 把 `.model3.json` bundle 里既有的 motion / expression / physics / hit-area 全部 fold 进 puppet。

输出：自包含的 `.puppet` zip，不需要附 Cubism SDK 就能散布（SDK 永不打包 — Live2D 的 Free Material License 规定）。

> **叠加到既有 rig**：如果已经开了一个 `.puppet`，此时选 `.model3.json` 会把它的 JSON 部分（motions、expressions、physics、hit areas、display names）叠加上去 — 适合把 Cubism 动作库嫁接到自己手绘的 PSD rig。`.moc3` 路径始终新建文档；要往既有 rig 加动作，请选 `.model3.json` 或单独的 `.motion3.json` / `.exp3.json`。

---

## 进阶功能

### 参数

每个会动的值都是 *parameter*，有 min、max、default。参数带 `keys`（单一值快照），runtime 线性采样。Cubism 标准 id 参考 `Imervue/puppet/standard_params.py`。

### 变形器

- **Rotation** — 锚点 + 角度。子节点继承父节点旋转，所以 body lean 会带着 head + arms 一起动。
- **Warp** — `rows × cols` bezier lattice。用于脸颊挤压、衣服褶皱、头发物理。
- **Vertex morphs** — Cubism 式每 drawable 的 delta 数组，在参数默认值跟极值之间做线性混合。`.moc3` 转换器产生这个。

### Pose groups

互斥的 drawable 可见度。同时只显示组里一个成员；切到别的隐藏其他。用于武器切换、嘴型变体、costume 切换。

### 物理

Verlet pendulum 链用于头发 / 衣物 / 缎带。*输入参数*（例如 `ParamAngleX`）移动链锚点；重力 + 阻尼 + per-particle 弹簧把链拉回静止；尖端横向位移映射回 *输出参数*（例如 `ParamHairFront`）。

从 Bone Tree 停靠栏编辑物理链。

### 表情

参数覆写堆栈，叠在滑块 / 动作值上。模式：`additive`（最终 = base + value）、`multiply`（最终 = base × value）、`overwrite`（最终 = value）。

用于瞬时情绪：*smile*、*surprised*、*angry*。March 7th rig 内置 8 个表情（`捂脸` / `比耶` / `照相` / `脸红` / `黑脸` / `哭` / `流汗` / `星星`）。

### Hit areas

rig 上的命名区域，用户点击内部会发出信号。可绑到动作组（`TapHead → tap_head` 从 `TapHead` 组随机播一个动作），或绑到表情切换（点 body → 切换 `surprised`）。

March 7th rig 有两个 hit area — `head` 触发 `tap_head` 动作、`body` 切换 `surprised` 表情。

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

切到不可用的功能时工具栏 / 状态栏会回报哪个依赖缺。**File > Install dependencies…** 可以一次装齐所有 Python 可选包；Cubism SDK 跟 NDI runtime 因为授权需要手动装。

---

## 键盘快捷键

只列 Puppet 标签特有的。完整快捷键参考 `README.md`。

| 快捷键 | 动作 |
|---|---|
| Canvas 上 **鼠标拖曳** | 平移（drag-track 关掉时） |
| **鼠标滚轮** | 缩放（以光标为中心） |
| Canvas 上 **右键** | 清除 bone 选取 overlay |
| **E** | 切换 Edit Mesh 模式（之后拖顶点编辑 mesh） |
| **B** | 切换 Auto-blink |
| **W** | 切换 Webcam tracking |
| **M** | 切换 Mic lip-sync |
| **D** | 切换 Drag-track |
| **I** | 切换 Auto-idle |
| **Space** | 播放 / 暂停选取的动作 |
| **Esc** | 停止当前动作（淡出） |
| **Ctrl+R** | Reset to rest |

（部分快捷键将来可能变动 — 工具栏按钮才是权威界面。）

---

## 疑难排解

### "Webcam tracking 开了什么都没发生"

预览窗口会弹出显示摄像头画面；如果画面里没有脸，没有参数会被驱动。状态栏显示 *"No face in frame"*。移到镜头前或改善光线。

如果预览是黑的：摄像头被其他 app 占用、或 OS 拒绝了摄像头存取。macOS 首次使用会要求权限 — 检查"系统设置 → 隐私与安全性 → 摄像头"。

### "Auto-blink 只眨了一次"

最近 commit 修了 — blink 改用 force-write 路径、绕过 canvas 的 no-change-skip 优化。更新到最新版。

### "OBS 看到洋红色背景"

设计使然 — 见上面 Path A。在 OBS 的 *Video Capture Device* 源加 Color Key filter、`Custom Color = #FF00FF`。

### "ndi-python 安装失败、找不到 cmake"

`ndi-python` 从源码编。装 CMake、Visual Studio C++ Build Tools、NDI SDK — 见 Path B 前置。不需要 NDI 的话用 Path A。

### "虚拟摄像头画面看起来被拉长"

最近 commit 修了 — 输出改用文档长宽比、纯角色内容。更新到最新版。

### "动作播完 rig 卡在最后一个姿势"

点工具栏 **Reset to rest**。动作停止不会自动倒带 — 停在最后采样值。Reset 给你干净基准。

### Cubism 转换器把相机显示成"多一只手"

March 7th 之类 rig 的比耶 / 拍照 / 捂脸手势是用 Cubism 动态可见度旗标驱动的。最近 commit 教转换器把这些切换存成 `opacity_keys` 曲线。如果你之前用旧版转过 `.moc3`，从 **File > Import Cubism…** 重新转一次，新 `.puppet` 就有正确的手势切换。

---

## 文件格式参考

`.puppet` 是 zip 容器、含 JSON manifest 跟 PNG 纹理。完整规格见 [`Imervue/puppet/FORMAT.md`](Imervue/puppet/FORMAT.md)。

内置 demo rig：[`examples/puppet/march_7th.puppet`](examples/puppet/march_7th.puppet).
