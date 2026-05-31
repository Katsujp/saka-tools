# タスクリスト：プレビューとOCRの完璧な同期とスレッドセーフ化

- [x] `docs/20260531_flawless_coordinate_and_thread_sync/implementation_plan.md` の作成（原因究明と修正計画）
- [x] ユーザーによる実装計画のレビューおよび承認 of 獲得
- [x] 【承認後】`app.py` の修正
  - [x] 貼り付けられた画像の「トリミング・正規化済みPIL画像」のセッション保存とOCRへの引き渡し統合
  - [x] `trigger_analysis` 受信時の単一統合データからの最新座標の完全同期
  - [x] Iframe呼び出し時への全パラメータ調整引数の追加
- [x] 【承認後】`src/fitting_hud/index.html` の修正
  - [x] `triggerAnalysis` ボタン押下時の座標データとトリガーシグナルの一括送信（単一メッセージ化）
  - [x] 親（Python）から渡されたアライメント調整パラメータ引数の初期反映
- [x] 【承認後】`src/ocr_engine.py` の修正
  - [x] すでにトリミング・正規化済みの画像が渡された場合に、再トリミング（境界検出）をスキップするバイパス処理の追加
  - [x] 座標計算における JavaScript 側（`Math.round`）と完全に一致する四捨五入（`round()`）処理の統一
  - [x] 拡大補間アルゴリズムの `cv2.INTER_LANCZOS4` への移行（モヤボケ排除）
  - [x] マルチスレッド競合を防ぐ `threading.Lock`（排他制御）の導入
  - [x] 複数検出結果から正当な数値（100〜9999）を自動抽出するアルゴリズムの実装
- [/] 【承認後】動作検証および `walkthrough.md` の作成
