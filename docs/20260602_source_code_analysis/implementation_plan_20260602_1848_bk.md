# サカつく2026 パラメータOCRリーダーのソースコード解析計画

本計画は、ユーザーのリクエスト「現在の最新のソースを全て解析して、仕様やUI/UXなどを完全に把握してください」に基づき、システムの全体構造、各モジュールの機能、UI/UX設計、およびOCR処理の仕様について調査を行い、詳細なレポート（walkthrough）を作成するための計画書です。

## 原因・背景
ユーザーが開発環境の現状（最新の仕様、UI/UXデザイン、内部ロジック）を完全に把握し、今後の機能追加やリファクタリングをスムーズに進められるようにするため、ソースコードの網羅的な解析を行います。

## ユーザー確認事項
> [!NOTE]
> 今回のタスクは調査とレポート作成であり、既存 of ソースコード（Python, HTML, JSなど）に対する機能変更やバグ修正は行いません。

## オープン質問
特にありません。

## 提案する変更内容
プロジェクトの `docs` ディレクトリ以下に、今回の解析結果およびタスク管理を行うための新規フォルダ `20260602_source_code_analysis` を作成し、各種ドキュメントを配置します。

### ドキュメントコンポーネント

#### [NEW] [task.md](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/docs/20260602_source_code_analysis/task.md)
調査の進捗状況を追跡するためのタスクリストです。

#### [NEW] [implementation_plan.md](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/docs/20260602_source_code_analysis/implementation_plan.md)
本実装計画書です。

#### [NEW] [walkthrough.md](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/docs/20260602_source_code_analysis/walkthrough.md)
ソースコードの解析結果（詳細な仕様、アーキテクチャ、UI/UX設計）をまとめた最終レポートです。

---

## 検証計画

### 調査範囲の確認
- 以下のファイルを網羅的に解析できているか確認します：
  - ルート直下の [app.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/app.py) （メインStreamlitアプリ）
  - [src/app.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/app.py) （以前のStreamlitアプリ）
  - [src/config.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/config.py) （座標・ROI設定）
  - [src/ocr_engine.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/ocr_engine.py) （OCR処理・画像前処理エンジン）
  - [src/fitting_hud/index.html](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/fitting_hud/index.html) （CanvasプレビューHUD）
  - [src/paste_bridge/index.html](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/paste_bridge/index.html) （ペーストブリッジ）

### ドキュメントの確認
- 作成された `walkthrough.md` に、システムの動作仕様、画像前処理・OCR認識アルゴリズム、UI/UXデザイン（Apple Pro漆黒ミニマリズムUIおよびコピペステーション）の詳細が漏れなく日本語で記述されていることを確認します。
