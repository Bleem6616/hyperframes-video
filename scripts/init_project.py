#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从技能内置模板起一个新工程。

  python init_project.py ./my-video --title "立志，是读书的第一要事" --duration 85.402 --scenes 10

只给工程名（不带路径）时，默认建在环境变量 $HF_PROJECTS（D 盘工程根）下：
先 `source scripts/hf-env.sh`，然后 `python init_project.py my-video --title ...`。

生成：
  my-video/index.html                       宿主（画布 + 音轨 + 各镜占位 + 空时间线）
  my-video/compositions/scene-1-title.html  可直接用的开场镜（含贯穿动效与踩拍入场）
  my-video/compositions/scene-N.html        其余镜的空白骨架
  my-video/vendor/gsap.min.js               GSAP 本地化（渲染不依赖外网）
  my-video/assets/                          放 bgm.mp3 等
"""
import argparse
import os
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), "assets", "project-template")
HF_PROJECTS = os.environ.get("HF_PROJECTS")

SCENE_DIV = """      <div id="{sid}" data-composition-id="{cid}"
           data-composition-src="compositions/{file}"
           data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="{idx}"
           data-width="{w}" data-height="{h}"></div>
"""


def main():
    ap = argparse.ArgumentParser(description="起一个新的 HyperFrames 工程")
    ap.add_argument("target", help="目标目录")
    ap.add_argument("--title", default="未命名短片")
    ap.add_argument("--duration", type=float, default=40.0, help="总时长（秒），须与音频裁切长度一致")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--scenes", type=int, default=1, help="镜头数（默认 1，只有开场镜）")
    ap.add_argument("--bgm", default="assets/bgm.mp3",
                    help="音轨相对路径；传空字符串则不挂音轨")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    # 只给了工程名（没有路径分隔符）时，默认落在 D 盘的工程根 $HF_PROJECTS 下
    target = args.target
    if HF_PROJECTS and os.sep not in target and "/" not in target:
        target = os.path.join(HF_PROJECTS, target)

    dst = os.path.abspath(target)
    if os.path.exists(dst) and os.listdir(dst) and not args.force:
        raise SystemExit("%s 非空，加 --force 覆盖" % dst)

    for sub in ("compositions", "assets", "vendor"):
        os.makedirs(os.path.join(dst, sub), exist_ok=True)

    shutil.copy2(os.path.join(TEMPLATE, "vendor", "gsap.min.js"),
                 os.path.join(dst, "vendor", "gsap.min.js"))

    n = max(1, args.scenes)
    dur_each = args.duration / n
    divs = []
    for i in range(1, n + 1):
        if i == 1:
            name, cid = "scene-1-title.html", "s1-title"
            src = os.path.join(TEMPLATE, "compositions", "scene-1-title.html")
        else:
            name, cid = "scene-%d.html" % i, "s%d-scene" % i
            src = os.path.join(TEMPLATE, "compositions", "scene-blank.html")
        text = open(src, encoding="utf-8").read()
        text = (text.replace("{{COMP_ID}}", cid)
                    .replace("{{SID}}", "s%d" % i)
                    .replace("{{DURATION}}", "%.3f" % dur_each)
                    .replace("{{WIDTH}}", str(args.width))
                    .replace("{{HEIGHT}}", str(args.height))
                    .replace("{{INDEX}}", str(i)))
        open(os.path.join(dst, "compositions", name), "w", encoding="utf-8").write(text)
        divs.append(SCENE_DIV.format(sid="s%d" % i, cid=cid, file=name,
                                     start=(i - 1) * dur_each, dur=dur_each,
                                     idx=i - 1, w=args.width, h=args.height))
        if i > 1:
            print("  [注意] %s 是空白骨架，需按拍网格重设 data-start/data-duration" % name)

    scene_dur = dur_each
    bgm_line = ""
    if args.bgm:
        bgm_line = ('      <audio id="bgm" src="%s" data-start="0" data-duration="%.3f"\n'
                    '             data-volume="0.9" data-track-index="20"></audio>\n'
                    % (args.bgm, args.duration))

    html = open(os.path.join(TEMPLATE, "index.html"), encoding="utf-8").read()
    html = (html.replace("{{TITLE}}", args.title)
                .replace("{{DURATION}}", "%.3f" % args.duration)
                .replace("{{WIDTH}}", str(args.width))
                .replace("{{HEIGHT}}", str(args.height))
                .replace("{{BGM}}", bgm_line)
                .replace("{{SCENES}}", "\n".join(divs)))
    open(os.path.join(dst, "index.html"), "w", encoding="utf-8").write(html)

    print("已创建工程：%s" % dst)
    print("  镜头数 %d，每镜 %.3f s（等分；有 BGM 时请按 beats.json 的拍网格改成拍点时长）"
          % (n, scene_dur))
    if args.bgm:
        print("  音轨：%s（记得把文件放进 assets/，audio 必须带 id 才有声）" % args.bgm)
    print("\n下一步（先 source scripts/hf-env.sh，用 hf 执行 CLI；路径要给绝对路径）：\n"
          "  1) 编辑 compositions/*.html（每镜必须挂贯穿动效，见 references/rhythm-motion.md）\n"
          "  2) hf lint \"%s\"\n"
          "  3) hf render \"%s\" -w 1 --video-bitrate 8M --output \"$HF_OUTPUT/%s.mp4\"\n"
          "  4) python %s \"$HF_OUTPUT/%s.mp4\" --ffmpeg \"$HF_FFMPEG\"   # 节奏验收"
          % (dst, dst, os.path.basename(dst),
             os.path.join(HERE, "motion_audit.py"), os.path.basename(dst)))


if __name__ == "__main__":
    main()
