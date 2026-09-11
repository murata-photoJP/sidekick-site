"""tools/optimize_images.py の挙動を固定する。

2026-09-12、sky-effect / sidekick-star の JPEG 26 枚が 6000x4000・Adobe RGB の
まま配信されていた問題を、このツールと同じ処理で解消した。再発防止のため、
「Adobe RGB → sRGB 変換」「縮小」「EXIF 除去」「規約内なら触らない」
「--in-place は退避してから上書き」を固定する。

Pillow は requirements-test.txt に固定済み（2026-09-12）。万一無い環境では skip する。
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import shutil
import sys
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageCms  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tools" / "optimize_images.py"
FIXTURE = REPO / "tests" / "fixtures" / "tools" / "adobe_rgb_sample.jpg"
# html/ 配下の入力は --out の下に html/ からの相対構造を保って出力される
FIXTURE_REL = FIXTURE.relative_to(REPO)


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("optimize_images", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["optimize_images"] = module
    spec.loader.exec_module(module)
    return module


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _profile(p: Path) -> str:
    with Image.open(p) as im:
        icc = im.info.get("icc_profile")
        if not icc:
            return "(none)"
        return ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))).strip()


def _make_conformant_jpeg(p: Path, size=(400, 300)) -> None:
    """規約内（小さい・sRGB・EXIF 無し）の JPEG を作る。"""
    im = Image.new("RGB", size, (30, 80, 200))
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    im.save(p, "JPEG", quality=85, icc_profile=srgb)


# --------------------------------------------------------------------
# フィクスチャ自体の前提
# --------------------------------------------------------------------
def test_fixture_is_adobe_rgb_with_exif():
    assert FIXTURE.exists()
    assert _profile(FIXTURE) == "Adobe RGB (1998)"
    with Image.open(FIXTURE) as im:
        assert im.info.get("exif"), "EXIF 付きであることが前提"
        assert im.size == (900, 600)


# --------------------------------------------------------------------
# 変換の中身
# --------------------------------------------------------------------
def test_out_mode_converts_to_srgb_resizes_and_strips_exif(tool, tmp_path):
    out = tmp_path / "out"
    rc = tool.main([str(FIXTURE), "--out", str(out), "--max-edge", "300"])
    assert rc == 0
    dst = out / FIXTURE_REL
    assert dst.exists(), "html/ からの相対パス（tests/fixtures/tools/...）を保って出力される"
    with Image.open(dst) as im:
        assert im.size == (300, 200), "長辺 300 に縮小される"
        assert not im.info.get("exif"), "EXIF は除去される"
        assert im.info.get("progressive") or im.info.get("progression"), "プログレッシブ JPEG"
    assert "sRGB" in _profile(dst), "sRGB プロファイルが埋め込まれる"
    # 元ファイルは無変更
    assert _profile(FIXTURE) == "Adobe RGB (1998)"


def test_color_is_actually_converted_not_just_relabeled(tool):
    """ICC を貼り替えただけなら画素は変わらない。変換していれば変わる。"""
    with Image.open(FIXTURE) as im:
        im.load()
        naive = im.convert("RGB").resize((300, 200), Image.LANCZOS)
        converted = tool.optimize_image(im, 300)
    assert converted.size == (300, 200)
    assert naive.tobytes() != converted.tobytes(), "Adobe RGB → sRGB 変換で画素値が変わっているはず"


def test_conformant_file_is_skipped_untouched(tool, tmp_path):
    p = tmp_path / "ok.jpg"
    _make_conformant_jpeg(p)
    before = _sha(p)
    out = tmp_path / "out"
    rc = tool.main([str(p), "--out", str(out)])
    assert rc == 0
    assert not (out / "ok.jpg").exists(), "規約内のファイルは出力されない"
    assert _sha(p) == before


def test_exif_alone_does_not_trigger_reencode(tool, tmp_path):
    """サイズも色も規約内なら、EXIF が残っていても再エンコードしない（世代劣化防止）。"""
    p = tmp_path / "with_exif.jpg"
    im = Image.new("RGB", (400, 300), (30, 80, 200))
    exif = Image.Exif()
    exif[0x010F] = "FixtureCam"
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    im.save(p, "JPEG", quality=85, icc_profile=srgb, exif=exif.tobytes())
    with Image.open(p) as chk:
        assert chk.info.get("exif"), "前提: EXIF 付き"
    before = _sha(p)
    out = tmp_path / "out"
    assert tool.main([str(p), "--out", str(out)]) == 0
    assert not out.exists() or not any(out.rglob("*.jpg")), "EXIF だけでは出力しない"
    assert _sha(p) == before


def test_second_run_is_idempotent(tool, tmp_path):
    """最適化済みをもう一度通しても再圧縮されない（劣化防止）。"""
    out1 = tmp_path / "o1"
    out2 = tmp_path / "o2"
    tool.main([str(FIXTURE), "--out", str(out1), "--max-edge", "300"])
    first = out1 / FIXTURE_REL
    assert first.exists(), "1 回目は出力される"
    rc = tool.main([str(first), "--out", str(out2), "--max-edge", "300"])
    assert rc == 0
    # first は html/ の外なので、出力されるなら out2 直下に同名で出るはず。それが無い＝skip。
    assert not out2.exists() or not any(out2.rglob("*.jpg")), "2 回目は skip されるはず"


# --------------------------------------------------------------------
# 安全装置
# --------------------------------------------------------------------
def test_default_is_dry_run_and_writes_nothing(tool, tmp_path):
    p = tmp_path / "a.jpg"
    shutil.copy2(FIXTURE, p)
    before = _sha(p)
    rc = tool.main([str(p)])
    assert rc == 0
    assert _sha(p) == before
    assert sorted(x.name for x in tmp_path.iterdir()) == ["a.jpg"], "何も生成しない"


def test_in_place_requires_backup(tool, tmp_path):
    p = tmp_path / "a.jpg"
    shutil.copy2(FIXTURE, p)
    before = _sha(p)
    rc = tool.main([str(p), "--in-place"])
    assert rc == 2
    assert _sha(p) == before, "退避先が無ければ触らない"


def test_backup_without_in_place_is_rejected(tool, tmp_path):
    p = tmp_path / "a.jpg"
    shutil.copy2(FIXTURE, p)
    rc = tool.main([str(p), "--backup", str(tmp_path / "bk")])
    assert rc == 2


def test_in_place_backs_up_original_then_replaces(tool, tmp_path):
    work = tmp_path / "work" / "sub"
    work.mkdir(parents=True)
    p = work / "a.jpg"
    shutil.copy2(FIXTURE, p)
    original = _sha(p)
    bk = tmp_path / "bk"

    rc = tool.main([str(p), "--in-place", "--backup", str(bk), "--max-edge", "300"])
    assert rc == 0

    # 退避: 元と同一バイト
    backed = list(bk.rglob("a.jpg"))
    assert len(backed) == 1
    assert _sha(backed[0]) == original
    # 本体: 置き換わっている
    assert _sha(p) != original
    with Image.open(p) as im:
        assert im.size == (300, 200)
        assert not im.info.get("exif")
    assert "sRGB" in _profile(p)
