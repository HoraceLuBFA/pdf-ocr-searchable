# pdf-ocr-searchable

在 Mac 上把扫描版 PDF 转为**可搜索、可复制的文档**，并按需提取为 Markdown。基于 Apple Vision / Live Text，本地离线处理，适合论文、书籍和扫描资料整理。

可作为 Agent Skill 使用，也可直接运行命令行脚本。[下载 V1.0.1](https://github.com/HoraceLuBFA/pdf-ocr-searchable/releases/tag/V1.0.1)

## 功能

- **可搜索 PDF**：保留页面版式，添加隐形文字层；默认保真模式不重新编码扫描图像。
- **Markdown 提取**：根据文字位置和章节特征整理标题、段落，合并扫描换行并过滤部分页眉、页码；已有文字层的 PDF 可直接提取。
- **多语言识别**：支持简体中文、繁体中文、英文、日文、韩文等，具体支持范围取决于识别模式和系统环境。
- **批量与增量处理**：支持多个文件及目录输入；已有较新产物时跳过重复 OCR。
- **保真、去斜与压缩**：按资料用途选择处理预设。
- **自动红框修复**：清理受支持的 AppleOCR 调试框，也可单独修复已有产物，并保留文件权限及 macOS Finder 标签等扩展属性。

## 安装

需要 macOS、[Homebrew](https://brew.sh/) 和 [uv](https://docs.astral.sh/uv/)。通过 skills CLI 安装还需 Node.js / npx。Live Text 模式依赖系统支持；如不可用，可选择 `--mode accurate`。

### 安装 Skill

通过 [skills CLI](https://skills.sh) 安装，并按提示选择使用的 Agent：

```bash
npx skills add HoraceLuBFA/pdf-ocr-searchable
```

也可克隆仓库到一个尚不存在的目录，作为独立命令行工具使用：

```bash
git clone https://github.com/HoraceLuBFA/pdf-ocr-searchable.git
cd pdf-ocr-searchable
bash scripts/ocr_pdf.sh --help
```

### 安装依赖

OCRmyPDF 与 AppleOCR 插件需安装在同一 Python 环境。以下命令使用 Python 3.12：

```bash
uv tool install --python 3.12 ocrmypdf --with ocrmypdf-appleocr
brew install ghostscript poppler
```

检查插件是否可用：

```bash
ocrmypdf --plugin ocrmypdf_appleocr --help 2>&1 | grep -q appleocr && echo OK
```

## 快速上手

以下示例以 Skill 安装在 `~/.agents/skills/pdf-ocr-searchable` 为例；如安装到其他位置，请相应修改路径。

```bash
S=~/.agents/skills/pdf-ocr-searchable/scripts/ocr_pdf.sh

# 检查文件是否需要 OCR
"$S" --check "论文.pdf"

# 生成 论文.ocr.pdf，保留原件
"$S" "论文.pdf"

# 同时输出 论文.md
"$S" --md "论文.pdf"

# 批量处理目录中的 PDF
"$S" ~/Scans/

# 去斜并识别繁体中文
"$S" --preset deskew --lang chi_tra "扫描件.pdf"
```

已有文字层的 PDF 会按脚本的文字密度判据跳过 OCR；使用 `--md` 时直接提取 Markdown。已有输出文件比原件新时会复用该产物。需要重新识别或更换处理参数时使用 `--force`，它会重做已有文字层并重写目标产物。

## 选择处理方式

| 预设 | 适用需求 | 图像处理 |
|---|---|---|
| `archive`（默认） | 论文、书籍、档案留存 | 保留扫描图像，不重新编码 |
| `deskew` | 扫歪或拍歪的页面 | 栅格化页面并矫正倾斜 |
| `compact` | 优先控制文件体积 | 尝试优化、重新编码图像，压缩效果取决于原文件 |

```bash
"$S" --preset compact "资料.pdf"
```

默认输出到原文件所在目录，以 `.ocr.pdf` 结尾。可用 `--outdir` 指定输出目录，或用 `--suffix` 修改后缀：

```bash
"$S" --outdir "./output" --suffix ".searchable" "资料.pdf"
```

## 语言与识别模式

默认语言为简体中文 `chi_sim`，可通过 `--lang` 指定：

| 语言 | 参数 |
|---|---|
| 简体中文 | `chi_sim` 或 `zh-Hans` |
| 繁体中文 | `chi_tra` 或 `zh-Hant` |
| 英文 | `eng` 或 `en` |
| 日文 | `jpn` 或 `ja` |
| 韩文 | `kor` 或 `ko` |

不支持 `chi_sim+eng` 形式的语言叠加。中文模型可识别部分页内英文，英文占比较高时请抽查专有名词和参考文献。

`--mode` 可选 `livetext`（默认）、`accurate`、`fast`。部分 Live Text 故障会自动回退到 `accurate`；也可直接指定该模式。`fast` 的语言支持范围较窄，不适合中文文档。

```bash
"$S" --lang eng --mode accurate "paper.pdf"
```

## 修复 OCR 调试红框

OCR 后会自动清理受支持的 AppleOCR 调试框。处理已有产物时，直接指定要修复的 PDF：

```bash
# 只检测，不修改
"$S" --strip-boxes --dry-run "论文.ocr.pdf"

# 修复该文件
"$S" --strip-boxes "论文.ocr.pdf"

# 批量修复目录中的 *.ocr.pdf
"$S" --strip-boxes ~/Scans/
```

修复支持普通表单和未签名的签名域，不改写加密或已签名文件。清理失败会报告错误，并停止该文件后续 Markdown 生成。适用格式与排查方法见[红框兼容性说明](references/red-boxes.md)。

## 使用提示

- OCR 和 Markdown 排版还原可能存在误差，重要内容请对照原页核查。目录、索引和复杂标题尤其需要检查。
- `--check` 根据文字密度判断是否需要 OCR；少量文字页和扫描页混排时，仍需抽查正文。
- 识别字数很少时脚本会提示人工检查；命令成功退出不代表所有页面都识别正确。
- 默认模式保留扫描图像，但 PDF 容器会重写，不保证整份文件字节不变。需要保留原始文件时，请留存源 PDF。
- 红框清理针对已知 AppleOCR 格式；插件升级后若提示格式不兼容，请参阅兼容性说明。

全部参数可运行 `"$S" --help` 查看。

## 项目文件

```text
SKILL.md                    # Agent 技能入口
scripts/ocr_pdf.sh          # PDF OCR 与批量处理入口
scripts/pdf_to_md.py        # PDF 文字层转 Markdown
scripts/strip_ocr_boxes.py  # AppleOCR 调试红框修复
references/red-boxes.md     # 修复边界与排查
tests/test_red_boxes.py     # 修复功能回归测试
```

## 致谢

- [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF)：PDF OCR 处理管道。
- [OCRmyPDF-AppleOCR](https://github.com/mkyt/OCRmyPDF-AppleOCR)：Apple Vision / Live Text 引擎插件。
- [mac-ocr](https://github.com/privatenumber/mac-ocr)：可选的单图 OCR 工具。
- [Poppler](https://poppler.freedesktop.org/)：PDF 文字和页面布局提取。

## 许可

[MIT](LICENSE)
