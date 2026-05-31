# 改修内容確認書 (Walkthrough) - Streamlit Cloud 依存関係エラー対策

本ドキュメントは、Streamlit Community Cloud へのデプロイ時に発生した `ModuleNotFoundError: No module named 'cv2'` エラーの調査と、その解決策として実施した `requirements.txt` の新規追加内容を記録したものです。

## 根本原因と解決アプローチ

1. **エラーの原因**:
   - リポジトリのルートに依存関係定義ファイルが存在しなかったため、Streamlit Cloud 側が Python の `cv2` (OpenCV) や `easyocr` パッケージを自動インストールできず、インポートエラーが発生していました。
2. **ヘッドレス環境での OpenCV 対策**:
   - 通常の `opencv-python` は X11 などの GUI 関連ライブラリをリンクするため、Streamlit Cloud の Linux コンテナ上では `libGL.so.1: cannot open shared object file` などのエラーを引き起こします。
   - 今回は、GUI 依存を排除した **`opencv-python-headless`** を `requirements.txt` に指定することで、OSパッケージマネージャでのライブラリ追加設定（`packages.txt`）を一切不要にし、確実かつ高速なコンテナビルドを可能としました。

---

## 実施した変更内容

### 1. requirements.txt の新規作成
プロジェクトのルートに、本アプリケーションを稼働させるために必要な以下の依存パッケージを指定した [requirements.txt](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/requirements.txt) を新規作成しました。

```text
streamlit>=1.30.0
easyocr>=1.6.2
opencv-python-headless>=4.8.0
pandas>=2.0.0
numpy>=1.24.0
pillow>=10.0.0
```

---

## 検証結果と展開手順

### 1. ローカル検証
- 作成した `requirements.txt` の定義内容に競合がなく、正常に Python のパッケージとして動作することを確認しました。

### 2. Streamlit Cloud への展開方法（ユーザー様による操作）
この変更をクラウド環境に反映するため、お手数ですが以下の手順を実行してください。

1. 新規作成された `requirements.txt` を含む、今回の変更をローカルの Git リポジトリでコミットします：
   ```bash
   git add requirements.txt
   git commit -m "feat: add requirements.txt for Streamlit Cloud deployment"
   ```
2. 変更をリモート（GitHubなど）の `main` ブランチにプッシュします：
   ```bash
   git push origin main
   ```
3. GitHub へのプッシュが完了すると、Streamlit Community Cloud は `requirements.txt` の変更を自動で検知し、依存ライブラリの再インストールおよびビルドを自動的に開始します（これには数分かかる場合があります）。
4. ビルド完了後、画面にツールが正しく表示されることをご確認ください。
