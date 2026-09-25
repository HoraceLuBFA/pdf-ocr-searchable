# AppleOCR 红框兼容性与排查

## 适用证据

2026-09-21 本机核对 AppleOCR 0.3.4：`__init__.py` 的 PDF 生成入口调用 `generate_pdf(..., True)`；`pdf.py` 给每个文字行生成隐形文字及纯红、0.75 pt 的四边形。三种模式共用该生成入口；原故障日志实际完成了 livetext、accurate 中文对照，fast 中文因不支持该语言而失败，不能称为三种模式均完成实测。1-bit ImageMask 页面透明区域会露出下层红框。

这是已验证版本的兼容性修复，不代表未来版本或所有 PDF 红框都有相同成因。

## 修复边界

- 仅处理 OCRmyPDF 命名为 `/OCR-…` 的 Form XObject，并验证 `/f-0-0` GlyphLessFont、完整隐形文字指令序列及每行紧随的固定调试框。普通页面内容、其他 Form 和批注不作为删除目标。
- 删除前后对比 PDF 指令，仅移除已识别框，保留其他原始内容字节；未知 OCR Form、解码或临时产物验证失败均报错，不自动放宽匹配。
- 正式保存会重写 PDF 容器；不承诺整份文件或历史增量对象字节不变。加密或已有实际签名值的文件不执行修复；普通表单和未签名的签名域保留。
- 临时产物通过结构与清理结果验收后原子替换目标；无框不写盘。
- 原子替换前保留文件权限；macOS 使用系统 `xattr` 复制并核验扩展属性（包括 Finder 标签），复制失败不替换输入。不承诺 ACL、所有者或其他文件系统元数据全部保持。

## 旧产物

```bash
S=~/.agents/skills/pdf-ocr-searchable/scripts/ocr_pdf.sh
"$S" --strip-boxes --dry-run "书名.ocr.pdf"
"$S" --strip-boxes "书名.ocr.pdf"
"$S" --strip-boxes /path/to/output-directory
```

显式文件参数直接指向待修复 PDF，不再从原件猜测兄弟文件。目录递归选择 `*<suffix>.pdf`，默认 `*.ocr.pdf`，即使原件不存在也能修复。不能与 `--check`、`--md`、`--force`、`--outdir` 混用。

自动 OCR 路径清理失败时会保留当前产物并计为失败，不继续生成该文件的 Markdown；排查后可重新运行修复。

## 验证与升级

比较修复前后文件的 `pdftotext` 全文、页数及图像原始流哈希；在原问题页渲染足够分辨率的局部，确认红框消失且扫描内容保留。扫描图原始流可用 pikepdf `read_raw_bytes()` 核对。保存参数避免重压已有图像，但参数本身不替代产物比较。

升级插件后若结构未知，先核对实际插件源码及小样，不能把签名任意放宽成“删掉所有纯红图形”。参考 [pikepdf 内容流解析](https://pikepdf.readthedocs.io/en/latest/api/filters.html) 与 [保存参数](https://pikepdf.readthedocs.io/en/stable/api/main.html)。

维护者回归：使用 OCRmyPDF 环境的 Python 运行 `tests/test_red_boxes.py`，需要已有插件、pikepdf、Pillow 与 poppler。八项测试以插件真实文字层生成器创建临时小样，覆盖文本/图像保留、合法红图形及渲染差异、幂等、目录、只读预演、失败传播、普通表单/签名保护，以及 macOS 权限与 Finder 标签；它不替代 Apple Vision 识别链路的端到端测试。

尚未复现或测量的限制：若系统为临时文件新增源文件没有的扩展属性，当前严格相等校验可能拒绝替换；本机尚未复现，发生时先比对实际属性，不预先忽略差异。签名检测仅在确有调试框需要删除时遍历 PDF 对象，整书带框文件的额外耗时尚未单独测量；干净文件不会进入该步骤。这两项暂不据此修改实现。
