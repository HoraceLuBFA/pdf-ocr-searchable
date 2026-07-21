#!/usr/bin/env bash
# ocr_pdf.sh — 给扫描 PDF 叠加隐形文字层，使其可搜索、可复制。
# 引擎：Apple Vision（经 ocrmypdf-appleocr 插件），livetext 失效自动回退 accurate。
set -uo pipefail

OCRMYPDF="${OCRMYPDF:-$HOME/.local/bin/ocrmypdf}"
[[ -x "$OCRMYPDF" ]] || OCRMYPDF="$(command -v ocrmypdf || true)"

PRESET=archive
LANG_CODE=chi_sim
MODE=livetext
OUTDIR=""
SUFFIX=".ocr"
DRYRUN=0
FORCE=0
CHECK=0
MD=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
declare -a INPUTS=()

usage() {
  cat <<'EOF'
用法: ocr_pdf.sh [选项] <PDF 或目录> [更多...]

  --preset archive   保真优先（默认）。内嵌图像逐字节不变，仅叠加文字层
          deskew     先去斜再 OCR。适合手机拍歪的扫描件（会栅格化页面）
          compact    重压图像减小体积（会重新编码原图）
  --lang CODE        chi_sim(默认) | chi_tra | eng | jpn | kor ...
                     注意：AppleOCR 插件不支持 chi_sim+eng 叠加写法
  --mode M           livetext(默认) | accurate | fast
  --outdir DIR       输出目录（默认与源文件同目录）
  --suffix S         输出文件名后缀（默认 .ocr）
  --force            连已有文字层的页也重做 OCR
  --check            只分诊不 OCR：报告每个 PDF 是否已有文字层
  --md               另产出同名 .md 纯文字版（按行高+章节正则还原标题层级）；
                     源 PDF 已可复制时跳过 OCR 直接生成
  --dry-run          只打印将要执行的命令

已有 .ocr.pdf 且比源文件新时自动跳过 OCR（--force 除外），重出 md 不重跑识别。

示例:
  ocr_pdf.sh --check ~/Scans/          # 先看哪些需要处理
  ocr_pdf.sh --md 论文.pdf             # 可复制 PDF + Markdown 各一份
  ocr_pdf.sh --preset deskew --lang chi_tra ~/Scans/
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset) PRESET="$2"; shift 2 ;;
    --lang)   LANG_CODE="$2"; shift 2 ;;
    --mode)   MODE="$2"; shift 2 ;;
    --outdir) OUTDIR="$2"; shift 2 ;;
    --suffix) SUFFIX="$2"; shift 2 ;;
    --force)  FORCE=1; shift ;;
    --check)  CHECK=1; shift ;;
    --md)     MD=1; shift ;;
    --dry-run) DRYRUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "未知选项: $1" >&2; usage; exit 2 ;;
    *) INPUTS+=("$1"); shift ;;
  esac
done

[[ ${#INPUTS[@]} -eq 0 ]] && { usage; exit 2; }
[[ -x "$OCRMYPDF" ]] || { echo "找不到 ocrmypdf。安装：uv tool install --python 3.12 ocrmypdf --with ocrmypdf-appleocr" >&2; exit 127; }

# 语言码归一：插件只认 tesseract 风格，把常见 BCP-47 写法静默映射过去；
# 拦截 chi_sim+eng 叠加（插件不支持，且中文模型本就能识别页内英文）
case "$LANG_CODE" in
  *+*) echo "AppleOCR 插件不支持多语言叠加（${LANG_CODE}）。中文文档用 --lang chi_sim 即可，页内英文照样识别。" >&2; exit 2 ;;
  zh-Hans|zh-CN|zh|chs|chi) LANG_CODE=chi_sim ;;
  zh-Hant|zh-TW|zh-HK|cht)  LANG_CODE=chi_tra ;;
  en|en-US|en-GB)           LANG_CODE=eng ;;
  ja|ja-JP)                 LANG_CODE=jpn ;;
  ko|ko-KR)                 LANG_CODE=kor ;;
esac

# 预设 → ocrmypdf 旗标
declare -a PRESET_ARGS=()
case "$PRESET" in
  archive) PRESET_ARGS=(--output-type pdf --optimize 0) ;;
  deskew)  PRESET_ARGS=(--output-type pdf --optimize 0 --deskew) ;;
  compact) PRESET_ARGS=(--output-type pdf --optimize 1) ;;
  *) echo "未知预设: ${PRESET}（可选 archive|deskew|compact）" >&2; exit 2 ;;
esac
[[ $FORCE -eq 1 ]] && PRESET_ARGS+=(--force-ocr) || PRESET_ARGS+=(--skip-text)

# 展开目录为 PDF 列表
declare -a FILES=()
for item in "${INPUTS[@]}"; do
  if [[ -d "$item" ]]; then
    while IFS= read -r f; do FILES+=("$f"); done \
      < <(find "$item" -type f -iname '*.pdf' ! -iname "*${SUFFIX}.pdf" | sort)
  elif [[ -f "$item" ]]; then
    FILES+=("$item")
  else
    echo "跳过（不存在）: $item" >&2
  fi
done
[[ ${#FILES[@]} -eq 0 ]] && { echo "没有找到可处理的 PDF" >&2; exit 1; }

# 提取文字层字符数，用于分诊与产出验收
count_chars() {
  command -v pdftotext >/dev/null 2>&1 || { echo -1; return; }
  pdftotext "$1" - 2>/dev/null | tr -d '[:space:]' | wc -m | tr -d ' '
}

# --check：只分诊不 OCR。按「字数/页」密度分级——总字数会被元数据页/部分文字页
# 严重误导（常见于正文全是扫描图、但被注入了几千字元数据附件的电子书），
# 中文正文密度通常数百字/页，<30 字/页视为疑似扫描件
count_pages() {
  command -v pdfinfo >/dev/null 2>&1 && pdfinfo "$1" 2>/dev/null | awk '/^Pages:/{print $2}' && return
  command -v qpdf >/dev/null 2>&1 && qpdf --show-npages "$1" 2>/dev/null && return
  echo 0
}
if [[ $CHECK -eq 1 ]]; then
  NEED=0
  for src in "${FILES[@]}"; do
    n=$(count_chars "$src"); pg=$(count_pages "$src"); [[ $pg -le 0 ]] && pg=1
    per=$((n / pg))
    if [[ $n -le 0 ]]; then
      echo "NEED  0 字 / ${pg} 页，需要 OCR              : $src"; NEED=$((NEED+1))
    elif [[ $per -lt 30 ]]; then
      echo "NEED  ${n} 字 / ${pg} 页（约 ${per} 字/页，疑似扫描件）: $src"; NEED=$((NEED+1))
    else
      echo "HAS   ${n} 字 / ${pg} 页（约 ${per} 字/页，已可复制）  : $src"
    fi
  done
  echo; echo "共 ${#FILES[@]} 个，其中 ${NEED} 个需要 OCR"
  exit 0
fi

# 从带文字层的 PDF 生成层级化 Markdown（$1=PDF $2=输出 md）
gen_md() {
  local info
  info="$(python3 "$SCRIPT_DIR/pdf_to_md.py" "$1" -o "$2" 2>&1)" \
    && echo "  📄 $(basename "$2") ← ${info}" \
    || { echo "  ❌ Markdown 生成失败: ${info}"; FAIL=$((FAIL+1)); }
}

OK=0; FAIL=0; FELL_BACK=0
echo "预设=$PRESET  语言=$LANG_CODE  模式=$MODE  共 ${#FILES[@]} 个文件"
echo

for src in "${FILES[@]}"; do
  base="$(basename "${src%.*}")"
  dir="${OUTDIR:-$(dirname "$src")}"
  mkdir -p "$dir"
  dst="$dir/${base}${SUFFIX}.pdf"

  declare -a CMD=("$OCRMYPDF" --plugin ocrmypdf_appleocr
                  --appleocr-recognition-mode "$MODE"
                  -l "$LANG_CODE" "${PRESET_ARGS[@]}" "$src" "$dst")

  if [[ $DRYRUN -eq 1 ]]; then printf '%q ' "${CMD[@]}"; echo; continue; fi

  # 增量：产物已存在且比源新则不重跑 OCR（--force 除外）
  if [[ $FORCE -eq 0 && -f "$dst" && "$dst" -nt "$src" ]]; then
    echo "  ⏭️  $base → 已有产物且比源文件新，跳过 OCR"
    OK=$((OK+1))
    [[ $MD -eq 1 ]] && gen_md "$dst" "$dir/${base}.md"
    continue
  fi

  # 源 PDF 已可复制（与 --check 同判据：≥30 字/页）：无需 OCR，
  # --md 时直接从源生成 Markdown
  if [[ $FORCE -eq 0 ]]; then
    n=$(count_chars "$src"); pg=$(count_pages "$src"); [[ $pg -le 0 ]] && pg=1
    if [[ $n -gt 0 && $((n / pg)) -ge 30 ]]; then
      echo "  ✅ $base → 已可复制（约 $((n / pg)) 字/页），无需 OCR"
      OK=$((OK+1))
      [[ $MD -eq 1 ]] && gen_md "$src" "$dir/${base}.md"
      continue
    fi
  fi

  before=$(count_chars "$src")
  err="$("${CMD[@]}" 2>&1 >/dev/null)"; rc=$?

  # livetext 走的是 VisionKit 私有类，macOS 更新可能打断 —— 回退纯公开 API
  if [[ $rc -ne 0 && "$MODE" == "livetext" ]]; then
    if grep -qiE 'VKCImageAnalyzer|lookUpClass|ImageAnalyzer|Timeout' <<<"$err"; then
      echo "  ⚠️  livetext 不可用，回退 accurate 模式重试"
      CMD=("$OCRMYPDF" --plugin ocrmypdf_appleocr --appleocr-recognition-mode accurate
           -l "$LANG_CODE" "${PRESET_ARGS[@]}" "$src" "$dst")
      err="$("${CMD[@]}" 2>&1 >/dev/null)"; rc=$?
      [[ $rc -eq 0 ]] && FELL_BACK=$((FELL_BACK+1))
    fi
  fi

  if [[ $rc -eq 0 ]]; then
    after=$(count_chars "$dst")
    gained=$((after - before))
    if [[ $before -gt 0 && $gained -le 0 ]]; then
      echo "  ✅ $base → 原本已有文字层，按 --skip-text 跳过（${after} 字）"
    elif [[ $after -lt 20 ]]; then
      echo "  ⚠️  $base → 只识别出 ${after} 字，疑似空白页或识别失败，请人工抽查"
    else
      echo "  ✅ $base → 新增 ${gained} 字，共 ${after} 字"
    fi
    OK=$((OK+1))
    [[ $MD -eq 1 ]] && gen_md "$dst" "$dir/${base}.md"
  else
    echo "  ❌ $base → 失败 (rc=$rc)"
    sed 's/^/       /' <<<"$err" | tail -4
    FAIL=$((FAIL+1))
  fi
done

echo
echo "完成：成功 ${OK}，失败 ${FAIL}$([[ $FELL_BACK -gt 0 ]] && echo "，其中 ${FELL_BACK} 个回退到 accurate 模式")"
[[ $FAIL -gt 0 ]] && exit 1 || exit 0
