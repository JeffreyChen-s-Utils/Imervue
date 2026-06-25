<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  PySide6 と OpenGL で構築された GPU アクセラレーション画像ビューア / 現像 / ペイントスタジオ / パペットアニメーター
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_zh-TW.md">繁體中文</a> ·
  <a href="README_zh-CN.md">简体中文</a> ·
  <strong>日本語</strong> ·
  <a href="README_ko.md">한국어</a> ·
  <a href="README_es.md">Español</a> ·
  <a href="README_fr.md">Français</a> ·
  <a href="README_de.md">Deutsch</a> ·
  <a href="README_pt-BR.md">Português (BR)</a> ·
  <a href="README_ru.md">Русский</a>
</p>

<p align="center">
  <a href="https://imervue.readthedocs.io/en/latest/?badge=latest"><img src="https://readthedocs.org/projects/imervue/badge/?version=latest" alt="Documentation Status"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

## 目次

- [概要](#概要)
- [インストール](#インストール)
- [使い方](#使い方)
- [Imervue — 画像ビューア & ライブラリ](#imervue--画像ビューア--ライブラリ)
- [Modify — 非破壊現像](#modify--非破壊現像)
- [Paint — 本格的なラスター描画スタジオ](#paint--本格的なラスター描画スタジオ)
- [Puppet — 2D リギングアニメーション](#puppet--2d-リギングアニメーション)
- [Desktop Pet — フレームレスオーバーレイ](#desktop-pet--フレームレスオーバーレイ)
- [キーボード & マウスショートカット](#キーボード--マウスショートカット)
- [メニュー構造](#メニュー構造)
- [プラグインシステム](#プラグインシステム)
- [MCP サーバー](#mcp-サーバー)
- [多言語サポート](#多言語サポート)
- [ユーザー設定](#ユーザー設定)
- [アーキテクチャ](#アーキテクチャ)
- [ライセンス](#ライセンス)

---

## 概要

Imervue は GPU アクセラレーション画像ワークステーションで、**5 つのトップレベルタブ** を備えています:

| タブ | 機能 |
|---|---|
| **Imervue** | 画像ライブラリの閲覧、表示、整理、検索、バッチ処理 |
| **Modify** | 非破壊現像パイプライン — スライダー、カーブ、LUT、マスク、レタッチ、マルチ画像合成 |
| **Paint** | 本格的なラスター描画スタジオ。ブラシ、レイヤー、アニメーション、漫画ツール、PSD I/O |
| **Puppet** | ゼロから構築された 2D リギングパペットアニメーター — メッシュ、デフォーマー、パラメーター、モーション、物理 |
| **Desktop Pet** | 任意の `.puppet` rig をフレームレスかつ透明な常に最前面のデスクトップオーバーレイとして実行 — ドラッグして移動、エッジスナップ、クリックスルー、ライブドライバー、システムトレイ統合 |

設計原則:

- **パフォーマンス第一** — モダンな GLSL シェーダーと VBO による GPU アクセラレーションレンダリング
- **大規模コレクション対応** — 仮想化タイルグリッドで表示中のサムネイルのみをロード
- **スムーズな体験** — 非同期マルチスレッド画像ロードとプリフェッチ機構
- **非破壊現像** — すべての調整は画像ごとの recipe に保存され、明示的にエクスポートするまで元ファイルは上書きされない
- **拡張可能** — ライフサイクル / メニュー / 画像 / 入力フックを備えたフルプラグインシステム。MCP サーバーは Qt フリーの純粋ロジックツールを AI アシスタントに公開

---

## インストール

### 要件

- Python >= 3.10
- OpenGL 対応 GPU(ソフトウェアレンダリングフォールバックも利用可能)

### ソースからインストール

```bash
git clone https://github.com/JeffreyChen-s-Utils/Imervue.git
cd Imervue
pip install -r requirements.txt
```

### パッケージとしてインストール

```bash
pip install .
```

### 依存パッケージ

| パッケージ | 用途 |
|---------|---------|
| PySide6 | Qt6 GUI フレームワーク |
| qt-material | Material Design テーマ |
| Pillow | 画像処理 |
| PyOpenGL | OpenGL バインディング |
| PyOpenGL_accelerate | OpenGL パフォーマンス最適化 |
| numpy | 配列演算とサムネイルキャッシュ |
| rawpy | RAW 画像のデコード |
| imageio | 画像 I/O |
| imageio-ffmpeg | スライドショー MP4 エクスポート(ffmpeg 経由の H.264) |
| defusedxml | 安全な XML 解析(XMP サイドカー) |

オプション(feature-gated。インストールしなければ該当機能は無効化):

| パッケージ | 用途 |
|---------|---------|
| open_clip_torch + torch | CLIP セマンティック検索(自然言語による画像検索) |
| onnxruntime | Real-ESRGAN AI アップスケール / CLIP ONNX 自動タグ付け |
| opencv-python | HDR 合成、パノラマ合成、フォーカススタック、顔検出、ヒーリングブラシ |
| sounddevice | Puppet マイクによるリップシンク |
| mediapipe | Puppet ウェブカメラによる顔追跡 |

---

## 使い方

### 基本起動

```bash
python -m Imervue
```

### 特定の画像またはフォルダを開く

```bash
python -m Imervue /path/to/image.jpg
python -m Imervue /path/to/folder
```

### コマンドラインオプション

| オプション | 説明 |
|--------|-------------|
| `--debug` | デバッグモードを有効化 |
| `--software_opengl` | ソフトウェア OpenGL レンダリングを使用(`QT_OPENGL=software` と `QT_ANGLE_PLATFORM=warp` を設定) |
| `file` | (位置引数)起動時に開く画像ファイルまたはフォルダ |

---

## Imervue — 画像ビューア & ライブラリ

**Imervue** タブはデフォルトのランディング画面で、画像ビューアとフォルダツリー、EXIF サイドバー、ライブラリ整理ツールを統合しています。

### ビューア

- **GPU アクセラレーションレンダリング** — OpenGL(GLSL 1.20 シェーダー + VBO)
- **ディープズームピラミッド** — 512×512 タイルのマルチレベル LANCZOS リサンプリング、最大 256 タイル / 1.5 GB VRAM 予算の LRU キャッシュ、最大 8× の異方性フィルタリング
- **非同期ロード** — マルチスレッドデコード + ±3 画像のプリフェッチ
- **仮想化サムネイルグリッド** — 可視タイルのみレンダリング。サムネイルサイズは設定可能(128 / 256 / 512 / 1024 / auto)
- **ディスクキャッシュ** — MD5 ベースの無効化付き圧縮 PNG サムネイル。`%LOCALAPPDATA%/Imervue/cache/thumbnails`(または `~/.cache/imervue/thumbnails`)に保存
- **アニメーション再生** — GIF / APNG、再生 / 一時停止 / フレーム送り / 速度調整付き

### 閲覧モード

- **グリッド**(デフォルト)— 仮想化タイルグリッド、ホバープレビュー(500 ms 遅延)
- **リスト(詳細)** — `Ctrl+L` で切り替え。列: プレビュー · ラベル · 名前 · 解像度 · サイズ · タイプ · 更新日時
- **ディープズーム** — タイルをダブルクリック。GPU によるスムーズなパン / ズーム + ミニマップ
- **分割ビュー**(`Shift+S`)— 2 枚の画像を並べて表示
- **見開きページ読書**(`Shift+D`、`Ctrl+Shift+D` で右から左へ読む漫画用)— 見開きリーダー
- **マルチモニターミラー**(`Ctrl+Shift+M`)— セカンダリディスプレイウィンドウ
- **シアターモード**(`Shift+Tab`)— すべての UI シェルを非表示
- **比較ダイアログ** — 並列 / オーバーレイ(α スライダー)/ 差分(ゲインスライダー)/ A|B ドラッグ分割
- **Timeline / Calendar / Map** ビュー — 撮影日でグループ化、カレンダー閲覧、Leaflet + OpenStreetMap で位置情報付き画像を地図表示

### オンスクリーンオーバーレイ

- RGB ヒストグラム(`H`)
- F8 OSD(ファイル名 / サイズ / タイプ)、Ctrl+F8 デバッグ HUD(VRAM / キャッシュ / スレッド)
- ピクセルビュー(`Shift+P`)— 400% 以上のズームでピクセルグリッド + ピクセルごとの RGB / HEX を表示
- カラーモード(`Shift+M`)— Normal / Grayscale / Invert / Sepia(GLSL)

### ナビゲーション

- 矢印キー、ブラウザ風履歴(`Alt+←/→`)、ランダムジャンプ(`X`)
- フォルダ間ナビゲーション(`Ctrl+Shift+←/→`)
- N 番目の画像へジャンプ(`Ctrl+G`)
- ファジー検索(`Ctrl+F` / `/`)
- **コマンドパレット**(`Ctrl+Shift+P`)— すべてのメニュー操作をファジー検索
- フォルダ末尾での自動ループ
- タッチパッドのピンチズーム + 水平スワイプによる画像切り替え

### 整理

- **ブックマーク** — 最大 5000 パス
- **レーティング** — 0-5 つ星(`1`-`5`)+ お気に入りハート(`0`)
- **カラーラベル** — other XMP-aware photo managers 式の赤 / 黄 / 緑 / 青 / 紫(`F1`-`F5`)
- **カリング**(Culling)— other XMP-aware photo managers 式の 3 状態フラグ(`P` = キープ、`Shift+X` = 拒否、`U` = フラグ解除)。状態でフィルタ、拒否済みの一括削除。自動カリングは近似重複グループごとに最もシャープなフレームをキープし、残りを拒否
- **階層タグ** — `animal/cat/british` のようなツリーパス。子孫が自動的にマッチ
- **Tags & Albums** マルチタグ AND / OR フィルタ
- **スマートアルバム** — ルールベースのクエリを保存し、ワンクリックで再適用。フィルタは拡張子、解像度 & **アスペクト比**、**ファイルサイズ**、レーティングの **下限 / 上限**、カラー、カリング、タグ(**除外**を含む)、**カメラ / レンズ**、**ファイル名の正規表現 / glob**、**ファイルの経過時間** にまたがり、さらにポータブルな JSON ファイルへの **エクスポート / インポート** が可能
- **RAW+JPEG ペアのスタック** — 同名キャプチャを単一タイルに折りたたみ。RAW はサイブリングとして引き続きアクセス可能
- **画像ごとのメモ** — EXIF サイドバーに、デバウンス付き自動保存、セッション間で永続化
- **ステージングトレイ** — フォルダ間で持続するバスケット。再起動後も保持。一括移動 / コピー / エクスポート
- **デュアルペインファイルマネージャー** — 2 ペインのツインツリービュー
- **セッション / ワークスペースレイアウト** — タブ / 選択 / フィルタ / ドック位置を `.imervue-session.json` にスナップショット。名前付きレイアウト(Browse / Develop / Export 配置)を保存可能
- **マクロ** — レーティング / お気に入り / カラー / タグ操作のバッチを録画 / 再生(`Alt+M` で前回のマクロを再生)
- **サムネイルバッジ + 密度** — カラーストリップ / お気に入り / ブックマーク / レーティングの星。Compact / Standard / Relaxed パディング
- **外部アプリへのドラッグアウト** — タイルを Explorer / Chrome / Discord に直接ドラッグ
- **最近のフォルダ / 画像** を追跡。起動時に最後のフォルダを自動復元

### ソート & フィルタ

- 名前 / 更新日 / 作成日 / サイズ / 解像度でソート(昇順 / 降順)
- 拡張子、カラーラベル、レーティング、タグ / アルバム、カリング状態でフィルタ
- **高度なフィルタ** — 解像度 / ファイルサイズ / 向き / 更新日範囲
- **マルチタグフィルタ** ダイアログ(AND / OR ブール論理付き)

### 検索

- **ファジーファイル名検索** 部分文字列ハイライト付き
- **類似画像検索** — pHash(64-bit DCT)調整可能なハミング距離
- **ライブラリ検索** — SQLite マルチルートインデックスに、コンパクトなクエリ DSL を併用: キーワード、タグ(否定を含む)、レーティング、カラー、拡張子、場所、カリング、お気に入り、アスペクト比、経過時間、サイズ、寸法、カメラ / レンズ、ファイル名の正規表現 / glob
- **類似検索(average hash)** — pHash と dHash に、補完的な近似重複メトリックとしてオプションの average-hash(aHash)を組み合わせ
- **セマンティック検索(CLIP)** — 自然言語クエリ(「雪の中のゴールデンレトリバー」など)をキャッシュ済み embedding で実行。`open_clip_torch` + `torch` が未インストール時は優雅に無効化
- **自動タグ付け** — ヒューリスティック分類 + 任意の CLIP ONNX アップグレード

### メタデータ

- **EXIF サイドバー** 折りたたみ可能なグループ + インラインの 0-5 つ星評価ストリップ
- **EXIF エディタ** ダイアログ
- **キーワードエディタ** — タイトル / 作成者 / 説明 / キーワード。タグの共起から導いた **関連タグの提案** 付き、さらに **統制語彙の展開**(リーフキーワードが、編集可能な階層語彙からその祖先 + 同義語を自動的に適用)
- **画像情報** ダイアログ(寸法 / サイズ / 日付)
- **XMP サイドカー**(`.xmp` コンパニオン)— レーティング / タイトル / 説明 / キーワード / カラーラベルを other XMP-aware photo managers と双方向同期(`defusedxml` で安全に解析)
- **GPS ジオタグエディタ** — EXIF GPS の緯度経度を読み書き(JPEG)
- **トークンバッチリネーム** — `{date:yyyymmdd}_{camera}_{counter:04}{ext}` のようなテンプレートをライブプレビュー
- **メタデータ CSV / JSON エクスポート** — 画像 1 枚あたり 1 行で、カリング / レーティング / タグ / メモを含む

### 追加ツール(Imervue タブ — バッチ処理)

**Tools** メニューからアクセス可能。機能別グループのサブメニューに整理されています:

- **バッチ** — フォーマット変換 · EXIF 除去 · 画像サニタイザー(再レンダリングして隠れたデータを削除)· 画像オーガナイザー · トークンバッチリネーム
- **AI / ヒューリスティック** — AI 画像アップスケール(Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU)· 重複検索 · 類似検索 · 自動タグ付け · 顔検出
- **ライブラリ & メタデータ** — ライブラリ検索 · スマートアルバム · 階層タグ · メタデータエクスポート · XMP サイドカー · GPS ジオタグ

### システム統合

- Windows 右クリック **Open with Imervue**(レジストリ経由で登録)
- フォルダ監視(`QFileSystemWatcher` による自動更新)
- トースト通知システム(info / success / warning / error)
- オンラインダウンローダ付きプラグインシステム([プラグインシステム](#プラグインシステム)を参照)

---

## Modify — 非破壊現像

**Modify** タブは現像ワークステーションです。すべての調整は画像ごとの **recipe** に保存され、明示的に **Export** または **Save As** を実行するまで、元ファイルは上書きされません。

### 現像スライダー

- ホワイトバランス — 色温度 / 色合い
- 階調領域 — シャドウ / 中間調 / ハイライト
- 露出 / コントラスト / 彩度 / 自然な彩度
- クロップ、回転、水平 / 垂直反転
- すべての調整は recipe を介して非破壊で動作

### カーブ & LUT

- **トーンカーブエディタ** — ドラッグ可能な RGB カーブ + 個別の R / G / B チャンネル、monotone cubic 補間付き
- **.cube LUT 適用** — Adobe 3D LUT(最大 64³)を読み込み、トリリニア補間、強度スライダーでブレンド
- **スプリットトーニング** — フラグベースのシャドウ / ハイライト色相 + 彩度、バランスピボット付き

### クリエイティブエフェクト

- **ソラリゼーション** — 暗室風の階調反転(しきい値 + ミックス)
- **ディフューズグロー / Orton** — ソフトフォーカスのハイライトブルーム(量 / 半径 / ハイライトしきい値)
- **グラデーションマップ** — 輝度 → パレット。オプションの知覚的(OkLCH)補間モードでは、彩度の高いグラデーションが中間点でグレーに転ばず鮮やかさを保つ
- **オーダードディザ** — Bayer マトリクスによる N 階調量子化(両端は保持)
- **段階フィルタ(Graduated Density)** — 角度 / ハードネス / オフセットによるリニア ND グラデーション。空や前景向けにオプションのティント付き
- **トーンイコライザ(Tone Equalizer)** — 平滑化したマスク上で、輝度ゾーン(シャドウからハイライトまで)ごとに独立した露出を適用
- **ディテールイコライザ(Detail Equalizer)** — 単一のクラリティスライダーを超えて、周波数帯域ごとにコントラストを再重み付け(細かなテクスチャ対粗いコントラスト)
- **フィルミックトーンマップ(Filmic Tone Map)** — ピボット付きコントラストと彩度復元を備えた純粋な Reinhard / Hable ハイライトロールオフ。高コントラストな単一露出向け
- **ベルビア(Velvia)** — 輝度で重み付けした彩度ブーストで、シャドウを守りつつくすんだ色を鮮やかに引き立てる
- **フィルムネガ(Film Negative)** — スキャンしたカラーネガを反転し、オレンジのフィルムベースを除算で取り除き、出力ガンマを適用
- **デフリンジ(Defringe)** — 高コントラストエッジ上の紫 / 緑の色収差フリンジを脱色
- **エンボス(Emboss)** — 輝度ハイトフィールドから方向光のレリーフを生成
- **極座標(Polar Coordinates)** — フレームを円盤に巻き取る、または展開する(tiny-planet / 極座標反転)
- **万華鏡(Kaleidoscope)** — 1 つの角度ウェッジを n 回対称にミラーリング
- **すりガラス(Frosted Glass)** — 決定論的なシード付きの局所ピクセル散乱
- **現像プリセット** — recipe を保存し、丸ごと適用するか、アクティブな調整だけを他の画像にマージ(各画像のクロップ等はそのまま維持)

### 局所調整

- **ブラシ / 放射状 / 線形グラデーションマスク** マスクごとの露出 / 明度 / コントラスト / 彩度 / ホワイトバランスのデルタ + フェザースライダー
- マスクは現像パイプラインを通じて非破壊にブレンド

### レタッチ & 変形

- **ヒーリングブラシ** — 円形スポット、OpenCV インペインティング(Telea または Navier-Stokes)
- **クローンスタンプ** — Shift+クリックでソース、フェザー処理付きで宛先にブリット
- **クロップ / 水平補正** — 正規化されたクロップ矩形 + 任意角度の水平補正で、最大内接矩形に自動クロップ
- **自動水平補正** — Hough-line による水平線 / 垂直線検出
- **レンズ補正** — pure-numpy の放射状歪み(樽型 / 糸巻き型)、周辺光量補正、チャンネルごとの色収差補正
- **ノイズ低減 / シャープニング** — エッジ保持バイラテラルノイズ除去 + アンシャープマスクシャープニング
- **空 / 背景** — 検出した空をグラデーションに置換、または背景を削除(透明または白塗り)。オプションで `rembg` / U²-Net アップグレード可

### マルチ画像

- **HDR 合成** — ブラケット露出を OpenCV Mertens fusion でマージ(AlignMTB プリアライメント付き)
- **パノラマ合成** — OpenCV `Stitcher`(panorama または scans モード)、黒縁の自動クロップ
- **フォーカススタック** — Laplacian フォーカスマップ + ガウスブレンド + オプションの ECC アライメント

### 出力

- **ウォーターマークオーバーレイ** — テキストまたは画像、9 アンカー、不透明度、スケール。エクスポート時にのみ適用
- **エクスポートプリセット** — Web 1600 / Print 300 dpi / Instagram 1080 のワンクリックパイプライン
- **Save As / Export** — PNG / JPEG / WebP / BMP / TIFF。ロッシー形式には品質スライダー
- **バッチ操作** — 選択画像のリネーム、移動 / コピー、回転
- **コンタクトシート PDF** — キャプション付きマルチページグリッド(A4 / A3 / Letter / Legal)
- **Web ギャラリー HTML** — `index.html` + JPEG サムネイル + インラインライトボックスを含む自己完結型フォルダ
- **スライドショー MP4** — H.264 動画、FPS / 画像ごとの保持秒数 / フェード・ディゾルブ・スライド・ワイプのトランジション設定可(`imageio-ffmpeg`)
- **プリントレイアウト** — マルチページ PDF(A4/A3/Letter/Legal)。グリッド / マージン / 綴じ代 / トンボ付き
- **ソフトプルーフ** — ICC プロファイルを読み込み、ターゲット色域をシミュレート、色域外ピクセルをマゼンタで強調
- **仮想コピー** — 画像ごとの名前付き recipe スナップショット。マスターを失わずに異なるルックを切り替え可能

### 外部エディタ

**File > External Editors…** でプログラム(画像エディタなど)を登録し、**File > Open in External Editor** から起動します。

---

## Paint — 本格的なラスター描画スタジオ

**Paint** タブは本格的なラスター描画スタジオで、独立した `QMainWindow` として埋め込まれています。メニュー、左ツールストリップ、コンテキスト対応のオプションバー、右側のタブ式ドックカラムを備えています。マルチドキュメント編集 — 複数の絵を同時に開け、それぞれが独自の undo スタックを持ちます。

### ツール(27)

ブラシ · 消しゴム · 塗りつぶし · スポイト · 矩形 / 投げ縄 / マジックワンド / クイック選択 · 移動 · テキスト · グラデーション · ぼかし · 指先 · 覆い焼き · 焼き込み · スポンジ · ペン · クローンスタンプ · 吹き出し · 矩形 · 楕円 · 直線 · 多角形 · クロップ · 変形 · ハンド · ズーム

暗室トーニングの 3 兄弟 — **覆い焼き(Dodge)**(明るく)、**焼き込み(Burn)**(暗く)、**スポンジ(Sponge)**(彩度を上げ / 下げ)— は、ブラシとシャドウ / 中間調 / ハイライトマスクで重み付けして、局所的な階調とクロマの調整を描き込みます。

シングルキーショートカット: `B / E / G / I / V / T / U / R / P / S / C / Z / H`。`Shift+R/E/I/P` で図形バリアントを切り替え。

### ブラシ

ペン / マーカー / 鉛筆 / 蛍光ペン / スプレー / カリグラフィ / 水彩 / 木炭 / クレヨン。サイズ / 不透明度 / 硬さ / 密度 / ブレンドモード付き。筆圧カーブエディタ、選択範囲からブラシ先端をキャプチャ、ブラシプリセットのインポート / エクスポート。

### レイヤー

サムネイル、表示切り替え、ドラッグ並び替え、ブレンドモード、不透明度、検索、ベクターレイヤー、1-bit レイヤーを備えたフルレイヤーパネル。**レイヤーマスク**(追加 / 選択から / 反転 / 適用)、**クリッピングマスク**、**レイヤー効果**(ドロップシャドウ / 外側の光彩 / 境界線)。色によるレイヤー分割、グラデーションマップのプリセット。

### 選択

矩形 / 投げ縄 / マジックワンド / クイック選択。**置換 / 追加 / 減算 / 交差** モード + フェザー付き。**クイックマスクモード**(`Q`)。**選択範囲のストローク** ダイアログ。

### アニメーション & 漫画

- **アニメーション** — スナップショット、再生、オニオンスキン、MP4 / GIF エクスポート付きのフレームタイムラインドック
- **漫画ツール** — コマ切り · トーンレイヤー · ノンブル印字 · スピード線(放射 / 平行 / バースト)· アクションフラッシュ · 吹き出しツール

### フィルタ & 表示補助

- **フィルタ** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone(それぞれライブプレビューダイアログ付き)
- **表示補助** — ピクセルグリッド · ピクセルスナップ · エッジスナップ · オニオンスキン · 裁ち落としガイド · キャンバス回転(`Ctrl+Shift+H` で反時計回り回転)

### ドック(10、タブ式)

カラー · ブラシ · レイヤー · ナビゲーター · 素材ライブラリ · 履歴 · スウォッチ · リファレンス · ヒストグラム · アニメーション。各ドックは移動 / フローティング可能。**Settings > Workspace Layouts** で名前付き配置を保存 / 呼び出し。

### ファイル I/O

- **PSD**(Photoshop)の読み書きをレイヤー完全往復で対応
- PNG / JPEG / WebP エクスポート、複数ページ漫画は **CBZ** または **PDF** にエクスポート
- 自動保存スナップショット + 最新復元

### パワーユーザー UX

- **Tab** ですべてのドックを切り替え(集中描画モード)
- `Ctrl+Tab` で Paint タブを循環
- `,` / `.` でブラシ種類を切り替え
- `0`-`9` で 10% ステップのブラシ不透明度
- `Alt+[` / `Alt+]` でアクティブレイヤーを下 / 上に切り替え
- キャンバス右クリックでクイック Undo / Redo / 全選択 / 選択解除 / Fit / 100% メニュー
- タブごとの変更アスタリスク、Undo / Redo のトースト通知、起動時の自動保存復元プロンプト

ディープズームから `E` を押すと、現在の画像をそのまま新しい Paint タブに送ることができます。

---

## Puppet — 2D リギングアニメーション

> **完全ガイド**: [`puppet_guide.md`](../puppet_guide.md) はライブストリーミング(OBS / NDI / 仮想カメラ)とアニメーション制作(録画 / タイムライン編集 / MP4 エクスポート)のエンドツーエンドのワークフローをカバーします。中国語版は [`puppet_guide.zh-TW.md`](../puppet_guide.zh-TW.md) および [`puppet_guide.zh-CN.md`](../puppet_guide.zh-CN.md) にあります。

**Puppet** タブはゼロから構築された 2D リギングパペットアニメーションシステムです。Live2D が行うこと(メッシュ変形リギング、パラメーター、モーション、物理、表情、ポーズ、リップシンク、ウェブカメラ顔追跡)と同等の機能を、**プロプライエタリな SDK を一切使わず**、**`live2d-py` も使わず**、`Imervue/puppet/FORMAT.md` で完全に文書化された完全オープンな `.puppet` ファイルフォーマットで実現します。

### ファイルフォーマット

`.puppet` は zip コンテナです:

- `puppet.json` — マニフェスト(drawables、deformers、parameters、motions、pose groups、parts、hit areas)
- `textures/*.png` — atlas テクスチャ
- `motions/*.json` — keyframe トラック
- `expressions/*.json` — パラメーターオーバーレイ
- `physics.json` — Verlet 物理構成

JSON ベースで、人間が diff 可能、プロプライエタリなバイナリは一切なし。

### レンダラ

`QOpenGLWidget` に vertex-array textured-triangle 描画(draw_order に従う)、drawable ごとのブレンドモード(normal / additive / multiply)、pose-group の排他性、画像空間正射投影、GL_REPEAT タイリングの透明チェッカー背景、ホイールズーム + 中ドラッグパンを実装。大規模 rig に最適化済み — March 7th(307 drawables / 2965 vertex morphs)が CPU で 60 FPS。

### 編集

- **PNG インポート** → アルファを考慮した三角形メッシュを自動生成
- **回転デフォーマー追加**(アンカー + 角度)/ **ワープデフォーマー追加**(rows × cols ベジエ格子)のツールバーアクション
- **パラメーター追加** → スライダー両端で **Set Key** を押してパラメータードックにキー形状を記録
- **メッシュエディタ** — Edit Mesh を切り替えて頂点をドラッグ。8 px 以内のクリックは最寄り頂点にスナップ
- **Save As…** で rig 全体を `.puppet` zip に書き出し

### 実行

- **パラメーターリギング** — 各パラメーターはスライダー値を部分的なデフォーマーフォームスナップショットにマップするキーリストを保持。実行時にサンプリングしてフィールドごとに線形補間
- **モーション再生** — 下部ドックにモーション一覧 + Play / Pause / Stop / Loop / スクラブ。カーブサンプラーは `linear`、`stepped`、`inverse-stepped`、`cubic-bezier` セグメントをサポート(ニュートン反復による time → param 解)。モーションごとのフェードイン / フェードアウト
- **表情** — `additive` / `multiply` / `overwrite` のパラメーターオーバーレイスタック
- **ポーズグループ** — 排他的な drawable 表示(武器の切り替え、口形バリアント)
- **物理** — 髪 / 服 / リボン用の Verlet 振り子チェーン。入力パラメーターがチェーンアンカーを動かし、重力 + 減衰 + パーティクルごとのばねがリセット状態に引き戻す
- **頂点モーフ** — Cubism スタイルの rest と ±extreme deltas 間の線形ブレンド。numpy でベクトル化、フレーム毎に 60 FPS
- **不透明度キー** — パラメーター駆動のアルファカーブ。ジェスチャーパラメーターに応じて代替ポーズのメッシュをフェードイン / アウト

### ライブ入力

- マウスドラッグ → 頭部角度パラメーター
- 自動まばたき。cosine open → close → open カーブ
- マイクリップシンク `sounddevice` RMS → `ParamMouthOpenY`(オプション依存)
- ウェブカメラ顔追跡 OpenCV + MediaPipe FaceMesh → 頭部 yaw / pitch / roll + 目 / 口の開閉(オプション依存)
- カスタムモーション録画 — スライダー操作 / カメラに向く / 物理の動作中に 30 Hz でパラメーター値を取得。停止時に線形セグメント Motion にベイク

### Cubism 相互運用

**Cubism Native SDK** をプラグイン可能(ユーザーが DLL を用意 — Live2D の Free Material License で再配布禁止)。任意の `.moc3` モデルを `.puppet` zip に変換できます。コンバーターは sample-and-reconstruct スイープを実行し、vertex-morph delta とパラメーター駆動の可視性切り替えを同時にキャプチャするので、ジェスチャー切り替え(ピース / 顔隠し / 写真 …)が変換後も完全に保持されます。

### 出力

- **画面キャプチャ…** `glReadPixels` で PNG として保存
- **録画…** 30 FPS フレームループを切り替え、`imageio` で GIF / WebM / MP4 として書き出し
- **仮想カメラ** — puppet キャンバスをシステムの webcam として公開
- **NDI 出力** — LAN 上で puppet を NDI ソースとして配信
- **VTube Studio API サーバー** — VTS 互換クライアント向けのオプション WebSocket API

### OBS ライブストリーミング連携

2 つの経路があります。A は「とりあえず動く」、B は低遅延・高品質で LAN が必要です。

#### A. 仮想カメラ(最も簡単)

puppet キャンバスを仮想 webcam として公開し、OBS の標準「Video Capture Device」ソースで取り込めます。

1. `pip install pyvirtualcam`
2. プラットフォームごとのドライバー:
   - **Windows**: OBS Studio 26+ をインストールすると *OBS Virtual Camera* ドライバーが同梱されます。最初に OBS を一度開き、右下の **Start Virtual Camera** をクリックするとドライバーがシステム全体に登録され、`pyvirtualcam` から見えるようになります。
   - **macOS**: OBS for Mac には system extension が同梱され、初回起動時に「システム設定 → プライバシーとセキュリティ」で有効化を求められます。
   - **Linux**: `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"`(事前に `apt install v4l2loopback-dkms` などが必要)。
3. Puppet タブで rig を開き、ツールバーまたは **Output > Virtual camera** をオン。ステータスバーに実際のデバイス名が表示されます。
4. OBS: **Sources > + > Video Capture Device** で、ステップ 3 のデバイス名(通常は *OBS Virtual Camera*)を選択。

Imervue は出力フレームの長辺を 1080 px に強制圧縮するので、Cubism ネイティブキャンバス(March 7th は 3503×7777)が DirectShow 仮想カメラドライバーに拒否されることはありません。アスペクト比は保持され、OBS 側でさらに縮小可能です。

各フレームはオフスクリーンフレームバッファで再描画されます — キャラクター本体のみをレンダリングし、チェッカー背景やエディタ UI シェルは含みません。そのため OBS には「キャラクター + 単色マゼンタ背景」が映ります。

##### なぜマゼンタ背景なのか?(そして取り除く方法)

仮想カメラは **DirectShow**(Windows)/ **AVFoundation**(macOS)/ **v4l2loopback**(Linux)で動作し、これら 3 つの伝送方式は **RGB のみ、アルファチャンネルなし** です。OBS の「Video Capture Device」ソースは入力映像を不透明 RGB として扱うため、Imervue がキャラクター以外に塗る色がそのまま OBS に表示されます。

**マゼンタ `#FF00FF`** を選んだのは業界標準のクロマキー色だからです。自然な肌色、髪色、瞳色にはほぼ出現しないため、キャラクターを傷つけずに広い許容差で透過できます。

OBS 側で透過する手順:

1. 追加した「Video Capture Device」ソースを右クリック → **フィルタ(Filters)**
2. 左下の **エフェクトフィルタ(Effect Filters)** セクション → **+** → **カラーキー(Color Key)**
3. 設定:
   - **Key Color Type**: `Custom Color`
   - **Custom Color**: HEX `FF00FF`(または R = 255 / G = 0 / B = 255)
   - **Similarity**: `80` から開始、エッジにマゼンタが残る場合は `200–300` まで上げる。値が大きいほど除去が強力
   - **Smoothness**: `30–50`。エッジが固くピクセルアートのようにならないようにする
4. ダイアログを閉じる。OBS はフィルタをソースに紐付けるので、次回仮想カメラを有効にすると自動で適用されます

キャラクターのパレットにマゼンタが含まれる場合(衣装 / 小物アートで稀にあり)、クロマキーがそのピクセルも食ってしまいます。下記の NDI に切り替えてください — アルファチャンネルを保持するのでクロマキー不要です。

**トラブルシューティング: OBS でまだマゼンタが見える**

- Color Key フィルタが **Video Capture Device ソース自体** に追加されていることを確認(Scene に追加されていないこと)。ソースに付けたフィルタはソースに付随しますが、Scene に付けたフィルタはソースが描画された後に適用されます。
- HEX が `FF00FF` ぴったりであることを確認 — `FF00FE` などではすべてのマゼンタピクセルを捕捉できません。
- キャラクターの輪郭に薄いマゼンタの halo が見える場合は *Similarity* を `300` まで上げる。これは GL_LINEAR がキャラクターの縁とマゼンタ背景の間で補間したもので、許容差を広げれば除去できます。

#### B. NDI(低遅延、プロ仕様)

NDI(Newtek の Network Device Interface)は LAN 上で 50 ms 未満の遅延、アルファチャンネル保持で puppet を伝送します。

1. <https://ndi.video/tools/> から **NDI Tools**(NDI ランタイム含む)をダウンロードしてインストール。
2. `pip install ndi-python`
3. OBS 側に **obs-ndi** プラグインをインストール: <https://github.com/obs-ndi/obs-ndi/releases>
4. Puppet タブのツールバーまたは **Output > NDI output** をオン。ステータスバーに NDI ソース名(デフォルト *Imervue Puppet*)が表示されます。
5. OBS: **Sources > + > NDI Source** で、ステップ 4 のソース名を選択。

NDI も 1080 上限のスケーリングですが、RGBA を伝送します。オフスクリーンレンダリングがキャラクター以外の領域を完全に透明にし、アルファチャンネルをそのまま伝送するので、OBS / vMix 側でクロマキーなしにキャラクターを直接シーンに合成できます。

#### C. ウィンドウキャプチャ(フォールバック)

OBS **Sources > + > Window Capture** で Imervue ウィンドウを直接取り込めます。依存ゼロ。画質は低く、UI シェルを自分でクロップする必要がありますが、ドライバーをインストールできないロックダウンマシンでも動作します。

### サンプル

サンプル rig は [`examples/puppet/march_7th.puppet`](../examples/puppet/march_7th.puppet) にあります — 307 drawable の Cubism Live2D キャラクターをリポジトリ内で変換したもの。**Open Puppet…** から開くと中央に rig がロードされ、18 個のモーション(Idle グループ + Gesture グループ)のいずれかをクリックすれば再生されます。ジェスチャーには、ピース、顔隠し、写真、頬染め、黒い顔、泣き、汗、星、流れ星 — rig が定義するすべての命名済みジェスチャーが含まれます。

---

## Desktop Pet — フレームレスオーバーレイ

タブ 5 — **Desktop Pet** は、任意の `.puppet` キャラクターをフレームレスで透明なオーバーレイとしてデスクトップに表示します。タブ自体はコントロールパネルで、実際のキャラクターは他のウィンドウの上(または背後)に浮かんでいます。Puppet タブで rig に対してできることはすべて — モーション、表情、物理、アイドルドライバー、ウェブカメラ / マイク入力 — ここでも動作します。

### できること

| 機能 | 説明 |
|---|---|
| フレームレスオーバーレイ | ウィンドウクロームなし、タスクバーエントリなし — デスクトップ上にキャラクターだけが表示されます。 |
| 透明な背景 | キャラクターが覆っていない部分は、すべてデスクトップが透けて見えます。 |
| ドラッグして移動 | キャラクターを左ドラッグして新しい位置へ。画面端の近くで離すと、その端にぴったりと**スナップ**します。 |
| クリックスルーモード | ペットがマウスを無視するようにして、その下で作業を続けられます。 |
| 位置のロック | ペットを固定して、誤ドラッグで動かないようにします。 |
| 常に最背面 | ペットをすべてのウィンドウの背後に配置 — 常に最前面ではなく、デスクトップウィジェットのような感覚に。 |
| フルスクリーン時に非表示 | 同じモニターで別のアプリ(ゲーム / 動画 / プレゼン)がフルスクリーンの間は自動的に非表示になり、フルスクリーンが終わると戻ります。 |
| 非表示中は一時停止 | 非表示の間はアニメーションを停止 — 画面外では CPU 使用ゼロです。 |
| サイズプリセット | Small / Medium / Large。中心を基準にリサイズされるので、ペットが画面を飛び跳ねることがありません。 |
| 不透明度スライダー | ペットを 10% から 100% までフェードできるので、控えめなデスクトップ装飾としても使えます。 |
| 位置を記憶 | お気に入りのコーナーにドラッグすれば、次回起動時にもそこに戻ります。 |

### クリック操作

- **本体への左クリック** — rig がヒットエリア(例:頭をタップ)を定義していれば、対応するモーションが再生されます。何もマッチしなければ、スピーチバブルで挨拶します。
- **どこでも右クリック** — コンテキストメニューを開きます:ペットを非表示、ライブドライバー、モーション再生(rig 内のすべてのモーション一覧)、表情適用、位置のロック、クリックスルー、常に最背面、フルスクリーン時に非表示、スピーチバブル、サイズ。
- **システムトレイアイコン** — 左クリックで表示切り替え、右クリックで表示 / 非表示、クリックスルー、Open puppet、Hide pet。

### ライブドライバー

タブまたは右クリックメニューから好きな組み合わせを選択。各ドライバーはデフォルトでオフ — 必要なものだけ有効にしてください。

- **オートアイドル** — 呼吸 + 微妙なドリフトでキャラクターが生きているように感じられます。
- **アイドルモーション** — rig の Idle グループのモーションをランダムに循環再生。
- **オートまばたき** — 数秒ごとに自然なまばたきサイクル。
- **ドラッグ追従ヘッド** — 頭がカーソルを追いかけます。
- **マイクリップシンク** — あなたの声で口が開きます(`sounddevice` が必要)。
- **ウェブカメラ追跡** — 頭 / 目 / 口の動きがパペットを駆動します(`opencv-python` と `mediapipe` が必要)。

### 始め方

1. **Desktop Pet** タブに切り替えます。
2. **Load bundled March 7th** をクリックして同梱キャラクターを使うか、**Open Puppet…** で自分の `.puppet` ファイルを選択します。
3. **Show pet on desktop** にチェックを入れます。
4. キャラクターを好きな場所にドラッグし、使うドライバーを選び、不透明度 / サイズを調整します。
5. いつでも右クリックでクイックアクションメニュー、またはシステムトレイアイコンからタブを開かずにペットを非表示にできます。

設定した内容 — 位置、ドライバー、不透明度、クリックスルー、サイズ — はすべて起動間で記憶されます。

---

## キーボード & マウスショートカット

### ナビゲーション(全モード)

| ショートカット | 動作 |
|----------|--------|
| 矢印キー | グリッドスクロール / 画像切り替え(ディープズーム中は左 / 右) |
| Shift + 矢印 | 細かいスクロール(半ステップ) |
| Ctrl+Shift+←/→ | 画像を含む前 / 次のサイブリングフォルダへジャンプ |
| Alt+← / Alt+→ | 履歴を戻る / 進む |
| Ctrl+G | N 番目の画像へジャンプ |
| X | ランダム画像へジャンプ |
| Home | ズームとパンを原点にリセット |
| Ctrl+F または / | ファジー検索ダイアログを開く |
| Ctrl+Shift+P | コマンドパレットを開く |
| Alt+M | 現在の選択で直前のマクロを再生 |
| S | スライドショーダイアログを開く |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z / Ctrl+Y | Redo |

### ディープズーム / 単一画像

| ショートカット | 動作 |
|----------|--------|
| F | フルスクリーン切り替え |
| Shift+Tab | シアターモード切り替え |
| R / Shift+R | 時計回り / 反時計回り回転 |
| E | 画像エディタを開く(Modify タブ) |
| W / Shift+W | 幅 / 高さに合わせる |
| H | RGB ヒストグラム切り替え |
| F8 / Ctrl+F8 | OSD オーバーレイ / デバッグ HUD |
| Shift+P | ピクセルビュー切り替え(400% 以上でグリッド + RGB を表示) |
| Shift+M | カラーモード循環 |
| B | ブックマーク切り替え |
| Ctrl+C / Ctrl+V | クリップボードへ画像をコピー / クリップボードから貼り付け |
| 0 / 1-5 | お気に入り切り替え / クイックレーティング |
| F1-F5 | クイックカラーラベル |
| P / Shift+X / U | カリング: キープ / 拒否 / フラグ解除 |
| Shift+S | 分割ビュー |
| Shift+D / Ctrl+Shift+D | 見開き(LTR / RTL) |
| Ctrl+Shift+M | マルチモニターミラーウィンドウ |
| Delete | ゴミ箱へ移動(復元可) |
| Escape | ディープズーム / フルスクリーン終了 |

### アニメーション再生(GIF / APNG)

| ショートカット | 動作 |
|----------|--------|
| Space | 再生 / 一時停止 |
| , (カンマ) / . (ピリオド) | 前のフレーム / 次のフレーム |
| [ / ] | 再生速度ダウン / アップ |

### タイルグリッド

| ショートカット | 動作 |
|----------|--------|
| Ctrl+L | グリッド ↔ リスト切り替え |
| ホバー(500 ms) | ホバープレビューポップアップ |
| Delete | 選択タイル削除 |
| Escape | 全選択解除 |

### マウス / タッチパッド

| 操作 | 動作 |
|--------|----------|
| 左クリック | タイル選択または画像を開く |
| 左ドラッグ | グリッドで矩形複数選択 |
| 長押し(500 ms) | タイル選択モード開始 |
| 中ドラッグ | ディープズーム中のパン |
| ホイール | ズームまたはスクロール |
| 右クリック | コンテキストメニュー |
| ピンチ | ディープズーム中のズーム |
| 水平スワイプ | 前 / 次の画像 |

### Paint タブ(上記に加えて)

| ショートカット | 動作 |
|----------|--------|
| B / E / G / I | ブラシ / 消しゴム / 塗りつぶし / スポイト |
| V / T / U / R | 移動 / テキスト / グラデーション / 矩形選択 |
| P / S / C / Z / H | ペン / 指先 / クローン / ズーム / ハンド |
| Q | クイックマスクモード切り替え |
| Tab | すべてのドック切り替え |
| Ctrl+Tab | Paint タブ循環 |
| , / . | ブラシ種類循環 |
| 0-9 | ブラシ不透明度 10% ステップ |
| Alt+[ / Alt+] | アクティブレイヤーを下 / 上へ |

---

## メニュー構造

### File

- New Window
- Open Image / Open Folder
- Recent(フォルダ + 画像)
- Bookmarks / Tags & Albums
- Commit Pending Deletions
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association(Windows)
- **Session** — Save / Load
- **Workspaces…** — 名前付きウィンドウレイアウトを保存 / 読み込み / リネーム
- **External Editors…** + **Open in External Editor**
- Keyboard Shortcuts(カスタマイズ可能なバインディング)
- Exit

### Tools(追加ツール — 8 つのグループ別サブメニュー)

- **バッチ** — フォーマット変換 · EXIF 除去 · 画像サニタイザー · 画像オーガナイザー · トークンバッチリネーム
- **ライブラリ & メタデータ** — ライブラリ検索 · スマートアルバム · 類似 / 重複検索 · 自動タグ付け · 階層タグ · メタデータエクスポート · XMP サイドカー · GPS ジオタグ
- **ビュー** — Timeline · Calendar · Map
- **ワークフロー** — カリング · ステージングトレイ · 仮想コピー · デュアルペイン FM · マクロ
- **エクスポート** — コンタクトシート PDF · Web ギャラリー · スライドショー動画(MP4)· プリントレイアウト
- **現像(非破壊)** — トーンカーブ · .cube LUT · スプリットトーニング · 局所調整マスク · 段階フィルタ · ベルビア · エンボス · デフリンジ · フィルムネガ · フィルミックトーンマップ · トーン / ディテールイコライザ · 極座標 · 万華鏡 · すりガラス · ソフトプルーフ
- **レタッチ & 変形** — AI 画像アップスケール · ノイズ低減 / シャープニング · ヒーリングブラシ · クローンスタンプ · 顔検出 · 空 / 背景 · クロップ / 水平補正 · 自動水平補正 · レンズ補正
- **マルチ画像** — HDR 合成 · パノラマ合成 · フォーカススタック

### View / Sort / Filter / Language / Plugins / Help

(標準メニュー — 完全なオプションはアプリ内を参照。)

### 右クリックコンテキストメニュー

ナビゲーション · クイック操作(表示 / パスコピー / 画像コピー)· 変形 · バッチ操作 · 削除 · 壁紙 · 比較 / スライドショー · エクスポート · 追加ツール · ブックマーク · 画像情報 · プラグインの提供項目。

---

## プラグインシステム

Imervue はサードパーティプラグインをサポートします。完全なリファレンスは [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md) を参照してください。

### クイックスタート

1. プロジェクトルートの `plugins/` フォルダ内にフォルダを作成
2. `ImervuePlugin` を継承するクラスを定義
3. `__init__.py` で `plugin_class = YourPlugin` として登録
4. Imervue を再起動

### フック

| フック | トリガー |
|------|---------|
| `on_plugin_loaded()` | プラグインがインスタンス化された後 |
| `on_plugin_unloaded()` | アプリ終了時 |
| `on_build_menu_bar(menu_bar)` | デフォルトメニューバー構築後 |
| `on_build_main_tabs(tabs)` | 4 つの組み込みタブが追加された後 |
| `on_build_context_menu(menu, viewer)` | 右クリックメニューを開いた時 |
| `on_image_loaded(path, viewer)` | ディープズームで画像がロードされた後 |
| `on_folder_opened(path, images, viewer)` | グリッドでフォルダが開かれた後 |
| `on_image_switched(path, viewer)` | 画像を切り替えた時 |
| `on_image_deleted(paths, viewer)` | 画像がソフト削除された後 |
| `on_key_press(key, modifiers, viewer)` | キー押下時(True を返すとイベント消費) |
| `on_app_closing(main_window)` | アプリ終了直前 |
| `get_translations()` | i18n 文字列を提供 |

### プラグインダウンローダ

**Plugins > Download Plugins** でオンラインダウンローダを開きます。ソースリポジトリ: [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins)。

---

## MCP サーバー

Imervue には [Model Context Protocol](https://modelcontextprotocol.io) サーバーが組み込まれており、AI アシスタント(Claude Code / Desktop、Cursor、Cline …)が GUI なしでプロジェクトの純粋ロジックツールを呼び出せます。Qt フリーで、1 つのコマンドで起動します:

```sh
python -m Imervue.mcp_server
```

### ツール

主なツール(全 41 種 — 完全な一覧はドキュメントを参照)。すべてのツールは JSON
の `outputSchema` と read-only / destructive の `annotations` を公開し、結果を
`structuredContent` として返します。長時間実行されるツールは
`notifications/progress` をストリーミングします。

| ツール | 用途 |
|------|---------|
| `list_images` | フォルダ内の画像をリスト(再帰オプション付き) |
| `read_image_metadata` / `read_xmp_tags` | 寸法、フォーマット、EXIF、XMP サイドカー(レーティング、ラベル、キーワード) |
| `image_statistics` / `quality_metrics` / `read_histogram` / `sharpness_score` | 参照なし解析: チャンネルごとの統計、colourfulness / entropy / contrast、ヒストグラム + クリッピング、ブラースコア |
| `image_thumbnail` / `ocr_text` / `find_similar` | Base64 プレビュー、Tesseract テキスト、知覚ハッシュによる近似重複グループ(進捗付き) |
| `convert_format` | PNG / JPEG / WebP / TIFF / BMP(+ オプションで HEIC / AVIF / JXL)間で変換 |
| `apply_watermark` / `apply_frame` | テキストウォーターマークを焼き込み、またはマット / ポラロイドフレーム + キャプションを追加 |
| `build_collage` | 複数の画像をグリッドモンタージュに合成(進捗付き) |
| `crop_image` / `resize_image` / `rotate_image` | ピクセル単位のクロップ、アスペクト比を保持したリサイズ、ロスレスな回転 / 反転 |
| `collection_stats` | フォルダのレーティング / お気に入り / カラーラベル / カリングのサマリー |
| `search_images` | スマートアルバムのクエリ DSL でフォルダをフィルタ(パス / EXIF / サイズ / 寸法) |
| `extract_gps` / `dominant_colors` | EXIF GPS 座標を読み取り(`reverse_geocode` に連鎖)、median-cut のカラーパレット(rgb / hex / 占有率) |
| `error_level_analysis` | JPEG 再圧縮の改ざんマップを PNG データ URI として出力 |
| `solarize_image` / `glow_image` | ソラリゼーションの階調反転、またはディフューズグローのブルームを適用して保存 |
| `velvia_image` / `emboss_image` / `defringe_image` | ベルビアの彩度ブースト、方向光のエンボス、エッジフリンジの脱色 |
| `film_negative_image` / `graduated_density_image` | スキャンしたネガを反転、リニアな段階フィルタのグラデーションを適用 |
| `filmic_tonemap_image` / `tone_equalizer_image` / `detail_equalizer_image` | フィルミックなハイライトロールオフ、ゾーンごとの露出、帯域ごとのコントラスト |
| `colormap_image` / `false_color_image` | 輝度を viridis/magma/jet のカラーマップで再着色、フォルスカラー露出スケール |
| `dither_image` / `split_toning_image` / `pixel_sort_image` | Bayer 整列ディザ、シャドウ/ハイライトのスプリットトーン、輝度帯のピクセルソート |
| `reverse_geocode` / `extract_video_frame` | オフラインで GPS → 都市名、動画の 1 フレームを静止画にデコード |
| `puppet_from_png` / `puppet_inspect` | PNG から `.puppet` rig を構築。`.puppet` を開いてインベントリを返す |

### プロンプト

4 つの再利用可能なプロンプト: `caption_image`、`suggest_edits`、`analyze_composition`
(saliency 駆動の構図批評)、`flag_issues`(sharpness + quality + clipping の
トリアージ)。プロンプトの引数は `completion/complete` で補完できます。

### 設定

リポジトリルートに `.mcp.json` が同梱されており、Claude Code が自動検出します。Desktop / その他のクライアントでは、`claude_desktop_config.json`(または等価ファイル)に以下を追加してください:

```json
{
  "mcpServers": {
    "imervue": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "Imervue.mcp_server"]
    }
  }
}
```

完全なプロトコル仕様は [docs/en/index.rst](../docs/en/index.rst) の MCP セクションを参照してください。

---

## 多言語サポート

| 言語 | コード |
|----------|------|
| English | `English` |
| 繁體中文 | `Traditional_Chinese` |
| 简体中文 | `Chinese` |
| 한국어 | `Korean` |
| 日本語 | `Japanese` |

**Language** メニューから切り替え可能。再起動が必要です。

プラグインは `language_wrapper.register_language()` で完全に新しい言語を登録するか、`get_translations()` で翻訳を提供できます。詳細は [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n) を参照。

---

## ユーザー設定

作業ディレクトリの `user_setting.json` に保存されます。主なエントリ:

| 設定 | 型 | 説明 |
|---------|------|-------------|
| `language` | string | 現在の言語コード |
| `user_recent_folders` / `user_recent_images` | list | 最近開いた項目 |
| `user_last_folder` | string | 起動時に自動復元 |
| `bookmarks` | list | ブックマークパス(最大 5000) |
| `sort_by` / `sort_ascending` | string / bool | ソート方法 + 順序 |
| `image_ratings` / `image_favorites` / `image_color_labels` | dict / set / dict | 画像ごとの整理 |
| `thumbnail_size` / `tile_padding` | int | グリッド構成 |
| `navigation_auto_loop` | bool | フォルダ末尾で自動ループ |
| `keyboard_shortcuts` | dict | カスタムキーバインド |
| `window_geometry` / `window_state` / `window_maximized` | string / string / bool | ウィンドウレイアウト永続化 |
| `stack_raw_jpeg_pairs` | bool | RAW+JPEG スタック切り替え |
| `external_editors` | list | 設定済みエディタ |
| `macros` / `macro_last_name` | list / string | 保存済みマクロ + Alt+M ターゲット |

---

## アーキテクチャ

```
Imervue/
├── __main__.py              # アプリケーションエントリーポイント
├── Imervue_main_window.py   # メインウィンドウ(QMainWindow)— 4 つのタブをマウント
├── gpu_image_view/          # IMERVUE タブ — GPU ビューア + ディープズーム
├── gui/                     # ダイアログとサイドパネル(現像、EXIF など)
├── paint/                   # PAINT タブ — 本格的なラスター描画エディタ
├── puppet/                  # PUPPET タブ — 2D リギングパペットアニメーター
├── export/                  # エクスポートジェネレータ(コンタクトシート、Web ギャラリー、MP4)
├── image/                   # 画像ユーティリティ(ピラミッド、タイルマネージャ、情報)
├── library/                 # ライブラリヘルパー(RAW+JPEG スタック、インデックス)
├── macros/                  # マクロ録画 / 再生
├── menu/                    # メニュー定義
├── mcp_server/              # Model Context Protocol stdio サーバー
├── multi_language/          # i18n(en / zh-tw / zh-cn / ja / ko)
├── external/                # 外部エディタ統合
├── plugin/                  # プラグインシステム(base / manager / downloader)
├── sessions/                # ワークスペースのシリアライズ
├── system/                  # Windows ファイル関連付け
└── user_settings/           # 永続ユーザー設定
```

### レンダリングパイプライン(Imervue タブ)

1. `GPUImageView` は `QOpenGLWidget` を継承
2. 2 つの GLSL 1.20 プログラム(textured quads + solid color rectangles)
3. LRU テクスチャキャッシュ — 256 タイル上限、1.5 GB VRAM 予算
4. 512 × 512 タイルサイズで LANCZOS によるマルチレベルタイルピラミッド構築
5. ハードウェアがサポートする場合は最大 8× の異方性フィルタリング
6. シェーダーコンパイル失敗時はソフトウェアレンダリングへフォールバック

### サムネイルキャッシュ

- **キー**: `{path}|{mtime_ns}|{file_size}|{thumbnail_size}` の MD5
- **フォーマット**: 圧縮 PNG(`compress_level=1` — 書き込み高速、サイズ小)
- **場所**: `%LOCALAPPDATA%/Imervue/cache/thumbnails`(Win)または `~/.cache/imervue/thumbnails`(Linux/macOS)
- **無効化**: ファイルメタデータ変更時に自動

### Puppet レンダリング(Puppet タブ)

- `QOpenGLWidget` に `glDrawElements` + クライアントサイド vertex array
- drawable ごと: rest vertices を float32 numpy にキャッシュ、vertex morphs をベクトル化、topological deformer sort を drawable ごとのループの外に巻き上げ
- 透明背景は 2×2 GL_REPEAT タイリングテクスチャ(最適化前は 100k+ の即時モード quads)
- Cubism コンバーターは opacity_keys カーブと vertex-morph delta を同時に生成するので、パラメーター駆動の可視性切り替えが `.moc3 → .puppet` 変換後も生き残る

---

## ライセンス

本プロジェクトは [MIT License](../LICENSE) でライセンスされています。

Copyright (c) 2026 JE-Chen
