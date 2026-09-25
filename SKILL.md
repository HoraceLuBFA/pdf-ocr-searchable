---
name: pdf-ocr-searchable
description: 在 macOS 本地将扫描 PDF OCR 为可搜索、可复制的 PDF，或提取 PDF 全文为 Markdown；支持批量处理和 AppleOCR 调试红框修复。用于扫描件无法选中文字、PDF OCR、PDF 转 Markdown 等请求。
---

# pdf-ocr-searchable

一切经由脚本，不要手写 ocrmypdf 命令行（脚本内置语言码归一、跳过已有文字层、livetext 私有 API 失效自动回退 accurate、逐文件字数验收）：

```bash
S=~/.agents/skills/pdf-ocr-searchable/scripts/ocr_pdf.sh

# 第一步：分诊。NEED=要处理，HAS=已可复制
$S --check <PDF 或目录>

# 第二步：OCR。输出 原名.ocr.pdf 不覆盖原件；目录则递归批量
# --md 另产出同名 .md 纯文字版（脚本按行高+章节正则还原标题层级，按段首缩进
#      把扫描换行并回整段并剔除书眉/页码/边码，勿手工转换）。
#      已可复制的 PDF（HAS）自动跳过 OCR、直接从源生成 md——只要 Markdown 也走这条命令
$S [--preset ...] [--lang chi_sim] [--md] <PDF 或目录>
```

已有 `.ocr.pdf` 且比源新时自动跳过 OCR（增量），重跑 `--md` 秒级完成。

按保真、去斜或体积需求选择预设：

| `--preset` | 何时用 | 对原图 |
|---|---|---|
| `archive`（默认） | 档案/论文/合同，要留底的一切 | 逐字节不变，只加文字层 |
| `deskew` | 手机拍的、扫歪的 | 栅格化以矫正倾斜 |
| `compact` | 只求体积小 | 重新编码，约省 15% |

`--lang` 默认 `chi_sim`；`zh-Hans`/`en`/`ja` 等写法脚本会自动归一，`chi_sim+eng` 叠加会被拒（中文模型本就能识别页内英文）。其余旗标看 `$S --help`。

注意两点：英文占比高的文档，交付前抽查专有名词、页眉、参考文献（中文模型识别英文是实践表现，非正式双语支持）；识别字数异常少的文件脚本会标 ⚠️，需人工抽查。

## 红框修复与验收

本机验证的 AppleOCR 0.3.4 会写入红色调试框。脚本在 OCR 后及增量复用时清理已识别的 OCR Form，失败返回非零，不能据 OCR 识别成功宣称已完成交付。修复旧产物、遇到未知结构或升级插件时，先读 [红框兼容性与排查](references/red-boxes.md)。

```bash
"$S" --strip-boxes --dry-run <待修复的.ocr.pdf>  # 只检测
"$S" --strip-boxes <待修复的.ocr.pdf或目录>      # 明确目标后修复
```

交付前抽查文字可搜索/复制及代表页的渲染；红框修复需核对修复前后的提取文本和图像流，并检查原问题页。字数相同不等于文字相同，未匹配到本脚本支持的框不等于不存在其他红框。

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
