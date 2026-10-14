# 工程结构与编写契约（照写即零 lint 错）

## 一、目录结构

工程一律建在数据根的 `projects/<slug>/`（用 `$HF_PROJECTS`），成片统一输出到 `output/`（`$HF_OUTPUT`）。前置：`source scripts/hf-env.sh`。

```bash
python scripts/init_project.py "$HF_PROJECTS/<slug>" --title "标题" --duration 85.4
```

```
<proj>/
├── index.html                  宿主：只放画布、音轨、各镜占位 div、一条空时间线
├── compositions/
│   ├── scene-1-title.html      每镜一个子组合（<template> 包裹）
│   └── scene-2-....html
├── vendor/gsap.min.js          GSAP 本地化（必需，见下）
└── assets/bgm.mp3              音轨与图片
```

**GSAP 必须本地化。** 宿主用根绝对路径引用：

```html
<script src="/vendor/gsap.min.js"></script>
```

国内网络环境常连不上 jsdelivr（`ERR_CONNECTION_RESET`），用 CDN 会让渲染在帧全部捕获完之后、在正确性检查处报 `sub_timeline_script_failure`——错误信息看不出是网络问题，极难排查。可从 `assets/project-template/vendor/gsap.min.js` 直接复制。

## 二、宿主 `index.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1280, height=720">
    <title>片名</title>
    <script src="/vendor/gsap.min.js"></script>
    <style>
      body { margin: 0; background: #101418; }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; background: #101418; }
      #root [data-composition-src] { position: absolute; inset: 0; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0"
         data-width="1280" data-height="720" data-duration="85.402">
      <audio id="bgm" src="assets/bgm.mp3" data-start="0" data-duration="85.402"
             data-volume="0.9" data-track-index="20"></audio>

      <div id="s1" data-composition-id="s1-title"
           data-composition-src="compositions/scene-1-title.html"
           data-start="0" data-duration="8.283" data-track-index="0"
           data-width="1280" data-height="720"></div>
      <!-- 其余各镜同理 -->
    </div>
    <script>
      const tl = gsap.timeline({ paused: true });
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
```

宿主根**不要**用 `<template>` 包裹（`standalone_composition_wrapped_in_template`）。

## 三、子组合 `compositions/scene-N-*.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head><meta charset="UTF-8"></head>
  <body>
    <template>
      <style>#root { position: absolute; inset: 0; overflow: hidden; ... }</style>
      <div id="root" data-composition-id="s1-title" data-width="1280" data-height="720">
        <div id="s1-glow" class="glow"></div>
        ...
      </div>
      <script>
        const tl = gsap.timeline({ paused: true });
        tl.fromTo("#s1-glow", {...}, {..., duration: 8.0, ease: "none"}, 0.05);
        window.__timelines["s1-title"] = tl;
      </script>
    </template>
  </body>
</html>
```

**三处 id 必须一致**：宿主占位 div 的 `data-composition-id` = 子组合内根节点 `data-composition-id` = `window.__timelines` 的 key。

**子组合内所有元素 id 加镜头前缀**（`s1-`、`s2-`…），避免跨镜冲突。

## 四、时间规则

- `data-start` + `data-duration` 是元素成为"片段"的唯一判据；`class="clip"` 只是约定。
- 渲染长度 = **根 `data-duration`**，不是时间线长度。时间线跑过头会被截断，提前结束则保持最后一帧。
- 片段结束不得越过根时长（`clip_ends_past_root_duration`）。
- `data-track-index` 只影响 Studio 轨道显示，无时序含义。
- 子组合内的 tween 时间点是**相对本镜起点**的，不是全片绝对时间。

## 五、lint 陷阱清单（全部踩过）

| 报错 / 症状 | 原因 | 正确写法 |
|---|---|---|
| `gsap_css_transform_conflict` | CSS 里写了初始 `transform`，GSAP 又 tween 同属性 | CSS 不写 transform，初始态一律用 `gsap.fromTo` 表达 |
| `gsap_animates_clip_element` | 直接 tween `.clip` 的 `autoAlpha`/`visibility`/`display` | 淡出只作用于**内部节点**（如 `#s1-wrap`），不碰片段本身 |
| `media_missing_id` | `<audio>` 没写 `id` | 每个 `<audio>` 必须有 `id`；**否则渲染无声且不报错** |
| `media_crossorigin_breaks_preview` | 媒体标签加了 `crossorigin` | 去掉，无例外 |
| `font_family_without_font_face` | 用了命名 `font-family` 而无 `@font-face` | 用 `system-ui, sans-serif` 及系统中文字体族 |
| `standalone_composition_wrapped_in_template` | 宿主根被 `<template>` 包住 | 宿主根直接放 `<body>` |
| 同元素两条 `fromTo` 相互覆盖 | 第二条 fromTo 的起点被第一条的终点覆盖 | 给后一条加 `immediateRender: false` |
| 两条 tween 被判 `overlapping` | 前后恰好首尾相接时，浮点精度让结束点落进下一条 | 让后一条**错开 0.05 s**（如 `2.6+1.3=3.9` 与 `3.9` → 改成 `3.95`） |
| `repeat: -1` 警告 | 无限循环在有限根时长下受限 | 用有限次数或覆盖整个镜长的一次性 tween |
| `gsap_non_transform_motion`（error） | tween 了 `letterSpacing` 这类逐像素取整的文本/布局属性，逐帧 seek 会抖 | 收尾动效只用 `x/y/scale/opacity/width`；文字散开要逐字拆元素 |
| "从半透明渐入"提前常驻 | `fromTo(el,{opacity:0.35},{opacity:1},t)` 不写 `immediateRender:false` 时，from 值在 authoring 期就生效，t 之前元素一直以 0.35 显示 | 先给 CSS `opacity:0`，再用 `tl.to(el,{opacity:1},t)`（`to` 无此问题） |

## 六、确定性

- 禁用 `Date.now()`、计时用 `requestAnimationFrame`、未播种的 `Math.random`、网络请求。
- 需要"随机感"（散点、抖动）→ 写死偏移数组，例如 `const dx = [12, -34, 27, -8, 41, ...]`。
- 正文不用 `<br>` 换行（分行用独立元素）。
- 每个 `id` 全页唯一；被 transform 的元素必须是块级且已定尺寸。

## 七、版式

**16:9（1280×720）**
- 四周安全边距 ≥64px；左右分栏（左 45–50% 文字 / 右 40% 图形）；底部可留字幕条。
- **信息流观感（倾向性，非硬线）**：抖音信息流会在画面右侧叠上头像/操作列、底缘叠进度条，遮挡范围随机型与版本变化。排版合理的前提下**尽量**让整块文字/卡片的右缘别顶到最右侧（右对齐时 `right` 用 100–200px 比 64px 更稳），关键信息别贴底缘；画面四边也别用近黑底（模板宿主自带 2px 内描边，不需要可删）。**不必为躲遮挡牺牲版式**——详见 `references/feed-safe-layout.md`。
- 字号：主标题 56–78px、副文 26–34px、小标签 18–24px。
- 配色：深色低饱和底（如 `#101418`）+ 一个暖强调色（如 `#c9a961`）+ 一个冷辅助色（如 `#7fa8d0`）。

**9:16（1080×1920，抖音竖屏）**
- 顶部 15% / 底部 20% / 右侧 15% 是遮挡区，核心大字与金句放中间 60%。
- **首帧不能是黑场或纯渐变**（信息流展示第一帧）。
- 竖屏是**重新排版**，不是给横屏加黑边。

## 八、自检流程（每次改完必做）

1. `hyperframes lint <proj>` → 必须 **0 errors 0 warnings**。有警告也修，警告会掩盖真问题。
2. **低清样片先看一眼**：短工程可直接 render；长工程建议先渲一个 20–40 s 的截短片确认版式与动效终点，别直接等 3 分钟。

   ```bash
   ffmpeg -v error -y -i out.mp4 -ss <起> -t <长> -c copy sample.mp4
   ```

3. **抽帧目检**（关键，无法省）：

   ```bash
   ffmpeg -v error -y -i out.mp4 -vf "fps=1/8" frames/f-%03d.png
   ```
   逐张看：中文是否乱码、文字是否溢出安全区、动效终点帧是否正确、**有无调试残留标注**（实测踩过：镜1 上遗留了"BPM 90.25"的临时标注，只有抽帧才发现）。

   如果某镜的整块文字/卡片顶到了最右侧或最底缘，可以顺手看一眼信息流遮挡的参考区（见 `references/feed-safe-layout.md` 的自查命令）——**属可选自查，不是验收门槛**；遮挡范围随机型与版本变化，排版合理时轻微贴边可以放过。

   > 别用 ffmpeg `xstack` 把多帧拼成一张接触表图省事——实测会乱序、丢格，看起来像"镜头错位"。老老实实逐张读。

4. 节奏验收（见 `rhythm-motion.md`：帧差检测静止段）。
