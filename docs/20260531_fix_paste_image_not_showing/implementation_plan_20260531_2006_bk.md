# 実装計画：グレーアウトクラッシュの完全封殺およびOCRモジュール強制リロードの実装

本ドキュメントは、スライダー移動時に発生する画面のグレーアウト（Iframe JavaScriptクラッシュ）の原因を究明し、かつ依然として発生しているOCRの `is_preprocessed` 引数エラー（TypeErrorキャッシュ問題）を強制的に再読込して解決する強固な修正設計を提案する実装計画書です。

---

## 🚨 先進的プロセス順守に関する誓約

> [!IMPORTANT]
> ユーザー様の明示的な計画承認を得る前に、勝手にソースコードの修正（実装）を進めることは一切行いません。
> **必ず本計画書のレビューとユーザー様の明確なご承認（GOサイン）をいただき、指示があるまで実際のソースコードの変更ツールは一切起動しない**ことを固く誓約いたします。

---

## 🚨 原因究明 (バグ診断)

### 1. スライダー操作時に画面がグレーアウトする根本原因
- **原因**: 
  前回の修正でJS側（`index.html`）の `streamlit:render` 受信時に `args.group_offsets !== undefined` などの条件分岐を追加しました。
  しかし、JavaScriptの仕様上、値が `null` の場合に `args.group_offsets !== undefined` は **真（true）** に判定されてしまいます。
  そのため、`null` がシリアライズされた状態で `JSON.parse(JSON.stringify(null))` ➔ `null` が実行され、その後のプロパティ読み取り（`grpOffCopy[grp]`）で **`TypeError: Cannot read properties of null`** が発生し、JavaScriptスレッドが完全にクラッシュ（実行停止）していました。これが画面がグレーアウトする根本原因です。

### 2. OCR実行時に依然として `is_preprocessed` エラーが発生する根本原因
- **原因**:
  Pythonの仕様上、一度 `import` されたモジュールは `sys.modules` にキャッシュされ、どれだけ `import` 文やクラスインスタンス生成を繰り返しても、キャッシュされた古いクラス定義（`is_preprocessed` を持たないもの）が使われ続けます。
  そのため、セッションにガードを入れて再生成をかけても、インポートキャッシュのせいで古いインスタンスが作られ続け、エラーが解消していませんでした。

---

## 🛠️ 提案する具体的な変更設計 (承認後に実施)

### 1. `app.py` の修正計画

* **インポートキャッシュを強制破棄するOCRエンジン完全リロードロジックの導入**:
  `importlib.reload` を使用し、更新検知時に `sys.modules` キャッシュ自体を破棄して最新の `src/ocr_engine.py` ファイルから最新定義を安全にリロードするガードを実装します。
  ```python
  import sys
  import importlib
  import inspect
  
  if "ocr_engine" not in st.session_state:
      with st.spinner("OCRシステム起動中..."):
          st.session_state.ocr_engine = SakatsukuOCREngine()
  else:
      # 開発中のコード変更に追従するため、メソッドシグネチャを動的に検証して自動再ロード
      sig = inspect.signature(st.session_state.ocr_engine.extract_all_parameters)
      if "is_preprocessed" not in sig.parameters:
          with st.spinner("OCRシステムの定義更新を検知。再起動中..."):
              if "src.ocr_engine" in sys.modules:
                  importlib.reload(sys.modules["src.ocr_engine"])
              from src.ocr_engine import SakatsukuOCREngine
              st.session_state.ocr_engine = SakatsukuOCREngine()
  ```

### 2. `src/fitting_hud/index.html` の修正計画

* **falsy（null / undefined）を完全に排除する厳密な真値チェックへの移行**:
  `!== undefined` による脆弱な比較を廃止し、`if (args.group_offsets)` などの強力な真値検証に移行してプロパティアクセス例外を100%封殺します。
* **レンダリングイベント全体の Try-Catch 保護の追加**:
  何らかの予期せぬブラウザ例外が発生した場合でも、Iframe全体の描画クラッシュ（グレーアウト）を完全に防ぎ、安全に動作を継続できるようにハンドラ全体を try-catch でセキュア保護します。
  ```javascript
  window.addEventListener("message", function(event) {
      const payload = event.data;
      if (payload.type === "streamlit:render") {
          try {
              const args = payload.args;
              if (!args) return;
              
              // 各種同期処理 (try-catchで安全に包まれて実行！)
              ...
          } catch (err) {
              console.error("[PasteHUD] Safety guard caught render error:", err);
          }
      }
  });
  ```

---

## 📊 検証計画 (Verification Plan)

### 自動/手動検証
1. `python -m py_compile app.py` による構文チェックを実行。
2. アプリケーションをリロードし、スライダーを操作した際に、画面がグレーアウトすることなく**100%スムーズに枠が追従し、操作可能であり続けること**を検証。
3. 「選択座標で解析を実行」ボタンをクリックした際、`is_preprocessed` エラーが発生せず、OCR解析が100%確実に成功することを検証。
