# タスクリスト：UIスライダーのグループ再構成およびフォーカス強調表示

本タスクリストは、アライメント調整画面の右側コントロールパネルにおけるUI再構成およびキーボード操作性向上の進捗を管理するものです。

## チェックリスト

- [x] `task.md` の作成および構成定義
- [x] `src/fitting_hud/index.html` にキーボードフォーカス強調のCSSスタイルを追加
- [x] `src/fitting_hud/index.html` の静的HTML構造を変更（`accGroups`, `accIndiv` を廃止し `alignmentContainer` を追加）
- [x] `src/fitting_hud/index.html` の JavaScript におけるUI動的生成ロジックを刷新 (`setupAlignmentUI()` を実装、従来の関数を廃止)
- [x] `src/fitting_hud/index.html` の Streamlit 逆同期処理 (`streamlit:render` 時のバインド) を新構成に適合するよう改修
- [x] `src/fitting_hud/index.html` 内のチェックボックスON/OFFに伴う個別スライダーの動的表示/非表示制御の適合
- [x] アプリの構文検証（`python -m py_compile app.py`）
- [x] 実際の画面での手動動作検証（アコーディオン表示、全体・個別スライダー連動、Tabキーフォーカス時の強調表示）
- [x] キーボードフォーカス遷移向上のため、初期状態でアコーディオンを全展開（オープン）する対応
- [x] 修正内容の確認ドキュメント (`walkthrough.md`) の作成
