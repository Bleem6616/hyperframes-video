#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实测音频的 BPM / 拍长 / 相位 / 拍网格 / 候选高潮点。

零第三方依赖（不需要 numpy）。输入 mono WAV（44.1kHz 最佳）。

  ffmpeg -v error -y -i bgm.mp3 -ac 1 -ar 44100 bgm.wav
  python bpm_grid.py bgm.wav --out beats.json

原理
  1) onset 包络：一阶差分（≈高通，突出鼓点瞬态）→ 半波整流 → 3 点平滑
  2) 梳状扫描：60~180 BPM 以 --step 步长扫，对每个 BPM 找最佳相位（相位桶法，O(L)）
  3) 判定比值：网格点上的 onset 均值 / 全局均值 —— 比值越大越可信，
     用它区分半频/倍频（例：90.25 得 12.679，112.75 得 11.251 → 前者胜）
  4) 高潮点：短窗能量找 "峰值骤降（换气）→ 骤升（重拍）"，并给出最近拍号与偏差
"""
import argparse
import array
import json
import math
import sys
import wave

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SR = 44100        # 占位，read_mono 会按输入文件实际采样率覆盖
HOP = 220         # 5 ms  → 分析帧率 200 fps
WIN = 441         # 10 ms


def read_mono(path):
    """读单声道样本，并按文件真实采样率重算 5ms/10ms 窗口。

    采样率必须从文件读取：早先版本把 SR 写死 44100，若输入是 22050
    会把时长读成一半、拍长与相位全部错乱（BPM 表面看对，实际是倍频）。
    """
    global SR, HOP, WIN
    w = wave.open(path, "rb")
    SR = w.getframerate()
    HOP = int(round(0.005 * SR))     # 5 ms
    WIN = int(round(0.010 * SR))     # 10 ms
    n, ch = w.getnframes(), w.getnchannels()
    raw = w.readframes(n)
    w.close()
    a = array.array("h")
    a.frombytes(raw)
    if ch == 2:
        m = array.array("h", bytes(2 * (len(a) // 2)))
        for i in range(0, len(a) - 1, 2):
            m[i // 2] = (a[i] + a[i + 1]) >> 1
        a = m
    return a


def onset_envelope(a):
    """返回 (归一化包络 env, 平滑后的 onset 强度 onset)。"""
    n = len(a)
    d = array.array("f", bytes(4 * n))
    prev = 0
    for i in range(n):
        v = a[i]
        d[i] = v - prev
        prev = v
    frames = (n - WIN) // HOP
    env = [0.0] * frames
    for i in range(frames):
        s = i * HOP
        acc = 0.0
        for j in range(s, s + WIN, 2):
            v = d[j]
            acc += v * v
        env[i] = math.sqrt(acc / (WIN // 2))
    mx = max(env) or 1.0
    env = [e / mx for e in env]
    o = [0.0] * frames
    for i in range(1, frames):
        v = env[i] - env[i - 1]
        o[i] = v if v > 0 else 0.0
    sm = [0.0] * frames
    for i in range(frames):
        lo, hi = max(0, i - 1), min(frames, i + 2)
        sm[i] = sum(o[lo:hi]) / (hi - lo)
    return env, sm


def smooth3(y):
    L = len(y)
    out = [0.0] * L
    for i in range(L):
        lo, hi = max(0, i - 1), min(L, i + 2)
        out[i] = sum(y[lo:hi]) / (hi - lo)
    return out


def best_phase(y, period, n_ph=200):
    """相位桶法：一圈 O(L)。返回 (网格点平均强度, 最佳相位帧, 全局均值)。"""
    L = len(y)
    bsum = [0.0] * n_ph
    bcnt = [0] * n_ph
    for i in range(L):
        b = int((i % period) / period * n_ph)
        if b >= n_ph:
            b = n_ph - 1
        bsum[b] += y[i]
        bcnt[b] += 1
    tot = sum(bsum)
    glob = tot / L if L else 0.0
    best_m, best_ph = 0.0, 0.0
    for b in range(n_ph):
        if not bcnt[b]:
            continue
        m = bsum[b] / bcnt[b]
        if m > best_m:
            best_m, best_ph = m, b * period / n_ph
    return best_m, best_ph, glob


def scan_bpm(y, fps, bpm_min, bpm_max, step):
    rows = []
    bpm = bpm_min
    while bpm <= bpm_max + 1e-9:
        period = fps * 60.0 / bpm
        m, ph, glob = best_phase(y, period)
        ratio = (m / glob) if glob else 0.0
        rows.append({"bpm": round(bpm, 2), "period": period / fps,
                     "phase": ph / fps, "ratio": ratio})
        bpm += step
    rows.sort(key=lambda r: -r["ratio"])
    return rows


def dedupe_harmonics(rows, keep=8):
    """去掉半频/倍频重复（按 bpm/2 取整分桶），保留每桶最高分。"""
    seen, out = set(), []
    for r in rows:
        k = round(r["bpm"] / 2)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
        if len(out) >= keep:
            break
    return out


def rms_energy(a, fps, win_s=0.25, hop_s=0.05):
    """短窗 RMS 能量，用于找换气/重拍。"""
    w = int(win_s * SR)
    h = int(hop_s * SR)
    out, t = [], 0
    n = len(a)
    while t + w <= n:
        s = 0
        for i in range(t, t + w, 8):
            v = a[i]
            s += v * v
        out.append(math.sqrt(s / max(1, (w // 8))))
        t += h
    return out, hop_s


def find_drops(a, ratio_thresh=3.0, max_lag=1.6):
    e, hop = rms_energy(a, SR)
    n = len(e)
    drops = []
    w = int(0.12 / hop)          # 局部最小判定窗
    for i in range(w, n - 1):
        lo, hi = e[max(0, i - w):i], e[i + 1:min(n, i + int(max_lag / hop))]
        if not lo or not hi:
            continue
        if e[i] > min(lo) or e[i] > min(hi):
            continue                  # 只在局部低谷上评估
        peak = max(hi)
        if e[i] <= 1e-6:
            continue
        r = peak / e[i]
        if r >= ratio_thresh:
            j = hi.index(peak)
            drops.append({"trough": round(i * hop, 3),
                          "peak": round((i + 1 + j) * hop, 3),
                          "ratio": round(r, 2),
                          "level": round(peak, 1)})
    # 合并相邻（1 秒内）只留比值最高的
    drops.sort(key=lambda d: -d["ratio"])
    kept = []
    for d in drops:
        if all(abs(d["peak"] - k["peak"]) > 1.0 for k in kept):
            kept.append(d)
        if len(kept) >= 8:
            break
    kept.sort(key=lambda d: d["peak"])
    return kept


def nearest_beat(t, phase, period):
    if t < phase:
        return 0, round(phase - t, 4)
    k = round((t - phase) / period)
    return k, round(abs(t - (phase + k * period)), 4)


def main():
    ap = argparse.ArgumentParser(description="实测 BPM / 拍网格 / 高潮点")
    ap.add_argument("wav", help="mono WAV 路径（44.1kHz 最佳）")
    ap.add_argument("--out", default="beats.json")
    ap.add_argument("--bpm-min", type=float, default=60.0)
    ap.add_argument("--bpm-max", type=float, default=180.0)
    ap.add_argument("--step", type=float, default=0.25)
    ap.add_argument("--drop-ratio", type=float, default=3.0,
                    help="换气→重拍的能量骤升比值阈值")
    ap.add_argument("--bars", type=int, default=12, help="打印多少个小节能量")
    args = ap.parse_args()

    a = read_mono(args.wav)
    dur = len(a) / SR
    fps = SR / HOP
    env, onset = onset_envelope(a)
    y = smooth3(onset)
    print("时长 %.3f 秒   分析帧数 %d (%.0f fps)" % (dur, len(onset), fps))

    rows = scan_bpm(y, fps, args.bpm_min, args.bpm_max, args.step)
    top = dedupe_harmonics(rows)
    print("\n=== 候选 BPM（判定比值 = 网格点均值 / 全局均值，越大越准）===")
    print("  比值     BPM       拍长(s)   相位(s)   小节(s)")
    for r in top:
        print("  %6.3f  %8.2f  %8.5f  %8.4f  %8.4f"
              % (r["ratio"], r["bpm"], r["period"], r["phase"], r["period"] * 4))

    best = top[0]
    bpm, period, phase = best["bpm"], best["period"], best["phase"]
    gap = ""
    if len(top) > 1:
        gap = "（次优 %.2f 比值 %.3f，领先 %.1f%%）" % (
            top[1]["bpm"], top[1]["ratio"],
            (best["ratio"] / top[1]["ratio"] - 1) * 100 if top[1]["ratio"] else 0)
    print("\n>>> 最佳 BPM = %.2f   拍长 = %.5f s   相位 = %.4f s %s"
          % (bpm, period, phase, gap))
    print(">>> 第 n 拍 = %.3f + n x %.5f" % (phase, period))

    beats = []
    t = phase
    while t < dur:
        beats.append(round(t, 4))
        t += period
    print(">>> 共 %d 拍；末拍 %.3f s" % (len(beats), beats[-1] if beats else 0))

    bars = []
    for bi in range(0, max(0, len(beats) - 4), 4):
        i0, i1 = int(beats[bi] * fps), int(beats[bi + 4] * fps)
        seg = onset[i0:i1]
        v = sum(seg) / max(1, len(seg))
        bars.append({"t": beats[bi], "e": round(v, 6)})
    print("\n=== 每 4 拍一小节的平均能量（找段落 / build / drop / breakdown）===")
    mx = max((b["e"] for b in bars), default=1.0) or 1.0
    for b in bars[:args.bars]:
        print("  t=%7.2f  %.5f  %s" % (b["t"], b["e"], "#" * int(b["e"] / mx * 40)))

    drops = find_drops(a, args.drop_ratio)
    for d in drops:
        k, off = nearest_beat(d["peak"], phase, period)
        d["beat_index"] = k
        d["beat_offset_s"] = off
    print("\n=== 候选高潮点（换气 → 重拍，比值越大越像 drop）===")
    print("  谷(s)     重拍(s)   比值    最近拍号   与拍网格偏差(s)")
    for d in drops:
        print("  %7.3f  %8.3f  %5.2f  %8d   %6.4f"
              % (d["trough"], d["peak"], d["ratio"], d["beat_index"], d["beat_offset_s"]))

    json.dump({"duration": round(dur, 3), "fps": fps,
               "bpm": bpm, "period": period, "phase": phase, "bar": period * 4,
               "beat_formula": "%.4f + n * %.5f" % (phase, period),
               "beats": beats, "bars": bars, "drops": drops,
               "candidates": top},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n已写出 %s" % args.out)


if __name__ == "__main__":
    main()
