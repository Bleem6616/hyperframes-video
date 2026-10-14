# 环境适配（Windows 实测）

目标：让 `hyperframes doctor` 全绿、`lint` 与 `render` 一次跑通。以下每条都是实机实测得出，**换一台 Windows 机器后按"症状 → 处置"表逐条对**即可。

> 优先用一键脚本，而不是手动照本文敲命令：
> ```bash
> powershell -ExecutionPolicy Bypass -File "<技能目录>/scripts/setup-env.ps1"
> ```
> 它会自动完成第二节到第四节的全部动作，并跑第五节的自检。本文余下部分是**手工版**与**原理说明**，用于排障。

## 一、环境事实（基线）

| 项 | 实测值 | 影响 |
|---|---|---|
| `spawnSync` | **一律失败 EBUSY**（沙箱内外均复现；async spawn 正常） | 任何用同步子进程做 postinstall 校验的 npm 包都装不上 |
| FFmpeg / FFprobe | PATH 中**不存在** | `doctor` 报 ✗，渲染无法合成音轨 → 走 npm 装（第三节） |
| Chrome | **未安装**，只有 Edge | 默认浏览器探测失败 → 用 `HYPERFRAMES_BROWSER_PATH` 顶替（第四节） |
| 内存 | 约 7.9 GB 总量 / **约 0.9 GB 可用** | 默认按 12 核起 12 个 Chrome worker 必崩 → 永远 `-w 1` |
| 外网 | npm registry、git clone、raw.githubusercontent 快；Google / gyan.dev / GitHub releases 慢或不通；**jsdelivr 被 RESET** | 大二进制走 npm，不走直链；GSAP 必须本地化 |

以上是**一台机器的实测值**，不是普适结论——换机后以 `hf doctor` 的输出为准。

## 二、装 CLI

工具链装在数据根下（`$HF_DATA_ROOT/toolchain`，约 257 MB），装一次即常驻：

```bash
mkdir -p "$HF_TOOLCHAIN" && cd "$HF_TOOLCHAIN"
npm install hyperframes --ignore-scripts
```

- `--ignore-scripts` **不是可选项**：同步子进程 EBUSY 会让 esbuild 的 postinstall 校验失败并中止整个安装（症状是 `npm install` 跑到一半报 EBUSY）。
- 装机后 CLI 可用：`node_modules/.bin/hyperframes`（环境变量里是 `$HF_BIN`，包装函数是 `hf`）。
- 实测版本：`hyperframes@0.8.152`。
- **必须在工具链目录下执行**：实测 CLI 靠「当前工作目录下的 `node_modules`」定位 FFmpeg/FFprobe，换到别处（哪怕 CLI 本身路径没变）会直接报 `FFmpeg not found`。`scripts/hf-env.sh` 里的 `hf()` 就是干这个的。

## 三、备 FFmpeg / FFprobe（走 npm，不走官网）

```bash
cd "$HF_TOOLCHAIN"
npm install @ffmpeg-installer/win32-x64 @ffprobe-installer/win32-x64 --ignore-scripts
```

得到（环境变量已封装为 `$HF_FFMPEG` / `$HF_FFPROBE`）：

- `$HF_TOOLCHAIN/node_modules/@ffmpeg-installer/win32-x64/ffmpeg.exe`
- `$HF_TOOLCHAIN/node_modules/@ffprobe-installer/win32-x64/ffprobe.exe`

`hf-env.sh` 不猜平台包名，直接按 `@ffmpeg-installer/*/ffmpeg.exe` 的目录结构找，所以官方源换了平台包名也不影响。

**不要**去 gyan.dev 或 GitHub releases 下（实测约 3 KB/s 与 HTTP 000）。转码一律用上面这两个路径。

## 四、浏览器：用系统里的 Edge / Chrome 顶替

```bash
export HYPERFRAMES_BROWSER_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

`hf-env.sh` 会自动搜索常见安装位置（Edge / Chrome，Windows 与 macOS 路径都列了），找不到才需要手动设 `HF_BROWSER`。

- CLI 的主渲染路径写死 `headless: true`，puppeteer 映射为 `--headless=new` → 渲染期间**不产生可见窗口**。
- 用 Edge 只是顶替内核，渲染行为与 Chrome 一致（渲染日志中的 UA 会显示 `Edg/155.x`）。

### 附带发现：真 headless-shell 停在暂存目录没搬到位

CLI 只查 `~/.cache/hyperframes/chrome/chrome-headless-shell/`，但真正解压好的二进制有时停在：

```
~/.cache/hyperframes/.chrome-staging-<uuid>/chrome-headless-shell/win64-<ver>/chrome-headless-shell-win64/chrome-headless-shell.exe
```

所以渲染会**退化成用完整 Edge**。日志指纹对照：

| 场景 | 渲染日志中的 UA |
|---|---|
| 用完整 Edge | `Edg/155.0.4283.45` |
| 指向 staging 里的二进制 | `HeadlessChrome/152.0.7977.30` |

想让渲染用回真 headless-shell，把 staging 目录搬到 CLI 期望的位置即可（可逆的目录移动）：

```bash
mkdir -p ~/.cache/hyperframes/chrome
mv ~/.cache/hyperframes/.chrome-staging-*/chrome-headless-shell ~/.cache/hyperframes/chrome/chrome-headless-shell
```

> 用完整 Edge 也能正常出片（本技能的成片全部是在这个状态下渲的），所以这一步**不必须**，属于可选优化。

## 五、验收：`doctor`

```bash
source scripts/hf-env.sh && hf doctor
```

期望：Node ✓、FFmpeg/FFprobe ✓（指向 `$HF_TOOLCHAIN`）、Chrome ✓（Edge 顶替）、内存告警（可忽略，但要记得 `-w 1`）。

## 六、症状 → 处置对照表

| 症状 | 根因 | 处置 |
|---|---|---|
| `npm install` 中途报 EBUSY / spawnSync | 同步子进程不可用 | 加 `--ignore-scripts` |
| `✗ FFmpeg not found` / `✗ FFprobe not found`（doctor 却全绿） | CLI 从**当前工作目录**的 `node_modules` 找 FFmpeg；cwd 不在工具链目录就找不到 | 用 `hf` 执行（内部先 `cd "$HF_TOOLCHAIN"`），不要直接敲 `hyperframes` |
| 渲染到一半报 `sub_timeline_script_failure`，帧已捕完 | 页面依赖外网 CDN，被 `net::ERR_CONNECTION_RESET` 打断 | 把 gsap.min.js 放工程 `vendor/`，改用 `/vendor/gsap.min.js` |
| 渲染进程被系统杀掉 / 卡死 | 多 worker 抢 ~1GB 内存 | `-w 1` |
| 出片无声，但不报错 | `<audio>` 缺 `id` | 补 `id`，并确认 `src` 相对路径正确 |
| 出片画面有彩色色带 | 默认 CRF 码率过低（约 1.1 Mbps） | `--video-bitrate 8M` |
| 每次操作都弹出一堆 Edge 标签页 | `preview`/`play`/`present` 会主动开系统浏览器且从不关闭 | 全部加 `--no-open`；残留用 `preview <proj> --stop` 收 |
| Studio 端口被占 / 预览打不开 | 上一次 preview 的后台服务还活着 | `hyperframes preview <proj> --stop`，必要时换端口 |
| 系统盘空间还在掉（以为数据都在数据根下） | 临时目录没设全：Node 读 `TMP`、Python 读 `TMPDIR`、Win32 API 读 `TMP`，只设 `TEMP` 会漏 | `source scripts/hf-env.sh`（它把三个都设了）；用 `du -sh` 对比两边确认 |
| `setup-env.ps1` 报编码错 / 源码被当命令回显 | `.ps1` 含非 ASCII，被按错误代码页解析 | 见第 8.2 节的说明；本技能内的 `.ps1` 一律纯 ASCII |

## 七、注意事项

- **不要**用 `npx hyperframes` 拉取临时版本：npx 会重新解析依赖并可能触发同样的 install 脚本问题；直接走 `hf`（即 `$HF_BIN`）。
- 渲染是**确定性**的：同参数同工程，帧数与时长可完全复现（实测 85.433 s / 2563 帧 稳定复现）。
- 渲染前建议先跑一次低清样片（见 `project-contract.md` 的自检流程），别直接等 3 分钟。

## 八、运行数据的落盘位置（数据根）

### 8.1 布局

技能实体（代码）与运行数据（动辄几百 MB 到几 GB）**分开放**：前者在 WorkBuddy 的 skills 目录，后者统一在一个"数据根"下，便于备份、清理与换盘。

| 内容 | 位置 |
|---|---|
| 技能实体 | `~/.workbuddy/skills/hyperframes-video/`（会被自动识别的唯一位置） |
| 数据根 `HF_DATA_ROOT` | 默认 `~/.workbuddy/hyperframes/`，可用环境变量或配置文件改 |
| ├ 工具链 | `$HF_DATA_ROOT/toolchain/`（CLI + FFmpeg/FFprobe，257 MB） |
| ├ 工程 | `$HF_DATA_ROOT/projects/<slug>/` |
| ├ 成片 | `$HF_DATA_ROOT/output/` |
| ├ 临时 / 帧缓存 | `$HF_DATA_ROOT/temp/`（`extract/` 是帧解压缓存，单次渲染可达 GB 级） |
| └ CLI 自建缓存与状态 | `$HF_DATA_ROOT/home/`（`.cache/hyperframes`、`.hyperframes`、`.local/state/hyperframes`） |

**数据根解析顺序**（`hf-env.sh` 实现）：① `$HF_DATA_ROOT` 环境变量 → ② 配置文件 `~/.workbuddy/hyperframes.env`（一行 `HF_DATA_ROOT="E:/hf"`）→ ③ 默认 `~/.workbuddy/hyperframes`。

**推荐用 ②**：技能包升级不会覆盖它，也不用改系统环境变量。示例（把数据放到 D 盘）：

```
# ~/.workbuddy/hyperframes.env
HF_DATA_ROOT="D:/hf"
```

配置**必须存为 UTF-8 且不要带 BOM**；路径含中文（如 `D:/数据/hf`）也能用，但读写时要显式指定编码（见 8.2 的 (b)）。

### 8.2 两套机制：为什么用联接，以及为什么 `.ps1` 必须纯 ASCII

**(a) CLI 缓存目录只能用目录联接挪盘。** CLI 的缓存目录全部由 `os.homedir()` 拼出，**没有环境变量开关**（源码实测）：

```
CACHE_DIR = join(homedir(), ".cache", "hyperframes")     # history / fonts / chrome
CONFIG_DIR = join(homedir(), ".hyperframes")             # config.json / lint-streaks / running
state      = join(homedir(), ".local", "state", "hyperframes", "previews")
```

数据目录只做文件读写，联接完全透明，所以可以在文件系统层用**目录联接**把它们指到数据根：

```
~/.cache/hyperframes        → $HF_DATA_ROOT/home/.cache/hyperframes
~/.hyperframes              → $HF_DATA_ROOT/home/.hyperframes
~/.local/state/hyperframes  → $HF_DATA_ROOT/home/.local/state/hyperframes
```

> ⚠ **技能实体目录本身绝不能用联接**（原因完全不同）：实测 Node 的 `readdirSync(withFileTypes)` 会把目录联接报成 `isSymbolicLink=true / isDirectory=false`，按目录类型过滤的扫描器会整个漏掉这个技能。

数据根不在默认位置时，`setup-env.ps1` 会自动建这三个联接；已有内容的真实目录不会被自动删除——那种情况用 `scripts/redirect-data.ps1`（幂等；会先把内容复制到数据根、校验文件数与字节数一致后才删原目录）：

```bash
source scripts/hf-env.sh          # 先把 HF_DATA_ROOT 设出来
powershell -ExecutionPolicy Bypass -File scripts/redirect-data.ps1 -DryRun   # 先看计划
powershell -ExecutionPolicy Bypass -File scripts/redirect-data.ps1           # 执行
```

**(b) `.ps1` 必须写成纯 ASCII。** 实测按系统错误代码页解析非 ASCII 的 `.ps1`，脚本会被解析坏——症状是它把自己的源码当命令回显、`if` 条件被吃掉、变量为空，却不报错。所以本技能的 `scripts/*.ps1` 注释与提示语全用英文，路径不写死在脚本里而是从 `$HF_DATA_ROOT` 读。**要中文提示就写 `.sh`。**

**同一个坑的第二张脸**：Windows PowerShell 5.1 读 UTF-8 文件也默认按系统代码页解——中文路径的配置文件会被解得连**行边界都错乱**（实测两行被并成一行，正则匹配静默失败）。所以 PowerShell 里读配置一律写 `Get-Content -Encoding UTF8`。`setup-env.ps1` 已按此实现。

### 8.3 临时目录与帧缓存（数据量最大的一块）

渲染期间最大的写入是帧解压缓存（上限 2 GB）与各种 scratch，走 `os.tmpdir()`，**不走 homedir**，必须靠环境变量重定向。三个变量都得设：

| 变量 | 谁在读 | 实测行为 |
|---|---|---|
| `TMP` | Node `os.tmpdir()`、Win32 `GetTempPath` | 设了就生效 |
| `TEMP` | 同上（优先级低一级） | 设了但可能被 `TMPDIR` 抢过 |
| `TMPDIR` | **Python `tempfile`** | 系统上常已预设为系统盘 Temp，**不覆盖它，Python 的中间文件仍落系统盘** |
| `HYPERFRAMES_EXTRACT_CACHE_DIR` | CLI 帧解压缓存专用开关 | 设了就生效，默认是 `os.tmpdir()/hyperframes-extract-cache-<uid>` |

`scripts/hf-env.sh` 已把这些全部指向 `$HF_DATA_ROOT/temp`。

### 8.4 自检

```bash
source scripts/hf-env.sh
echo "$HF_DATA_ROOT"                              # 应是你期望的位置
echo "$TMP | $TMPDIR"                             # 两处都应在数据根下
ls -la ~/.hyperframes                             # 数据根非默认位置时，应显示为链接
python -c "import tempfile;print(tempfile.gettempdir())"   # 应在数据根下
du -sh "$HF_DATA_ROOT"/{toolchain,home,temp,projects,output} 2>/dev/null
# 反查：系统临时目录里不该再有 hyperframes 的残留
ls -d "$(cygpath -u "$LOCALAPPDATA")/Temp/hyperframes*" 2>/dev/null   # 应为空
```
