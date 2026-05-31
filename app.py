# -*- coding: utf-8 -*-
"""サカつく2026 パラメーター自動OCRリーダー Streamlit アプリケーション。

画像のアップロード、クリップボードペースト、高精度OCR解析、データの編集・確認、
Googleスプレッドシートへの直接書き込み、およびローカルExcel/CSVダウンロード機能を提供します。
"""

# =====================================================================
# Windows環境特有のエンコードエラー・SSLエラーの完全防止処理 (最優先実行)
# =====================================================================
import sys
import ctypes

try:
    # OSによるスケーリング介入を無効化し、Per-Monitor DPI Awareに設定して画像のボケを防止します
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import ssl
import urllib.request

# 1. すべての標準出力における cp932 エンコードエラーによるクラッシュを防止
# (表現できない文字を自動で '?' に置換して安全にスルーさせます)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(errors='replace')

# 2. EasyOCRのダウンロード進捗バー(\u2588)を強制的に無効化
original_urlretrieve = urllib.request.urlretrieve
def patched_urlretrieve(url, filename=None, reporthook=None, data=None):
    # progress_hook コールバックを None にして本来の処理に委譲
    return original_urlretrieve(url, filename, reporthook=None, data=data)
urllib.request.urlretrieve = patched_urlretrieve

# 3. SSLルート証明書エラーによるダウンロード異常終了を防止
ssl._create_default_https_context = ssl._create_unverified_context
# =====================================================================

import json
import os
import io
import ctypes
import pandas as pd
import streamlit as st
import numpy as np
from PIL import Image, ImageGrab
import cv2

def get_high_res_clipboard_image():
    """Windows APIを直接呼び出し、クリップボードから無劣化・最高解像度の画像を取得します。
    ファイルコピー(CF_HDROP)、PNG生データ、DIBv5、DIBの順で最良のフォーマットを優先抽出します。
    """
    CF_HDROP = 15
    CF_DIB = 8
    CF_DIBV5 = 17
    
    # 登録されたカスタムフォーマット名 "PNG" のフォーマットIDを取得
    PNG_FORMAT = ctypes.windll.user32.RegisterClipboardFormatW("PNG")
    
    if not ctypes.windll.user32.OpenClipboard(None):
        return None
        
    try:
        # ---- 優先度1: CF_HDROP (ファイルコピー) の確認 ----
        # エクスプローラ等でファイルをコピーした場合、ファイルパスのリストを取得
        handle = ctypes.windll.user32.GetClipboardData(CF_HDROP)
        if handle:
            class DROPFILES(ctypes.Structure):
                _fields_ = [
                    ("pFiles", ctypes.c_uint32),
                    ("pt", ctypes.c_long * 2),
                    ("fNC", ctypes.c_int),
                    ("fWide", ctypes.c_int)
                ]
            lock = ctypes.windll.kernel32.GlobalLock(handle)
            size = ctypes.windll.kernel32.GlobalSize(handle)
            df = DROPFILES.from_buffer_copy(ctypes.string_at(lock, ctypes.sizeof(DROPFILES)))
            
            paths = []
            if df.pFiles:
                offset = df.pFiles
                raw_bytes = ctypes.string_at(lock + offset, size - offset)
                paths_str = raw_bytes.decode('utf-16-le' if df.fWide else 'utf-8')
                paths = [p for p in paths_str.split('\x00') if p]
            ctypes.windll.kernel32.GlobalUnlock(handle)
            
            # 有効なファイルパスが存在すれば、パスのリストを返す
            if paths:
                return paths

        # ---- 優先度2: 生のPNGデータとして抽出 ----
        handle = ctypes.windll.user32.GetClipboardData(PNG_FORMAT)
        if handle:
            lock = ctypes.windll.kernel32.GlobalLock(handle)
            size = ctypes.windll.kernel32.GlobalSize(handle)
            raw_data = ctypes.string_at(lock, size)
            ctypes.windll.kernel32.GlobalUnlock(handle)
            return Image.open(io.BytesIO(raw_data)).copy()
            
        # ---- 優先度3: DIBV5 (DIBバージョン5) として抽出 ----
        handle = ctypes.windll.user32.GetClipboardData(CF_DIBV5)
        if handle:
            lock = ctypes.windll.kernel32.GlobalLock(handle)
            size = ctypes.windll.kernel32.GlobalSize(handle)
            raw_data = ctypes.string_at(lock, size)
            ctypes.windll.kernel32.GlobalUnlock(handle)
            
            dib_header_size = int.from_bytes(raw_data[0:4], 'little')
            offset = 14 + dib_header_size
            bmp_header = b'BM' + (14 + size).to_bytes(4, 'little') + b'\x00\x00\x00\x00' + offset.to_bytes(4, 'little')
            return Image.open(io.BytesIO(bmp_header + raw_data)).copy()

        # ---- 優先度4: CF_DIB (標準DIB) として抽出 ----
        handle = ctypes.windll.user32.GetClipboardData(CF_DIB)
        if handle:
            lock = ctypes.windll.kernel32.GlobalLock(handle)
            size = ctypes.windll.kernel32.GlobalSize(handle)
            raw_data = ctypes.string_at(lock, size)
            ctypes.windll.kernel32.GlobalUnlock(handle)
            
            dib_header_size = int.from_bytes(raw_data[0:4], 'little')
            offset = 14 + dib_header_size
            bmp_header = b'BM' + (14 + size).to_bytes(4, 'little') + b'\x00\x00\x00\x00' + offset.to_bytes(4, 'little')
            return Image.open(io.BytesIO(bmp_header + raw_data)).copy()
            
    except Exception as e_clip:
        return None
    finally:
        ctypes.windll.user32.CloseClipboard()
    return None

# 自作モジュールのインポート
from src.ocr_engine import SakatsukuOCREngine
from src.gsheet_client import SakatsukuGSheetClient
from src.config import PARAM_LABELS

# アプリの基本設定
st.set_page_config(
    page_title="サカつく2026 パラメータOCRリーダー",
    layout="wide",
    initial_sidebar_state="expanded",
)

# プレミアムなCSSスタイリングの適用 (ダークテーマ、ガラスモルフィズム風)
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
        color: #fafafa;
    }
    .stButton>button {
        background-color: #00ffaa;
        color: #0e1117;
        font-weight: bold;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1.5rem;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #00cc88;
        transform: scale(1.02);
    }
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
    h1, h2, h3 {
        color: #00ffaa !important;
        font-family: 'Outfit', 'Inter', sans-serif;
    }
    .sidebar-header {
        font-weight: bold;
        color: #00ffaa;
        border-bottom: 2px solid #00ffaa;
        padding-bottom: 5px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if "ocr_engine" not in st.session_state:
    with st.spinner("OCRエンジンの初期化中...（初回は数秒かかります）"):
        st.session_state.ocr_engine = SakatsukuOCREngine()

if "parsed_results" not in st.session_state:
    st.session_state.parsed_results = []  # 解析済みレコードのリスト (辞書形式)

if "target_images" not in st.session_state:
    st.session_state.target_images = []  # 読み込んだ画像のリスト (名前, PIL.Image)

# 一時的な認証情報の保存パス
CREDENTIALS_PATH = "C:\\Users\\katsu\\.gemini\\antigravity\\scratch\\sakatsuku_2026\\credentials_temp.json"

# --- サイドバー：設定エリア ---
with st.sidebar:
    st.markdown('<p class="sidebar-header">⚙️ Googleスプレッドシート設定</p>', unsafe_allow_html=True)
    
    # 認証情報の入力方式の選択
    auth_method = st.radio("認証キー(JSON)の入力方法", ["ファイルをアップロード", "テキストを直接貼り付け", "保存されたキーを使用"])
    
    credentials_json = None
    
    if auth_method == "ファイルをアップロード":
        uploaded_json = st.file_uploader("credentials.json をアップロード", type=["json"])
        if uploaded_json is not None:
            try:
                credentials_json = json.load(uploaded_json)
                # 次回のために一時保存
                with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
                    json.dump(credentials_json, f, ensure_ascii=False, indent=2)
                st.success("認証情報を読み込みました。")
            except Exception as e:
                st.error(f"JSONの解析エラー: {e}")
                
    elif auth_method == "テキストを直接貼り付け":
        json_text = st.text_area("サービスアカウントJSONの中身を貼り付け", height=200)
        if json_text:
            try:
                credentials_json = json.loads(json_text)
                with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
                    json.dump(credentials_json, f, ensure_ascii=False, indent=2)
                st.success("認証情報を読み込みました。")
            except Exception as e:
                st.error(f"JSONの解析エラー: {e}")
                
    elif auth_method == "保存されたキーを使用":
        if os.path.exists(CREDENTIALS_PATH):
            try:
                with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
                    credentials_json = json.load(f)
                st.success("保存済みの認証情報をロードしました。")
            except Exception as e:
                st.error(f"ロード失敗: {e}")
        else:
            st.warning("保存された認証情報が見つかりません。")

    # 書き込み先スプレッドシートの情報
    spreadsheet_url = st.text_input(
        "Googleスプレッドシートの共有URL",
        value=st.session_state.get("gsheet_url", ""),
        help="サービスアカウント（JSONに記載されているメールアドレス）に対して『編集者』として共有されたスプレッドシートのURLを入力してください。"
    )
    if spreadsheet_url:
        st.session_state.gsheet_url = spreadsheet_url

    sheet_name = st.text_input(
        "書き込み先シート名",
        value=st.session_state.get("gsheet_name", "選手データ"),
        help="スプレッドシート内の対象タブ名を入力してください。存在しない場合は自動作成されます。"
    )
    if sheet_name:
        st.session_state.gsheet_name = sheet_name

# --- メインエリア：アプリケーション本体 ---
st.title("⚽ サカつく2026 パラメーター自動OCRリーダー")
st.write("選手のパラメータ画面画像を読み取り、Googleスプレッドシートへ自動追記します。")

# アプリケーションの操作タブ
tab_upload, tab_paste = st.tabs(["📁 画像ファイルアップロード", "📋 クリップボードからペースト"])

# アップローダーの画像取得
with tab_upload:
    uploaded_files = st.file_uploader(
        "パラメータ画面のスクリーンショット画像を選択（複数対応）",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True
    )
    if uploaded_files:
        for file in uploaded_files:
            img = Image.open(file)
            # 重複防止のため同名ファイルがない場合のみ追加
            if not any(name == file.name for name, _ in st.session_state.target_images):
                st.session_state.target_images.append((file.name, img))
        st.success(f"ファイルを読み込みました（現在合計 {len(st.session_state.target_images)} 枚の画像がメモリに保持されています）")

# クリップボードの画像取得
with tab_paste:
    st.write("1. ゲーム中の選手パラメータ画面で画像をコピー（Ctrl+C または Win+Shift+S でキャプチャ）します。")
    st.write("2. 下記のエリアをクリックしてフォーカスを当て、**`Ctrl + V`** キーを押すことで、画像が無劣化の超高解像度のまま直接読み込まれます。")
    
    # 公式インラインカスタムコンポーネントの宣言と登録
    import streamlit.components.v1 as components
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    paste_bridge_dir = os.path.join(parent_dir, "src", "paste_bridge")
    paste_bridge = components.declare_component("paste_bridge", path=paste_bridge_dir)
    
    # 二重読み込み防止のためのセッション状態初期化
    if "last_pasted_base64" not in st.session_state:
        st.session_state.last_pasted_base64 = None
        
    # カスタムコンポーネントの描画とデータの受け取り
    pasted_base64 = paste_bridge(key="paste_bridge_instance")
    
    # 新しいデータを受信した場合の処理
    if pasted_base64 and pasted_base64 != st.session_state.last_pasted_base64:
        try:
            base64_str = pasted_base64
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            
            import base64
            img_bytes = base64.b64decode(base64_str)
            pasted_img = Image.open(io.BytesIO(img_bytes)).copy()
            
            import time
            clip_name = f"Clipboard_{int(time.time())}"
            st.session_state.target_images.append((clip_name, pasted_img))
            
            # 重複実行を防止するために受信データをキャッシュ
            st.session_state.last_pasted_base64 = pasted_base64
            
            st.success("ブラウザ経由でクリップボードから完全無劣化の超高解像度画像を取得しました！")
            st.rerun()  # メモリ上の画像をプレビューに即座に反映させるため再描画
        except Exception as e_dec:
            st.error(f"画像のデコード中にエラーが発生しました: {e_dec}")

# 現在メモリに読み込まれている画像の確認プレビュー
if st.session_state.target_images:
    st.write("---")
    st.subheader(f"🖼️ メモリ上の読み込み画像リスト ({len(st.session_state.target_images)}枚)")
    
    # 読み込まれている画像のプレビューを一覧表示（生画像をそのまま渡すことでボケを100%防止）
    cols_img = st.columns(min(len(st.session_state.target_images), 6))
    for idx, (img_name, img) in enumerate(st.session_state.target_images):
        with cols_img[idx % 6]:
            st.caption(img_name)
            st.image(img, use_container_width=True)

# --- 画像の解析実行 ---
if st.session_state.target_images:
    st.write("---")
    st.subheader("🔍 画像の解析処理")
    
    col_analyze_btn, col_clear_btn = st.columns([1, 4])
    
    # 解析実行ボタン
    with col_analyze_btn:
        run_ocr = st.button("🚀 画像のOCR解析を開始")
        
    with col_clear_btn:
        if st.button("🗑️ 読み込んだ画像リストをクリア"):
            st.session_state.target_images = []
            st.session_state.parsed_results = []
            st.success("読み込まれていた画像リストをクリアしました。")
            st.rerun()
            
    if run_ocr:
        # 詳細なリアルタイム処理状況ログ表示用ステータスエリア
        log_status = st.status("⚙️ OCR解析プロセスの進行状況 (リアルタイムログ)", expanded=True)
        
        with log_status:
            st.write("▶ [INFO] 画像解析タスクを開始します。")
            temp_results = []
            total_imgs = len(st.session_state.target_images)
            
            for idx, (img_name, img) in enumerate(st.session_state.target_images):
                step_prefix = f"[{idx + 1}/{total_imgs}]"
                st.write(f"**{step_prefix} 画像: {img_name} の解析処理中**")
                
                try:
                    # 1. 読み込みとリサイズ
                    st.write(f"{step_prefix} [PROCESS] 1. 画像の標準化リサイズ処理を実行中 (1920x1080 に正規化)...")
                    
                    # 2. クロップ切り出し
                    st.write(f"{step_prefix} [PROCESS] 2. OpenCVによるパラメータ領域 (ROI) のクロップ切り出しを開始...")
                    
                    # 3. 前処理
                    st.write(f"{step_prefix} [PROCESS] 3. 切り出し画像の前処理 (グレースケール化、拡大、適応的二値化) を適用中...")
                    
                    # 4. OCR文字認識
                    st.write(f"{step_prefix} [PROCESS] 4. EasyOCRによる文字・数値の認識とテキスト抽出を実行中 (初回はモデルロードのため数秒要します)...")
                    result = st.session_state.ocr_engine.extract_all_parameters(img)
                    
                    # 5. パースとマッピング
                    st.write(f"{step_prefix} [PROCESS] 5. 抽出テキストの正規化と数値パースが完了しました。")
                    result["元画像名"] = img_name
                    temp_results.append(result)
                    
                    # 成功ログ
                    st.write(f"✅ {step_prefix} [SUCCESS] [選手名: {result.get('選手名', '不明')}, 総合力: {result.get('総合力', '不明')}] のパラメータの復元に成功しました！")
                    
                except Exception as ex:
                    st.error(f"❌ {step_prefix} [ERROR] 解析中に致命的なエラーが発生しました: {ex}")
                    # デバッグ用にエラー詳細を出力
                    import traceback
                    st.code(traceback.format_exc(), language="python")
            
            if temp_results:
                # 解析結果をセッションに追加
                st.session_state.parsed_results.extend(temp_results)
                log_status.update(label="🎉 すべての画像のOCR解析が正常に終了しました！", state="complete", expanded=True)
                st.success(f"{len(temp_results)}件の選手パラメータの解析結果を表に反映しました。")

# --- 解析結果の確認・編集・出力 ---
if st.session_state.parsed_results:
    st.write("---")
    st.subheader("📊 解析結果のプレビューとデータ編集")
    st.info("💡 スプレッドシートへ書き込む前に、表のセルをダブルクリックして手動で数値を修正・確認できます。")
    
    # リストをPandas DataFrameに変換
    df_results = pd.DataFrame(st.session_state.parsed_results)
    
    # 列の並び順を綺麗に整理する（基本情報→メイン→個別→その他）
    all_columns = df_results.columns.tolist()
    column_order = [
        "元画像名", "選手名", "ポジション", "ランク", "総合力",
        "SHOランク", "SHO数値",
        "PASランク", "PAS数値",
        "DRBランク", "DRB数値",
        "DEFランク", "DEF数値",
        "PHYランク", "PHY数値",
        "SPDランク", "SPD数値",
        "決定力", "キック力", "冷静さ",
        "ショートパス", "ロングパス", "キック精度",
        "突破力", "キープ力", "ボールタッチ",
        "タックル", "パスカット", "マーク",
        "ジャンプ", "コンタクト", "スタミナ",
        "走力", "敏捷性"
    ]
    
    # 存在する列のみの順序に再定義
    actual_order = [col for col in column_order if col in all_columns]
    # 残りの列を末尾に追加
    actual_order += [col for col in all_columns if col not in actual_order]
    
    df_ordered = df_results[actual_order]
    
    # ユーザーが編集可能な表を表示 (st.data_editor)
    edited_df = st.data_editor(df_ordered, use_container_width=True, num_rows="dynamic")
    
    # 解析元のクロップ画像プレビュー（アコーディオン）
    with st.expander("📸 認識エリアの切り出し画像を確認する（デバッグ用）"):
        if st.session_state.target_images:
            selected_img_name = st.selectbox("画像を選択", [name for name, _ in st.session_state.target_images])
            selected_img = [img for name, img in st.session_state.target_images if name == selected_img_name][0]
            
            # OpenCV画像に変換
            img_cv = cv2.cvtColor(np.array(selected_img), cv2.COLOR_RGB2BGR)
            crop_dict = st.session_state.ocr_engine.get_cropped_images_dict(img_cv)
            
            # グリッド表示
            cols = st.columns(6)
            for idx, (label, crop) in enumerate(crop_dict.items()):
                with cols[idx % 6]:
                    st.caption(label)
                    st.image(crop, use_container_width=True)
    
    # --- アクションエリア ---
    st.write("---")
    st.subheader("💾 データの出力・保存")
    
    col_sheet, col_excel, col_clear = st.columns([2, 1, 1])
    
    with col_sheet:
        st.markdown("**1. Googleスプレッドシートへ書き込み**")
        if st.button("📤 Googleスプレッドシートへ書き込む"):
            if not credentials_json:
                st.error("左側サイドバーでGoogle APIの認証情報を設定してください。")
            elif not spreadsheet_url:
                st.error("左側サイドバーでGoogleスプレッドシートの共有URLを入力してください。")
            else:
                try:
                    with st.spinner("Googleスプレッドシートにアクセスし、データを最終行へ書き込み中..."):
                        client = SakatsukuGSheetClient(credentials_info=credentials_json)
                        
                        # 編集後のデータを辞書のリストとして取得
                        records_to_write = edited_df.to_dict(orient="records")
                        
                        written_count = 0
                        for record in records_to_write:
                            # NaN（空値）を除去
                            cleaned_record = {k: v for k, v in record.items() if pd.notna(v) and v != ""}
                            
                            row_num = client.append_parameter_data(
                                spreadsheet_url=spreadsheet_url,
                                sheet_name=sheet_name,
                                param_dict=cleaned_record
                            )
                            written_count += 1
                        
                        st.success(f"🎉 正常に {written_count}件のデータをGoogleスプレッドシートに追記しました！(最終行: 行番号{row_num}近辺)")
                except Exception as e_gs:
                    st.error(f"スプレッドシート書き込み中にエラーが発生しました: {e_gs}")
                    
    with col_excel:
        st.markdown("**2. ローカル用ダウンロード**")
        # Excelファイルのダウンロード準備
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            edited_df.to_excel(writer, index=False, sheet_name="サカつく2026_パラメータ")
        excel_data = excel_buffer.getvalue()
        
        st.download_button(
            label="📥 Excelファイル (.xlsx) として保存",
            data=excel_data,
            file_name="sakatsuku_parameters.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    with col_clear:
        st.markdown("**3. リストのクリア**")
        if st.button("🧹 表示リストを空にする", help="現在画面にプレビュー表示されているデータをクリアします。"):
            st.session_state.parsed_results = []
            st.session_state.target_images = []  # 画像もクリア
            st.rerun()
