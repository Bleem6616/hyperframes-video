# 安装教程

**hyperframes-video** —— 用 HyperFrames（HTML + GSAP 时间线）制作可发布短视频的完整流水线。

这份文档教你从零装好它，并附一份「报错 → 处置」对照表。全过程三步，只有第 2 步需要敲命令。

| 你需要的 | 说明 |
|---|---|
| WorkBuddy 桌面版 | 技能要装在它的技能目录里才会被识别 |
| 磁盘空间 | 约 300 MB（技能本体 228 KB + 工具链 257 MB + 引擎 FFmpeg/FFprobe） |
| 网络 | 第 2 步要联网下载工具链；之后可离线使用 |
| Node.js 18+ | **通常不用自己装**——WorkBuddy 自带 Node，安装脚本会自动找到它 |
| Python 3.8+ | 可选。只影响两个分析脚本（BPM 网格/静止段检测）；同样优先用 WorkBuddy 自带的 |
| Chromium 内核浏览器 | **不用装**——自动复用系统里的 Edge 或 Chrome，省掉约 150 MB 下载 |

---

## 第 1 步：把技能装进 WorkBuddy

三种方式任选一种。**推荐方式 A**，最省事。

### 先拿到分发包

到本仓库的 **Releases** 页面下载 `hyperframes-video.zip`。

> **别点绿色 `Code` 按钮里的「Download ZIP」。**
> GitHub 自动生成的那个包，解出来的顶层目录是 `hyperframes-video-main/`，
> 跟本技能要求的目录名不一致。Release 附件里才是干净的 `hyperframes-video/`。

如果你是直接从别人那里拿到 zip（网盘、微信），跳过这一步。

### 方式 A：上传技能包（推荐）

1. 拿到分发包 `hyperframes-video.zip`（不要解压）。
2. 打开 WorkBuddy，在左侧找到**技能**面板。
3. 点**添加技能** → 选**上传技能** → 拖拽或点击**选择文件**，选中这个 zip。
4. 导入后系统自动完成配置，无需其他操作。

> 之后在**已安装**列表里能看到 `hyperframes-video`。首次导入默认是启用状态；如果某次被关掉了，在列表里重新打开即可（关闭不会删文件，只是不参与自动调用）。

### 方式 B：手动放进技能目录

把 `hyperframes-video` 整个文件夹放到用户级技能目录：

| 平台 | 路径 |
|---|---|
| WorkBuddy 桌面版（Windows） | `C:\Users\<你的用户名>\.workbuddy\skills\hyperframes-video\` |
| WorkBuddy 桌面版（macOS / Linux） | `~/.workbuddy/skills/hyperframes-video/` |
| CodeBuddy CLI / IDE | `~/.codebuddy/skills/hyperframes-video/` |

三条硬性要求，缺一个技能就不会被识别：

- **文件夹名必须正好是 `hyperframes-video`**（名字不对，扫描器找不到）。
- **必须直接放在 `skills/` 下**，不能多套一层目录。
- **绝不能用目录联接（junction / symlink）挂到这里**。实测 Node 的 `readdirSync(withFileTypes)` 会把目录联接报成 `isSymbolicLink=true / isDirectory=false`，按目录类型过滤的扫描器会整个漏掉这个技能。数据目录可以用联接，技能实体目录不行。

### 方式 C：从技能市场一键安装

若该技能已在市场发布，直接在**技能市场**搜索 `hyperframes` 点安装即可，效果与方式 A 相同。

---

## 第 2 步：初始化运行环境（只有这一步要敲命令）

技能本体只有 228 KB，真正干活的 CLI、FFmpeg、FFprobe 需要下载安装一次。已经为你写好一键脚本。

**打开 Git Bash**，执行：

```bash
# Windows
powershell -ExecutionPolicy Bypass -File "$USERPROFILE/.workbuddy/skills/hyperframes-video/scripts/setup-env.ps1"
```

macOS / Linux（本技能未在真机实测，见文末「macOS / Linux」一节）：

```bash
bash ~/.workbuddy/skills/hyperframes-video/scripts/hf-env.sh   # 先看它给出的期望路径
# 再按 references/env-setup.md 手动安装
```

脚本按固定顺序做 7 件事，**每一步都是幂等的**，中断了重跑就行：

1. 解析数据根（去哪儿找 `HF_DATA_ROOT`，见第 4 节）
2. 找 Node + npm（PATH 优先，找不到就回落 WorkBuddy 自带的那份）
3. 找 Python 3（会主动排除 `WindowsApps` 下的应用商店转发器存根，并实跑一次验证）
4. 建数据目录
5. 装工具链：`hyperframes` CLI + FFmpeg + FFprobe（约 250 MB，首次几分钟）
6. 把 CLI 的缓存/状态目录用目录联接指到数据根
7. 跑 `hf doctor` 自检并打印结果

先看计划不实际执行，加 `-DryRun`：

```bash
powershell -ExecutionPolicy Bypass -File "$USERPROFILE/.workbuddy/skills/hyperframes-video/scripts/setup-env.ps1" -DryRun
```

想直接指定数据盘：

```bash
powershell -ExecutionPolicy Bypass -File "$USERPROFILE/.workbuddy/skills/hyperframes-video/scripts/setup-env.ps1" -DataRoot "E:\hf"
```

> 安装过程中**不要**中途关窗口。第 5 步下载的是 Node 包，断了重跑即可，已下载的部分会复用。

---

## 第 3 步：自检

在 Git Bash 里：

```bash
source ~/.workbuddy/skills/hyperframes-video/scripts/hf-env.sh
hf doctor
```

期望看到这几行是 ✓：

```
✓ Node.js          v22.x
✓ FFmpeg           ffmpeg version ... at <数据根>/toolchain/node_modules/@ffmpeg-installer/win32-x64/ffmpeg.exe
✓ FFprobe          ffprobe ... at <数据根>/toolchain/node_modules/@ffprobe-installer/win32-x64/ffprobe.exe
✓ Chrome           env: C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe
```

`doctor` 里还有几行 ✗，**都是可选功能，不影响出片**：`whisper-cpp`（语音转写）、`TTS`、`BGM(MusicGen)`（本地兜底音源）、`Docker`。另有 `Memory` 一项，可用内存低于约 1.5 GB 时会提示——渲染时关掉占内存的程序即可，渲染本身固定用单 worker（`-w 1`）。

全绿就算装好了。想验一遍完整链路，直接对 WorkBuddy 说：

> 用 hyperframes 做一条 10 秒测试片，纯色背景 + 一行文字淡入。

---

## 第 4 步（可选）：数据放哪儿 / 换盘

技能实体（代码）和运行数据（动辄几百 MB 到几 GB）是分开的：

| 内容 | 默认位置 | 体积 |
|---|---|---|
| 技能实体 | `~/.workbuddy/skills/hyperframes-video/` | 228 KB |
| ├ 工具链 | `<数据根>/toolchain/` | 257 MB |
| ├ 工程 | `<数据根>/projects/<slug>/` | 每片几百 KB |
| ├ 成片 | `<数据根>/output/` | 每片数十 MB |
| ├ 临时 / 帧缓存 | `<数据根>/temp/` | 单次渲染可达 GB 级 |
| └ CLI 缓存与状态 | `<数据根>/home/` | 较小 |

**数据根默认是 `~/.workbuddy/hyperframes`**（也就是 C 盘用户目录下）。它按这个顺序解析：

1. `HF_DATA_ROOT` 环境变量
2. 配置文件 `~/.workbuddy/hyperframes.env` ← **推荐用这个**
3. 默认值 `~/.workbuddy/hyperframes`

**为什么推荐配置文件**：它不随技能包升级被覆盖，也不用改系统环境变量。想放到 D 盘就新建 `C:\Users\<你>\.workbuddy\hyperframes.env`：

```
HF_DATA_ROOT="D:/hf"
```

存成 **UTF-8 无 BOM**。路径含中文也能用（如 `D:/数据/hf`），但 PowerShell 侧必须显式按 UTF-8 读写，否则中文路径会被按系统代码页解码、连行边界都错乱——这个坑已经踩过，`setup-env.ps1` 里已按正确方式实现。

改完重跑一次 `setup-env.ps1`，脚本会把三个 CLI 缓存目录（`~/.cache/hyperframes`、`~/.hyperframes`、`~/.local/state/hyperframes`）用目录联接指过去。

> **这些缓存目录只能用联接挪盘**：CLI 全部由 `os.homedir()` 拼路径，源码里没有环境变量开关。数据目录只做文件读写，联接完全透明；而**技能实体目录反过来绝不能是联接**（原因见第 1 步方式 B）。
>
> C 盘上**已经存在真实数据**时，`setup-env.ps1` 不会自动删它，会提示你改用 `scripts/redirect-data.ps1`——那个脚本先把内容复制到新位置、校验文件数与字节数一致，才删原目录。

---

## 报错对照表

| 症状 | 原因 | 处置 |
|---|---|---|
| `npm install` 报 `EBUSY` / esbuild postinstall 失败 | 部分 Windows 环境 `spawnSync` 会占用文件 | 安装命令**必须**带 `--ignore-scripts`（`setup-env.ps1` 已内置） |
| `hf doctor` 报 `FFmpeg not found` | CLI 靠**当前工作目录**下的 `node_modules` 找 FFmpeg，cwd 不对就报错 | 用 `hf` 包装函数而不是直接敲 `hyperframes`；`hf()` 会先 `cd` 到工具链目录 |
| 系统盘（C 盘）被写满 | 没有 `source hf-env.sh`，帧缓存与临时文件落回了系统临时目录 | 每个新 shell 先 `source scripts/hf-env.sh`。它同时设 `TMP` / `TEMP` / `TMPDIR` —— 三个都得设，因为 Node 读 `TMP`、Python 读 `TMPDIR`、Win32 读 `TMP` |
| 跑 `.ps1` 时脚本把自己的源码当命令回显、`if` 条件像没生效、变量是空的，却不报错 | `.ps1` 含非 ASCII 字符，被按系统错误代码页解析 | 重新从包里解压原文件，**不要手改注释或提示语**。本包所有 `.ps1` 都是纯 ASCII（提示语用英文） |
| `setup-env.ps1` 读不到 `hyperframes.env` 里的中文路径 | Windows PowerShell 5.1 读 UTF-8 文件默认按系统代码页解，中文字节会把行边界搞乱，正则静默失配 | 已修：脚本内用 `Get-Content -Encoding UTF8`。自己写脚本时也要这样写 |
| `hf doctor` 报 `Chrome ✗` 且提示 `Chrome Headless Shell is required` | 没找到 Chromium 内核浏览器，或环境变量没带上 | 装 Edge/Chrome；手动 `source scripts/hf-env.sh` 后再看 `doctor`。**若 `setup-env.ps1` 最后那次自检报这一条、但你确实有 Edge/Chrome**，那是 v1.0.0 的已知缺陷（脚本收尾自检没带环境变量），v1.0.1 已修——重跑新版脚本即可 |
| 显式指定浏览器 | 想用非默认的 Chromium 内核 | `export HF_BROWSER="C:/Program Files/Google/Chrome/Application/chrome.exe"` |
| 技能列表里没有 `hyperframes-video` | 目录名不对 / 多套了一层 / 用了目录联接 | 见第 1 步方式 B 的三条硬性要求；把技能实体放在真实目录里 |
| `Node.js not found` 或提示版本过低 | 系统里没有 Node 18+ | 装 Node 18+（https://nodejs.org）；或直接重跑 `setup-env.ps1`，它会用 WorkBuddy 自带的那份 |
| Python 找到了但一跑就退、没有输出 | 命中了 `WindowsApps` 下的应用商店转发器存根，不是真 Python | 用 `python -c "print('ok')"` 验一下；`setup-env.ps1` 已排除这类路径并实跑验证 |
| `doctor` 提示 `Memory` 不足 | 可用内存低于约 1.5 GB | 关掉占内存的程序；渲染保持 `-w 1`（默认就跑单 worker，多 worker 必崩） |
| 渲染出来**没有声音** | 工程里的 `<audio>` 标签缺 `id` | 给 `<audio>` 加 `id`（这是框架契约，不报错但静默无声） |
| 渲染被 `sub_timeline_script_failure` 拦下 | 工程用 CDN 引了 GSAP，国内网络常连不上 jsdelivr | 用包内的 `assets/project-template/vendor/gsap.min.js`，本地引用 |
| `hf render` 中途崩 / 卡死 | 并发 worker 太多 | 固定加 `-w 1` |
| 给 `hf` 传了裸工程名（如 `hf lint myvideo`）报 `Not a directory` | `hf()` 会先 `cd` 到工具链目录，裸名被解析成 `toolchain/myvideo` | 统一用 `$HF_PROJECTS/<slug>` 或绝对路径 |
| `bpm_grid.py` 读出的时长只有实际的一半 | 用了 2026-10-14 之前的旧版脚本分析非 44.1 kHz 的 wav | 用包内的新版（从 wav 头读实际采样率）。**判据：脚本打印的时长必须等于 `ffprobe` 的时长** |

大部分问题都可以用一条命令先排除：

```bash
source scripts/hf-env.sh && hf doctor
```

---

## 升级

- **上传方式安装的**：拿到新 zip，重复第 1 步方式 A 即可覆盖。
- **手动放置的**：直接替换 `hyperframes-video` 文件夹。
- 数据根（工具链 / 工程 / 成片）**不受升级影响**，不用重装。
- 升级后如果 `doctor` 报工具链缺失，重跑一次 `setup-env.ps1`。

### 锁版本 / 回退

技能**不锁** CLI 版本，`setup-env.ps1` 装的是 npm 上的最新版。想让多台机器都用同一个版本，或某个新版本出问题时：

```bash
cd "$HF_TOOLCHAIN"
npm install hyperframes@0.8.152 --ignore-scripts --no-audit --no-fund
```

改完重跑 `hf doctor` 确认版本号。**已知兼容区间**：`0.8.152`（技能编写基线）与 `0.8.157` 均实测通过 `lint` 与完整渲染出片。

## 卸载

- 在 WorkBuddy **技能**面板里选中它，点**卸载技能**（支持批量）。
- 手动放置的，直接删掉 `hyperframes-video` 文件夹。
- **运行数据不会自动删**。它可能占几百 MB 到几 GB，要一起清就删数据根：

```bash
du -sh "$HF_DATA_ROOT"        # 先看看多大
# 确认后：Windows 资源管理器里直接删除；Git Bash 里
rm -rf "$HF_DATA_ROOT"
```

> 删之前确认里面没有你还要的成片（`output/`）和工程（`projects/`）。

---

## macOS / Linux

**本技能在 Windows + Git Bash 上实测通过；macOS / Linux 的路径逻辑已在 `hf-env.sh` 里写了分支，但没有在真机验证过。**

`hf-env.sh` 已做的适配：平台检测、浏览器自动搜索（含 `/Applications/Google Chrome.app`、`/usr/bin/chromium`）、临时目录变量。仍缺的是一个装工具链的 shell 脚本（目前一键脚本只有 PowerShell 版）。

手动安装大致是：

```bash
source ~/.workbuddy/skills/hyperframes-video/scripts/hf-env.sh    # 先让它算出 $HF_TOOLCHAIN
mkdir -p "$HF_TOOLCHAIN" && cd "$HF_TOOLCHAIN"
npm install hyperframes --ignore-scripts --no-audit --no-fund
# 按平台装 FFmpeg / FFprobe（macOS 用 darwin-x64 / darwin-arm64）
npm install @ffmpeg-installer/darwin-arm64 @ffprobe-installer/darwin-arm64 --ignore-scripts
source ~/.workbuddy/skills/hyperframes-video/scripts/hf-env.sh
hf doctor
```

更细的步骤与每一处坑（为什么必须 `--ignore-scripts`、为什么 CLI 必须在工具链目录里执行、headless-shell 的 staging 行为、缓存目录为什么只能用联接）见 `references/env-setup.md`。装完请以 `hf doctor` 的输出为准。

---

## 怎么用

装好后不需要记命令，直接用自然语言提需求即可，技能会自动生效。例如：

> 做一条 60 秒的知识科普短视频，主题是「课题分离」，16:9 横屏，纯音乐卡点。

工作流细节见 `SKILL.md`；节奏对齐、工程契约、发布前置分别见 `references/` 下的对应文档。
