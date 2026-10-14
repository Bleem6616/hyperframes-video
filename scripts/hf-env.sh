#!/usr/bin/env bash
# hyperframes-video · 运行环境（可移植版）
#
# 用法：source <技能目录>/scripts/hf-env.sh      （必须 source，不能直接执行）
#
# 它做什么：把工具链、工程、成片、临时目录、帧缓存的位置算出来并导出，
#          并提供 hf() 包装函数（CLI 必须在工具链目录下执行，见下）。
#
# ── 数据根（HF_DATA_ROOT）解析顺序 ───────────────────────────────
#   1) 已显式设置的 $HF_DATA_ROOT 环境变量
#   2) 用户级配置文件 ~/.workbuddy/hyperframes.env（不随技能包分发，
#      用于把数据挪到别的盘，例如指向 D:/hf）
#   3) 默认 $HOME/.workbuddy/hyperframes
#
# ── 设计依据（Windows 实机实测，macOS/Linux 路径逻辑兼容但未实测）──────
# 1) CLI 的所有缓存/状态目录都由 os.homedir() 拼出，没有独立环境变量开关
#    （源码实测：~/.cache/hyperframes、~/.hyperframes、~/.local/state/hyperframes）。
#    要让它们落到别的盘，只能在文件系统层做目录联接——
#    Windows: mklink /J    macOS/Linux: ln -s
#    ⚠ 但「技能实体目录本身」不要用联接：扫描器按目录类型过滤时会把联接漏掉。
# 2) 帧解压缓存与所有临时文件走 os.tmpdir()，是渲染期间最大的写入来源，
#    必须重定向，否则系统盘会被吃满。
# 3) 临时目录三个变量都得设，因为不同运行时读取顺序不同：
#      Node (os.tmpdir)       : TMP → TEMP → USERPROFILE
#      Python (tempfile)      : TMPDIR → TEMP → TMP
#      Win32 API (GetTempPath): TMP → TEMP → USERPROFILE
#    只设 TEMP 会漏，只设 TMP 会漏掉 Python。

# ---------- 平台 ----------
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) HF_OS="windows" ;;
  Darwin)               HF_OS="macos" ;;
  Linux)                HF_OS="linux" ;;
  *)                    HF_OS="unknown" ;;
esac
export HF_OS

# ---------- 技能实体目录（本文件位于 <技能目录>/scripts/）----------
HF_SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HF_SKILL_DIR

# ---------- 路径风格转换（下面几个变量要交给 Windows 原生进程读）----------
if [ "$HF_OS" = "windows" ]; then
  _hf_winpath() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1" | sed 's|/|\\|g'; fi
  }
else
  _hf_winpath() { printf '%s' "$1"; }
fi

# ---------- 数据根 ----------
HF_ENV_FILE="${HF_ENV_FILE:-$HOME/.workbuddy/hyperframes.env}"
if [ -z "$HF_DATA_ROOT" ] && [ -f "$HF_ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$HF_ENV_FILE"
  # 配置文件若被 Windows 记事本改成 CRLF，值会带上尾随 \r，必须剥掉
  HF_DATA_ROOT="${HF_DATA_ROOT%$'\r'}"
fi
if [ -z "$HF_DATA_ROOT" ]; then
  HF_DATA_ROOT="$HOME/.workbuddy/hyperframes"
fi
export HF_DATA_ROOT HF_ENV_FILE
export HF_TOOLCHAIN="$HF_DATA_ROOT/toolchain"
export HF_PROJECTS="$HF_DATA_ROOT/projects"
export HF_OUTPUT="$HF_DATA_ROOT/output"
export HF_TEMP="$HF_DATA_ROOT/temp"

# ---------- 工具链可执行文件 ----------
export HF_BIN="$HF_TOOLCHAIN/node_modules/.bin/hyperframes"

# 不猜平台包名，直接按目录找（@ffmpeg-installer/<平台>/ffmpeg[.exe]）
# 注意 .exe 必须排在前：Git Bash 对可执行文件有隐式后缀匹配（[ -f ffmpeg ] 对
# ffmpeg.exe 也为真），先匹配无后缀会得到 Windows 原生进程不认的路径。
_hf_find_bin() {
  local p
  for p in "$HF_TOOLCHAIN"/node_modules/"$1"/*/"$2".exe "$HF_TOOLCHAIN"/node_modules/"$1"/*/"$2"; do
    if [ -f "$p" ]; then printf '%s' "$p"; return 0; fi
  done
  return 1
}
export HF_FFMPEG="$(_hf_find_bin @ffmpeg-installer ffmpeg)"
export HF_FFPROBE="$(_hf_find_bin @ffprobe-installer ffprobe)"
unset -f _hf_find_bin 2>/dev/null

# ---------- 临时目录与帧缓存 ----------
export TMP="$(_hf_winpath "$HF_TEMP")"
export TEMP="$(_hf_winpath "$HF_TEMP")"
export TMPDIR="$(_hf_winpath "$HF_TEMP")"
export HYPERFRAMES_EXTRACT_CACHE_DIR="$(_hf_winpath "$HF_TEMP/extract")"

# ---------- 浏览器 ----------
# hyperframes 需要一个 Chromium 内核浏览器。优先用系统已有的 Edge / Chrome，
# 省掉下载整个 Chromium（约 150 MB）。HF_BROWSER 可显式指定。
if [ -z "$HYPERFRAMES_BROWSER_PATH" ]; then
  if [ -n "$HF_BROWSER" ] && [ -f "$HF_BROWSER" ]; then
    HYPERFRAMES_BROWSER_PATH="$HF_BROWSER"
  else
    # Windows 分支直接用 C:/… 正斜杠形式：Node 与 Win32 都接受，无需转换
    for _c in \
      "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
      "C:/Program Files/Microsoft/Edge/Application/msedge.exe" \
      "C:/Program Files/Google/Chrome/Application/chrome.exe" \
      "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
      "/usr/bin/google-chrome" "/usr/bin/chromium" "/usr/bin/chromium-browser" ; do
      if [ -f "$_c" ]; then HYPERFRAMES_BROWSER_PATH="$_c"; break; fi
    done
    unset _c
  fi
fi
export HYPERFRAMES_BROWSER_PATH
unset -f _hf_winpath 2>/dev/null

# ---------- 目录（首次或换机时不存在就建）----------
mkdir -p "$HF_PROJECTS" "$HF_OUTPUT" "$HF_TEMP/extract" 2>/dev/null

# ---------- 便捷函数：CLI 必须在工具链目录下执行 ----------
# 实测：CLI 靠「当前工作目录下的 node_modules」定位 FFmpeg/FFprobe，
# 在别处执行会报 "FFmpeg not found"。用 hf 包一层，永远对。
hf() { ( cd "$HF_TOOLCHAIN" && "$HF_BIN" "$@" ); }

# ---------- 自检提示 ----------
if [ -z "$HF_ENV_QUIET" ]; then
  echo "[hf-env] 技能实体 : $HF_SKILL_DIR"
  echo "[hf-env] 数据根   : $HF_DATA_ROOT"
  echo "[hf-env] 工具链   : $HF_TOOLCHAIN"
  echo "[hf-env] 工程/成片: $HF_PROJECTS  |  $HF_OUTPUT"
  echo "[hf-env] 临时/缓存: $HF_TEMP"
  echo "[hf-env] 浏览器   : ${HYPERFRAMES_BROWSER_PATH:-（未找到，需设 HF_BROWSER）}"
  if [ ! -f "$HF_BIN" ]; then
    echo "[hf-env] ⚠ 工具链未安装 —— 先跑一次初始化脚本，详见 INSTALL.md："
    echo "         Windows: powershell -ExecutionPolicy Bypass -File \"$HF_SKILL_DIR/scripts/setup-env.ps1\""
    echo "         macOS/Linux: 本技能未实测，参考 references/env-setup.md 手动安装"
  fi
fi
