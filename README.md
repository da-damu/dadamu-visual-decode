# visual-decode · 视觉与设计术语拆解

给自媒体创作者用的逆向拆解工具。

你发来一条视频、一个网站、一个 App 界面或一张图，它告诉你：

1. 画面里到底有哪些可见元素
2. 这些元素对应的专业术语叫什么（中英对照）
3. 用什么参数 / 步骤能做出来
4. 怎么把「我想要这种感觉」写成能直接发给 AI 或设计师的需求

它不产出设计稿、分镜脚本、生图 prompt 成稿或成片。它只做拆解、教学和需求翻译。

---

## 解决什么问题

- 看得懂好坏，但说不出差在哪
- 只能说「高级、大气、有氛围」，AI 只能给平均值
- 知道喜欢某个作品，但不知道喜欢的是光、色、构图、剪辑还是字体
- 想学视觉语言，但一打开术语表就被几十个词劝退

拆解把感觉拆成四层：

```
现象 → 术语 → 参数 → 需求
```

每一层都能被指出来、被验证、被复用。

---

## 快速开始

### 1. 视频

```bash
python3 scripts/prepare_media.py path/to/video.mp4 --out outputs/my-video
```

产出：

- `metadata.json`：时长、分辨率、帧率、编码、码率、音轨
- `frames/`：按场景切点和均匀间隔抽出的关键帧
- `contact-sheet.jpg`：联系表
- `contact-sheet-index.md`：每一格对应的时间码
- `palette.png`：主色板
- `waveform.png`：音频波形

然后只读联系表和关键帧，不要直接「看视频」。

### 2. 图片

```bash
python3 scripts/prepare_media.py path/to/image.jpg --out outputs/my-image
```

产出 `*-preview.jpg`（最长边 1080）和 `palette.png`。只读预览图，不读原图。

### 3. 网页

```bash
node scripts/probe_site.js https://example.com --out outputs/my-site
```

产出桌面 / 平板 / 手机三档截图和 `site-probe.json`（字体、颜色、间距、圆角、阴影、动效、组件统计）。

需要 Node.js 和 Playwright：

```bash
npm init -y
npm i playwright
npx playwright install chromium
```

没有 Playwright 时，脚本会打印安装命令并退出。如果本机别的项目已经装过，可以把那个项目的 `node_modules` 加进 `NODE_PATH` 复用，不必再装一份：

```bash
NODE_PATH=/path/to/project/node_modules node scripts/probe_site.js https://example.com --out outputs/my-site
```

也可以让用户提供三档截图，或先用 `curl` 看 HTML / CSS 的结构与 token；视觉判断仍以截图为准。

### 4. 自检拆解稿

```bash
python3 scripts/decode_lint.py outputs/my-analysis.md
```

检查：

- 必需章节是否齐全
- 术语卡字段是否完整
- 每个术语是否有证据、参数、怎么说、置信度
- 模糊形容词是否翻译成了可观察特征
- 术语数量是否在 3–7 个之间（超过 7 个直接报错）

退出码不为 0 时先修再交。`--strict` 会把警告也当成错误。

`assets/` 里的空模板本身会被 lint 报缺字段，那是预期行为；lint 只对填完的成品稿跑。

---

## 目录

```text
visual-decode/
├── SKILL.md
├── README.md
├── references/
│   ├── 00-拆解总纲.md
│   ├── 01-视频语言.md
│   ├── 02-网页与App.md
│   ├── 03-平面与图像.md
│   ├── 04-风格与流派.md
│   ├── 05-需求翻译.md
│   └── 06-术语库与练习.md
├── assets/
│   ├── icon.svg
│   ├── icon.png
│   ├── 输出模板-标准拆解.md
│   ├── 需求卡模板.md
│   ├── 术语库模板.md
│   └── 证据表模板.md
└── scripts/
    ├── prepare_media.py
    ├── probe_site.js
    └── decode_lint.py
```

---

## 安装

把整个 `visual-decode` 目录放到你的 agent skills 目录，或软链到该目录。软链名与 `SKILL.md` 里的 `name` 保持一致：`visual-decode`。

实体文件只保留一份。不要同时在项目目录和 skills 目录各放一份副本，否则会出现「改了项目里的，实际运行的是另一份」。

---

## 依赖

| 功能 | 依赖 | 没有时怎么办 |
| --- | --- | --- |
| 视频抽帧、图片预览、色板、波形 | `ffmpeg` + `ffprobe` | 脚本会打印安装命令并退出；也可以让用户直接提供关键帧截图 |
| 网页截图与计算样式 | Node.js + Playwright + Chromium | 脚本会打印安装命令；也可以让用户提供三档截图 |
| 拆解稿自检 | Python 3.9+ | 手动按 `assets/输出模板-标准拆解.md` 检查 |
| 读图 | 运行环境自带的看图能力 | 只读预览图，不读原图 |

安装命令示例：

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows
winget install Gyan.FFmpeg
```

Playwright：

```bash
npm init -y
npm i playwright
npx playwright install chromium
```

---

## 输入与输出

| 输入 | 先做什么 | 不能做什么 |
| --- | --- | --- |
| 视频文件 / 屏幕录制 / GIF | 抽帧、场景切点、联系表、色板、波形 | 不能直接「看视频」；必须抽帧后分析 |
| 图片 / 截图 / 海报 / 封面 | 生成预览图和色板 | 不能读原图；不要凭缩略图判断字体细节 |
| 网页 URL | 三档截图 + 计算样式 JSON | 没有浏览器时，不要只凭 HTML / CSS 猜画面 |
| App UI | 关键状态截图 | 只有一张截图时，不能判断动效和完整流程 |
| 只有口头描述 | 让用户给 1–2 个参考作品 | 不能假装分析了不存在的画面 |

标准输出：

1. 一句话判断
2. 五层拆解（整体、结构、元素、动态、技术）
3. 术语卡 ×5–7
4. 复现配方（分成本档）
5. 需求翻译卡（对 AI / 对设计师 / 对自己）
6. 下一步学什么
7. 置信度与不可见项
8. 自检

短拆解直接在对话里回；深拆写成 `outputs/YYYY-MM-DD-<载体>-<slug>.md`，对话里给摘要和文件路径。

---

## 术语表覆盖

- **视频**：景别、机位、运镜、镜头光学、构图、灯光、调色、剪辑、转场、特效、动效、声音、字幕、画幅、风格
- **网页 / App**：网格、间距、字体、色彩、组件、图标、图像、动效、交互、设计系统、平台规范、UI 风格
- **平面 / 图像**：构图、光线、色彩、材质、字体排印、摄影后期、平面类型、图像风格、AI 痕迹
- **风格**：40+ 张跨媒介风格卡，含识别特征、常见载体、关键参数、易混
- **需求**：模糊词替换表、三版需求卡、句式库、验收标准、交接规则

---

## 边界

- 不产出设计稿、分镜脚本、生图 prompt 成稿、成片。
- 不做视觉成品验收；归第 17 层 `visual-qa`。
- 不做文案 / 文章 / 视频稿打分；归第 11 层 `publish-preflight`。
- 不接入「表达习惯档案」。
- 不主动抓小红书；用户要平台数据时，按主规则先暂停并询问。
- 不读原图，只读预览图。
- 不编造外部事实；风格史、器材、软件版本不确定时标「常见说法」或不写。
- 不替用户做审美判决；只做效果归因、手段拆解、成本说明。

---

## 已知限制

1. **视频不能直接看。** 抽帧会漏掉帧间的运动细节；快速运动、闪烁、细微抖动需要用户补充描述或提供更高密度抽帧。
2. **精确参数不可见。** 焦距、光圈、镜头型号、LUT、插件、字体名、hex 色值，通常只能推断，不能确认。
3. **平台压缩会骗人。** 画质糊、色彩断层、暗部死黑，可能是上传压缩，不一定是创作选择。
4. **网页抓取有边界。** 登录页、强反爬、Canvas / WebGL 为主的项目，计算样式可能拿不全；需要用户提供截图或录屏。
5. **风格判断是坐标，不是判决。** 一件作品常常混了两三种风格，输出会给「主导 + 次要」，不会硬塞一个标签。

---

## 给其他 agent 用时

- 不写死本机路径、用户名、主机名。
- 不依赖任何 API key。
- 脚本缺依赖时打印可复制的安装命令，不静默失败。
- 只带实体文件，不带本机软链。
- `SKILL.md` 里的边界与自检要求优先于本 README。

---

## 许可

MIT，见 [LICENSE.md](./LICENSE.md)。
