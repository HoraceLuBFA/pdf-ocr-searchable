# pdf-ocr-searchable

> Local, offline OCR for scanned PDFs on macOS — outputs searchable/copyable PDFs (original images preserved byte-for-byte) and optionally structured Markdown, powered by Apple Vision / Live Text. Excellent CJK + English quality. Also works as a [Claude Code](https://claude.com/claude-code) skill.

把扫描版/图片版 PDF 在 Mac 本地 OCR 成**可搜索、可复制**的 PDF，可选同时产出**层级化 Markdown 全文**。引擎为 Apple Vision / Live Text（经 [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) + [ocrmypdf-appleocr](https://github.com/mkyt/OCRmyPDF-AppleOCR) 插件），全程离线，中英文（含繁体、竖排、日韩）皆可。

- **保真**：默认档内嵌扫描图逐字节不变（sha1 验证），只叠加隐形文字层
- **快**：约 0.7 秒/页，多核并行；557 页整书实测 6 分 17 秒
- **增量**：产物比源新则跳过 OCR，重出 Markdown 秒级
- **中文质量**：实测显著优于 Tesseract（后者中文逐字断裂、错字明显）

## 环境要求

- macOS 13+（Live Text 模式；12 及以下自动用 accurate 模式）
- Homebrew、[uv](https://docs.astral.sh/uv/)、poppler（`pdftotext`/`pdfinfo`，Markdown 输出需要）

## 安装

```bash
# 0. 获取本仓库
git clone https://github.com/HoraceLuBFA/pdf-ocr-searchable.git ~/.agents/skills/pdf-ocr-searchable

# 1. OCRmyPDF + AppleOCR 插件（必须同一环境安装，--python 3.12 必需，3.14 装不上）
uv tool install --python 3.12 ocrmypdf --with ocrmypdf-appleocr

# 2. 外部依赖
brew install ghostscript poppler

# 3.（可选）单图/单页随手 OCR 工具
npm install -g mac-ocr

# 4.（可选）作为 Claude Code skill 使用
ln -s ~/.agents/skills/pdf-ocr-searchable ~/.claude/skills/pdf-ocr-searchable
```

验证（注意 ocrmypdf 的 help 输出走 stderr）：

```bash
ocrmypdf --plugin ocrmypdf_appleocr --help 2>&1 | grep -q appleocr && echo OK
```

## 快速上手

```bash
S=~/.agents/skills/pdf-ocr-searchable/scripts/ocr_pdf.sh

$S --check ~/Scans/            # 分诊：哪些文件真需要 OCR（按字数/页密度判定）
$S 论文.pdf                     # OCR → 论文.ocr.pdf（不覆盖原件）
$S --md 某本书.pdf              # 额外产出 某本书.md（整段正文 + 原书标题层级）
$S --preset deskew --lang chi_tra ~/Scans/   # 拍歪的繁体件，整目录批量
$S --help                      # 全部选项
```

### 预设（三档是真实取舍，不能兼得）

| `--preset` | 何时用 | 对原图 |
|---|---|---|
| `archive`（默认） | 档案/论文/合同 | 逐字节不变，只加文字层 |
| `deskew` | 手机拍的、扫歪的 | 栅格化以矫正倾斜 |
| `compact` | 只求体积小 | 重新编码，约省 15% |

### Markdown 输出（`--md`）

`pdf_to_md.py` 纯标准库、不经过任何模型：按行高+章节正则还原标题层级（部/章/节），按段首缩进把扫描换行并回整段（跨页续接），剔除书眉、页码、原书边码；目录页自动识别并降级。无缩进的西式版式自动退回块分段。

## 语言

`--lang` 默认 `chi_sim`；`chi_tra`/`eng`/`jpn`/`kor`，BCP-47 写法（`zh-Hans` 等）自动归一。`chi_sim+eng` 叠加不受插件支持且无必要——中文模型对页内英文实测识别正确（含索引页中英混排）。英文占比高的文档建议交付前抽查专有名词与参考文献。

## 已知限制

- livetext 模式经 PyObjC 调 VisionKit 私有类（`VKCImageAnalyzer`），macOS 更新可能打断——脚本会自动回退公开 API 的 `accurate` 模式（横排中英文输出实测与 livetext 逐字相同，差异仅在竖排 CJK）
- `mac-ocr searchable-pdf` 的文字层会丢英文词间空格，出可复制 PDF 一律走本脚本；`mac-ocr` 只用于把单图/单页直接吐成文字
- Markdown 中目录、索引页以正文段落保留，未专门排版；极少数跨块折行的长章题可能截断
- 空白页/识别失败与成功在退出码上无区别，靠脚本的字数验收（<20 字标 ⚠️）提示人工抽查

## 文件

```
SKILL.md              # Claude Code 触发入口
scripts/ocr_pdf.sh    # 主脚本：分诊/批量 OCR/验收/回退/增量
scripts/pdf_to_md.py  # PDF 文字层 → 层级化 Markdown（纯 stdlib）
```

## 致谢

- [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) — PDF OCR 管道（页面处理、文字层叠加、输出验证）
- [OCRmyPDF-AppleOCR](https://github.com/mkyt/OCRmyPDF-AppleOCR) — Apple Vision / Live Text 引擎插件
- [mac-ocr](https://github.com/privatenumber/mac-ocr) — 单图 OCR 伴侣工具
- [Poppler](https://poppler.freedesktop.org/) — `pdftotext -bbox-layout` 是 Markdown 重建的坐标来源

## 许可

[MIT](LICENSE)
