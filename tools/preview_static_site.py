"""ローカル確認用の静的サーバー（Vercel の cleanUrls を最低限まねる）。2026-09-20 新設。

`python -m http.server` はリポジトリをそのまま配信できるが、`vercel.json` の
`cleanUrls: true` を知らないため、ページ内の `.html` 無しの内部リンク
（例: `/dl-planner`、`/sidekick-planner`、`/register-dl?product=planner`）が 404 になり、
導線（製品ページ → register-dl → dl-*）をクリックで追えない。
このサーバーは `/foo` を `foo.html`、`/dir` を `dir/index.html` へ解決するだけで、
それ以外は http.server と同じ。`/api/*` は無い（404）ので、登録フォームは
本番の Firestore / Brevo に何も書かずに次のページへ進む。

使い方:
    py -3.10 tools/preview_static_site.py            # http://127.0.0.1:3334/
    py -3.10 tools/preview_static_site.py --port 8080

本番配信には使わない（確認専用）。
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]


class CleanUrlHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        clean = urlsplit(path).path
        resolved = Path(super().translate_path(clean))
        if resolved.is_dir():
            return str(resolved)
        if not resolved.exists() and not resolved.suffix:
            html = resolved.with_suffix(".html")
            if html.is_file():
                return str(html)
        return str(resolved)

    def end_headers(self) -> None:  # 確認中に古い HTML を掴まない
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=3334)
    parser.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args(argv)
    handler = partial(CleanUrlHandler, directory=str(REPO_ROOT))
    with ThreadingHTTPServer((args.bind, args.port), handler) as httpd:
        print(f"sidekick-site preview (cleanUrls): http://{args.bind}:{args.port}/  root={REPO_ROOT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
