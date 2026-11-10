# pdf-ocr-searchable

Turn scanned PDFs on a Mac into **searchable documents with selectable, copyable text**, and extract Markdown when needed. Processing runs locally and offline through Apple Vision / Live Text, for papers, books, and scanned reference material.

Use it as an Agent Skill or run the command-line scripts directly. [Release V1.0.1](https://github.com/HoraceLuBFA/pdf-ocr-searchable/releases/tag/V1.0.1) was published on 2026-09-25.

**English | [中文](./README.md)**

## Features

- **Searchable PDFs**: preserve page layout and add an invisible text layer. The default preservation preset does not re-encode scanned images.
- **Markdown extraction**: organize headings and paragraphs from text positions and section features, join scanned line breaks, and filter some headers, footers, and page numbers. PDFs with an existing text layer can be extracted directly.
- **Multiple languages**: support Simplified Chinese, Traditional Chinese, English, Japanese, Korean, and other languages, subject to the recognition mode and system environment.
- **Batch and incremental processing**: accept multiple files and directories, and skip repeated OCR when newer outputs already exist.
- **Preservation, deskewing, and compression**: choose a processing preset for the material's intended use.
- **Automatic red-box repair**: remove supported AppleOCR debugging boxes, including from existing outputs, while preserving file permissions and extended attributes such as macOS Finder tags.

## Installation

Requires macOS, [Homebrew](https://brew.sh/), and [uv](https://docs.astral.sh/uv/). The skills CLI route also requires Node.js / npx. Live Text depends on system support; if unavailable, select `--mode accurate`.

### Install the skill

Use the [skills CLI](https://skills.sh) and select the host you use:

```bash
npx skills add -g HoraceLuBFA/pdf-ocr-searchable
```

For a manual installation, inspect any existing installation before cloning into the shared directory:

```bash
git clone https://github.com/HoraceLuBFA/pdf-ocr-searchable.git ~/.agents/skills/pdf-ocr-searchable
bash ~/.agents/skills/pdf-ocr-searchable/scripts/ocr_pdf.sh --help
```

### Website package and installation guide

The [detail page](https://www.lumenghe.com/en/skills/pdf-ocr-searchable/) provides bilingual documentation and a complete ZIP. See [INSTALL.en.md](./INSTALL.en.md) for installation and verification; the [plain-text guide](https://www.lumenghe.com/en/skills/pdf-ocr-searchable/install.txt) lists the current package URL and SHA-256. Package files match the stated GitHub source commit.

### Install dependencies

OCRmyPDF and the AppleOCR plugin must be installed in the same Python environment. These commands use Python 3.12:

```bash
uv tool install --python 3.12 ocrmypdf --with ocrmypdf-appleocr
brew install ghostscript poppler
```

Check that the plugin is available:

```bash
ocrmypdf --plugin ocrmypdf_appleocr --help 2>&1 | grep -q appleocr && echo OK
```

## Quick start

These examples assume the skill is installed at `~/.agents/skills/pdf-ocr-searchable`. If you use the scripts independently from another location, adjust the paths accordingly.

```bash
S=~/.agents/skills/pdf-ocr-searchable/scripts/ocr_pdf.sh

# Check whether a file needs OCR
"$S" --check "论文.pdf"

# Create 论文.ocr.pdf and retain the original
"$S" "论文.pdf"

# Also produce 论文.md
"$S" --md "论文.pdf"

# Process PDFs in a directory
"$S" ~/Scans/

# Deskew and recognize Traditional Chinese
"$S" --preset deskew --lang chi_tra "扫描件.pdf"
```

The script uses a text-density criterion to skip OCR for PDFs that already contain a text layer; with `--md`, it extracts Markdown directly. An existing output newer than the source is reused. Use `--force` to recognize the document again or change processing parameters; this redoes an existing text layer and rewrites the target output.

## Choose a processing preset

| Preset | Intended use | Image processing |
|---|---|---|
| `archive` (default) | Preserve papers, books, and archival material | Retain scanned images without re-encoding |
| `deskew` | Correct tilted scans or photographs | Rasterize pages and correct their rotation |
| `compact` | Prioritize a smaller file | Attempt optimization and image re-encoding; results depend on the input |

```bash
"$S" --preset compact "资料.pdf"
```

By default, outputs are written beside the original with the suffix `.ocr.pdf`. Use `--outdir` to choose a destination or `--suffix` to change the suffix:

```bash
"$S" --outdir "./output" --suffix ".searchable" "资料.pdf"
```

## Languages and recognition modes

The default language is Simplified Chinese, `chi_sim`. Select a language with `--lang`:

| Language | Parameter |
|---|---|
| Simplified Chinese | `chi_sim` or `zh-Hans` |
| Traditional Chinese | `chi_tra` or `zh-Hant` |
| English | `eng` or `en` |
| Japanese | `jpn` or `ja` |
| Korean | `kor` or `ko` |

Choose one language from the table for each `--lang` argument. Chinese models may recognize some English within a page; spot-check proper names and references when a document contains substantial English.

`--mode` accepts `livetext` (default), `accurate`, or `fast`. Some Live Text failures automatically fall back to `accurate`, which you can also select directly. `fast` supports fewer languages and is unsuitable for Chinese documents.

```bash
"$S" --lang eng --mode accurate "paper.pdf"
```

## Repair OCR debugging boxes

After OCR, supported AppleOCR debugging boxes are removed automatically. To repair an existing output, specify the PDF directly:

```bash
# Detect only; do not modify the file
"$S" --strip-boxes --dry-run "论文.ocr.pdf"

# Repair this file
"$S" --strip-boxes "论文.ocr.pdf"

# Repair *.ocr.pdf files in a directory
"$S" --strip-boxes ~/Scans/
```

The repair supports ordinary form fields and unsigned signature fields; encrypted or signed files retain their original content. If cleanup fails, the script reports an error and stops subsequent Markdown generation for that file. See [red-box compatibility and troubleshooting](references/red-boxes.md) for supported formats and diagnostic steps.

## Usage notes

- OCR and Markdown layout reconstruction may contain errors. Check important content against the original pages, especially contents lists, indexes, and complex headings.
- `--check` determines whether OCR is needed from text density. Spot-check the body when pages with little text are mixed with scanned pages.
- The script prompts for review when very few characters are recognized. Spot-check body text, proper names and references during acceptance.
- The default preset preserves scanned images and rewrites the PDF container. Retain the source PDF as the original.
- Red-box cleanup targets known AppleOCR formats. If a plugin update triggers a format-compatibility warning, consult the compatibility guide.

Run `"$S" --help` to see all parameters.

## Project files

```text
SKILL.md                    # Agent skill entry point
scripts/ocr_pdf.sh          # PDF OCR and batch-processing entry point
scripts/pdf_to_md.py        # Convert a PDF text layer into Markdown
scripts/strip_ocr_boxes.py  # Repair AppleOCR debugging boxes
references/red-boxes.md     # Repair boundaries and troubleshooting
tests/test_red_boxes.py     # Regression tests for red-box repair
```

## Acknowledgments

- [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF): the PDF OCR processing pipeline.
- [OCRmyPDF-AppleOCR](https://github.com/mkyt/OCRmyPDF-AppleOCR): the Apple Vision / Live Text engine plugin.
- [mac-ocr](https://github.com/privatenumber/mac-ocr): an optional OCR tool for individual images.
- [Poppler](https://poppler.freedesktop.org/): PDF text and page-layout extraction.

## License

[MIT](LICENSE)
