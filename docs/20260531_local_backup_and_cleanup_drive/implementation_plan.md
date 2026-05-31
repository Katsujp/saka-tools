# 実装計画：Googleドライブ連携の撤回およびローカルJSONファイルによる矩形位置情報保存・復元機能の実装

本ドキュメントは、Google APIのOAuth2制限（ invalid_client ）エラーにより発生したドライブ連携の課題をスマートに回避するため、Google Drive連携機能を完全に撤回し、代わりにローカル環境で安全かつ確実に動作する「JSONファイルによる矩形位置情報の保存・復元機能」を実装するための計画書です。

---

## 原因・現状の課題

1. **Google OAuth2 認証ブロックエラー**:
   アプリに仮内蔵した Google OAuth クライアント資格情報が実在しない、または開発用アカウント制限によりブロックされたことで、接続時に「Access blocked: Authorization Error / Error 401: invalid_client」が発生し、保存・復元が実行できない問題が発生しました。
2. **クラウド依存の回避とオフライン対応**:
   Google アカウントを所有していない、または連携させたくないユーザーや、インターネットに接続されていない完全オフライン環境においても、調整した各パラメータの矩形枠座標（アライメント）を確実にPC内に永続化・復元できる仕組みへの変更が必要です。

---

## 提案する具体的な変更設計

### 1. Google Drive連携機能の完全排除
- **Drive APIコードの削除**: 
  - `app.py` から、先ほど追加した Google OAuth2 認証、InstalledAppFlow、Drive APIクライアント関連のロジック、および `DRIVE_CLIENT_CONFIG` などの構成情報をすべて完全に削除します。
- **起動時ダイアログの削除**: 
  - ツールを開いた初回時に表示されていた「Google Driveから設定情報を復元するかどうか」を尋ねる確認ダイアログ（`st.dialog`）およびセッションフラグ（`drive_restore_checked`）を完全に撤廃し、最初から不要なステップなしで即座にアプリが起動するように戻します。

### 2. ローカルでのJSONファイル保存・復元機能の実装
Streamlitの性質（Webアプリケーションフレームワーク）および動作の極めて高い安定性を考慮し、以下の**「Streamlit標準のセキュアなWebダウンロード/アップロード方式」**を採用します。
※Pythonの `tkinter.filedialog` をサーバー側で呼び出す方式は、GUIダイアログが開いている間に Streamlit のプロセスが完全にブロック（フリーズ）してブラウザがタイムアウトを起こしたり、Tkinterの非メインスレッド例外でアプリがハングアップする重大なリスクがあるため、以下のStreamlit公式方式が最も安全で洗練されています。

#### A. 「ローカルに保存」ボタン (ブラウザダウンロード方式)
- `fitting_hud`（アライメントプレビュー）のすぐ下に「ローカルに保存 (JSON)」ボタンを配置します。
- このボタンは Streamlit の `st.download_button` を使用して実装します。
- ボタンをクリックすると、ブラウザ標準の「名前を付けて保存」ダイアログがOSから安全に開き、ユーザーは**PC内の任意のフォルダを指定して「sakatsuku_alignment.json」などのファイル名でアライメント設定を直接保存**できます。

#### B. 「ローカルから復元」ボタン (ファイルアップローダー方式)
- 「ローカルに保存 (JSON)」ボタンの隣に、アライメント設定JSONをアップロードするためのスマートなファイルアップローダー（`st.file_uploader`）を配置します。
- ユーザーが過去に保存した設定JSONファイルをドラッグ＆ドロップ、またはクリックして選択した瞬間、Python側で即座にファイルを解析し、`st.session_state` の該当パラメータ群（シフト、スケール、GKロール、有効項目）を一括上書きして `st.rerun()` を実行し、アライメント枠に反映（逆同期）させます。

- **保存・復元対象データ**:
  - `global_scale_x`, `global_scale_y`, `global_offset_x`, `global_offset_y`
  - `group_offsets`, `group_scales`
  - `individual_offsets`, `individual_scales`
  - `is_gk`, `active_items`

---

## Proposed Changes

### [Backend / UI Components]

#### [MODIFY] [app.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/app.py)
- Google OAuth2、Drive API、`get_drive_credentials`、`save_to_google_drive`、`restore_from_google_drive`、および起動時ダイアログ `show_restore_dialog` を完全に削除。
- `fitting_hud` のすぐ下に、ローカル保存用の `st.download_button` と、ローカル復元用の `st.file_uploader` を美しいApple Proスタイルの2カラム構成で追加配置。
- アップロードされたJSONを検証・展開し、セッション状態を更新して即時再レンダリング（逆同期）する復元ハンドラーの実装。

---

## Verification Plan

### 自動・構文検証
1. `python -m py_compile app.py` による構文チェックを実行します。

### 手動・UI/UX検証
1. ツールを起動した際、Google Drive関連のポップアップ確認ダイアログが一切表示されず、即座にメイン画面が立ち上がることを確認します。
2. アライメントスライダーで、適当なオフセットやスケール（例: Xシフトを+30px、全体スケールを1.15xなど）に変更します。
3. 「ローカルに保存 (JSON)」ボタンを押下した際、ブラウザの「名前を付けて保存」ウィンドウが開き、任意の場所に `sakatsuku_alignment.json` ファイルを正しく保存できることを確認します。
4. 一度ページを再読み込みする、あるいはスライダーの値をすべて初期値（0 px）にリセットします。
5. 「ローカルから復元」のアップローダーに、先ほど保存した `sakatsuku_alignment.json` をアップロードします。
6. アップロードした瞬間に、プレビュー枠およびスライダーが**保存時の位置（Xシフト+30px、全体スケール1.15xなど）に完璧に自動復元されること**を確認します。
