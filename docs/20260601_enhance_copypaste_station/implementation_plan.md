# コピペステーションの機能強化およびUI日本語化 改修計画書

本ドキュメントは、コピペステーションの柔軟性向上、およびプレイヤー向けUIの最適化（タイトルと説明文の日本語化）に関する改修計画をまとめたものです。

## 変更の背景と原因

1. **コピペ操作の利便性向上**:
   - 解析結果テーブルを維持したまま、コピペステーションの表示エリアだけをクリアしたいというユーザーの要望に対応するため、クリア専用ボタンが不足していました。
2. **純粋な数値コピペの実現（横・縦展開の完全数値化）**:
   - 項目名出力トグルが OFF の際、スプレッドシートの選手データ列の並びに、余計な文字を含めずに「数値（値）のみ」を直接一括貼り付けしたいというユースケースに対応します。
   - **縦展開（縦型カルテ入力用）**: 先頭の画像デリミタ `--- 【画像: Clipboard_xxxx】 ---` 行を完全に非表示とし、項目名も除外して「数値のみ」を縦に並べます。
   - **横展開（スプレッドシート行追加用）**: 先頭の「元画像名」の値自体も完全に非表示とし、純粋な「パラメータ数値のみ（タブ区切り）」を横に並べます。ヘッダー行も出力しません。
3. **プレイヤー向けUIの直感化**:
   - 「Parameter Precision Reader」という英語表記から、サカつくプレイヤーにとって直感的な「サカつく2026 パラメータOCRリーダー v0.1」に変更し、説明文もツールの目的を明確にした日本語に更新します。

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
- **コピペステーション展開ロジックの修正（画像名・デリミタの除外）**:
  - **横展開（`tsv_horizontal`）**:
    - `show_headers` が `True` の場合:
      - `output_cols` の先頭に `"元画像名"` を含めてヘッダー行および各行データを出力します。
    - `show_headers` が `False` の場合:
      - `output_cols` から `"元画像名"` を除外し、ヘッダー行は出力せず、各データ行についても「パラメータ値のみ（タブ区切り）」を出力します。
  - **縦展開（`tsv_vertical`）**:
    - `show_headers` が `True` の場合:
      - 各画像データの先頭にデリミタ `--- 【画像: {img_name}】 ---` を出力し、項目名付き（`項目名\t値`）で出力します。
    - `show_headers` が `False` の場合:
      - デリミタ `--- 【画像: {img_name}】 ---` の出力を完全にスキップし、かつ項目名も除外した「値のみ」を縦に出力します。

---

## 変更イメージ

```python
# 横展開TSVの構築（修正後イメージ）
tsv_h_lines = []
if show_headers:
    # 項目名（ヘッダー）を出力し、先頭に画像名も含める
    tsv_h_lines.append("\t".join(output_cols))
    for _, row in selected_df.iterrows():
        tsv_h_lines.append("\t".join([str(row[col]) for col in output_cols]))
else:
    # 項目名なし、かつ先頭の「元画像名」の値自体も完全に非表示
    # output_colsから「元画像名」を除外したリストで出力
    data_cols = [col for col in output_cols if col != "元画像名"]
    for _, row in selected_df.iterrows():
        tsv_h_lines.append("\t".join([str(row[col]) for col in data_cols]))
            
st.session_state.tsv_horizontal = "\n".join(tsv_h_lines)
```

```python
# 縦展開TSVの構築（修正後イメージ）
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
    
    # 画像間の区切り改行
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
- 「項目名を出力する」チェックボックスを OFF にして「コピペステーションに展開する」をクリックした際：
  - **横展開**: 各行の先頭の画像名が非表示になっており、純粋にパラメータ数値（タブ区切り）だけが出力されることを確認。ヘッダー行がないことを確認。
  - **縦展開**: 先頭の `--- 【画像: ...】 ---` が一切出力されず、かつ項目名もなく、純粋な数値だけが縦並びで出力されることを確認。
- ON にして展開した際には、従来通り画像名およびデリミタ行、項目名が出力されることを確認。
