# ペースト・クリア競合不具合の根本解決計画 (ワンタイムIDプロトコル)

## 原因の特定
前回の修正で「クリアボタン押下時に重複防止キャッシュ（`last_pasted_base64`）を `None` にリセット」した結果、別の深刻な通信競合バグが発生しました。

### 発生の流れ：
1. 画像をペーストすると、JSコンポーネントの「状態値（Value）」にそのBase64データが保持されます。
2. 個別クリアボタンを押すと、画像がリストから削除され、`last_pasted_base64` が `None` にリセットされます。そして `st.rerun()` が呼ばれます。
3. **Rerun再描画の直後**:
   - Streamlitは画面全体を再読み込みしますが、JSコンポーネントは**前回のペーストデータ（Base64）を保持したまま**になっています。
   - そのため、Python側で `pasted_base64` を再取得した際、削除したはずのデータが入ってきます。
   - この時、キャッシュ `last_pasted_base64` は `None` なので、`pasted_base64 != None`（＝不一致）となり、**新規にペーストされたと誤認識され、削除したはずの画像が自動的に勝手に再登録されてしまう**というバグが起きていました。

---

## ユーザー確認事項（要レビュー）
> [!IMPORTANT]
> **ワンタイムIDプロトコルの導入による根本解決**
> 単純なデータ比較での二重防止では、Streamlitの状態保持の仕様（Rerun時に直近の値を再度返す）により競合を防げません。
> 本計画では、JS側から送信するデータに「タイムスタンプ付きのユニークID」を含めるプロトコルを導入します。これにより、「削除直後の自動ペースト」を防ぎつつ、「同一画像の安全な再ペースト」を完全に両立させます。

---

## 提案する具体的な変更内容

### 1. 【JS側】送信データ形式の変更
- ファイル: `src/paste_bridge/index.html`
- `handleFile` 内の `streamlit:setComponentValue` で送るデータを、単なるBase64文字列から以下のようなID付きオブジェクト形式に変更します。
```javascript
sendMessageToStreamlit("streamlit:setComponentValue", {
    value: {
        id: "paste_" + Date.now(),
        data: base64Data
    }
});
```

### 2. 【Python側】判定ロジックの変更
- ファイル: `app.py`
- コンポーネントからの受信値 `pasted_data`（旧 `pasted_base64`）を辞書オブジェクトとして受け取り、その中の `id` が `st.session_state.last_paste_id` と異なる場合にのみ処理を行います。
- 個別クリアやアライメント復元時の `last_pasted_base64 = None` という無理なリセット処理はすべて廃止します（IDプロトコルによって自動再読み込みは自然にガードされます）。

---

## 変更対象ファイル

### [MODIFY] [index.html](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/paste_bridge/index.html)
- `sendMessageToStreamlit("streamlit:setComponentValue", { value: base64Data });` を変更し、オブジェクト `{ id, data }` を送るように修正します。

### [MODIFY] [app.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/app.py)
- セッション状態 `last_paste_id` を初期化。
- ペースト受け取り部分（L305付近）のコードを以下のように修正します。
```python
    pasted_obj = paste_bridge(key="paste_bridge_instance")
    
    if pasted_obj and isinstance(pasted_obj, dict):
        paste_id = pasted_obj.get("id")
        base64_str = pasted_obj.get("data", "")
        
        if paste_id and paste_id != st.session_state.get("last_paste_id"):
            try:
                # デコード・ロード・リサイズ・追加処理
                ...
                st.session_state.last_paste_id = paste_id
                st.success("画像をロードしました。")
                st.rerun()
```
- 前回追加した「個別クリアボタン」および「ローカル復元」処理内の `st.session_state.last_pasted_base64 = None` はすべて削除します。

---

## 検証計画

### 自動検証
- `python -m py_compile app.py` による構文エラー検証。

### 手動検証
1. **個別クリアの確認**:
   - 画像ペースト ➔ 個別クリア ➔ **画像がリストから確実に消え、自動で再追加されないこと**を確認。
2. **同一画像の再ペースト確認**:
   - 個別クリア ➔ その後、クリップボードから**全く同一の画像**を再度ペースト。
   - IDが新しく発行されるため、今度はガードされず2回目も正しくペーストされ、HUDが表示されることを確認。
