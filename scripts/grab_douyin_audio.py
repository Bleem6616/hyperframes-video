#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓抖音视频/音频直链（并可选下载），用于卡点分析或抽音轨。

  python grab_douyin_audio.py 7693296008339442986 --out ./audio --download
  python grab_douyin_audio.py "https://www.douyin.com/video/<id>" --out ./audio

为什么不用 yt-dlp
  1) 无 cookie 时报 "Fresh cookies are needed"；
  2) `--cookies-from-browser edge` 在 Edge ≥127 会因 App-Bound Encryption 报
     "Failed to decrypt with DPAPI"（关掉浏览器也无效）；
  3) 抖音接口被 ArgusSecurityPlugin 拦、分享页是客户端渲染的空壳。
可行解法：用 Playwright 驱动**系统已装的 Edge / Chrome**（免下载内核），在网络层截获
播放器的分片请求 —— 音频流特征 `v*-web.douyinvod.com/.../media-audio-und-mp4a/`，
视频流为 `media-video-avc1`。拿到直链后带 Referer 直接下载即可。
常常能抓到**完整曲目**，而不是视频里那 70 秒片段。

依赖：pip install playwright（安装约需 9 分钟；用默认 PyPI 源，不要用清华镜像）
"""
import argparse
import json
import os
import re
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

AUDIO_HINTS = ("media-audio", "media_audio", "und-mp4a", "/music/", "audio")
VIDEO_HINTS = ("media-video", "media_video", "avc1", "hvc1")


def normalize(target):
    if re.fullmatch(r"\d{8,}", target.strip()):
        return "https://www.iesdouyin.com/share/video/%s/" % target.strip()
    return target.strip()


def classify(url):
    u = url.lower()
    if any(k in u for k in AUDIO_HINTS) and not any(k in u for k in VIDEO_HINTS):
        return "audio"
    if any(k in u for k in VIDEO_HINTS):
        return "video"
    return None


def grab(target, wait_ms, headless, browser_channel):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "缺少 playwright。安装：\n"
            "  python -m pip install playwright\n"
            "无需再跑 `playwright install`：直接用系统 Edge/Chrome（channel='msedge'/'chrome'）。")

    url = normalize(target)
    found = {"audio": [], "video": []}

    with sync_playwright() as p:
        browser = None
        for ch in ([browser_channel] if browser_channel else ["msedge", "chrome", None]):
            try:
                kw = {"headless": headless,
                      "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]}
                if ch:
                    kw["channel"] = ch
                browser = p.chromium.launch(**kw)
                print("[i] 浏览器内核：%s" % (ch or "bundled"))
                break
            except Exception as e:
                print("[!] 启动 %s 失败：%s" % (ch, e))
        if browser is None:
            raise SystemExit("无法启动浏览器，请检查 Edge 是否安装")

        ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 800},
                                  locale="zh-CN")
        page = ctx.new_page()

        def on_resp(resp):
            kind = classify(resp.url)
            if kind:
                found[kind].append({"url": resp.url, "status": resp.status,
                                    "type": (resp.headers or {}).get("content-type", "")})

        page.on("response", on_resp)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print("[!] goto 异常：%s" % e)
        page.wait_for_timeout(wait_ms)
        print("[i] 标题：%s" % page.title())
        browser.close()

    return url, found


def download(url, out_path, referer="https://www.douyin.com/"):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": referer,
        "Accept": "*/*",
    })
    with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
        total = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    return total


def main():
    ap = argparse.ArgumentParser(description="抓抖音音视频直链")
    ap.add_argument("target", help="视频 URL 或纯数字视频 ID")
    ap.add_argument("--out", default=".", help="输出目录")
    ap.add_argument("--download", action="store_true", help="下载最佳音频直链")
    ap.add_argument("--wait", type=int, default=8000, help="页面停留毫秒数")
    ap.add_argument("--headless", action="store_true", help="无头模式（默认有头，拦截成功率更高）")
    ap.add_argument("--browser-channel", default=None, help="强制指定内核，如 msedge")
    ap.add_argument("--save-html", action="store_true", help="保存页面 HTML 以便排查")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    url, found = grab(args.target, args.wait, args.headless, args.browser_channel)

    print("\n=== 音频候选 ===")
    for i, it in enumerate(found["audio"]):
        print("  [%d] (%s) %s" % (i, it["status"], it["url"][:220]))
    print("=== 视频候选 ===")
    for i, it in enumerate(found["video"]):
        print("  [%d] (%s) %s" % (i, it["status"], it["url"][:220]))

    meta = {"source": url, "audio": found["audio"], "video": found["video"]}
    jpath = os.path.join(args.out, "grab.json")
    json.dump(meta, open(jpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n已写出 %s" % jpath)

    if args.download:
        if not found["audio"]:
            print("[!] 没抓到音频直链。可加 --wait 15000 延长停留，或去掉 --headless 重试。")
            return
        best = found["audio"][0]["url"]
        ext = ".m4a" if ".m4a" in best else ".mp4"
        out_path = os.path.join(args.out, "audio_src" + ext)
        n = download(best, out_path)
        print("已下载 %s（%.2f MB）" % (out_path, n / 1048576))
        print("\n下一步：转码 + 分析\n"
              "  ffmpeg -v error -y -i %s -vn -c:a libmp3lame -b:a 192k bgm.mp3\n"
              "  ffmpeg -v error -y -i bgm.mp3 -ac 1 -ar 44100 bgm.wav\n"
              "  python bpm_grid.py bgm.wav --out beats.json" % out_path)


if __name__ == "__main__":
    main()
