# タスクリスト：Googleスプレッドシート設定の廃止およびGoogleドライブ矩形位置情報バックアップ機能の実装

本タスクリストは、Googleスプレッドシート/Excel書き出し機能のクリーンアップ、およびGoogle Driveへのアライメント調整データ（矩形位置情報）のバックアップ機能の進捗を管理するものです。

## チェックリスト

- [x] `task.md` の作成および構成定義
- [x] 依存ライブラリのインストール (`google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`)
- [x] `app.py` から Googleスプレッドシート設定および Excel 書き出し機能の完全削除
- [x] `app.py` に起動時の「復元確認ダイアログ」処理の実装
- [x] `app.py` に Google Drive へのアライメント保存・復元処理（OAuth2連携・トークンキャッシュ）の実装
- [x] `app.py` 内の「解析データを空にする」ボタンの再配置
- [x] 不要になった `src/gsheet_client.py` ファイルの削除
- [x] アプリの構文検証（`python -m py_compile app.py`）
- [x] 動作検証（起動時ダイアログ挙動、Google Drive 保存、スライダー値への復元反映確認）
- [x] 修正内容の確認ドキュメント (`walkthrough.md`) の作成
