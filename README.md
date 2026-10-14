# hyperframes-video

用 HyperFrames（HTML + GSAP 时间线）把一段脚本做成**可发布的短视频**。

起工程 → lint → 抽帧自检 → 节奏验收 → render 出片 → 发布前置，一条流水线走完。
适用于**知识科普视频、音乐卡点视频、分镜动画**。

这是一个 WorkBuddy / CodeBuddy 技能（skill）包。

---

## 能力

| 环节 | 做什么 |
| --- | --- |
| 起工程 | 一条命令生成工程骨架：宿主 `index.html` + 镜头子组合 + GSAP 本地化 |
| 卡点对拍 | 实测 BPM、生成拍网格，把关键画面钉在高潮拍与收束拍上 |
| 节奏验收 | 自动扫出镜头内的静止段，量化「最长静止时长 / 占比 / 最小帧差」 |
| 抽帧自检 | 按镜位抽帧，提前发现入场过晚、元素出画、文字被压 |
| 出片 | 1080p / 30fps，可流复制去音轨（默认交付无音轨版） |
| 发布前置 | 抖音站内音频抓取、发布参数与注意项 |

## 前置要求

| 项 | 要求 |
| --- | --- |
| 系统 | Windows 10/11（macOS / Linux 路径逻辑兼容，**但未实测**） |
| 运行时 | Node.js 18+、Python 3.9+ |
| 浏览器 | 系统自带的 Edge 或 Chrome（不额外下载 Chromium 内核） |
| 磁盘 | 约 250 MB 放工具链（FFmpeg 占大头），另加成片空间 |

## 安装

### 1. 下载技能包

**请到本仓库的 Releases 页面下载 `hyperframes-video.zip`。**

> **不要**用绿色 `Code` 按钮里的「Download ZIP」。
> GitHub 自动生成的那个包，解出来的顶层目录是 `hyperframes-video-main/`，
> 导入后目录名不规范。Release 附件才是干净的 `hyperframes-video/`。

### 2. 导入 WorkBuddy

**技能面板 →「添加技能」→「上传技能」→ 把 `hyperframes-video.zip` 拖进去。**

手动安装等价操作：解压后，把整个 `hyperframes-video` 目录放进技能目录
（WorkBuddy 通常是 `~/.workbuddy/skills/`）。

### 3. 初始化环境（每台机器只做一次）

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE/.workbuddy/skills/hyperframes-video/scripts/setup-env.ps1"
```

脚本会依次：定位 Node / npm / Python → 建目录 → 安装工具链 → 建三个缓存目录联接 → 跑环境自检。

- 想先预览它要做什么：加 `-DryRun`
- 想把运行数据放到别的盘：加 `-DataRoot "D:/your-data/hyperframes"`

### 4. 验证

```bash
source ~/.workbuddy/skills/hyperframes-video/scripts/hf-env.sh
hf doctor
```

`Node` / `FFmpeg` / `FFprobe` / `Chrome` 四项都是 ✓，即安装成功。

## 怎么用

装好后在 WorkBuddy 里直接说需求，技能会被自动唤起：

> 用 hyperframes 做一条 60 秒的知识科普视频，主题是「课题分离」

也可以显式点名：

> 用 hyperframes-video 技能帮我做一条卡点视频

## 日常命令

```bash
# 每个新终端都要先 source：它导出工具链与目录变量，并定义 hf() 包装
source ~/.workbuddy/skills/hyperframes-video/scripts/hf-env.sh

hf doctor                            # 环境自检
hf lint   "$HF_PROJECTS/my-video"    # 静态校验工程
hf render "$HF_PROJECTS/my-video" --output "$HF_OUTPUT/my-video.mp4"
```

起一个新工程：

```bash
python ~/.workbuddy/skills/hyperframes-video/scripts/init_project.py \
  "$HF_PROJECTS/my-video" --title "我的视频" --duration 71.801 --scenes 10
```

成片出来后做节奏验收：

```bash
python ~/.workbuddy/skills/hyperframes-video/scripts/motion_audit.py \
  "$HF_OUTPUT/my-video.mp4" --ffmpeg "$HF_FFMPEG"
```

去音轨（默认交付形态）：

```bash
"$HF_FFMPEG" -y -i "$HF_OUTPUT/my-video.mp4" -c copy -an "$HF_OUTPUT/my-video_无音轨.mp4"
```

## 运行数据放在哪

**技能实体（代码）与运行数据是分离的**。数据根 `HF_DATA_ROOT` 按顺序解析：

1. 环境变量 `HF_DATA_ROOT`
2. 配置文件 `~/.workbuddy/hyperframes.env`
3. 默认 `~/.workbuddy/hyperframes`

数据根下的四个目录：

```
toolchain/   CLI 与 FFmpeg / FFprobe
projects/    工程
output/      成片
temp/        临时文件与帧解压缓存（渲染期间写入量最大）
```

想换到别的盘，写一个 `~/.workbuddy/hyperframes.env`：

```
HF_DATA_ROOT="D:/your-data/hyperframes"
```

## 目录结构

```
hyperframes-video/
├── SKILL.md                     技能主文档（WorkBuddy 读取入口）
├── INSTALL.md                   安装与排错手册
├── references/
│   ├── env-setup.md             环境适配（Windows 实测）
│   ├── project-contract.md      工程契约（宿主 + 子组合写法）
│   ├── beat-sync.md             卡点对拍（BPM / 拍网格）
│   ├── rhythm-motion.md         节奏与动效（消除静止段）
│   ├── feed-safe-layout.md      信息流观感（遮挡与边缘对比）
│   └── publish-douyin.md        抖音发布前置
├── scripts/
│   ├── hf-env.sh                环境变量与 hf() 包装（必须 source）
│   ├── setup-env.ps1            一键初始化（Windows）
│   ├── redirect-data.ps1        把缓存目录联接到数据根
│   ├── init_project.py          生成工程骨架
│   ├── bpm_grid.py              实测 BPM 并生成拍网格
│   ├── motion_audit.py          节奏验收（静止段检测）
│   └── grab_douyin_audio.py     抓抖音站内音频
└── assets/project-template/     工程模板
```

## 遇到问题

见 [INSTALL.md](INSTALL.md) 的**报错对照表**：13 条实测症状 → 处置，覆盖 npm `EBUSY`、
`FFmpeg not found`、系统盘被写满、`.ps1` 编码、应用商店假 Python、目录联接失效、
渲染无声等。

## 许可

[MIT](LICENSE)
