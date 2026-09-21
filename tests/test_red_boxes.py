"""Run with the OCRmyPDF environment's Python. Fixtures stay in a temporary directory."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import pikepdf
from ocrmypdf_appleocr.common import BoundingBox, Point, Textbox
from ocrmypdf_appleocr.pdf import generate_pdf

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('stripper', ROOT / 'scripts/strip_ocr_boxes.py')
stripper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stripper)
SHELL = ROOT / 'scripts/ocr_pdf.sh'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(path):
    return subprocess.check_output(['pdftotext', str(path), '-'])


def images(path):
    with pikepdf.open(path) as pdf:
        return sorted(hashlib.sha256(o.read_raw_bytes()).hexdigest()
                      for o in pdf.objects if isinstance(o, pikepdf.Stream)
                      and o.get('/Subtype') == pikepdf.Name.Image)


class RedBoxes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        layer = self.d / 'layer.pdf'
        box = BoundingBox(Point(20, 20), Point(180, 20), Point(20, 45), Point(180, 45))
        generate_pdf((72, 72), 240, 120, 1.0,
                     [Textbox('中文 OCR preservation', box, 100, False)], layer, True)
        self.path = self.d / 'book.ocr.pdf'
        with pikepdf.open(layer) as src, pikepdf.Pdf.new() as pdf:
            page = pdf.add_blank_page(page_size=(240, 120))
            form = pdf.copy_foreign(src.pages[0].as_form_xobject())
            mask = pdf.make_stream(b'\xaa' * 8)
            mask.Type = pikepdf.Name.XObject
            mask.Subtype = pikepdf.Name.Image
            mask.Width = 8
            mask.Height = 8
            mask.BitsPerComponent = 1
            mask.ImageMask = True
            page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary({'/OCR-test': form, '/Mask': mask}))
            # A legitimate red rectangle in the page, with a nearby invisible text marker.
            page.Contents = pdf.make_stream(b'q /OCR-test Do Q\nq 8 0 0 8 210 10 cm /Mask Do Q\nBT 3 Tr ET\nq\n1 0 0 RG\n0.75 w\n10 10 m\n30 10 l\n30 30 l\n10 30 l\nh\nS\nQ\n')
            pdf.save(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def run_shell(self, *args):
        return subprocess.run(['bash', str(SHELL), *map(str, args)], capture_output=True, text=True)

    def test_repair_preserves_content_and_is_idempotent(self):
        original = sha(self.path)
        before_text, before_images = text(self.path), images(self.path)
        with pikepdf.open(self.path) as pdf:
            page_bytes = pdf.pages[0].Contents.read_bytes()
        self.assertEqual(stripper.strip_pdf(self.path), ('fixed', True))
        self.assertEqual(sha(Path(str(self.path) + '.bak-redbox')), original)
        self.assertEqual(text(self.path), before_text)
        self.assertEqual(images(self.path), before_images)
        with pikepdf.open(self.path) as pdf:
            self.assertEqual(pdf.pages[0].Contents.read_bytes(), page_bytes)
            self.assertEqual(sum(stripper.cleaned_stream(s)[1] for s in stripper.iter_candidate_streams(pdf)), 0)
        clean = sha(self.path)
        self.assertEqual(stripper.strip_pdf(self.path), ('clean', False))
        self.assertEqual(sha(self.path), clean)

    def test_directory_dry_run_and_orphan_product(self):
        original = sha(self.path)
        result = self.run_shell('--strip-boxes', '--dry-run', self.d)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sha(self.path), original)
        self.assertFalse(Path(str(self.path) + '.bak-redbox').exists())
        result = self.run_shell('--strip-boxes', self.d)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(sha(self.path), original)

    def test_unknown_form_fails_without_mutation(self):
        altered = self.d / 'unknown.ocr.pdf'
        with pikepdf.open(self.path) as pdf:
            form = pdf.pages[0].Resources.XObject['/OCR-test']
            form.write(form.read_bytes().replace(b'0.75 w', b'2 w'))
            pdf.save(altered)
        original = sha(altered)
        result = self.run_shell('--strip-boxes', altered)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sha(altered), original)
        # Incremental OCR path must also report cleanup failure.
        source = self.d / 'unknown.pdf'
        shutil.copy2(self.d / 'layer.pdf', source)
        os.utime(source, (1, 1))
        result = self.run_shell(source)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('成功 0，失败 1', result.stdout)

    def test_conflicting_flags_are_rejected(self):
        original = sha(self.path)
        result = self.run_shell('--strip-boxes', '--check', self.path)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(sha(self.path), original)

    def test_stale_backup_does_not_block_new_ocr(self):
        stripper.strip_pdf(self.path)
        backup = Path(str(self.path) + '.bak-redbox')
        old_hash = sha(backup)
        replacement = self.d / 'replacement.pdf'
        with pikepdf.open(backup) as pdf:
            pdf.docinfo['/Subject'] = 'New OCR run'
            pdf.save(replacement)
        shutil.copyfile(replacement, self.path)
        new_hash = sha(self.path)
        self.assertNotEqual(old_hash, new_hash)
        self.assertEqual(stripper.strip_pdf(self.path), ('fixed', True))
        self.assertEqual(sha(backup), old_hash)
        self.assertEqual(sha(Path(str(backup) + '.' + new_hash)), new_hash)

    def test_normal_forms_and_unsigned_signature_fields_survive(self):
        for kind in ('/Tx', '/Sig'):
            with self.subTest(kind=kind):
                candidate = self.d / (kind[1:] + '.pdf')
                with pikepdf.open(self.path) as pdf:
                    field = pikepdf.Dictionary(FT=pikepdf.Name(kind), T='test-field')
                    if kind == '/Tx':
                        field.V = 'retained value'
                    pdf.Root.AcroForm = pikepdf.Dictionary(Fields=[pdf.make_indirect(field)])
                    pdf.save(candidate)
                self.assertEqual(stripper.strip_pdf(candidate), ('fixed', True))
                with pikepdf.open(candidate) as pdf:
                    field = pdf.Root.AcroForm.Fields[0]
                    self.assertEqual(str(field.FT), kind)
                    if kind == '/Tx':
                        self.assertEqual(str(field.V), 'retained value')

    def test_populated_signature_field_is_rejected(self):
        signed = self.d / 'signed.pdf'
        with pikepdf.open(self.path) as pdf:
            # A synthetic signature value tests the guard, not cryptographic validity.
            parent = pdf.make_indirect(pikepdf.Dictionary(FT=pikepdf.Name('/Sig')))
            child = pdf.make_indirect(pikepdf.Dictionary(T='signature', V=pikepdf.Dictionary(Contents=b'fixture'), Parent=parent))
            parent.Kids = [child]
            pdf.Root.AcroForm = pikepdf.Dictionary(Fields=[parent])
            pdf.save(signed)
        original = sha(signed)
        with self.assertRaisesRegex(RuntimeError, '已签名'):
            stripper.strip_pdf(signed)
        self.assertEqual(sha(signed), original)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS xattr regression')
    def test_permissions_and_finder_tags_survive(self):
        import plistlib
        tag = plistlib.dumps(['OCR review\n6'], fmt=plistlib.FMT_BINARY).hex()
        name = 'com.apple.metadata:_kMDItemUserTags'
        subprocess.run(['/usr/bin/xattr', '-wx', name, tag, str(self.path)], check=True)
        self.path.chmod(0o644)
        before = stripper.read_xattrs(str(self.path))
        stripper.strip_pdf(self.path)
        self.assertEqual(stripper.read_xattrs(str(self.path)), before)
        self.assertEqual(stripper.read_xattrs(str(self.path) + '.bak-redbox'), before)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o644)

    def test_render_removes_only_expected_red_pixels(self):
        from PIL import Image
        def render(label):
            dest = self.d / label
            subprocess.run(['pdftoppm', '-singlefile', '-scale-to', '960', '-png', str(self.path), str(dest)], check=True, capture_output=True)
            return Image.open(str(dest) + '.png').convert('RGB')
        before = render('before')
        stripper.strip_pdf(self.path)
        after = render('after')
        if os.environ.get('OCR_TEST_EVIDENCE'):
            before.save(Path(os.environ['OCR_TEST_EVIDENCE']) / 'before.png')
            after.save(Path(os.environ['OCR_TEST_EVIDENCE']) / 'after.png')
        red = lambda p: p[0] > 180 and p[1] < 150 and p[2] < 150
        self.assertGreater(sum(map(red, before.getdata())), sum(map(red, after.getdata())) + 100)
        self.assertGreater(sum(map(red, after.getdata())), 100)  # Legitimate rectangle survives.
        self.assertEqual(before.crop((0, 330, 160, 470)).tobytes(), after.crop((0, 330, 160, 470)).tobytes())


if __name__ == '__main__':
    unittest.main()
