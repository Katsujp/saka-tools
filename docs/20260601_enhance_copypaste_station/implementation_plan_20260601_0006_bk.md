# コピペステーションの機能強化およびUI日本語化 改修計画書

本ドキュメントは、コピペステーションの柔軟性向上、およびプレイヤー向けUIの最適化（タイトルと説明文の日本語化）に関する改修計画をまとめたものです。

## 変更の背景と原因

1. **コピペ操作の利便性向上**:
   - 解析結果テーブルを維持したまま、コピペステーションの表示エリアだけをクリアしたいというユーザーの要望に対応するため、クリア専用ボタンが不足していました。
2. **純粋な数値コピペの実現**:
   - 項目名出力トグルが OFF の際、他のスプレッドシートや管理表に縦列データをそのままバルクペーストしたいユースケースにおいて、先頭に `--- 【画像: Clipboard_xxxx】 ---` という画像デリミタ行が出力されていると、コピペ時に手動で消去する手間が発生していました。そのため、完全な「数値（値）のみ」の出力を実現するようロジックを修正します。
3. **プレイヤー向けUIの直感化**:
   - 「Parameter Precision Reader」という英語表記から、サカつくプレイヤーにとって直感的な「サカつく2026 パラメータOCRリーダー v0.1」に変更し、説明文もツールの目的を明確にした日本語に更新します。

---

## ユーザー確認が必要な事項

> [!NOTE]
> **横展開（スプレッドシート行追加用）での画像名出力について**
> 項目名出力トグルが OFF の場合、縦展開（縦型カルテ入力用）では先頭の画像名デリミタ `--- 【画像: ...】 ---` を完全に非表示にします。
> 一方、横展開（横1行形式）においては、データ行の先頭カラムとしての「画像名（選手名）」は、貼り付けたデータがどの画像（選手）のものかを識別するために必要であるため、現状どおり値として出力します（ヘッダー行である「元画像名」という文字列のみが非表示になります）。
> もし横展開でも画像名そのものを非表示にし、純粋にパラメータ値のみを並べたい場合は、お知らせください。

---

## 提案する変更内容

### app.py の改修

#### [MODIFY] [app.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/app.py)

- **タイトル・説明文の変更**:
  - `st.markdown('<div class="main-title">Parameter Precision Reader</div>', ...)` を `st.markdown('<div class="main-title">サカつく2026 パラメータOCRリーダー v0.1</div>', ...)` に変更。
  - `st.markdown('<div class="subtitle">高精度画像解析と、極めてスムーズなアライメント調整を提供するパラメータ抽出システム。</div>', ...)` を `st.markdown('<div class="subtitle">選手のパラメータタブの中身を読み取るツール</div>', ...)` に変更。
- **「コピペステーションをクリアする」ボタンの追加**:
  - `st.columns` の比率を調整し、「解析結果テーブルを空にする」ボタンと「コピペステーションに展開する」ボタンの間に「コピペステーションをクリアする」ボタンを配置。
  - ボタン押下時にセッション状態の `tsv_horizontal` と `tsv_vertical` を空文字（`""`）にクリアし、`st.rerun()` を実行。
- **コピペステーション展開ロジックの修正（デリミタの除外）**:
  - 縦展開（`tsv_vertical`）のループ処理において、`show_headers` が `False` の場合は、`tsv_v_lines.append(f"--- 【画像: {img_name}】 ---")` を追加しないように条件分岐を実装。

---

## 変更イメージ

```python
# ボタンレイアウトの変更イメージ
col_empty_spacer, col_clear_res, col_clear_station, col_export = st.columns([1, 1, 1, 1])
with col_clear_res:
    if st.button("解析結果テーブルを空にする", use_container_width=True):
        st.session_state.parsed_results = []
        st.session_state.tsv_horizontal = ""
        st.session_state.tsv_vertical = ""
        st.rerun()

with col_clear_station:
    if st.button("コピペステーションをクリアする", use_container_width=True):
        st.session_state.tsv_horizontal = ""
        st.session_state.tsv_vertical = ""
        st.rerun()

with col_export:
    btn_export = st.button("コピペステーションに展開する", use_container_width=True)
```

```python
# 縦展開TSV構築ロジックの変更イメージ
tsv_v_lines = []
for _, row in selected_df.iterrows():
    img_name = row.get("元画像名", "Image")
    # 項目名出力がONの場合のみ画像名デリミタを出力する
    if show_headers:
        tsv_v_lines.append(f"--- 【画像: {img_name}】 ---")
    
    for col in selected_df.columns:
        if col != "元画像名":
            is_active = col in st.session_state.active_items
            val_str = str(row[col]).strip()
            if is_active and val_str != "":
                if show_headers:
                    tsv_v_lines.append(f"{col}\t{row[col]}")
                else:
                    tsv_v_lines.append(f"{row[col]}")
    
    # 項目名出力がON、またはOFFであっても改行を挟むことで画像ごとの塊を維持（あるいはデリミタなし時は詰めるか要検討、現状は改行のみ挿入）
    if show_headers:
        tsv_v_lines.append("")
    elif tsv_v_lines and tsv_v_lines[-1] != "":
        tsv_v_lines.append("")
```

---

## 検証計画

### 1. 静的コードチェック
- `python -m py_compile app.py` を実行し、構文エラーがないことを確認。

### 2. 動作確認項目
- 起動時にタイトルが「サカつく2026 パラメータOCRリーダー v0.1」、説明文が「選手のパラメータタブの中身を読み取るツール」になっていることを確認。
- 解析結果が存在する状態で「コピペステーションをクリアする」ボタンをクリックし、表示エリアが「データが展開されていません。」に戻ることを確認。この際、上の編集テーブルの中身（解析結果テーブル）が削除されずに残っていることを確認。
- 「項目名を出力する」チェックボックスを OFF にして「コピペステーションに展開する」をクリックした際、縦展開エリアに `--- 【画像: ...】 ---` が出力されず、純粋な数値だけが縦並びで出力されることを確認。
- ON にして展開した際には、従来通り `--- 【画像: ...】 ---` および項目名が出力されることを確認。
