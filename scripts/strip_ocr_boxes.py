#!/usr/bin/env python3
"""strip_ocr_boxes.py — 删除 AppleOCR 文字层里硬编码的红色调试框。

背景（2026-09 实测，插件 0.3.4）：
  ocrmypdf_appleocr/pdf.py 在生成文字层时为**每一个识别文本行**追加一段
      q  1 0 0 RG  0.75 w  <四点多边形>  h  S  Q
  纯红描边框；其上层 __init__.py 调用 generate_pdf(..., boxes=True) 把这个行为
  硬打开，三种识别模式共用此生成入口；本机中文运行验证覆盖 livetext / accurate。

  对普通灰度/彩色扫描页，红框被页面图像盖住，多数情况下看不见；
  但对 1-bit ImageMask 扫描件（纸面透明，墨迹按当前填充色画出）红框会从底下
  透出来 —— 整页文字因此套上红框。

仅处理 OCRmyPDF 的 /OCR- Form，验证 GlyphLessFont 和整条指令序列后，
删除紧随隐形文字的已知调试框。普通页面及其他 Form 不参与删除。
无框不写盘；临时产物验收后原子替换。
PDF 容器会重写，不承诺文件级字节不变。适用版本及限制见 references/red-boxes.md。

用法:
  strip_ocr_boxes.py [--check] [--quiet] FILE.pdf [FILE2.pdf ...]
    --check   只检测不修改
    --quiet   无红框时不输出
退出码: 0 成功；1 有文件处理失败。
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import zlib

import pikepdf

# 仅匹配本机 AppleOCR 0.3.4 的固定绘图序列，不泛化成红色图形删除器。
RED_BOX = re.compile(
    rb"(?m)^q\s*\n" rb"\s*1 0 0 RG\s*\n" rb"\s*0\.75 w\s*\n"
    rb"\s*[-\d.]+ [-\d.]+ m\s*\n"
    rb"(?:\s*[-\d.]+ [-\d.]+ l\s*\n){3}" rb"\s*h\s*\n" rb"\s*S\s*\n" rb"\s*Q(?:\s*\n|$)"
)


def iter_candidate_streams(pdf):
    """只选 OCRmyPDF 命名的 OCR Form；遍历嵌套资源并去重。"""
    seen = set()

    def usable(obj):
        return isinstance(obj, pikepdf.Stream) and obj.objgen not in seen

    def walk(resources):
        if resources is None:
            return
        xobjects = resources.get("/XObject")
        if xobjects is None or not isinstance(xobjects, pikepdf.Dictionary):
            return
        for name, obj in xobjects.items():
            if not usable(obj) or obj.get("/Subtype") != pikepdf.Name("/Form"):
                continue
            seen.add(obj.objgen)
            if str(name).startswith("/OCR-"):
                yield obj
            yield from walk(obj.get("/Resources"))

    for page in pdf.pages:
        yield from walk(page.get("/Resources"))


def cleaned_stream(stream):
    """校验整条 OCR 指令序列，再仅删除框的原始字节，保留文本字节。"""
    data = stream.read_bytes()  # 解码失败必须上报，不能当作已检查且干净。
    fonts = stream.get("/Resources", {}).get("/Font", {})
    font = fonts.get("/f-0-0", {})
    if font.get("/BaseFont") != pikepdf.Name("/GlyphLessFont"):
        raise RuntimeError("OCR Form 字体不符合已验证的 AppleOCR 格式，未修改")
    ops = list(pikepdf.parse_content_stream(stream))
    names = [str(i.operator) for i in ops]
    expected = []
    count = 0
    if not names or names[0] != "q" or names[-1] != "Q":
        raise RuntimeError("OCR Form 结构未知，未修改")
    expected.append(ops[0])
    pos = 1
    while pos < len(ops) - 1:
        text_ops = ops[pos:pos + 9]
        if names[pos:pos + 9] != ["BT", "BDC", "Tr", "Tm", "Tf", "Tz", "TJ", "EMC", "ET"]:
            raise RuntimeError("OCR Form 混有未知内容，未修改")
        if (list(text_ops[2].operands) != [3]
                or list(text_ops[4].operands) != [pikepdf.Name('/f-0-0'), 1]):
            raise RuntimeError("OCR 文字格式未知，未修改")
        expected.extend(text_ops)
        pos += 9
        if names[pos:pos + 10] == ["q", "RG", "w", "m", "l", "l", "l", "h", "S", "Q"]:
            if list(ops[pos + 1].operands) != [1, 0, 0] or list(ops[pos + 2].operands) != [0.75]:
                raise RuntimeError("OCR 描边格式未知，未修改")
            pos += 10
            count += 1
    if pos != len(ops) - 1:
        raise RuntimeError("OCR Form 结尾异常，未修改")
    expected.append(ops[-1])
    new, n = RED_BOX.subn(b"", data)
    if n != count:
        raise RuntimeError("红框字节匹配与 PDF 指令不一致，未修改")
    # 防止正则误命中文字字符串等非绘图数据。
    probe = pikepdf.Pdf.new()
    parsed = pikepdf.parse_content_stream(probe.make_stream(new))
    if pikepdf.unparse_content_stream(parsed) != pikepdf.unparse_content_stream(expected):
        raise RuntimeError("清理改变了预期之外的 PDF 指令，未修改")
    return new, n


def digest(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def has_signature(pdf):
    """含实际签名值才拒绝；普通表单及未签名的签名域可以保留。"""
    objects = list(pdf.objects)
    fields = list(pdf.Root.get('/AcroForm', {}).get('/Fields', []))
    visited = set()
    while fields:
        field = fields.pop()
        if not isinstance(field, pikepdf.Dictionary):
            continue
        ident = field.objgen if field.is_indirect else id(field)
        if ident in visited:
            continue
        visited.add(ident)
        objects.append(field)
        fields.extend(field.get('/Kids', []))
    for obj in objects:
        if not isinstance(obj, pikepdf.Dictionary):
            continue
        if obj.get('/Type') == pikepdf.Name('/Sig') or ('/ByteRange' in obj and '/Contents' in obj):
            return True
        if obj.get('/V') is None:
            continue
        field = obj
        seen = set()
        while isinstance(field, pikepdf.Dictionary):
            if field.get('/FT') is not None:
                if field.get('/FT') == pikepdf.Name('/Sig'):
                    return True
                break
            ident = field.objgen
            if ident in seen:
                break
            seen.add(ident)
            field = field.get('/Parent')
    return False


def read_xattrs(path):
    """macOS Python 未必有 os.listxattr；使用系统 CLI，失败即报错。"""
    if sys.platform != 'darwin':
        return {}
    names = subprocess.check_output(['/usr/bin/xattr', path], text=True).splitlines()
    return {name: ''.join(subprocess.check_output(
        ['/usr/bin/xattr', '-px', name, path], text=True).split()) for name in names}


def copy_xattrs(attrs, path):
    if sys.platform != 'darwin':
        return
    for name, value in attrs.items():
        subprocess.run(['/usr/bin/xattr', '-wx', name, value, path], check=True, capture_output=True)
    if read_xattrs(path) != attrs:
        raise RuntimeError('扩展属性复制校验失败，未覆盖输入')


def strip_pdf(path, check_only=False, quiet=False):
    """返回 (状态字符串, 是否已修改)。"""
    path = os.path.realpath(path)
    original_hash = digest(path)
    with pikepdf.open(path) as pdf:
        total = 0
        touched = 0
        for stream in iter_candidate_streams(pdf):
            new, n = cleaned_stream(stream)
            if not n:
                continue
            total += n
            touched += 1
            if not check_only:
                # 注意：pikepdf 的 write(data, filter=...) 要求 data 已经按该 filter
                # 编码过，所以这里自己 deflate，不能直接传明文
                stream.write(zlib.compress(new), filter=pikepdf.Name("/FlateDecode"))

        if total == 0:
            if not quiet:
                print(f"{path}: 未发现可识别的 AppleOCR 调试框（不排除其他来源的红框）")
            return "clean", False
        if check_only:
            print(f"{path}: 发现 {total} 处红框（{touched} 个内容流），未修改")
            return "found", False

        directory = os.path.dirname(os.path.abspath(path))
        fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=directory)
        os.close(fd)
        try:
            if pdf.is_encrypted or has_signature(pdf):
                raise RuntimeError("加密或已签名的 PDF 不适用此修复，未修改")
            pdf.save(
                tmp,
                compress_streams=False,
                recompress_flate=False,
                object_stream_mode=pikepdf.ObjectStreamMode.preserve,
            )
            with pikepdf.open(tmp) as saved:
                if len(saved.pages) != len(pdf.pages) or saved.check_pdf_syntax():
                    raise RuntimeError("临时产物结构验收失败，未修改")
                if any(cleaned_stream(s)[1] for s in iter_candidate_streams(saved)):
                    raise RuntimeError("临时产物仍有调试框，未修改")
            if digest(path) != original_hash:
                raise RuntimeError("输入文件已被其他进程改变，未覆盖")
            attrs = read_xattrs(path)
            os.chmod(tmp, os.stat(path).st_mode & 0o777)
            copy_xattrs(attrs, tmp)
            if digest(path) != original_hash or read_xattrs(path) != attrs:
                raise RuntimeError("输入内容或扩展属性已改变，未覆盖")
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
    print(f"{path}: 已删除 {total} 处红框（{touched} 个文字层内容流），文字层保留")
    return "fixed", True


def main():
    ap = argparse.ArgumentParser(description="删除 AppleOCR 文字层中的红色调试框")
    ap.add_argument("--check", action="store_true", help="只检测不修改")
    ap.add_argument("--quiet", action="store_true", help="无红框时不输出")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()

    failed = 0
    for path in args.files:
        try:
            strip_pdf(path, check_only=args.check, quiet=args.quiet)
        except Exception as exc:  # noqa: BLE001 — 逐文件报告，不中断其余文件
            print(f"{path}: 处理失败: {exc}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
