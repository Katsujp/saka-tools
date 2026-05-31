# 実装計画書：アライメント矩形位置情報の保存・復元バグの修正（最新版）

復元時に「PHY（ジャンプ、コンタクト、スタミナ）」および「SPD（走力、敏捷性）」の個別微調整座標が復元されず、全体を含めた表示がリセットされたように見えてしまう致命的なバグの原因を調査し、これを確実に解消するための実装計画です。

---

## 原因分析

本バグの根本原因は、JavaScript側（フロントエンド）のコンポーネント `src/fitting_hud/index.html` における親フレーム（Streamlit）からの逆同期処理（`streamlit:render` 受信時）の不備にあります。

1. **TypeError による JS クラッシュ（最大の原因）**:
   `fitting_hud/index.html` の `streamlit:render` 内で個別微調整オフセット/スケールを同期する際、ループ処理の対象が `state.activeItems`（その時点でチェックONの項目）に限定されていました。
   GK/FPロール切り替え時やJSONファイルのキー定義状態の差異により、もし受け取った `args.individual_offsets` 内に該当キーが存在しない場合（`undefined`）、`indOffCopy[item][0]` の値にアクセスした瞬間に **JavaScript の TypeError （`Cannot read properties of undefined (reading '0')`）** が発生します。
   この例外エラーによって JavaScript プロセスが完全にクラッシュし、その直後にある UI 描画やスライダー値の反映処理が丸ごと停止してしまっていたため、スライダーが初期化されたように見えていました。

2. **アクティブ項目外の同期漏れ**:
   チェックが外れている非アクティブ項目は同期のループから除外されていたため、JSONから復元された調整値がJS側に引き継がれませんでした。

3. **`active_items` の逆同期漏れ**:
   Streamlit 側で復元された「どのチェックボックスがON/OFFされているか」という状態（`active_items`）が JS 側の `state.activeItems` に逆同期される処理が実装されていませんでした。

---

## 対策案（提案内容）

バグおよびクラッシュを構造的に100%封殺するため、フロントエンドの同期ロジックを以下のように刷新します。

1. **安全ガードの導入と TypeError の排除**:
   JS側の同期ループ内で、逆同期対象のキーがデータ内に存在しない場合（`undefined`）は即座に `continue` する安全ガードを導入し、JavaScript のクラッシュを完璧に封殺します。

2. **同期対象の網羅（全個別項目の逆同期）**:
   逆同期のループ対象を `state.activeItems` から `Object.keys(indOffCopy)` および `Object.keys(indSclCopy)` に変更します。これにより、アクティブ/非アクティブに関わらず、すべての個別項目の調整値が確実に JS 側の `state` に同期されます。

3. **`active_items` の完全逆同期**:
   親フレームから受け取った `args.active_items` が存在する場合、JS 側の `state.activeItems` に安全に逆同期する処理を追加し、チェックON/OFF状態も完璧に復元します。

---

## 変更対象ファイル

#### [MODIFY] [src/fitting_hud/index.html](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/fitting_hud/index.html)

- **`streamlit:render` メッセージ受信ハンドラの修正**
  - `active_items` の逆同期処理を追加します。
  - 個別オフセット・スケールの同期処理（`args.individual_offsets` / `args.individual_scales`）について、ループ対象を `Object.keys(...)` に変更し、存在チェック of 安全ガードを追加します。

---

## Verification Plan（検証計画）

### 1. 手動による機能動作検証
1. **大項目・個別微調整と保存**:
   - アプリケーションを起動し、「敏捷性」のYシフトを `+4px`、「走力」のXシフトを変更するなど、PHYおよびSPDを含む複数の個別項目を調整します。
   - 全体アライメント（Global）の全体Xシフト等も適当に調整します。
   - 「ローカルに保存 (JSON)」ボタンを押下して `sakatsuku_alignment.json` を保存します。
2. **JSONからの完全復元**:
   - 画面を一度リロードして初期状態（すべてのスライダーが 0 または 1.00）に戻します。
   - 「ローカルから復元」で保存したJSONファイルをアップロードします。
   - アップロード後、ブラウザの開発者ツール（F12）のコンソールに JavaScript の TypeError などのエラーが出力されないことを確認します。
   - 全体アライメントおよび「敏捷性」「走力」などのすべての項目が、保存前と寸分違わず完全に復元されていることを目視確認します。
