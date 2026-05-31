# Streamlit Cloud 依存関係エラー対策 改修計画書

本ドキュメントは、本アプリケーションを Streamlit Community Cloud にデプロイした際に発生した `ModuleNotFoundError: No module named 'cv2'` エラーの調査結果と対策についてまとめたものです。

## 根本原因の分析

Streamlit Community Cloud 上でアプリ実行が失敗していた原因は以下の通りです：

1. **`requirements.txt` の欠落**:
   - リポジトリのルートディレクトリに依存ライブラリを記述した `requirements.txt` が存在しないため、Streamlit Cloud環境が `app.py` や `src/ocr_engine.py` に記述された外部ライブラリ（`easyocr`, `cv2`, `numpy`, `pandas`, `pillow` など）を検出してインストールすることができませんでした。
2. **OpenCV の環境依存（GUIパッケージの問題）**:
   - ヘッドレスな Linux コンテナ環境である Streamlit Cloud では、通常の `opencv-python` パッケージをインストールすると `libGL.so.1` などの X11/GUI 関連の共有ライブラリが見つからないエラー（`ImportError`）で起動に失敗します。
   - 対策として、GUI機能を除外した `opencv-python-headless` をインストールする必要があります。

---

## 提案する解決策

### 1. `requirements.txt` の新規追加

プロジェクトのルートディレクトリに、必要な依存パッケージを完全に網羅した `requirements.txt` を新規作成します。

#### [NEW] [requirements.txt](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/requirements.txt)
```text
streamlit>=1.30.0
easyocr>=1.6.2
opencv-python-headless>=4.8.0
pandas>=2.0.0
numpy>=1.24.0
pillow>=10.0.0
```

> [!TIP]
> **`opencv-python-headless` の採用メリット**
> `opencv-python-headless` を指定することで、Streamlit Cloud側のOSパッケージ設定ファイル（`packages.txt`）で `libgl1-mesa-glx` 等のシステムライブラリをわざわざインストールする手間を省略でき、コンテナビルドが高速化かつ軽量化されます。

---

## 検証計画

### 1. ローカルでのインストール検証
- ローカル環境で `pip install -r requirements.txt` を実行し、パッケージの競合やエラーがないことを確認します。

### 2. Streamlit Cloud への再デプロイ検証
- リポジトリに `requirements.txt` をコミット・プッシュしていただき、Streamlit Cloud が自動で依存パッケージをビルドおよびインストールし、正常に「サカつく2026 パラメータOCRリーダー v0.1」のUIが表示されることを確認します。
