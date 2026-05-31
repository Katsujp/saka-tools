# 実装計画：プレビューとOCRの動的座標完全同期（通信バグと再トリミングの徹底排除）

本ドキュメントは、アライメント調整プレビューの青枠が数値（541など）を完璧にタイトに囲んでいるのにもかかわらず、OCR実行時に誤読や空欄が発生してしまう謎を究明し、その不整合を引き起こしている「非同期通信の競合」および「動的トリミングのブレ」を100%完璧に封殺するための実装計画書です。

---

## 🚨 先進的プロセス順守に関する誓約

> [!IMPORTANT]
> ユーザー様の明示的な計画承認を得る前に、勝手にソースコードの修正（実装）を進めることは一切行いません。
> **必ず本計画書のレビューとユーザー様の明確なご承認（GOサイン）をいただき、指示があるまで実際のソースコードの変更ツールは一切起動しない**ことを固く誓約いたします。

---

## 🚨 エラーの原因究明 (バグ診断)

プレビュー画面で青枠が数値を完璧に囲んでいる（日本語文字は完全に枠の外にある）にもかかわらず、OCRで誤読（決定力541➔461、キック力536➔空欄等）が発生する原因について、ゼロベースで処理フローを検証した結果、**極めて重大な3つの設計的要因（不整合）**を特定いたしました。

### 1. 【要因①：最致命】Streamlit双方向通信の競合による「最新座標の消失（上書き）」
*   **原因**:
    現在, JavaScript側で「選択座標で解析を実行」ボタンを押した瞬間、`triggerAnalysis()` 関数内で以下の2つのメッセージを連続送信しています。
    1. `notifyStateChange()` ➔ Python側に最新スライダー状態を送信 (`update_state`)
    2. `sendMessage("trigger_analysis", {})` ➔ Python側に解析実行シグナルを送信 (`trigger_analysis`)
*   **上書きの発生**:
    Streamlitカスタムコンポーネントの非同期プロトコル上、極めて短いミリ秒単位で `sendMessage` を連続送信すると、**後から送信されたメッセージ（`trigger_analysis`）が前回の状態を上書きし、前回の座標同期処理（`update_state`）が完全に無視（消失）されてしまう**という致命的な通信仕様が存在します。
*   **結果**:
    ユーザーが画面上でどんなに完璧にアライメントを調整しても、解析実行ボタンを押した瞬間にその**最新座標データがPython側に届かず、初期値（`0 px`, `1.0x`）またはズレた状態のままOCR解析が実行されてしまっていた**ため、大誤読を引き起こしていました。

### 2. 【要因②】OCR実行時における「生画像からの自動トリミング再実行」による数pxの境界ブレ
*   **原因**:
    プレビュー画像生成時にはトリミング済みの画像を使用していましたが、**OCR実行時には `app.py` から元の「トリミング前の生画像」をOCRエンジンにそのまま渡してしまっていました**。
    これにより、OCRエンジン内部で再び `scan_game_boundary`（自動境界検出）が実行されていました。
*   **結果**:
    `scan_game_boundary` は画像の明暗差を動的にスキャンする処理であるため、わずかなノイズや色調によって、境界の検出値が数ピクセル動的に変化（ブレ）します。
    プレビュー生成時とOCR実行時でトリミングが数ピクセルでもブレてしまうと、アライメントは完全に狂ってしまい、誤読を招いていました。

### 3. 【要因③】PythonからJSへの状態引数の引き渡し不足による「リラン時の座標リセット」
*   **原因**:
    `fitting_hud` のコンポーネント呼び出し時の引数に、現在調整された `st.session_state` のスライダーパラメータ（`group_scales` や `individual_offsets` など）を一切引き渡していません。
*   **結果**:
    OCR実行や他の操作によって Streamlit が再実行（リラン）された際、Iframe（HTML）側のパラメータが初期値に勝手にリセットされてしまい、Python側とフロントエンド側で座標のミスマッチが恒常的に発生していました。

---

## 🛠️ 提案する具体的な解決策 (承認後に実施)

この3つの不整合を完全に封殺し、プレビューの完璧な見た目とOCRのスキャン結果を「1pxの狂いもなく」100%完全に同期させます。

### 対策①：単一メッセージへの「座標データと実行シグナルの統合」（通信上書きの排除）
JS側でボタンを押した際、メッセージを2回に分けるのを廃止し、**`trigger_analysis` の中に現在の最新スライダー状態をすべて同梱して一括送信**します。これで通信の競合を100%完全に排除し、画面で見ている完璧なスライダー位置をダイレクトにOCRへ引き渡します。

#### 【JavaScript側設計 (`triggerAnalysis`)】
```javascript
function triggerAnalysis() {
    sendMessage("trigger_analysis", {
        isGk: state.isGk,
        activeItems: state.activeItems,
        global_scale_x: state.g_s_x,
        global_scale_y: state.g_s_y,
        global_offset: [state.g_x, state.g_y],
        group_scales: state.group_scales,
        group_offsets: state.group_offsets,
        individual_scales: state.individual_scales,
        individual_offsets: state.individual_offsets
    });
}
```

#### 【Python側設計 (`app.py`)】
```python
        elif resp_type == "trigger_analysis":
            # 同梱された最新の座標データを一括同期！
            st.session_state.is_gk = resp_data.get("isGk", False)
            st.session_state.active_items = resp_data.get("activeItems", [])
            st.session_state.global_scale_x = resp_data.get("global_scale_x", 1.0)
            ... (すべてのスライダー値をその場で同期)
            
            # 即座にOCR実行フラグを立てる
            if not st.session_state.get("ocr_run_completed", False):
                trigger_ocr_run = True
```

---

### 対策②：トリミング画像の一本化キャッシュと再トリミングの完全廃止
*   **`app.py` 側**:
    画像がアップロードまたはペーストされた時点で、**「トリミングおよび1920x1080正規化を完了した状態の画像（PILオブジェクト）」を `st.session_state.normalized_image` として一度だけ生成・キャッシュ保存**します。
    プレビューCanvasへのBase64送信も、OCR実行（`extract_all_parameters`）への引き渡しも、すべてこのキャッシュ画像に統一します。OCR実行時には元の生画像を絶対に渡さないようにします。
*   **`ocr_engine.py` 側**:
    `preprocess_image` 処理において、すでにトリミング・正規化済みの画像が渡された場合は、`scan_game_boundary` をスキップするバイパス用フラグ（`is_preprocessed=True`）を追加し、トリミングの動的なブレを **「物理的に0%（発生不可能）」** にします。

---

### 対策③：Python ➔ JS への全状態スライダー値の引数同期
*   `fitting_hud` コンポーネントの呼び出し引数として、現在調整された `group_scales` や `individual_offsets` 等のすべてのセッション状態パラメータを明示的に追加します。
*   HTML/JS側では、ロード完了（`streamlit:render`）時にこれらのパラメータを読み取って初期状態として復元します。これでリラン時の意図しないパラメータ初期化が完璧に消滅します。

---

## 📊 検証計画 (Verification Plan)

### 自動/手動検証
1. `python -m py_compile app.py src/ocr_engine.py` による構文チェック。
2. アプリ上で Mohamed Salah 選手の画像をロード。
3. プレビューの青枠が「541」等の数値にぴったり合っていることを確認。
4. 解析を実行し、**「総合力: 8369」「SHO数値: 1609」「決定力: 541」「キック力: 536」「冷静さ: 532」「ロングパス: 449」などのすべての数値が、一切の誤読なく100%完璧に正しい値で超速コピペステーションに抽出されること**を確認。
