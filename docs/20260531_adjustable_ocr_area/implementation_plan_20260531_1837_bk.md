# 実装計画：Iframeクロスドメイン通信バグの解消およびApple Pro HUDコンポーネントの完全活性化

本ドキュメントは、Streamlitのカスタムコンポーネントにおける「クロスオリジン（CORS）セキュリティ制限によるHUD非表示バグ」の根本原因を特定し、ブラウザのセキュリティ規格に準拠した強固な双方向通信プロトコルへと修正するための計画書です。

---

## 🚨 エラーの原因究明 (バグ診断)

### 1. 現状の問題
- 画像をアップロードまたはペーストしてメモリに展開することには成功している（「プレビュー対象画像」に画像名が表示されている）ものの、調整用HUDおよびプレビューCanvasが画面に一切表示されず、空白になってしまっている。

### 2. 根本原因：CORS（クロスドメイン）制限によるJSクラッシュ
- 従来の `fitting_hud`（`src/fitting_hud/index.html`）では、親ウィンドウ（Streamlit）への値の送信に `window.parent.dispatchEvent(new CustomEvent(...))` を使用していました。
- しかし、Streamlitはセキュリティ上の理由から、カスタムコンポーネント（Iframe）を親ウィンドウとは異なる別ドメイン（別オリジン）として隔離してホストします。
- ブラウザの同一オリジンポリシー（Same-Origin Policy）により、異なるドメイン間での `window.parent.dispatchEvent` や直接のDOM操作は**セキュリティ例外を引き起こして完全に遮断され、JavaScriptプロセス全体がクラッシュ**します。
- JSがクラッシュした結果、Streamlit側にロード完了（`componentReady`）や描画高さ（`setFrameHeight`）が一切送信されず、StreamlitはIframeの表示高さを `0` (非表示) としてレンダリングしてしまいます。これが表示されない原因です。

### 3. 解決策：`postMessage` 通信プロトコルへの完全移行
- ブラウザがクロスドメイン間での安全なデータ交換を公式に認めている唯一の方法である **`window.parent.postMessage` API** を使用して、Streamlit親フレームと通信するようにJSコードを全面的にリファクタリングします。
- Streamlitが公式に定義しているコンポーネント通信プロトコル（`isStreamlitMessage: true` メッセージ）に従い、以下のシグナルを確実に中継します：
  1. **`streamlit:componentReady`**: 接続の初期化シグナル。
  2. **`streamlit:setFrameHeight`**: 描画高さを親に明示的に通知し、非表示化を防止。
  3. **`streamlit:setComponentValue`**: パラメータ値をPython側に送信。

---

## 📐 Apple Pro 基準のサイジング設計 (UXの洗練)

Iframe内でスクロールバーが二重に出てしまうダサさを完全に排除し、Apple Pro基準にふさわしい「1枚の洗練された極上設定パネル」としてスクロールなしで完結するようにサイズを最適化します。

- **Iframe表示高さ**: `720` px に固定。
- **Canvasおよびコントロールパネルの高さ**: `660` px に統一。
- **スクロール挙動**: 右側の設定項目が非常に多いため、右側のコントロールパネルの「スクロールコンテンツエリア」のみにApple風の極細スクロールバーを配置し、その他の要素は固定位置に配置します。これにより、極めて静粛で美しい操作性が手に入ります。

---

## 🛠️ 主要な修正方針

### 1. `src/fitting_hud/index.html`
- **通信プロトコルの書き換え**: `postMessage` 方式へ移行。
  ```javascript
  function sendMessageToStreamlit(type, payload = {}) {
      window.parent.postMessage(Object.assign({
          isStreamlitMessage: true,
          type: type
      }, payload), "*");
  }
  ```
- **初期疎通の自動化**: `window.onload` またはスクリプト末尾で `componentReady` と `setFrameHeight` (height: 720) を自動送信。
- **CSSの微調整**: `100vh` を排除し、固定高さ `660px`（全体コンテナは `700px`）に最適化。二重スクロールバーの発生を防止。

### 2. `app.py`
- コンポーネント呼び出し時の `fitting_hud` にて、Iframeの初期高さを明示的に `height=720` に指定。
  ```python
  hud_response = fitting_hud(
      key="fitting_hud_instance",
      default_rois=DEFAULT_ROIS,
      groups=GROUPS,
      height=720  # 明示的に高さを確保して非表示を100%防止
  )
  ```
