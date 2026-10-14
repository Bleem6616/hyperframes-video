---
name: hyperframes-video
description: |
  用 HyperFrames（HTML + GSAP 时间线）制作可发布的短视频全流程：起工程 → lint → 抽帧自检 → 节奏验收 → render 出片 → 发布前置。
  含音乐卡点对拍（实测 BPM / 拍网格 / 高潮对齐）、镜头内静止段消除、信息流观感（右栏遮挡与边缘对比）、环境适配（Windows 实测）、抖音抓音频与发布参数。
  当用户要求做短视频 / 卡点视频 / 知识科普视频 / 分镜动画，或提到 hyperframes、GSAP 时间轴、渲染出片、视频卡点、抖音发布时使用。
description_en: |
  End-to-end workflow for producing publishable short videos with HyperFrames (HTML + GSAP timelines): project scaffold, lint, frame-by-frame self-check, rhythm acceptance test, render, and Douyin publish prerequisites — including measured-BPM beat sync, eliminating static stretches, local environment setup, and audio capture.
agent_created: true
---

# HyperFrames 短视频制作流水线

把"一句话需求"做成"能发布的 MP4"。核心不是写出好看的 HTML，而是**节奏可控、可验证、不返工**。

上游参考：HeyGen 开源框架 HyperFrames（Apache-2.0）；第三方技能包 `dy-hashiqi/hyperframes-vibe-169`（原 `VibeDS-skill`）。本 skill 自包含，不依赖上游仓库。

## 安装与存储布局

**首次使用先初始化环境**（约 250 MB，只在第一次做）：

```bash
# Windows
powershell -ExecutionPolicy Bypass -File "<skill目录>/scripts/setup-env.ps1"
```

脚本会自动找 Node/npm/Python（优先用 WorkBuddy 自带的，不要求系统另装）、建数据目录、装工具链、把 CLI 缓存目录指到数据根、最后跑 `doctor` 自检。完整说明与报错对照见 `INSTALL.md`。

| 内容 | 位置 | 说明 |
|---|---|---|
| 技能实体（本目录） | `~/.workbuddy/skills/hyperframes-video/`（Windows: `C:\Users\<你>\.workbuddy\skills\…`） | **只有这里才会被自动识别** |
| 数据根 `HF_DATA_ROOT` | 默认 `~/.workbuddy/hyperframes/` | 工具链 / 工程 / 成片 / 临时全在它下面；想放别的盘就设这个变量（见下） |
| ├ 工具链 | `$HF_DATA_ROOT/toolchain/` | CLI + FFmpeg/FFprobe，约 257 MB |
| ├ 工程 | `$HF_DATA_ROOT/projects/<slug>/` | 每个片子一个目录 |
| ├ 成片 | `$HF_DATA_ROOT/output/` | render 的 `--output` 指这里 |
| └ 临时 / 帧缓存 | `$HF_DATA_ROOT/temp/` | 渲染期间最大的数据来源 |
| CLI 自建缓存与状态 | `$HF_DATA_ROOT/home/`（可选） | CLI 只按 `os.homedir()` 拼路径、无环境变量开关，要挪盘就用目录联接 |

**换盘 / 换目录**：数据根解析顺序是 ① `$HF_DATA_ROOT` 环境变量 → ② 配置文件 `~/.workbuddy/hyperframes.env`（内容一行 `HF_DATA_ROOT="E:/hf"`）→ ③ 默认 `~/.workbuddy/hyperframes`。**建议用 ②**：技能包升级不会覆盖它，也不必改 `PATH`。若数据根不在默认位置，`setup-env.ps1` 会自动把 `~/.cache/hyperframes`、`~/.hyperframes`、`~/.local/state/hyperframes` 三个目录用联接指过去。

**动手前第一件事**（每次新 shell）：

```bash
source <skill目录>/scripts/hf-env.sh    # 设好工具链/工程/成片/临时目录与浏览器路径
hf lint  "$HF_PROJECTS/<slug>"          # 用 hf 包装函数执行 CLI，勿直接调 hyperframes
```

- `hf` 会先 `cd` 到工具链目录再执行——**实测 CLI 靠"当前工作目录下的 node_modules"找 FFmpeg，离开工具链目录就报 `FFmpeg not found`**。
- 三个临时目录变量必须一起设：Node 读 `TMP`、Python 读 `TMPDIR`、Win32 API 读 `TMP`，只设 `TEMP` 或只设 `TMP` 都会漏。
- 浏览器：`hf-env.sh` 自动找系统里的 Edge / Chrome（省掉下载整个 Chromium）；找不到就用 `HF_BROWSER` 显式指定。
- 技能实体**永远不要**用目录联接挂别处：实测 Node 的 `readdirSync(withFileTypes)` 会把目录联接报成 `isSymbolicLink=true / isDirectory=false`，按目录过滤的扫描器会整个漏掉这个 skill。数据目录反过来——那里只做文件读写，联接完全透明，所以可以用。

**平台支持**：本技能在 **Windows + Git Bash** 上实测通过（CLI/FFmpeg/Edge 路线）。macOS / Linux 的路径逻辑已在 `hf-env.sh` 里写了分支，但**未在真机验证过**；换平台请先跑 `hf doctor` 确认。

下文 `scripts/xxx.py` 均指本 skill 目录下的脚本，用 Python 3.8+ 运行，**纯标准库、无第三方依赖**（仅 `grab_douyin_audio.py` 需 playwright）。

## 六阶段流程（顺序不可颠倒）

| 阶段 | 动作 | 产出 | 参考 |
|---|---|---|---|
| 0 环境 | 装 CLI、备 FFmpeg/浏览器、验 `doctor` | 可跑通的 CLI | `references/env-setup.md` |
| 1 定节奏 | 有 BGM → 实测 BPM / 拍网格 / 高潮点；无 BGM → 按段落定镜长 | `beats.json` | `references/beat-sync.md` |
| 2 写工程 | 宿主 `index.html` + `compositions/scene-*.html` | 工程目录 | `references/project-contract.md` |
| 3 校验 | `lint` 0 error → `render` 低清样片 → 抽帧目检 | 通过 | `references/project-contract.md` |
| 4 节奏验收 | 帧差检测静止段，不达标就改再测 | 达标报告 | `references/rhythm-motion.md` |
| 5 出片 | 正式 render（码率/分辨率）→ 流复制去音轨 | 无音轨 MP4（默认交付） | 本文"出片参数" |
| 6 发布 | 画幅、合规标注、BGM 版权、话题 | 发布清单 | `references/publish-douyin.md` |

**阶段 1 与 4 是这条流水线的价值所在**——它们把"感觉节奏不对"变成可测的数字。跳过它们必然返工。

## 阶段 0：环境（装一次即常驻，仅在换机或工具链被清掉时才需重做）

```bash
source <skill目录>/scripts/hf-env.sh    # 一切的前置
hf doctor                               # 期望：Node ✓ FFmpeg ✓ FFprobe ✓ Chrome ✓
```

工具链装在数据根下（`$HF_DATA_ROOT/toolchain`），装一次即常驻，无需重复安装。重装或换机直接跑 `scripts/setup-env.ps1`（Windows，幂等）；也可以手工按 `references/env-setup.md` 的步骤来：

```bash
# 部分 Windows 环境 spawnSync 报 EBUSY，必须 --ignore-scripts，否则 esbuild postinstall 失败
cd "$HF_TOOLCHAIN" && npm install hyperframes --ignore-scripts
npm install @ffmpeg-installer/win32-x64 @ffprobe-installer/win32-x64 --ignore-scripts
```

数据根的位置、挪盘机制与校验方法见 `references/env-setup.md` 第八节。

## 阶段 2：写工程的四条铁律 + 一条观感倾向

1. **GSAP 必须本地化**：`vendor/gsap.min.js`，宿主用 `/vendor/gsap.min.js` 引用。国内网络环境常连不上 jsdelivr（`ERR_CONNECTION_RESET`），用 CDN 会让渲染在正确性检查处被 `sub_timeline_script_failure` 拦下。
2. **每镜自带贯穿动效**（背景光晕大幅缓移 + 整幅持续推近），不要依赖"入场动效做完→静止等待"。见 `references/rhythm-motion.md`。
3. **音频标签必须有 `id`**，否则渲染无声；`data-volume` 基线 0.2（无口播时可 0.8–0.9）；<u>不得加 `crossorigin`</u>。
4. **确定性**：禁用 `Math.random`、实时时钟；需要随机感就用写死的偏移数组。
5. **信息流观感（倾向，非硬线）**：抖音信息流会在画面右侧叠头像/操作列、底缘叠进度条。**排版合理的前提下**尽量别让整块文字/卡片的右缘顶到最右侧（右对齐时 `right` 用 100–200px 比 64px 更稳），画面四边别用近黑底。遮挡范围随机型/版本变化，**不设强制安全线，也不为躲遮挡牺牲版式**——见 `references/feed-safe-layout.md`。

完整契约与 lint 陷阱清单见 `references/project-contract.md`。工程骨架可直接取用 `assets/project-template/`（默认落到 `$HF_DATA_ROOT/projects/`）：

```bash
python <skill目录>/scripts/init_project.py "$HF_PROJECTS/<slug>" --title "标题" --duration 85.4
```

## 阶段 5：出片参数

```bash
hf render "$HF_PROJECTS/<slug>" -w 1 --video-bitrate 8M --output "$HF_OUTPUT/<slug>.mp4"
# 默认交付形态：无音轨版（流复制去音轨，不重编码）
"$HF_FFMPEG" -v error -y -i "$HF_OUTPUT/<slug>.mp4" -c copy -an "$HF_OUTPUT/<slug>_无音轨.mp4"
```

- 默认 CRF 只有约 1.1 Mbps，纯色渐变会被平台压出色带 → **显式给 `--video-bitrate 8M`**。
- CLI 会自动把音轨压 4.5 dB 以守 −1 dBTP 峰值，不必手动加 `-af`。
- 渲染耗时经验值：长片约 **2.3 秒渲染 / 1 秒成片**（单 worker、1280×720），85 秒片 ≈ 3.5 分钟；短于 15 秒的片子有固定开销，实测 8.3 秒片耗时 32 秒（约 3.9 : 1）。

### 交付形态与时长（默认约定）

**无特别声明时，只交付无音轨版**——发布时通常在抖音 App 内挂站内音乐库的同款，带音轨版属于多余产物。工程内仍可正常挂 BGM 用于卡点对拍（阶段 1 的 BPM/拍网格仍需实测），只是**渲染后按上面的命令去掉音轨再交付**，带音轨版留不留在 `output/` 由用户定。

**时长目标：60 秒以上，但不为凑时长拖慢节奏**——这是硬性下限 + 软性上限的关系：内容讲完就到，低于 60 秒才考虑补内容；宁可 62 秒收尾，也不许为了凑到 90 秒在镜头里留静止段。判定标准始终是阶段 4 的节奏验收，不是秒数。

## 绝对不要做的事（全部是实测踩过的坑）

| 禁止 | 原因 |
|---|---|
| 直接敲 `hyperframes`，不用 `hf` | CLI 靠 cwd 下的 `node_modules` 找 FFmpeg，cwd 不对就直接报 `FFmpeg not found` |
| 忘了 `source scripts/hf-env.sh` | 帧缓存与临时文件会落回系统盘；`$HF_*` 路径全部失效 |
| `npm install hyperframes`（不加 `--ignore-scripts`） | 部分 Windows 环境下 `spawnSync` 报 EBUSY，esbuild postinstall 必失败 |
| `render` 不加 `-w 1` | 内存约 1GB 可用，多 worker 必崩 |
| 工程里用 CDN 引 GSAP | 国内网络环境下 jsdelivr 常 `ERR_CONNECTION_RESET`，渲染中断 |
| `<audio>` 忘记 `id` | 渲染结果**无声**，且不报错 |
| 给 `<video>`/`<audio>` 加 `crossorigin` 或调 `.play()`/seek | 违反框架契约，lint 拒绝 |
| 直接 tween 带 `.clip` 的元素 | 片段可见性由框架管理（`gsap_animates_clip_element`） |
| 为凑时长在镜头内留静止段 | 用户反馈的第一号问题；见阶段 4 |
| 不抽帧就交付 | 调试残留（如临时标注文字）只有抽帧才看得见。**抽帧点位必须覆盖每镜前 1/3**：元素入场过晚造成的"半空屏"只在开头暴露，抽中段永远看不出来（实战实测：面板被推迟到 3s 后，前 3 秒右半全空，中段抽帧完全正常） |
| `preview` / `play` / `present` 不加 `--no-open` | 每次调用都会新开一个系统浏览器标签页且从不关闭，多轮迭代堆成一片 |
| 把工程或成片写到数据根之外（系统盘根目录 / `/tmp`） | 不跟着数据根一起备份、也容易把系统盘写满；统一放 `$HF_*` 下 |
| 给 `hf` 传裸工程名（如 `hf lint myvideo`） | `hf()` 会先 `cd "$HF_TOOLCHAIN"`，裸名解析成 `toolchain/myvideo` → 报 `Not a directory`。统一用 `../projects/<slug>` 或绝对路径 |
| 用旧版 `bpm_grid.py` 分析非 44.1 kHz 的 wav | 旧版把采样率写死 44100，时长读成一半、拍长与相位全错（BPM 表面看还对，实为倍频）。现已从 wav 头读实际采样率；**判据是脚本打印的时长必须等于 ffprobe 的时长** |

## 命令速查

前置：`source <skill目录>/scripts/hf-env.sh`（详见 `scripts/hf-env.sh`）

| 命令 | 用途 |
|---|---|
| `hf doctor` | 环境体检（Node / FFmpeg / Chrome / 内存） |
| `hf lint <proj>` | 静态校验，目标 0 errors 0 warnings |
| `hf preview <proj> --no-open` | 起本地 Studio（默认 3002）；收工 `--stop` |
| `hf render <proj> -w 1 --video-bitrate 8M --output <out.mp4>` | 出片 |
| `"$HF_FFMPEG" ...` | 转码 / 裁剪 / 抽音轨，一律用工具链里的 ffmpeg |

分析脚本（纯标准库，无第三方依赖）：

```bash
# BPM / 拍网格 / 高潮点：先转 wav 再分析
"$HF_FFMPEG" -v error -y -i bgm.mp3 -ac 1 -ar 44100 "$HF_TEMP/bgm.wav"
python <skill目录>/scripts/bpm_grid.py "$HF_TEMP/bgm.wav" --out beats.json

# 静止段检测（可直接吃 mp4，内部调 ffmpeg；中间文件自动落 $HF_TEMP）
python <skill目录>/scripts/motion_audit.py "$HF_OUTPUT/<slug>.mp4" --ffmpeg "$HF_FFMPEG"

# 抓抖音音频直链（需 playwright + 系统 Edge/Chrome）
python <skill目录>/scripts/grab_douyin_audio.py <视频URL或ID> --out "$HF_TEMP" --download
```

## 汇报格式

交付时给出：工程目录（`$HF_PROJECTS/<slug>`）→ lint 结果 → 成片路径（`$HF_OUTPUT/`）与参数（ffprobe 实测：分辨率/帧率/时长/码率/音轨）→ 节奏验收数字（最长静止 / 静止占比）→ 抽帧目检结论 → 下一步（发布前置或继续改）。

默认交付**无音轨版**（见阶段 5 约定），汇报里注明"无音轨版已交付 / 带音轨版是否需要"。
