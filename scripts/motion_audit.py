#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""节奏验收：逐帧像素差检测「镜头内静止段」。

  python motion_audit.py out.mp4 --ffmpeg "$HF_FFMPEG"        # 推荐：用 hf-env.sh 导出的变量
  python motion_audit.py out.mp4 --ffmpeg "X:\\...\\@ffmpeg-installer\\win32-x64\\ffmpeg.exe"
  python motion_audit.py --raw out.raw --duration 85.4        # 已有 raw 时跳过 ffmpeg

判定口径（与 SKILL.md 一致）
  达标：最长连续静止 < 1.0 s、静止总占比 < 5%、最小帧差 > 0.3

原理
  FFmpeg 抽 320x180 灰度 2fps 的 rawvideo → 逐帧平均绝对像素差 → 低于阈值即视为静止。
"""
import argparse
import os
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def make_raw(video, ffmpeg, w, h, fps, out_path):
    cmd = [ffmpeg, "-v", "error", "-y", "-i", video,
           "-vf", "fps=%g,scale=%d:%d,format=gray" % (fps, w, h),
           "-f", "rawvideo", out_path]
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, check=True)
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise SystemExit("FFmpeg 未产出 raw 数据，请检查 --ffmpeg 路径与输入文件")
    return out_path


def audit(raw_path, w, h, fps, thresh, top, max_still, max_ratio, min_diff):
    fs = w * h
    data = open(raw_path, "rb").read()
    n = len(data) // fs
    if n < 2:
        raise SystemExit("raw 帧数不足，检查分辨率/帧率参数是否与生成时一致")
    frames = memoryview(data)
    diffs = []
    for i in range(1, n):
        a = frames[(i - 1) * fs:i * fs]
        b = frames[i * fs:(i + 1) * fs]
        s = 0
        for x, y in zip(a, b):
            s += x - y if x > y else y - x
        diffs.append(s / fs)

    runs, cur, start = [], 0, 0
    for i, d in enumerate(diffs):
        if d < thresh:
            if cur == 0:
                start = i
            cur += 1
        else:
            if cur:
                runs.append((start / fps, cur / fps))
            cur = 0
    if cur:
        runs.append((start / fps, cur / fps))

    total = n / fps
    still = sum(s for _, s in runs)
    longest = max((s for _, s in runs), default=0.0)
    rng = "%d..%d" % (min(diffs), max(diffs)) if False else ""

    print("=" * 66)
    print("时长≈%.1fs   采样 %d 帧 @ %g fps   %dx%d 灰度   阈值=%.2f"
          % (total, n, fps, w, h, thresh))
    print("帧差：均值=%.2f  最小=%.3f  最大=%.2f"
          % (sum(diffs) / len(diffs), min(diffs), max(diffs)))
    print("静止段数量=%d   静止总时长=%.1fs (%.1f%%)"
          % (len(runs), still, still / total * 100 if total else 0))
    print(">>> 最长连续静止 = %.1f 秒" % longest)
    if runs:
        runs.sort(key=lambda x: -x[1])
        print("最长几段（起 / 时长）：")
        for t0, sd in runs[:top]:
            print("   %7.1fs 起   %5.1fs" % (t0, sd))

    ratio = still / total * 100 if total else 0.0
    ok = (longest <= max_still) and (ratio <= max_ratio) and (min(diffs) >= min_diff)
    print("-" * 66)
    print("达标线：最长静止 <= %.1fs  占比 <= %.1f%%  最小帧差 >= %.2f" % (max_still, max_ratio, min_diff))
    print("结论：%s" % ("✅ 通过" if ok else "❌ 未通过 —— 去加贯穿动效（见 references/rhythm-motion.md）"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="镜头内静止段检测")
    ap.add_argument("video", nargs="?", help="输入 mp4")
    ap.add_argument("--raw", help="已有的 rawvideo 文件（给了就跳过 FFmpeg）")
    ap.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件路径")
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--height", type=int, default=180)
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--thresh", type=float, default=0.8, help="平均绝对差低于此值算静止")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--max-still", type=float, default=1.0)
    ap.add_argument("--max-ratio", type=float, default=5.0)
    ap.add_argument("--min-diff", type=float, default=0.3)
    ap.add_argument("--keep-raw", action="store_true", help="保留中间 raw 文件")
    ap.add_argument("--tmp-dir", help="中间 raw 文件放哪（默认读 HF_TEMP，其次系统临时目录）")
    args = ap.parse_args()

    if not args.raw and not args.video:
        raise SystemExit("请给出 mp4 路径，或用 --raw 指定已有 rawvideo")

    # 中间 raw 体积 = 宽×高×帧数，长片可达数百 MB，绝不能默认落在 C 盘临时目录。
    # 系统上 TMPDIR 常被预设到系统盘 Temp，Python 的 tempfile 又优先读 TMPDIR，
    # 所以这里显式指定，不依赖 TMP/TEMP 是否被正确继承。
    tmp_root = args.tmp_dir or os.environ.get("HF_TEMP")
    if tmp_root:
        os.makedirs(tmp_root, exist_ok=True)
        tempfile.tempdir = tmp_root

    tmp = None
    raw = args.raw
    if not raw:
        fd, tmp = tempfile.mkstemp(suffix=".raw")
        os.close(fd)
        print("中间文件：%s" % tmp)
        raw = make_raw(args.video, args.ffmpeg, args.width, args.height, args.fps, tmp)

    try:
        ok = audit(raw, args.width, args.height, args.fps,
                   args.thresh, args.top, args.max_still, args.max_ratio, args.min_diff)
    finally:
        if tmp and not args.keep_raw and os.path.exists(tmp):
            os.remove(tmp)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
