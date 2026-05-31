# 実装計画：ペースト画像非表示バグの解消およびカスタムコンポーネント画像データ伝送の堅牢化

本ドキュメントは、画像を貼り付けた際、あるいは画像を切り替えた際に左側のプレビュー Canvas が真っ黒になり画像が表示されないバグの原因を究明し、その強固な修正設計を提案する実装計画書です。

---

## 🚨 先進的プロセス順守に関する誓約

> [!IMPORTANT]
> ユーザー様の明示的な計画承認を得る前に、勝手にソースコードの修正（実装）を進めることは一切行いません。
> **必ず本計画書のレビューとユーザー様の明確なご承認（GOサイン）をいただき、指示があるまで実際のソースコードの変更ツールは一切起動しない**ことを固く誓約いたします。

---

## 🚨 エラーの原因究明 (バグ診断)

### 1. 現状の問題
- 画像のロード（ペースト）に成功し、右側の調整スライダーやチェックボックスカード、FP/GKボタンといったUIは完全に活性化して表示されているものの、左側のCanvasエリアが真っ黒なままで画像が描画されていません。

### 2. 根本原因：`hud_response is None` のライフサイクル判定ミス
- 従来の `app.py` では、コンポーネントロード時に `window.parent.postMessage` を用いて画像をHTML側に送信していました。
- しかし、その送信処理が `if hud_response is None:` という限定された条件ブロック内に記述されていました。
- Streamlitのライフサイクルにおいて、コンポーネントが一度でも親（Python）に状態（パラメータなど）を送信すると、`hud_response` は `None` ではなく「前回の返り値データ」を返し続ける仕様になっています。
- そのため、新しく画像をペーストして `app.py` が再実行された際、`hud_response` が `None` ではないため、**画像データをIframeにプッシュ送信するJavaScriptコードが実行されず、HTML側に画像が一切届かない状態**になっていました。これが画像が真っ黒になる直接の原因です。

### 3. 解決策：Streamlit公式のコンポーネント引数 (`args`) 経由による直接データ引き渡し
- 不安定な `if hud_response is None` での `postMessage` 処理を完全に撤廃します。
- 代わりに、Streamlitカスタムコンポーネントの標準引数として、**画像データ（Base64 Data URI）を `fitting_hud` の引数に直接渡す設計**に変更します。

#### 【Python側設計 (`app.py`)】
```python
# コンポーネント実行時に、画像データ（image_base64）を直接引数として引き渡す
hud_response = fitting_hud(
    key="fitting_hud_instance",
    image_base64=image_uri,  # 標準引数として直接転送！
    default_rois=DEFAULT_ROIS,
    groups=GROUPS,
    height=720
)
```

#### 【JavaScript側設計 (`src/fitting_hud/index.html`)】
Streamlitの `streamlit:render` メッセージの引数（`args`）から、直接画像データを取得して読み込みます。
```javascript
window.addEventListener("message", (event) => {
    const payload = event.data;
    if (payload.type === "streamlit:render") {
        const args = payload.args;
        if (!args) return;
        
        const imgBase64 = args.image_base64; // 引数から画像をダイレクトに取得！
        
        // 画像が新規ロード、または別の画像に変更された場合のみ読み込み処理を実行（チラつき防止）
        if (imgBase64 && imgBase64 !== bgImage.src) {
            bgImage.src = imgBase64;
            bgImage.onload = function() {
                imageLoaded = true;
                redrawHUD();
            };
        }
    }
});
```

- **この設計のメリット**:
  - `postMessage` による無理な外部プッシュ処理が不要になり、Streamlitの正規 of Iframeライフサイクルに完全に従うため、**画像ペースト時や画像切り替え時にも100%確実に、遅延なく瞬時にプレビューが再描画されます**。

---

## 🛠️ 提案する具体的な変更箇所 (承認後に実施)

### 1. `app.py`
- `fitting_hud` コンポーネント呼び出し時に `image_base64=image_uri` 引数を追加。
- `if hud_response is None:` のハック的 `postMessage` スクリプト送信処理を完全に削除。

### 2. `src/fitting_hud/index.html`
- JS of メッセージリスナー（`streamlit:render`）を上記仕様に書き換え、引数 `args.image_base64` から画像をロードするように更新。

---

## 📊 検証計画 (Verification Plan)

### 自動/手動検証
1. `python -m py_compile app.py` による構文チェックを実行。
2. Streamlitサーバーを起動し、ブラウザでアプリケーションにアクセス。
3. 画像をペーストした際、左側のCanvasエリアに即座に画像が表示され、枠線（Apple Pro Blue）がオーバーレイされることを確認。
4. スライダーを動かした際、ドラッグ操作と同時に枠線が完全にリアルタイム（0遅延）で追従することを確認。
5. 別の画像を読み込ませた際、チラつきなくスムーズに画像と枠線が更新されることを確認。
