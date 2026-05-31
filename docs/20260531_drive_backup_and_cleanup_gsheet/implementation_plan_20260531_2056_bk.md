# 実装計画：Googleスプレッドシート設定の廃止およびGoogleドライブ矩形位置情報バックアップ機能の実装

本ドキュメントは、不要となった「Googleスプレッドシート/Excel書き出し機能および設定」をUIから完全に排除してUIを整理し、代わりにユーザーが長時間の調整で作り上げた「矩形位置情報（ROIパラメータ）」をGoogle Drive上の「Saka-tools_backup.json」としてセキュアに保存・復元できるOAuth2連携機能を実装するための計画書です。

---

## 現状の課題・背景 (原因)

1. **スプレッドシート直接保存の廃止ニーズ**: 
   スプレッドシート設定やExcelエクスポート機能は現在不要となっており、代わりにコピペ用のTSVテキスト（超速コピペステーション）や表の直接編集機能があれば十分であるため、サイドバーの設定フォームや下部の書き出しボタン群が画面を煩雑にさせている原因となっていました。
2. **矩形調整データ消失の懸念**: 
   せっかく調整した各パラメータの矩形枠座標が、アプリの再起動やブラウザの更新によってリセットされてしまうため、設定値をクラウド上に安全に永続化し、いつでも一発で復元できるバックアップ機能が強く求められていました。

---

## ユーザーレビューが必要な内容 (Open Questions)

> [!IMPORTANT]
> **Q1. Google APIのクライアント資格情報 (client_secrets.json) のロード方法について**
> Google Driveへの接続（OAuth2認証）を実行するには、Google Cloud Consoleからダウンロードした「OAuth 2.0 クライアント ID (デスクトップ アプリ)」の認証用JSONファイル（`client_secrets.json`）が必要です。
> 今回の実装では、サイドバーに新設する「Google Driveバックアップ設定」から、この `client_secrets.json` ファイルをドラッグ＆ドロップでアップロード可能にし、ローカルに自動保存する設計を想定していますが、この方針でよろしいでしょうか？
> 
> **Q2. ドライブ保存先について**
> バックアップファイルはGoogleドライブのルートフォルダ（直下）に「Saka-tools_backup.json」という名前で作成します。もし既存のファイルがある場合は自動的に上書きアップロードを行います。この仕様でよろしいでしょうか？

---

## 提案する具体的な変更設計

### 1. スプレッドシート保存およびExcelエクスポート機能の完全廃止
- **サイドバー設定の削除**: 
  - `app.py` からサイドバー内の「Googleスプレッドシート設定」セクション全体（認証JSONアップロード、スプレッドシートURL入力、シート名入力など）を完全に削除し、サイドバーをすっきり整理します。
- **エクスポートセクションの整理**: 
  - 画面最下部の「5. バックアップ保存と出力」カードを廃止します。
  - スプレッドシートへの追記処理、SakatsukuGSheetClient関連コード、Excelダウンロードボタンを完全に削除します。
  - 「解析データを空にする（データテーブルのクリア）」ボタンのみを、解析結果テーブルのすぐ下などの適切な位置にシンプルに再配置します。
  - 表のプレビュー、ダブルクリック編集、TSVコピペ用コード（横展開・縦展開）はユーザーのご要望通りそのまま完全に残します。

### 2. Google Drive矩形位置情報バックアップ機能の実装 (OAuth2)
- **依存ライブラリの追加**: 
  - Google Drive APIおよびOAuth2認証フローをサポートするため、以下のライブラリを利用可能にします（実装時にインストールを実行）：
    - `google-api-python-client`
    - `google-auth-oauthlib`
    - `google-auth-httplib2`
- **サイドバー認証管理機能の追加**: 
  - 削除したスプレッドシート設定に代わり、サイドバーに「Google Drive認証設定」を新設します。
  - ユーザーがアップロードした `client_secrets.json` を `C:\Users\katsu\.gemini\antigravity\scratch\sakatsuku_2026\client_secrets.json` に安全に格納します。
- **セキュアなOAuth2フローの実装**: 
  - ローカルデスクトップサーバー環境であることを活かし、`InstalledAppFlow.from_client_config` と `flow.run_local_server(port=0)` による認可サーバー自動起動フローを実装します。
  - 認証が完了すると、取得した有効トークンを `token_drive.json` としてローカルに安全に保存し、2回目以降はバックグラウンドで自動的にトークンをリフレッシュ（Refresh Token）し、完全シームレスな接続を実現します。
  - スコープには、アプリ専用の書き込み領域に限定し、セキュリティが極めて高い `https://www.googleapis.com/auth/drive.file` を適用します。
- **保存・復元UIの追加**:
  - `fitting_hud` （アライメントプレビュー）のすぐ下に、「Googleアカウントに保存」「Googleアカウントから復元」ボタンをビジュアルに優れたApple Proデザインで2カラム配置します。
- **保存処理 (Save)**:
  - Google Drive上に「Saka-tools_backup.json」が存在するか検索。
  - 存在する場合は上書き更新（Update）、存在しない場合は新規作成（Create）をGoogle Drive APIを介してセキュアに実行。
  - 保存対象：
    - `global_scale_x`, `global_scale_y`, `global_offset_x`, `global_offset_y`
    - `group_offsets`, `group_scales`
    - `individual_offsets`, `individual_scales`
    - `is_gk`, `active_items`
- **復元処理 (Restore)**:
  - ドライブから「Saka-tools_backup.json」を読み込んでデコード。
  - Pythonの `st.session_state` のアライメント値を一括上書き。
  - `st.rerun()` を実行して逆同期ハンドラを経由し、フロントエンドのCanvas HUDスライダーや座標枠に復元データを即時同期します。

---

## Proposed Changes

### [Backend / UI Components]

#### [MODIFY] [app.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/app.py)
- サイドバーの「Googleスプレッドシート設定」を削除し、「Google Drive認証設定」を新設。
- スプレッドシート追記処理・Excelダウンロード・旧バックアップ出力エリアを削除。
- 「解析データを空にする」ボタンをテーブル編集エリアの下に整理配置。
- アライメントプレビューの直下に「Googleアカウントに保存」「Googleアカウントから復元」ボタンを配置。
- Google OAuth2認証フロー、Drive APIへのファイル検索・アップロード（Update/Create）・ダウンロードのバックエンドロジックを追加。

#### [DELETE] [gsheet_client.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/gsheet_client.py)
- 不要になったGoogleスプレッドシートクライアントファイルを完全に削除します。

---

## Verification Plan

### 自動・構文検証
1. `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2` を実行し、依存ライブラリをセットアップします。
2. `python -m py_compile app.py` による構文チェックを実行します。

### 手動・UI/UX検証
1. サイドバーから不要になった「スプレッドシート設定」が綺麗に消去されていることを確認します。
2. 新設されたサイドバーの「Google Drive認証設定」から `client_secrets.json` をアップロードします。
3. アライメントスライダーで、適当なオフセットやスケール（例: Xシフトを+50px、全体スケールを1.2xなど）に変更します。
4. 「Googleアカウントに保存」ボタンを押下した際、初回のみブラウザが自動起動し、認証完了後に「Saka-tools_backup.json を保存しました」とサクセスメッセージが表示されることを確認します。
5. 一度スライダーを適当な値にリセット、またはページをリロードして初期状態（0 px）に戻します。
6. 「Googleアカウントから復元」ボタンを押下した際、Google Driveからバックアップファイルが瞬時に読み込まれ、スライダーやプレビュー枠の座標が**保存時の位置（Xシフト+50px、スケール1.2xなど）に寸分違わず自動復元されること**を確認します。
7. 「解析データを空にする」ボタンが期待通り結果テーブルをクリアすることを確認します。
