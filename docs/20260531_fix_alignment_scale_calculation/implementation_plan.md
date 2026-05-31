# 実装計画：アライメントスケール計算バグの修正（位置移動から純粋サイズ変更への移行）

本ドキュメントは、アライメントの各スケール（全体、グループ、個別）を変更した際、矩形枠のサイズが変わるだけでなく、枠の位置（左上座標）まで勝手に移動（シフト）してしまい、アライメント調整が極めて困難になるバグの原因を究明し、その強固な修正計画を提案する設計書です。

---

## 🚨 先進的プロセス順守に関する誓約

> [!IMPORTANT]
> ユーザー様の明示的な計画承認を得る前に、勝手にソースコードの修正（実装）を進めることは一切行いません。
> **必ず本計画書のレビューとユーザー様の明確なご承認（GOサイン）をいただき、指示があるまで実際のソースコードの変更ツールは一切起動しない**ことを固く誓約いたします。

---

## 🚨 エラーの原因究明 (バグ診断)

### 1. 現状の問題点
スライダーでスケール（全体スケール、グループスケール、個別スケール）を変更した際、枠線のサイズ（幅・高さ）が変わるだけでなく、**枠線全体が右や下に大きく移動してしまう**という現象が発生しています。
これにより、シフトスライダーで位置を合わせた後にスケールスライダーを動かすと位置がズレてしまい、無限に調整を繰り返さなければならない致命的なUX崩壊が生じています。

### 2. 根本原因：座標計算式における `def_x` へのスケール積算
JavaScript側（`calculateROI`）およびPython側（`calculate_dynamic_roi`）の座標計算式において、以下の記述になっていました。
```javascript
// 従来の計算式
const finalX = Math.round(defX * totalScaleX + state.g_x + grpOff[0] + indivOff[0]);
const finalY = Math.round(defY * totalScaleY + state.g_y + grpOff[1] + indivOff[1]);
```
この式では、デフォルトの左上X座標（`defX`）に対して直接スケール値（`totalScaleX`）が掛け算されています。
これは、**画面左上原点 (0, 0) を基準とした拡大・縮小**になってしまうため、原点から遠い項目（例：右側にある「SPD数値」や「敏捷性」など、X座標が 1600px を超える項目）ほど、スケールをわずか `1.01` に変えただけで、
`1600 * 1.01 = 1616`（16px右に勝手に移動）というように、**矩形の幅ではなく位置そのものが大きくシフトしてしまう**現象が発生していました。

### 3. 解決策：スケールを「サイズ（W, H）のみ」に適用する設計への移行
アライメント調整の役割分担を以下のように完全に分離し、ユーザーの直感と100%一致する極上のUXを提供します。
*   **シフト調整（全体、グループ、個別）**: 枠線の「位置（左上X/Y座標）」のみを移動させる。
*   **スケール調整（全体、グループ、個別）**: 枠線の「位置（X, Y）」は1pxも動かさず、**その場での「サイズ（幅・高さ）」のみを拡大・縮小**させる。

#### 【修正後の座標計算式】
```python
# 左上座標(X, Y)はスケールの影響を受けず、純粋にシフト値のみで決定される
final_x = int(def_x + global_offset[0] + grp_offset[0] + indiv_offset[0])
final_y = int(def_y + global_offset[1] + grp_offset[1] + indiv_offset[1])

# サイズ(Width, Height)にのみスケールが積算適用される
final_w = int(def_w * total_scale_x)
final_h = int(def_h * total_scale_y)
```

この式に改めることで、まずシフトで位置を合わせ、その後にスケールで大きさを文字にぴったり合わせる、という合理的でストレスフリーな2ステップ調整が実現します。

---

## 🛠️ 提案する具体的な変更箇所 (承認後に実施)

### 1. JavaScript側（[src/fitting_hud/index.html](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/fitting_hud/index.html)）
`calculateROI` 関数（730〜745行目付近）の座標計算式を修正します。
```javascript
        const finalX = Math.round(defX + state.g_x + grpOff[0] + indivOff[0]);
        const finalY = Math.round(defY + state.g_y + grpOff[1] + indivOff[1]);
        const finalW = Math.round(defW * totalScaleX);
        const finalH = Math.round(defH * totalScaleY);
```

### 2. Python側（[src/ocr_engine.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/ocr_engine.py)）
`calculate_dynamic_roi` 関数（155〜158行目付近）の座標計算式を修正します。
```python
        final_x = int(def_x + global_offset[0] + grp_offset[0] + indiv_offset[0])
        final_y = int(def_y + global_offset[1] + grp_offset[1] + indiv_offset[1])
        final_w = int(def_w * total_scale_x)
        final_h = int(def_h * total_scale_y)
```

---

## 📊 検証計画 (Verification Plan)

### 自動/手動検証
1. `python -m py_compile app.py src/ocr_engine.py` による構文チェック。
2. アプリ上で適当な画像をロード。
3. 全体、グループ、個別のいずれかのスケール（X/Y）スライダーを動かした際、**左側のCanvas上で矩形枠の左上位置が1pxもズレることなく、その場でサイズ（幅・高さ）だけが拡大・縮小すること**を目視確認。
4. OCR解析を実行し、枠線のアライメント通りの正確な範囲がクロップされ、OCR結果が返ってくることを確認。
