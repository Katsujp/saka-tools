# システム全体の構造と思想の解析・調査計画

本計画書は、ユーザーからの指示に基づき、「サカつく2026 パラメータOCRリーダー」のシステム全体のコードを詳細まで解析し、その全体の構造と思想を余さず把握するための調査計画と概要をまとめたものです。

## 原因（解析の背景）
ユーザーより「まずはコード全体を詳細まで全て解析し、システムの全体の構造と思思想まで余さず把握してください」との指示があったため。本プロジェクトはフロントエンドとバックエンドの非同期通信、OpenCVによる高精度な画像正規化・前処理、EasyOCRの並行処理時スレッドロックなど、高度で繊細なアルゴリズムが融合しているため、これらを正確に読み解く必要があります。

## 調査および整理の構成要素

### 1. 全体構造の可視化
- コンポーネント間の関係（Streamlit, EasyOCR, HTML/JS Canvas HUD, Paste Bridge, Googleスプレッドシート）を整理・可視化します。
- データの流れ（画像取得 → 正規化 → アライメント計算 → 前処理 → OCR解析 → 結果確認/編集 → コピペ展開）を整理します。

### 2. プレミアムな設計思想の抽出
- **堅牢な非同期同期ガード機構**: Streamlitと双方向カスタムコンポーネント間で発生しやすい「非同期逆流上書き戻りバグ」をJS側の `lastSentState` キャッシュでどのように完全封殺しているかを解説。
- **高精度OCRのための画像前処理の黄金比**: Lanczos4補間による3.5倍拡大、パラメータカテゴリごとの絶対二値化閾値（個別詳細は生グレースケール拡大のみ、総合力/メイン数値は155）の設定思想を抽出。
- **Windows環境のクラッシュ徹底防止処理**: DPI Aware設定、標準出力エンコードパッチ、EasyOCR進捗バーパッチなど、実用性を極限まで高めるためのWindows環境対策の解説。
- **双方向ロール連携**: FPとGKのロール切替時に、対応する調整座標（オフセット、スケール）をメモリ上で相互移行する親切設計の整理。

### 3. ドキュメントの構成
- [task.md](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/docs/20260602_system_structure_and_philosophy/task.md): 進捗管理
- [implementation_plan.md](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/docs/20260602_system_structure_and_philosophy/implementation_plan.md): 調査設計（本ファイル）
- [walkthrough.md](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/docs/20260602_system_structure_and_philosophy/walkthrough.md): 解析報告書

## 検証計画
- 抽出したROI算出計算式や前処理アルゴリズム、スレッドロックなどの仕様が実際のソースコード（`app.py`, `src/config.py`, `src/ocr_engine.py`, `src/fitting_hud/index.html`, `src/paste_bridge/index.html`）の記述と100%一致していることを机上デバッグおよびコード比較で厳密に確認します。
