# tests/fixtures/tools

## adobe_rgb_sample.jpg

`tools/optimize_images.py` のテスト用。900x600 の合成グラデーション（実写ではない）に、
**Adobe RGB (1998)** の ICC プロファイル（560 バイト、Adobe Systems 1999）と
ダミーの EXIF（Make/Model/Copyright）を埋め込んだもの。

サイトで実際に配信されていた 6000px 原本と同じ「Adobe RGB + EXIF 付き」という
入力条件を、21KB で再現するために作った（2026-09-12）。

ICC プロファイルは Adobe が配布条件下で再配布を許可しているもので、
デジタルカメラの JPEG に広く埋め込まれている標準プロファイルと同一。
