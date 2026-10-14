# 更新日志

## v1.0.1 — 2026-10-14

修复「首次安装后自检误报」——明明装好了，看起来却像失败。

- **`setup-env.ps1` 收尾自检补齐环境变量**：脚本末尾那次 `doctor` 没有带上
  `hf-env.sh` 导出的那组变量，于是全新安装后自检会显示
  `✗ Chrome — Chrome Headless Shell is required`，并把帧缓存指到系统盘
  （`…\AppData\Local\Temp`）。现在自检前会设置
  `HYPERFRAMES_BROWSER_PATH` / `HYPERFRAMES_EXTRACT_CACHE_DIR` /
  `TMP` / `TEMP` / `TMPDIR`，仅作用于该子进程，不影响用户环境。

**兼容性说明（实测）**

- 工具链不锁版本，装到的是 npm 上的最新版（本次实测为 `hyperframes@0.8.157`，
  技能内容按 `0.8.152` 编写）。已实测 `0.8.157` 下：旧工程 `lint` 0 errors /
  0 warnings，模板工程可完整渲染出片（20.0 s / H.264 / AAC）。
- 若将来某个 CLI 版本引入不兼容改动，见 `INSTALL.md` 的版本回退说明。

## v1.0.0 — 2026-10-14

首个公开版本。

**核心流水线**

- 六阶段：环境 → 定节奏 → 写工程 → 校验 → 节奏验收 → 出片（→ 发布前置）
- `hf` 包装函数，自动处理「CLI 必须在工具链目录下执行」这一坑

**卡点与节奏**

- `bpm_grid.py`：实测 BPM 并生成拍网格，标出 drop 与收束线
- `motion_audit.py`：扫出镜头内静止段，量化最长静止时长 / 占比 / 最小帧差

**工程与出片**

- `init_project.py`：生成工程骨架（宿主 + 镜头子组合 + GSAP 本地化）
- 默认交付无音轨版（`-c copy -an`），需要带音轨时另行导出

**环境适配（Windows 实测）**

- `setup-env.ps1` 一键初始化：定位 Node / npm / Python → 装工具链 → 建缓存联接 → 自检
- 技能实体与运行数据分离，数据根三级解析（环境变量 → 配置文件 → 默认目录）
- 浏览器自动探测（复用系统 Edge / Chrome，免下载 Chromium 内核）
- 三个临时目录变量同时重定向，避免系统盘在渲染期间被写满

**已知限制**

- macOS / Linux 路径逻辑兼容，但未在真机实测
