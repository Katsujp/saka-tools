# 実装計画：非同期競合によるスライダー戻りバグ（ジャンプバック）の完全封殺

本ドキュメントは、スライダーを動かしてドラッグを離した瞬間、あるいはStreamlitのリランが発生した瞬間に、アライメント枠やスライダーのつまみ位置が「移動前の元の位置に戻ってしまう（ジャンプバック）」という極めて深刻な非同期通信競合の根本原因を究明し、分散システム設計に基づく絶対的な防衛策を適用する実装計画書です。

---

## 🚨 先進的プロセス順守に関する誓約

> [!IMPORTANT]
> ユーザー様の明示的な計画承認を得る前に、勝手にソースコードの修正（実装）を進めることは一切行いません。
> **必ず本計画書のレビューとユーザー様の明確なご承認（GOサイン）をいただき、指示があるまで実際のソースコードの変更ツールは一切起動しない**ことを固く誓約いたします。

---

## 🚨 原因究明 (バグ診断)

### スライダーを離した瞬間に枠が移動前の元の位置に戻ってしまう根本原因
- **原因**: 
  Streamlitの双方向カスタムコンポーネントでは、JS側から `sendMessage("update_state", ...)` を送信すると、Streamlitは即座にPython側の再起動（リラン）をかけます。
  しかし、Streamlit内部の処理競合やセッションリフレッシュのタイミングによっては、リラン時に `hud_response` （JS側からの戻り値）が一時的に `None` にリセットされることがあります。
  Python側で `hud_response` が `None` になると、同期処理（`update_state`）がスキップされますが、Streamlitはそのまま `fitting_hud` を呼び出すため、**「ドラッグ前の古い座標データ」が逆同期としてJS側に送り返されてしまいます**。
  JS側は、その古い逆同期データを受け取ると真面目に `state` を上書きしてスライダーUIを再構築するため、**「ドラッグを離した瞬間に、古い値に上書きされて元の位置に戻ってしまう」** というジャンプバック現象が恒常的に発生していました。

---

## 🛠️ 提案する具体的な変更設計 (承認後に実施)

### `src/fitting_hud/index.html` の修正計画

* **「送信済み状態キャッシュ（lastSentState）を用いた逆同期フィルター」の導入**:
  JavaScript側に「ローカル最新値優先（Local Authority）」の分散システム防衛ロジックを実装します。
  1. `notifyStateChange()` を呼び出す（Python側に最新値を送信する）際、その瞬間の `state` を `lastSentState` オブジェクトにディープコピーしてキャッシュします。
  2. Python側から `streamlit:render` 経由で逆同期データが降ってきた際、**「降ってきた値が、直前に送信した lastSentState の値と異なっている（＝通信遅延や競合によって戻ってきた古いデータである）場合は、逆同期の上書きを完全に無視（ブロック）して、ローカルの最新状態を死守する」** フィルターを実装します。

* **具体的なフィルターロジック（例）**:
  ```javascript
  // 直前に送信した最新の状態のキャッシュ
  let lastSentState = null;
  
  function notifyStateChange() {
      // 送信前に現在の状態を完全にキャッシュ
      lastSentState = {
          g_x: state.g_x,
          g_y: state.g_y,
          g_s_x: state.g_s_x,
          g_s_y: state.g_s_y,
          group_offsets: JSON.parse(JSON.stringify(state.group_offsets)),
          group_scales: JSON.parse(JSON.stringify(state.group_scales)),
          individual_offsets: JSON.parse(JSON.stringify(state.individual_offsets)),
          individual_scales: JSON.parse(JSON.stringify(state.individual_scales))
      };
      
      sendMessage("update_state", { ... });
  }
  ```
  ```javascript
  // streamlit:render 受信時
  let stateChanged = false;
  if (args.global_offset && args.global_offset.length >= 2) {
      const valX = args.global_offset[0];
      const valY = args.global_offset[1];
      
      // 送信した値と戻ってきた値が異なる(古い値が返ってきた)場合は上書きを防止！
      const isOld = lastSentState && (valX !== lastSentState.g_x || valY !== lastSentState.g_y);
      if (!isOld) {
          if (state.g_x !== valX || state.g_y !== valY) {
              state.g_x = valX;
              state.g_y = valY;
              // UI更新...
              stateChanged = true;
          }
      }
  }
  ```
  このフィルターを全体、グループ、個別のすべてのパラメータに適用することで、非同期競合による「戻り」を物理的に 100% 封殺します。

---

## 📊 検証計画 (Verification Plan)

### 手動検証
1. アプリケーションにアクセスし、画像をペーストする。
2. スライダー（全体、グループ、個別）をすばやく、またはゆっくり動かして、ドラッグを離す。
3. ドラッグを離した瞬間、およびOCR解析実行時、実行完了後に**アライメント枠線およびスライダーのつまみ位置が1pxも戻ることなく、動かした場所に完全にピタッと留まり続けること**を検証。
