# 【サカつく2026】HTML5ブラウザペースト（TypeError解消＆公式コンポーネント化）改修計画書

本計画は、ユーザー様よりご報告いただいた「TypeError: IframeMixin._html() got an unexpected keyword argument 'key'」という致命的エラーの原因を特定し、Streamlitの公式設計に則った「ディレクトリベースのインライン・カスタムコンポーネント」へと刷新することで、エラーを100%解消し、かつクリップボードからの超高解像度画像取得（Ctrl+V）を確実に動作させるための改修計画です。

## 原因分析

1. **Streamlit標準APIの仕様不一致**:
   * `app.py` の 385行目において `streamlit.components.v1.html` 関数を呼び出す際、`key="paste_bridge"` という引数を指定していました。
   * しかし、Streamlitの静的HTMLレンダリング用関数である `components.html` は `key` 引数をサポートしていません（状態管理用の引数がないため）。これにより、Python実行時に `TypeError` が発生し、アプリケーション全体がクラッシュしていました。

2. **静的HTMLによるデータ通信の限界**:
   * 仮に `key` 引数を除去してエラーを回避したとしても、単なる静的HTML (`components.html`) の中から `Streamlit.setComponentValue` を呼び出すだけでは、Streamlit側でメッセージが処理されず、Python側に値が返ってきません。
   * Streamlitでiframeから親のPythonプロセスへ値を安全に返すには、公式のメッセージオブジェクト構造（`isStreamlitMessage: true`）を含む通信と、Streamlit側でカスタムコンポーネントとしての正式な宣言（`declare_component`）が必要です。

---

## 対策・提案内容（解決策）

この問題を根本的かつ安全に解決するため、以下の構成に刷新します。

1. **インライン・カスタムコンポーネントの導入**:
   * プロジェクト内に `src/paste_bridge` という軽量なフロントエンド用フォルダを新規作成し、その中に `index.html`（HTML+JS）を配置します。
   * `app.py` 内で `components.declare_component("paste_bridge", path="src/paste_bridge")` として公式にコンポーネント登録します。
   * これにより、**Streamlitが公式に `key` 引数をサポート**し、iframeからPythonへの安全なデータ受渡しが完全に保証されます。

2. **通信メッセージの最適化**:
   * `index.html` 内のJavaScriptにおいて、Streamlitが認識できる公式の通信プロトコル（`isStreamlitMessage: true`）を明示的に付与した `postMessage` を送信するように変更します。

---

## 変更対象ファイルと具体的な修正内容

### 1. フロントエンド（新規追加）
#### [NEW] [index.html](file:///C:/Users/katsu/.gemini/antigravity/scratch/sakatsuku_2026/src/paste_bridge/index.html)
* **役割**: `Ctrl + V`（ペーストイベント）およびドラッグ＆ドロップをキャッチし、画像を無劣化のbase64形式で親のStreamlit（Python）に送信します。
* **主要処理**:
  * ユーザーのペーストアクションを検知し、`FileReader`でbase64へ変換。
  * `window.parent.postMessage` に `isStreamlitMessage: true` と `type: "streamlit:setComponentValue"` を乗せて送信。

### 2. バックエンド（修正）
#### [MODIFY] [app.py](file:///C:/Users/katsu/.gemini/antigravity/scratch/sakatsuku_2026/app.py)
* **主要修正点**:
  * `components.html(...)` を廃止し、`components.declare_component` で `src/paste_bridge` を読み込む。
  * クリップボード操作タブ内でカスタムコンポーネントを呼び出し、返ってきたbase64画像データをデコードしてメモリ (`st.session_state.target_images`) にロードする。
  * `key` 引数を適切に引き渡すことで、再描画時も二重取り込みが発生しないように状態管理を堅牢化する。

---

## 影響範囲とリスク

* **既存機能への影響**: クリップボードペーストタブ以外の機能（ファイルアップロード、OCR解析、GSheet連携など）への悪影響は一切ありません。
* **依存関係**: 新たな外部PythonライブラリやNode.jsパッケージのインストールは不要であるため、ユーザー環境での動作互換性リスクは極めて低いです。

---

## 検証計画

### 自動テスト＆動作検証
1. `python -m py_compile app.py` を実行し、構文エラーがないことを確認します。
2. アプリケーションを起動し、初期ロード時に `TypeError` が解消され、画面が正常に表示されることを確認します。
3. 「クリップボードからペースト」タブを開き、ゲーム画像をペースト（Ctrl+V）して、エラーなく瞬時に高解像度のままメモリにロードされることを検証します。
4. ロードされた画像からOCR解析を実行し、パラメータが完璧に読み取れることを確認します。
