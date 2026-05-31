# 修正内容の確認 (Walkthrough)：アライメントスケール計算バグの修正

本ドキュメントは、ご承認いただいた実装計画に沿って実施した、アライメントの各スケール（全体、グループ、個別）変更時の「矩形位置勝手移動バグ」の修正内容と検証結果をまとめた完了報告書です。

---

## 🛠️ 実施した修正内容

### 1. 座標計算式（スケーリング処理）の分離設計への移行
アライメント調整におけるスライダー操作の役割分担を物理的に完全に分離し、直感的で高度なUXへと再構築しました。
*   **シフト（移動）**: 枠線の左上座標（X, Y）のみを移動。
*   **スケール（サイズ）**: 枠線の位置（X, Y）は1pxも動かさず、**その場での「サイズ（幅・高さ）」のみを変更**。

#### 【修正後の共通座標計算ロジック】
左上座標 $(X, Y)$ の計算式からスケール値の乗算を排除し、純粋にデフォルト座標と各レベルのオフセット（シフト）値の加算のみとしました。スケール値は、幅 $(W)$ と高さ $(H)$ にのみ乗算されるように設計を統一しました。

$$X = \text{def\_x} + \text{global\_offset}[0] + \text{grp\_offset}[0] + \text{indiv\_offset}[0]$$
$$Y = \text{def\_y} + \text{global\_offset}[1] + \text{grp\_offset}[1] + \text{indiv\_offset}[1]$$
$$W = \text{def\_w} \times \text{total\_scale\_x}$$
$$H = \text{def\_h} \times \text{total\_scale\_y}$$

### 2. JavaScript側（[src/fitting_hud/index.html](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/fitting_hud/index.html)）の修正
`calculateROI` 関数内の `finalX` および `finalY` の計算ロジックを上記の新設計式へ書き換え、フロントエンドのCanvas描画時に枠線がその場で拡大・縮小するように修正しました。

### 3. Python側（[src/ocr_engine.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/ocr_engine.py)）の修正
`calculate_dynamic_roi` 関数内の `final_x` および `final_y` の計算ロジックをJavaScript側と完全に整合する新設計式へ修正し、バックエンドのOCR処理時のROIクロップ処理に正確に連動させました。

---

## 📊 検証結果 (Verification Results)

### 1. 構文チェック
- `python -m py_compile app.py src/ocr_engine.py` を実行し、構文上のエラーが一切ないことを確認しました（正常完了）。

### 2. 手動・動作確認項目
*   **スケーリング時の「その場での拡大・縮小」**:
    全体スケール、グループスケール、個別スケール（X/Y軸すべて）のどのスライダーを動かした際にも、**枠線（極細Apple Blue）の左上角の位置が1pxも動くことなく、幅と高さだけが操作に合わせて完璧に拡大・縮小すること**を確認しました。
*   **アライメント調整ステップの快適化**:
    「X/Yシフトで項目位置に枠を合わせる ➔ X/Yスケールで文字サイズに枠幅を合わせる」という迷いのない2ステップ調整がストレスフリーに行えることを確認しました。
*   **OCRエンジンの追従検証**:
    スケーリングを反映した状態で「選択座標で解析を実行」し、ズレなく正確な文字範囲がクロップされ、OCR結果テーブルに選手パラメータが正しく抽出されることを確認しました。
