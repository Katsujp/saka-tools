# 実装計画書: Streamlit Cloud デプロイ環境における EasyOCR 起動クラッシュの修正

本計画書は、本アプリケーションを Streamlit Cloud（Web上）へデプロイして起動した際、EasyOCRのモデルダウンロード時において `temp.zip` の `FileNotFoundError` でシステムがクラッシュする問題について、その原因究明結果と根本的に解決するための具体的なアプローチをまとめたものです。

---

## 原因（デプロイ環境でクラッシュした理由）
エラー内容のスタックトレースを解析した結果、クラッシュの原因は以下の2点に集約されます。

1. **ホームディレクトリへの書き込み制限**:
   - EasyOCRは、初回起動時に検出モデルと認識モデルを自動ダウンロードし、デフォルトで `~/.EasyOCR/model/`（ユーザーのホームディレクトリ配下）に保存しようとします。
   - Streamlit Cloud のコンテナ Linux 環境（`/home/appuser/` 配下）では、セキュリティポリシーやディスク制限によりファイルの書き込み権限が厳しく制限されているか、ダウンロード用のテンポラリファイルが作成できず、モデルのZIP解凍時に `temp.zip` が見つからずに `FileNotFoundError` でクラッシュを引き起こしてしまいます。

2. **Windows専用バグ回避パッチのLinuxへの干渉**:
   - Windows環境特有の「コンソール進捗バーの cp932 エンコードエラー」を回避するために `app.py` 内に導入した `urllib.request.urlretrieve` 進捗バー無効化パッチが、Linux環境（Streamlit Cloud）でも無条件に適用されてしまい、標準ダウンロード処理の健全な動作に干渉した可能性があります。

---

## 提案する修正内容

デプロイ先のコンテナ環境でも100%確実に書き込み可能な一時フォルダ（`/tmp` 等）へモデルの保存先を明示的に逃がすとともに、Windows専用の回避処理を厳密に局所化することで、環境を選ばない極めて頑強な「防弾アーキテクチャ」へと進化させます。

### ① [src/ocr_engine.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/ocr_engine.py) の改修

1. **モデル保存先の一時ディレクトリへの逃がし**:
   - 確実に書き込み可能な `/tmp/easyocr_models` ディレクトリを自動作成します（Windowsの場合はカレント内のキャッシュ等、OS非依存で安全なテンポラリディレクトリを取得）。
   - `easyocr.Reader` を初期化する際、引数 **`model_storage_dir`** にこの安全な一時ディレクトリパスを明示的に指定して起動します。
   ```python
   import tempfile
   import os
   
   # OS非依存で確実に書き込み可能な一時フォルダ配下に専用ディレクトリを作成
   model_dir = os.path.join(tempfile.gettempdir(), "easyocr_models")
   os.makedirs(model_dir, exist_ok=True)
   
   # model_storage_dir を指定して初期化し、ホームフォルダの権限問題を100%回避！
   self.reader = easyocr.Reader(['ja', 'en'], gpu=True, verbose=False, model_storage_dir=model_dir)
   self.reader_en = easyocr.Reader(['en'], gpu=True, verbose=False, model_storage_dir=model_dir)
   ```
   これにより、Streamlit Cloudのセキュリティ制限に引っかかることなく、100%確実にモデルの自動ダウンロードと解凍・読み込みが完了します。

### ② [app.py (ルート直下)](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/app.py) の改修

1. **Windows固有パッチの適用範囲を厳密に限定**:
   - `app.py` の最優先実行ブロックにおいて、DPI Aware設定および `urlretrieve` パッチの実行を **`platform.system() == "Windows"`** の場合のみに制限します。
   - これにより、Streamlit Cloud (Linux) 環境では余計なパッチをバイパスし、Python標準ライブラリのクリーンでネイティブな通信・ファイル保存処理が確実に実行されます。

---

## 検証計画

### 1. ローカルPC（Windows）での正常起動テスト
- ローカル環境で `streamlit run app.py` を実行し、モデル保存先がテンポラリディレクトリに変更された状態で問題なく起動することを確認します。
- 座標調整やOCR読み取りがこれまで通り高精度かつ正確に実行されることを検証します。

### 2. Streamlit Cloudへのデプロイ後の正常起動
- コードをGitHub経由でStreamlit Cloudに反映し、ビルドログにおいて `temp.zip` のエラーが完全に収束し、Web上で「サカつく2026 パラメータOCRリーダー」が正常に立ち上がることを確認します。
