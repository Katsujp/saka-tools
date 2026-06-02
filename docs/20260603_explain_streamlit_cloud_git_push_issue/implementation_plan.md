# 実装計画書: Streamlit CloudにおけるGitプッシュ未反映によるTypeErrorの原因究明

本計画書は、ローカル環境では正常に起動するにもかかわらず、Web上のStreamlit Cloudサーバーで依然として `TypeError: Reader.__init__() got...` が発生する問題について、その正確な原因究明と解決手順をまとめたものです。

---

## 原因（Web上でエラーが残っている理由の正確な特定）
添付画像のスタックトレース画像を詳細に解析した結果、エラーの根本的な原因は**「修正済みの最新コードがGitHubにプッシュ（反映）されていないため、Webサーバー上で古いコードが実行され続けていること」**にあります。

### 確実な証拠（エラーログの比較）:
- **Webサーバー上のエラー箇所（添付画像より抽出）**:
  ```python
  File "/mount/src/saka-tools/src/ocr_engine.py", line 33, in __init__
    self.reader = easyocr.Reader(['ja', 'en'], gpu=True, verbose=False, model_storage_dir=model_dir)
  ```
  ご覧の通り、Webサーバー上では依然として古い引数名である **`model_storage_dir=model_dir`** が実行されています。
  
- **ローカル環境の最新コード（修正済み）**:
  ローカル環境では、先ほどのスペル修正により、引数名が正しい **`model_storage_directory=model_dir`** に完全に書き換えられています。
  
- **結論**:
  ローカルPC上で行った最新の修正コードが、まだ GitHub リポジトリ（`main` ブランチ）に **プッシュ（git push）されていない**、あるいは **Streamlit Cloud 側への最新コミットの反映（Sync）が完了していない** ため、Web上のコンテナが古いリポジトリデータを引っ張って起動し、TypeErrorを起こしています。

---

## 解決手順

修正済みのローカルコードを GitHub にプッシュし、Streamlit Cloud に最新状態を同期させることで、バグはWeb上でも完全に解決します。

1. **Gitのコミットとプッシュ**:
   コマンドライン等で、修正したファイルをコミットして GitHub にプッシュします。
   ```bash
   git add app.py src/ocr_engine.py src/fitting_hud/index.html
   git commit -m "fix: EasyOCR model directory TypeError and add auto-repeat slide adjustments"
   git push origin main
   ```
2. **Streamlit Cloudでの再同期（Sync）の確認**:
   - プッシュが行われると、Streamlit Cloud は自動的にGitHubの更新を検知し、最新コードを引き抜いて（Pull）アプリを自動再起動します。
   - これにより、Web上でもTypeErrorが消え去り、一時フォルダ `/tmp/easyocr_models` へのダウンロードが正常に走り、アプリが100%確実に立ち上がります。

---

## 検証計画

### 1. Webサーバー上での正常起動確認
- GitHubへのプッシュ完了後、Streamlit Cloudの管理画面（Manage App）のビルドログを監視します。
- `model_storage_directory` に修正された最新の `ocr_engine.py` がロードされ、TypeErrorが収束し、Web上で選手パラメータOCRリーダーの漆黒ミニマルUIが正常に起動することを確認します。
