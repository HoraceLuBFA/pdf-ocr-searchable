---
name: pdf-ocr-searchable
description: 把扫描版/图片版 PDF 在本地 OCR 成可搜索、可复制的 PDF，保留原始版式，中英文（含繁体、竖排、日韩）皆可，引擎为 Apple Vision，离线秒级。默认保真档内嵌图像逐字节不变，仅叠加隐形文字层；已有文字层的页自动跳过，支持整目录批量。当用户说「这个 PDF 不能复制/选不中字」「扫描件转文字」「PDF OCR」「让 PDF 可搜索」「把扫描的论文弄成能复制的」「searchable PDF」时使用。目标是产出 Markdown/结构化文本喂模型（而非 PDF）时不适用；翻译论文用 pdf-paper-zh-translation。
---

# pdf-ocr-searchable

一切经由脚本，不要手写 ocrmypdf 命令行（脚本内置语言码归一、跳过已有文字层、livetext 私有 API 失效自动回退 accurate、逐文件字数验收）：

```bash
S=~/.agents/skills/pdf-ocr-searchable/scripts/ocr_pdf.sh

# 第一步：分诊。NEED=要处理，HAS=已可复制（别做无用功）
$S --check <PDF 或目录>

# 第二步：OCR。输出 原名.ocr.pdf 不覆盖原件；目录则递归批量
# --md 另产出同名 .md 纯文字版（脚本按行高+章节正则还原标题层级，按段首缩进
#      把扫描换行并回整段并剔除书眉/页码/边码，勿手工转换）
$S [--preset ...] [--lang chi_sim] [--md] <PDF 或目录>
```

已有 `.ocr.pdf` 且比源新时自动跳过 OCR（增量），重跑 `--md` 秒级完成。

唯一要动脑的决策是选预设，三档是真实取舍不能兼得：

| `--preset` | 何时用 | 对原图 |
|---|---|---|
| `archive`（默认） | 档案/论文/合同，要留底的一切 | 逐字节不变，只加文字层 |
| `deskew` | 手机拍的、扫歪的 | 栅格化以矫正倾斜 |
| `compact` | 只求体积小 | 重新编码，约省 15% |

`--lang` 默认 `chi_sim`；`zh-Hans`/`en`/`ja` 等写法脚本会自动归一，`chi_sim+eng` 叠加会被拒（中文模型本就能识别页内英文）。其余旗标看 `$S --help`。

注意两点：英文占比高的文档，交付前抽查专有名词、页眉、参考文献（中文模型识别英文是实践表现，非正式双语支持）；识别字数异常少的文件脚本会标 ⚠️，需人工抽查。

## 单张图片 / 只要文字不要 PDF

```bash
mac-ocr 截图.png                 # 文字直接进终端
mac-ocr 论文.pdf --format jsonl  # 带坐标结构化输出
```

不要用 `mac-ocr searchable-pdf` 产出 PDF——其文字层英文单词间空格会丢，换语言参数也治不了；出 PDF 一律走本脚本。

## 新机器重建依赖

```bash
uv tool install --python 3.12 ocrmypdf --with ocrmypdf-appleocr  # 插件必须与主程序同环境；3.12 必需（3.14 装不上）
brew install ghostscript
npm install -g mac-ocr   # 可选
```
