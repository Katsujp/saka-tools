# タスクリスト: Streamlit Cloud デプロイ環境における EasyOCR 起動クラッシュの修正

- [x] 改修計画の作成とユーザー承認の取得（implementation_plan.mdの作成）
- [x] `app.py`（ルート）の修正
  - [x] Windows固有パッチ（DPI Aware、urlretrieve進捗パッチ）の適用範囲を Windows 環境のみに制限
- [x] `src/ocr_engine.py` の修正
  - [x] 確実に書き込み可能な一時ディレクトリ（`/tmp/easyocr_models`等）を自動生成し、EasyOCRリーダー初期化時の `model_storage_dir` に明示的に設定するよう改修
- [x] ローカル（Windows）での起動テストおよび動作検証
- [x] 修正結果の確認（walkthrough.mdの作成）
