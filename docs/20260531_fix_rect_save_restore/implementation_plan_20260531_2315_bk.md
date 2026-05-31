# 実装計画書：アライメント矩形位置情報の保存・復元バグの修正（徹底対応版）

JSONファイルから復元する際、「PHY（ジャンプ、コンタクト、スタミナ）」および「SPD（走力、敏捷性）」の個別微調整座標が復元されず、全体を含めたアコーディオン（コントロールパネル）の表示がリセット・破壊されてしまう不具合の根本原因を徹底的に調査し、これを完全に解消するための実装計画です。

---

## 🔍 原因分析

本不具合の根本原因は、前回の改修においてフロントエンド（JavaScript側）の `src/fitting_hud/index.html` に導入した逆同期処理（親フレーム Streamlit からのデータ受け取り）において、**ガード条件が不十分であり、JavaScript 内部で TypeError が発生して描画処理が途中で完全にクラッシュ（中断）していたこと**にあります。

1. **`lastSentState` および `state` 参照時の TypeError**:
   JS側で `streamlit:render` イベントを受け取った際、親から渡された調整値（`args.individual_offsets` や `args.group_offsets`）と「直前に送信した状態（`lastSentState`）」を比較する処理（`isOld` チェック）において、以下のケースで `undefined` へのプロパティアクセスが発生していました。
   - 初期ロード直後などで `lastSentState` がまだ存在しない、またはその中に該当するキー（グループキーや個別キー）が存在しない場合。
   - 復元データ（アップロードされたJSON）の中に一部のキーが欠落している場合。
   これにより、**`TypeError: Cannot read properties of undefined (reading '0')`** などの例外が JavaScript 内部で発生していました。

2. **描画プロセスの完全フリーズ**:
   この TypeError が発生すると、イベントハンドラ内の後続処理である `setupItemsGrid()` や `redrawHUD()` が一切実行されず、処理が途中で完全にフリーズします。
   その結果、アコーディオンの生成が最初の `overall`（総合力）だけで中断し、残りのアコーディオン（カテゴリー数値、SHO、PAS、DRB、DEF、PHY、SPD）が画面上に一切表示されなくなる現象（「走力に至っては項目すら表示されない」状態）を引き起こしていました。

3. **個別パラメータの初期値欠落**:
   JS側の `state` オブジェクトの初期化処理において、グループパラメータは初期化されていたものの、個別パラメータ（`individual_offsets`, `individual_scales`）の初期キーの事前生成が行われておらず、空オブジェクト `{}` のまま同期フェーズに突入していました。これも `undefined` を誘発する要因となっていました。

---

## 🛠️ 対策案（提案内容）

二度と同じ不具合を繰り返さないため、JavaScript側の同期および初期化ロジックに対し、防弾仕様の完全な安全ガードと事前初期化を導入します。

1. **個別パラメータの完全事前初期化の導入**:
   `fitting_hud/index.html` の初期化フェーズにおいて、`DEFAULT_ROIS` に定義されたすべての日本語項目、およびGK特有の追加項目（`セービング`, `反応速度`, `1対1`）について、個別オフセット `[0, 0]` および個別スケール `[1.0, 1.0]` を事前にすべて明示的に初期化・生成します。これにより、JS側で「キーが存在しない」ことによる `undefined` エラーを構造的に100%封殺します。

2. **逆同期処理（親からのデータ受信）における防弾仕様の安全ガード実装**:
   `group_offsets`, `group_scales`, `individual_offsets`, `individual_scales` の逆同期処理において、`lastSentState` や親から受け取ったデータのキーの存在を徹底的にチェックする多重ガードを実装します。
   ```javascript
   const lastSentInd = lastSentState && lastSentState.individual_offsets && lastSentState.individual_offsets[item];
   const isOld = lastSentInd && (indOffCopy[item][0] !== lastSentInd[0] || ...);
   ```
   このように、オブジェクトおよびキーの存在確認（`&&` 演算子による連鎖チェック）を徹底し、どのような場合でも絶対に `TypeError` を発生させず、常に安全にスライダーおよびHUD描画に復元データが伝播するようにします。

---

## 変更対象ファイル

#### [MODIFY] [src/fitting_hud/index.html](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/fitting_hud/index.html)

- **状態初期化処理（HTML末尾 of スクリプト部）の修正**
  - 個別パラメータ（`individual_offsets` / `individual_scales`）を全項目についてデフォルト値で事前初期化する処理を追加します。
- **`streamlit:render` メッセージ受信ハンドラの修正**
  - `group_offsets`, `group_scales`, `individual_offsets`, `individual_scales` の差分比較・逆同期ロジックについて、安全ガードを徹底した防弾設計に書き換えます。

---

## Verification Plan（検証計画）

### 1. 手動による機能動作検証
1. **大項目・個別微調整と保存**:
   - アプリケーションを起動し、全体スライダーや、「敏捷性」「走力」といったPHY・SPD個別微調整のスライダーを操作します。
   - 「ローカルに保存 (JSON)」を押下してアライメントデータを保存します。
   - 画面を一度リロードし、設定を初期状態に戻します。
   - 「ローカルから復元」で保存したJSONファイルをアップロードします。
2. **完全復旧の実証**:
   - 復元後、ブラウザの開発者ツール（F12キーのConsole）に JavaScript の TypeError などのエラーが一切出力されていないことを確認します。
   - 全体アライメント、および「敏捷性」「走力」を含むすべての項目（PHY・SPDアコーディオンを含む）が消滅することなく正しく画面に表示され、保存前と寸分違わずスライダー値・HUD枠線位置が完全に復旧していることを確認します。
