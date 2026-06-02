# 実装計画書: EasyOCRの初期化パラメータ名誤りによるTypeErrorの修正

本計画書は、ローカル環境でアプリケーションを起動した際、EasyOCRの Reader 初期化において `TypeError: Reader.__init__() got an unexpected keyword argument 'model_storage_dir'` が発生し起動が失敗するバグについて、その原因と根本的解決のための具体的なアプローチをまとめたものです。

---

## 原因（ローカル起動でクラッシュした理由）
ローカル環境のシステム（およびEasyOCRパッケージ）を調査した結果、EasyOCRのモデル保存先を指定する引数キーワード名に誤りがあったことが原因です。

- **誤ったコード**:
  `model_storage_dir=model_dir` を使用して `easyocr.Reader` を呼び出していました。
- **実際の正しい引数定義**:
  Python標準の inspect モジュールによるシグネチャ検証の結果、EasyOCR Readerクラスのコンストラクタでサポートされている引数キーワードは **`model_storage_directory`** であることが判明しました。
  
  ```python
  # 正しい定義:
  (lang_list, gpu=True, model_storage_directory=None, user_network_directory=None, ...)
  ```

引数の名称が微妙に異なっていた（`_dir` ではなく `_directory`）ため、Python側で `TypeError` が発生し、アプリケーション全体の起動プロセスが途中で異常終了してしまっていました。

---

## 提案する修正内容

`src/ocr_engine.py` 内で EasyOCR を初期化している箇所の引数名を正しいキーワード名に修正します。

### ① [src/ocr_engine.py](file:///d:/User%20Files/Masashi/HOME/repos/saka-tools/src/ocr_engine.py) の改修

引数名を `model_storage_dir` から **`model_storage_directory`** へ完璧に書き換えます。

```python
# 修正前:
self.reader = easyocr.Reader(['ja', 'en'], gpu=True, verbose=False, model_storage_dir=model_dir)
self.reader_en = easyocr.Reader(['en'], gpu=True, verbose=False, model_storage_dir=model_dir)

# 修正後:
self.reader = easyocr.Reader(['ja', 'en'], gpu=True, verbose=False, model_storage_directory=model_dir)
self.reader_en = easyocr.Reader(['en'], gpu=True, verbose=False, model_storage_directory=model_dir)
```

---

## 検証計画

### 1. ローカルPC（Windows）での正常起動テスト
- ローカル環境で `streamlit run app.py` を実行し、TypeErrorが完全に収束し、Webブラウザ上で「サカつく2026 パラメータOCRリーダー」のプレミアムUIが正常かつスムーズに立ち上がることを確認します。
- 座標調整やOCR読み取り機能が、一時フォルダ `/tmp`（Windowsの場合は `%TEMP%\easyocr_models`）にモデルを保持した状態で100%正確に動作することを実証します。
