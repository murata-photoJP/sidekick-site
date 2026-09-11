#!/usr/bin/env python3
"""配信用 JPEG を Web 向けに最適化する（Photoshop「Web用に保存」相当）。

--------------------------------------------------------------------
経緯
--------------------------------------------------------------------
2026-09-10、Vercel Hobby の Deployment Storage（10GB）が満杯になった。
原因は sky-effect / sidekick-star で配信していた JPEG 26 枚が、
**6000x4000 のカメラ原寸・Adobe RGB (1998) のまま**置かれていたこと。
1 デプロイ 372MB が保持中の全デプロイ分積み上がっていた。

さらに Adobe RGB のままだと、色管理をしないブラウザ（LINE / X の
アプリ内ブラウザ等）で空の青や夕焼けの橙が沈んで見える。
容量以前に「見せたい色が届いていない」問題でもあった。

2026-09-12 に 26 枚を本ツールと同じ処理で差し替え、144.9MB → 6.4MB。
（原本は SideKick販売ページ/html_未追跡素材_退避/images_original_6000px_2026-09-12/）

--------------------------------------------------------------------
処理内容
--------------------------------------------------------------------
  1. 埋め込み ICC が sRGB でなければ sRGB へ変換（相対的な色域）。
     ICC を「削るだけ」だと色が転ぶので必ず変換する。
  2. 長辺を --max-edge（既定 2000px）へ LANCZOS で縮小。
     サイトの最大表示幅は #lightbox-img の 1000px。Retina 2倍で 2000px。
  3. JPEG q85・プログレッシブ・4:4:4（空のグラデーション保護）・
     sRGB プロファイル埋め込み・EXIF 除去。
     images/PhotoAdvice/web/ の既存規約（1600px・EXIF なし）に準ずる。

既に「長辺 <= max-edge かつ sRGB/プロファイル無し」なら **何もしない**
（再圧縮による劣化を防ぐ。何度実行しても安全）。EXIF が残っているだけでは
再エンコードしない。縮小/色変換で書き出すときに副次的に除去される。

--------------------------------------------------------------------
使い方
--------------------------------------------------------------------
Pillow が必要（requirements-test.txt に固定済み。.venv / py -3.10 どちらでも動く）。

    # 何が起きるかを見るだけ（既定。ファイルは一切書かない）
    .\\.venv\\Scripts\\python.exe tools/optimize_images.py images/SkyEffects

    # 別ディレクトリへ出力（元ファイルは無変更）
    .\\.venv\\Scripts\\python.exe tools/optimize_images.py images/SkyEffects --out build-output/opt

    # その場で置き換える。必ず --backup が要る（退避→SHA-256 検証→上書き）
    .\\.venv\\Scripts\\python.exe tools/optimize_images.py images/SkyEffects --in-place \\
        --backup "../html_未追跡素材_退避/images_original_YYYY-MM-DD"

パスは html/ 直下からの相対でも絶対でも可。ディレクトリを渡すと再帰する。

新しい製品画像を追加するときは、置く前にこのツールを通すこと。
6000px の原本を images/ に置かない（置くなら .vercelignore に追記）。
"""

from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageCms
except ImportError:  # pragma: no cover
    sys.exit("Pillow が必要です: .venv なら  .\\.venv\\Scripts\\python.exe -m pip install -r requirements-test.txt")

HTML_ROOT = Path(__file__).resolve().parent.parent
JPEG_SUFFIXES = {".jpg", ".jpeg"}

DEFAULT_MAX_EDGE = 2000
DEFAULT_QUALITY = 85

_SRGB_PROFILE = ImageCms.createProfile("sRGB")
_SRGB_BYTES = ImageCms.ImageCmsProfile(_SRGB_PROFILE).tobytes()


@dataclass
class Result:
    path: Path
    action: str            # "optimize" | "skip" | "dry-run"
    before_bytes: int
    after_bytes: int | None
    size_before: tuple[int, int]
    size_after: tuple[int, int] | None
    profile_before: str    # "sRGB" / "Adobe RGB (1998)" / "(none)" ...
    reason: str = ""


# --------------------------------------------------------------------
# 判定
# --------------------------------------------------------------------
def _profile_desc(im: Image.Image) -> str:
    icc = im.info.get("icc_profile")
    if not icc:
        return "(none)"
    try:
        return ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))).strip()
    except Exception:
        return "(unreadable)"


def _is_srgb_or_none(desc: str) -> bool:
    return desc == "(none)" or "sRGB" in desc


def needs_optimization(im: Image.Image, max_edge: int) -> tuple[bool, str]:
    """(要最適化か, 理由)。既に規約内なら False。

    判定は「長辺が上限超」か「プロファイルが sRGB 以外」の 2 つだけ。
    EXIF が残っているだけでは再エンコードしない（消すためだけに JPEG を
    もう一世代劣化させる方が損）。縮小/色変換で書き出すときに副次的に消える。
    """
    desc = _profile_desc(im)
    reasons = []
    if max(im.size) > max_edge:
        reasons.append(f"長辺 {max(im.size)}px > {max_edge}px")
    if not _is_srgb_or_none(desc):
        reasons.append(f"プロファイル {desc}")
    return (bool(reasons), " / ".join(reasons))


# --------------------------------------------------------------------
# 変換
# --------------------------------------------------------------------
def optimize_image(im: Image.Image, max_edge: int) -> Image.Image:
    """sRGB 変換 → 縮小。保存はしない（呼び出し側が save_jpeg する）。"""
    if im.mode != "RGB":
        im = im.convert("RGB")
    icc = im.info.get("icc_profile")
    if icc:
        src_prof = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        if "sRGB" not in ImageCms.getProfileDescription(src_prof):
            im = ImageCms.profileToProfile(
                im, src_prof, _SRGB_PROFILE,
                renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                outputMode="RGB",
            )
    w, h = im.size
    scale = max_edge / max(w, h)
    if scale < 1:
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    return im


def save_jpeg(im: Image.Image, dst: Path, quality: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(
        dst, "JPEG",
        quality=quality, optimize=True, progressive=True,
        subsampling=0,                 # 4:4:4
        icc_profile=_SRGB_BYTES,       # EXIF は渡さない = 除去
    )


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------
# 1 ファイル処理
# --------------------------------------------------------------------
def process_one(src: Path, *, max_edge: int, quality: int,
                out_dir: Path | None, in_place: bool, backup_dir: Path | None,
                rel_root: Path) -> Result:
    before = src.stat().st_size
    with Image.open(src) as im:
        im.load()
        size_before = im.size
        desc = _profile_desc(im)
        need, reason = needs_optimization(im, max_edge)
        if not need:
            return Result(src, "skip", before, None, size_before, None, desc, "既に規約内")
        if out_dir is None and not in_place:
            return Result(src, "dry-run", before, None, size_before, None, desc, reason)

        optimized = optimize_image(im, max_edge)

    rel = src.resolve().relative_to(rel_root.resolve())
    if in_place:
        assert backup_dir is not None
        bk = backup_dir / rel
        bk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, bk)
        if _sha256(src) != _sha256(bk):
            raise RuntimeError(f"退避コピーの検証に失敗: {src}")
        dst = src
    else:
        assert out_dir is not None
        dst = out_dir / rel

    save_jpeg(optimized, dst, quality)
    return Result(src, "optimize", before, dst.stat().st_size, size_before, optimized.size, desc, reason)


# --------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------
def _base_for(p: Path) -> Path:
    """--out / --backup 配下に再現する相対パスの基準。
    html/ の中なら html/（images/... の構造を保つ）。外なら渡されたパス自身。"""
    rp = p.resolve()
    try:
        rp.relative_to(HTML_ROOT)
        return HTML_ROOT
    except ValueError:
        return rp if rp.is_dir() else rp.parent


def collect_targets(paths: list[str]) -> list[tuple[Path, Path]]:
    """[(JPEG, 相対パスの基準ディレクトリ), ...]"""
    found: list[tuple[Path, Path]] = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = HTML_ROOT / p
        base = _base_for(p)
        if p.is_dir():
            found += [(x, base) for x in sorted(p.rglob("*")) if x.suffix.lower() in JPEG_SUFFIXES]
        elif p.is_file() and p.suffix.lower() in JPEG_SUFFIXES:
            found.append((p, base))
        else:
            print(f"  [skip] JPEG でもディレクトリでもありません: {raw}", file=sys.stderr)
    return found


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="配信用 JPEG を Web 向けに最適化する（既定は dry-run）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("paths", nargs="+", help="JPEG ファイルまたはディレクトリ（html/ 相対 or 絶対）")
    ap.add_argument("--max-edge", type=int, default=DEFAULT_MAX_EDGE, help=f"長辺の上限 px（既定 {DEFAULT_MAX_EDGE}）")
    ap.add_argument("--quality", type=int, default=DEFAULT_QUALITY, help=f"JPEG 品質（既定 {DEFAULT_QUALITY}）")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--out", type=Path, help="この下へ html/ からの相対パスを保って出力（元は無変更）")
    mode.add_argument("--in-place", action="store_true", help="その場で置き換える（--backup 必須）")
    ap.add_argument("--backup", type=Path, help="--in-place 時の退避先。SHA-256 検証後に上書きする")
    return ap


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)

    if args.in_place and not args.backup:
        print("エラー: --in-place には --backup <退避先> が必須です（原本を消さないため）", file=sys.stderr)
        return 2
    if args.backup and not args.in_place:
        print("エラー: --backup は --in-place と組み合わせて使います", file=sys.stderr)
        return 2

    targets = collect_targets(args.paths)
    if not targets:
        print("対象の JPEG がありません")
        return 1

    mode = "IN-PLACE（退避あり）" if args.in_place else ("OUT → " + str(args.out)) if args.out else "DRY-RUN（書き込みなし）"
    print(f"=== optimize_images  {mode}  max-edge={args.max_edge}  q={args.quality} ===")

    results: list[Result] = []
    for src, base in targets:
        r = process_one(src, max_edge=args.max_edge, quality=args.quality,
                        out_dir=args.out, in_place=args.in_place, backup_dir=args.backup,
                        rel_root=base)
        results.append(r)
        try:
            shown = r.path.resolve().relative_to(HTML_ROOT)
        except ValueError:
            shown = r.path
        if r.action == "skip":
            print(f"  skip      {r.before_bytes/1024:7.0f}K  {r.size_before[0]}x{r.size_before[1]}  {r.profile_before:<18} {shown}")
        elif r.action == "dry-run":
            print(f"  would-do  {r.before_bytes/1024:7.0f}K  {r.size_before[0]}x{r.size_before[1]}  {r.profile_before:<18} {shown}   ← {r.reason}")
        else:
            assert r.after_bytes is not None and r.size_after is not None
            print(f"  done      {r.before_bytes/1024:7.0f}K → {r.after_bytes/1024:6.0f}K  "
                  f"{r.size_before[0]}x{r.size_before[1]} → {r.size_after[0]}x{r.size_after[1]}  {r.profile_before:<18} {shown}")

    n_opt = sum(1 for r in results if r.action == "optimize")
    n_dry = sum(1 for r in results if r.action == "dry-run")
    n_skip = sum(1 for r in results if r.action == "skip")
    b = sum(r.before_bytes for r in results if r.action == "optimize")
    a = sum(r.after_bytes or 0 for r in results if r.action == "optimize")
    print()
    print(f"  対象 {len(results)} / 最適化 {n_opt} / 要最適化(dry-run) {n_dry} / 規約内スキップ {n_skip}")
    if n_opt:
        print(f"  {b/1048576:.1f} MB → {a/1048576:.1f} MB")
    if args.in_place and n_opt:
        print(f"  原本の退避先: {args.backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
