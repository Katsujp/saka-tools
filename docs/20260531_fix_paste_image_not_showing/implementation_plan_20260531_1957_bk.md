# 実装計画：OCRエラーの解消およびアライメントスライダージャンプバグの完全封殺

本ドキュメントは、発生しているOCR解析時の `is_preprocessed` 引数エラー（TypeError）を解消し、スライダーを動かしてドラッグを離した瞬間に枠やスライダーが元の位置（あるいは意図しない位置）にジャンプしてしまう深刻な不整合バグを徹底究明し、その強固な修正設計を提案する実装計画書です。

---

## 🚨 先進的プロセス順守に関する誓約

> [!IMPORTANT]
> ユーザー様の明示的な計画承認を得る前に、勝手にソースコードの修正（実装）を進めることは一切行いません。
> **必ず本計画書のレビューとユーザー様の明確なご承認（GOサイン）をいただき、指示があるまで実際のソースコードの変更ツールは一切起動しない**ことを固く誓約いたします。

---

## 🚨 原因究明 (バグ診断)

### 1. OCR解析時の `is_preprocessed` 引数エラーの根本原因
- **原因**: 
  Streamlitの仕様上、セッション状態（`st.session_state`）に一度格納された `ocr_engine` インスタンスは、Streamlitサーバーが起動し続ける限り（または手動でキャッシュをクリアしない限り）メモリ上に残り続けます。
  前回のアップデートで `src/ocr_engine.py` の `extract_all_parameters` メソッドに `is_preprocessed` 引数を追加しましたが、セッションにキャッシュされている古いクラス定義のインスタンスが使われ続けたため、引数不整合（`TypeError: got an unexpected keyword argument 'is_preprocessed'`）が発生してクラッシュしていました。

### 2. スライダーを離した際に枠がジャンプするバグの根本原因
- **原因①: Python側とJS側での個別座標キーの不一致による強制リセット**
  Python側（`app.py`）の個別座標の同期処理において、`DEFAULT_ROIS.keys()` を使ってループを回していました。
  しかし、JS側の個別スライダーは基本項目やメイン数値（"総合力" や "SHO数値" など）の個別スライダーを生成しないため、JS側から送られてくる個別アライメント座標（`individual_offsets`）にはこれらのキーが含まれていません。
  そのため、`js_ind_offsets.get(item, [0, 0])` によって、Python側の個別アライメント座標が同期のたびにすべて `[0, 0]`（初期値）に強制上書き（リセット）されていました。
- **原因②: GK特有項目（セービング、反応速度、1対1）の同期漏れ**
  `DEFAULT_ROIS.keys()` にはGK特有項目のキーが含まれていないため、GKロール選択時にユーザーが調整した「セービング」「反応速度」「1対1」の個別座標がPython側に一切同期されず、逆同期の際にJS側に「空（存在しない）」の状態で書き戻され、初期値にリセットされていました。
- **原因③: `JSON.stringify` 比較による無限再描画・ジャンプのトリガー**
  JS側（`index.html`）の `streamlit:render` メッセージ受信時、`JSON.stringify(state.individual_offsets) !== JSON.stringify(args.individual_offsets)` によって値の変更を検知していました。
  しかし、上記①・②のキー不一致があるため、この比較結果は**常に不一致（true）**となり、スライダーを動かして離すたびにスライダーUI全体が毎回強制的に再構築（DOMの innerHTML 再生成）され、入力値やフォーカスが吹き飛び、スライダーと枠が初期位置（0 px や 1.00 x）にジャンプして戻ってしまっていました。

---

## 🛠️ 提案する具体的な変更設計 (承認後に実施)

### 1. `app.py` の修正計画

* **OCRエンジンのキャッシュ定義不整合の自動修復ガードの追加**:
  モジュールが更新されたことをシグネチャ検証で自動検知し、安全に再ロードするロジックを `app.py` に追加します。
  ```python
  import inspect
  
  if "ocr_engine" not in st.session_state:
      with st.spinner("OCRシステム起動中..."):
          st.session_state.ocr_engine = SakatsukuOCREngine()
  else:
      # 開発中のコード変更に追従するため、メソッドシグネチャを動的に検証して自動再ロード
      sig = inspect.signature(st.session_state.ocr_engine.extract_all_parameters)
      if "is_preprocessed" not in sig.parameters:
          with st.spinner("OCRシステムの定義更新を検知。再起動中..."):
              st.session_state.ocr_engine = SakatsukuOCREngine()
  ```

* **ロール（FP/GK）に応じた動的同期キーの最適化**:
  `DEFAULT_ROIS.keys()` による同期ループを廃止し、現在選択されているロールに応じてJS側と100%一致する有効な個別キーリストのみを動的に定義して同期します。
  ```python
  # ロールに応じた有効な個別パラメータのキーリストを定義
  base_detail_items = ["決定力", "キック力", "冷静さ", "ショートパス", "ロングパス", "キック精度", "突破力", "キープ力", "ボールタッチ", "ジャンプ", "コンタクト", "スタミナ", "走力", "敏捷性"]
  if st.session_state.is_gk:
      detail_items = base_detail_items + ["セービング", "反応速度", "1対1"]
  else:
      detail_items = base_detail_items + ["タックル", "パスカット", "マーク"]
      
  # 個別パラメータの同期
  js_ind_offsets = resp_data.get("individual_offsets", {})
  js_ind_scales = resp_data.get("individual_scales", {})
  for item in detail_items:
      st.session_state.individual_offsets[item] = js_ind_offsets.get(item, [0, 0])
      st.session_state.individual_scales[item] = js_ind_scales.get(item, [1.0, 1.0])
  ```

### 2. `src/fitting_hud/index.html` の修正計画

* **`streamlit:render` 受信時の比較と代入の安全化（ディープコピー適用）**:
  代入時の参照共有を防ぐため、`JSON.parse(JSON.stringify(args.xxx))` を用いて値コピーを行い、かつ値が本当に変わったキーのみをスマートに検知して部分適用します。
  ```javascript
  // 個別パラメータの逆同期 (ディープコピーを適用し、値が本当に変化したか厳密にスマートチェック)
  let indivChanged = false;
  if (args.individual_offsets !== undefined) {
      const argsCopy = JSON.parse(JSON.stringify(args.individual_offsets));
      // 有効なキーのみで値の差分を厳密に比較
      let hasDifference = false;
      for (const item of state.activeItems) {
          if (!state.individual_offsets[item] || !argsCopy[item] ||
              state.individual_offsets[item][0] !== argsCopy[item][0] ||
              state.individual_offsets[item][1] !== argsCopy[item][1]) {
              hasDifference = true;
              break;
          }
      }
      if (hasDifference) {
          state.individual_offsets = argsCopy;
          indivChanged = true;
      }
  }
  ```

---

## 📊 検証計画 (Verification Plan)

### 自動/手動検証
1. `python -m py_compile app.py` による構文チェックを実行。
2. アプリケーションにアクセスし、画像をロードまたはペーストする。
3. 全体スライダー、グループスライダー、個別スライダーを操作し、ドラッグを離した瞬間に枠線が元の位置に戻ることなく、**配置した場所に100%確実にピタッと留まり続けること**を検証。
4. GKロールに切り替えた際、「セービング」「反応速度」「1対1」の個別座標スライダーを動かして離した際にも、枠がズレたり初期位置にジャンプしないことを検証。
5. 「選択座標で解析を実行」ボタンを押し、`is_preprocessed` エラーが発生せず、OCR解析が100%確実に完了することを検証。
