# -*- coding: utf-8 -*-
"""サカつく2026 パラメーター自動OCRリーダー Streamlit アプリケーション。

画像のアップロード、クリップボードペースト、高精度な動的座標調整（案A・案B）、
FP/GKロール切り替え、縦横展開対応コピペステーション、Googleスプレッドシート書き込み、
およびローカルExcelダウンロード機能を提供します。
"""

# =====================================================================
# Windows環境特有のエンコードエラー・SSLエラーの完全防止処理 (最優先実行)
# =====================================================================
import sys
import ctypes

try:
    # OSによるスケーリング介入を無効化し、Per-Monitor DPI Awareに設定して画像のボケを防止
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import ssl
import urllib.request

# 1. すべての標準出力における cp932 エンコードエラーによるクラッシュを防止
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(errors='replace')

# 2. EasyOCRのダウンロード進捗バー(\u2588)を強制的に無効化
original_urlretrieve = urllib.request.urlretrieve
def patched_urlretrieve(url, filename=None, reporthook=None, data=None):
    return original_urlretrieve(url, filename, reporthook=None, data=data)
urllib.request.urlretrieve = patched_urlretrieve

# 3. SSLルート証明書エラーによるダウンロード異常終了を防止
ssl._create_default_https_context = ssl._create_unverified_context
# =====================================================================

import json
import os
import time
import io
import base64
import pandas as pd
import streamlit as st
import numpy as np
from PIL import Image
import cv2

# 自作モジュールのインポート
from src.ocr_engine import SakatsukuOCREngine
from src.gsheet_client import SakatsukuGSheetClient
from src.config import DEFAULT_ROIS, GROUPS, GK_ALIASES

# アプリの基本設定
st.set_page_config(
    page_title="サカつく2026 パラメータOCRリーダー",
    layout="wide",
    initial_sidebar_state="expanded",
)

# プレミアムなApple Pro漆黒ミニマリズムUIスタイリングの適用 (色数を極限まで抑制し、メリハリを最大化)
st.markdown("""
<style>
    /* 全体背景とベーステキストの強制適用 */
    [data-testid="stAppViewContainer"], .stApp, .main, [data-testid="stHeader"] {
        background-color: #1c1c1e !important;
        color: #f5f5f7 !important;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif;
    }
    .main {
        background-color: #1c1c1e;
        color: #f5f5f7;
    }
    
    /* Apple Pro ミニマルタイトル */
    .main-title {
        color: #ffffff;
        font-size: 2.2rem;
        font-weight: 700;
        text-align: center;
        margin-top: 1.5rem;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    
    .subtitle {
        text-align: center;
        color: #8e8e93; /* SF Text Secondary */
        font-size: 1.0rem;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* Apple純正設定のようなフラットなカードデザイン */
    .apple-card {
        background: #2c2c2e; /* Apple System Card Background */
        border: 1px solid #3a3a3c;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    }
    
    /* Appleスタイルボタン */
    .stButton>button {
        background-color: #0071e3; /* Apple SF Pro Blue Primary */
        color: #ffffff !important;
        font-weight: 600;
        font-size: 13px;
        border-radius: 8px;
        border: none;
        padding: 8px 24px;
        transition: background-color 0.15s ease;
    }
    .stButton>button:hover {
        background-color: #147ce5;
        border: none;
    }
    .stButton>button:active {
        background-color: #0062c4;
    }

    /* クールでフラットな見出し */
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: 700;
        letter-spacing: -0.01em;
        border: none !important;
        margin-top: 0;
    }
    
    /* サイドバーのApple System Settings風デザイン */
    .sidebar-header {
        font-weight: 700;
        color: #ffffff;
        font-size: 14px;
        padding-bottom: 8px;
        border-bottom: 1px solid #3a3a3c;
        margin-bottom: 16px;
    }
    
    /* タブデザインの最適化 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background-color: #1c1c1e;
        padding: 4px;
        border-radius: 8px;
        border: 1px solid #3a3a3c;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 6px 16px;
        color: #8e8e93;
        font-weight: 600;
        font-size: 13px;
        transition: all 0.1s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2c2c2e !important;
        color: #ffffff !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
import sys
import importlib
import inspect
if "ocr_engine" not in st.session_state:
    with st.spinner("OCRシステム起動中..."):
        st.session_state.ocr_engine = SakatsukuOCREngine()
else:
    # 開発中のコード変更に追従するため、メソッドシグネチャを動的に検証して自動再ロード
    sig = inspect.signature(st.session_state.ocr_engine.extract_all_parameters)
    if "is_preprocessed" not in sig.parameters:
        with st.spinner("OCRシステムの定義更新を検知。再起動中..."):
            # キャッシュされたモジュールを強制リロードして最新のコードを100%確実に読み込む
            if "src.ocr_engine" in sys.modules:
                importlib.reload(sys.modules["src.ocr_engine"])
            from src.ocr_engine import SakatsukuOCREngine
            st.session_state.ocr_engine = SakatsukuOCREngine()

if "parsed_results" not in st.session_state:
    st.session_state.parsed_results = []  # 解析結果レコードリスト

if "target_images" not in st.session_state:
    st.session_state.target_images = []  # メモリ上の画像リスト (name, PILImage)

# 座標調整パラメータのセッション同期用初期化
if "global_scale_x" not in st.session_state:
    st.session_state.global_scale_x = 1.00
if "global_scale_y" not in st.session_state:
    st.session_state.global_scale_y = 1.00
if "global_offset_x" not in st.session_state:
    st.session_state.global_offset_x = 0
if "global_offset_y" not in st.session_state:
    st.session_state.global_offset_y = 0
if "is_gk" not in st.session_state:
    st.session_state.is_gk = False
if "active_items" not in st.session_state:
    st.session_state.active_items = list(DEFAULT_ROIS.keys())

# グループオフセット・スケールの初期化
if "group_offsets" not in st.session_state:
    st.session_state.group_offsets = {grp: [0, 0] for grp in GROUPS.keys()}
if "group_scales" not in st.session_state:
    st.session_state.group_scales = {grp: [1.0, 1.0] for grp in GROUPS.keys()}

# 個別オフセット・スケールの初期化
if "individual_offsets" not in st.session_state:
    st.session_state.individual_offsets = {item: [0, 0] for item in DEFAULT_ROIS.keys()}
if "individual_scales" not in st.session_state:
    st.session_state.individual_scales = {item: [1.0, 1.0] for item in DEFAULT_ROIS.keys()}

# 一時的な認証情報の保存パス
CREDENTIALS_PATH = "C:\\Users\\katsu\\.gemini\\antigravity\\scratch\\sakatsuku_2026\\credentials_temp.json"

def get_image_base64(img_pil):
    """PIL画像をBase64形式のData URIに高速変換します。"""
    buffered = io.BytesIO()
    img_pil.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"

def normalize_and_convert_to_pil(img_pil, ocr_engine):
    """画像の自動トリミングおよび1920x1080正規化を行い、PIL Imageとして返します。"""
    # OpenCV BGR画像に変換
    image_np = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    # OCRエンジンによる自動トリミング・1920x1080リサイズ
    normalized_np = ocr_engine.preprocess_image(image_np)
    # PIL RGB画像に戻す
    normalized_rgb = cv2.cvtColor(normalized_np, cv2.COLOR_BGR2RGB)
    return Image.fromarray(normalized_rgb)

# --- サイドバー：設定エリア ---
with st.sidebar:
    st.markdown('<p class="sidebar-header">Googleスプレッドシート設定</p>', unsafe_allow_html=True)
    
    auth_method = st.radio("認証キー(JSON)の入力方法", ["保存されたキーを使用", "ファイルをアップロード", "テキストを直接貼り付け"])
    
    credentials_json = None
    
    if auth_method == "ファイルをアップロード":
        uploaded_json = st.file_uploader("credentials.json をアップロード", type=["json"])
        if uploaded_json is not None:
            try:
                credentials_json = json.load(uploaded_json)
                os.makedirs(os.path.dirname(CREDENTIALS_PATH), exist_ok=True)
                with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
                    json.dump(credentials_json, f, ensure_ascii=False, indent=2)
                st.success("認証情報をロードしました。")
            except Exception as e:
                st.error(f"JSONの解析エラー: {e}")
                
    elif auth_method == "テキストを直接貼り付け":
        json_text = st.text_area("サービスアカウントJSONの中身を貼り付け", height=150)
        if json_text:
            try:
                credentials_json = json.loads(json_text)
                os.makedirs(os.path.dirname(CREDENTIALS_PATH), exist_ok=True)
                with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
                    json.dump(credentials_json, f, ensure_ascii=False, indent=2)
                st.success("認証情報をロードしました。")
            except Exception as e:
                st.error(f"JSONの解析エラー: {e}")
                
    elif auth_method == "保存されたキーを使用":
        if os.path.exists(CREDENTIALS_PATH):
            try:
                with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
                    credentials_json = json.load(f)
                st.success("保存済みキーをロードしました。")
            except Exception as e:
                st.error(f"ロード失敗: {e}")
        else:
            st.warning("保存された認証情報が見つかりません。")

    spreadsheet_url = st.text_input(
        "Googleスプレッドシートの共有URL",
        value=st.session_state.get("gsheet_url", "")
    )
    if spreadsheet_url:
        st.session_state.gsheet_url = spreadsheet_url

    sheet_name = st.text_input(
        "書き込み先シート名",
        value=st.session_state.get("gsheet_name", "選手データ")
    )
    if sheet_name:
        st.session_state.gsheet_name = sheet_name

# --- メインエリア：アプリケーション本体 ---
st.markdown('<div class="main-title">Parameter Precision Reader</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">高精度画像解析と、極めてスムーズなアライメント調整を提供するパラメータ抽出システム。</div>', unsafe_allow_html=True)

# 1. 画像のインプットエリア
st.markdown('<div class="apple-card">', unsafe_allow_html=True)
st.subheader("画像ソースのロード")

tab_upload, tab_paste = st.tabs(["画像ファイルアップロード", "クリップボードからペースト"])

# アップローダーの画像取得
with tab_upload:
    uploaded_files = st.file_uploader(
        "パラメータ画面のスクリーンショットを選択",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="file_uploader_instance"
    )
    if uploaded_files:
        for file in uploaded_files:
            img = Image.open(file)
            if not any(name == file.name for name, _ in st.session_state.target_images):
                # ロードと同時にあらかじめ高精度自動トリミング・1920x1080正規化を完了させ、完全に一本化
                normalized_img = normalize_and_convert_to_pil(img, st.session_state.ocr_engine)
                st.session_state.target_images.append((file.name, normalized_img))
        st.success(f"画像をロードおよび高精度正規化トリミング処理しました (現在合計: {len(st.session_state.target_images)}枚)")

# クリップボードからのペースト
with tab_paste:
    st.write("ゲーム中の選手パラメータ画面でキャプチャをコピーし、下のフォームをクリックして Ctrl + V キーを押してください。")
    
    # ペーストブリッジカスタムコンポーネント
    import streamlit.components.v1 as components
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    paste_bridge_dir = os.path.join(parent_dir, "src", "paste_bridge")
    paste_bridge = components.declare_component("paste_bridge", path=paste_bridge_dir)
    
    if "last_pasted_base64" not in st.session_state:
        st.session_state.last_pasted_base64 = None
        
    pasted_base64 = paste_bridge(key="paste_bridge_instance")
    
    if pasted_base64 and pasted_base64 != st.session_state.last_pasted_base64:
        try:
            base64_str = pasted_base64
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            
            import base64
            img_bytes = base64.b64decode(base64_str)
            pasted_img = Image.open(io.BytesIO(img_bytes)).copy()
            
            # ロードと同時にあらかじめ高精度自動トリミング・1920x1080正規化を完了させ、完全に一本化
            normalized_img = normalize_and_convert_to_pil(pasted_img, st.session_state.ocr_engine)
            
            clip_name = f"Clipboard_{int(time.time())}"
            st.session_state.target_images.append((clip_name, normalized_img))
            st.session_state.last_pasted_base64 = pasted_base64
            
            st.success("クリップボードから画像を取得および高精度トリミング処理しました。")
            st.rerun()
        except Exception as e_dec:
            st.error(f"画像のデコード中にエラーが発生しました: {e_dec}")
st.markdown('</div>', unsafe_allow_html=True)

# 2. クライアントサイド完全リアルタイム調整Canvas HUDのロード
if st.session_state.target_images:
    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    st.subheader("高精度座標フィッティング & リアルタイムプレビュー")
    st.write("右側のスライダーを操作すると、ブラウザ側で遅延なく完全に滑らかに枠線が動きます。枠が数値エリアに重なるよう調整してください。")
    
    # 対象画像のセレクトボックス
    img_names = [name for name, _ in st.session_state.target_images]
    selected_img_name = st.selectbox("プレビュー対象画像", img_names)
    selected_pil = [img for name, img in st.session_state.target_images if name == selected_img_name][0]
    
    # すでにトリミング・正規化済みのPIL画像のBase64 Data URIを取得（フロント/バックの座標完全統合）
    image_uri = get_image_base64(selected_pil)

    # カスタムコンポーネント「fitting_hud」の宣言
    fitting_hud_dir = os.path.join(parent_dir, "src", "fitting_hud")
    fitting_hud = components.declare_component("fitting_hud", path=fitting_hud_dir)

    # セッション状態でOCRの実行完了フラグを初期化
    if "ocr_run_completed" not in st.session_state:
        st.session_state.ocr_run_completed = False

    # 双方向カスタムコンポーネントの実行 (Streamlit側からすべての最新調整パラメータを確実にJS側に引き渡してリセットを防止)
    hud_response = fitting_hud(
        key="fitting_hud_instance",
        image_base64=image_uri,  # 標準引数として画像URIを確実に直接転送！
        default_rois=DEFAULT_ROIS,
        groups=GROUPS,
        height=720,
        is_gk=st.session_state.is_gk,
        active_items=st.session_state.active_items,
        global_scale_x=st.session_state.global_scale_x,
        global_scale_y=st.session_state.global_scale_y,
        global_offset=[st.session_state.global_offset_x, st.session_state.global_offset_y],
        group_scales=st.session_state.group_scales,
        group_offsets=st.session_state.group_offsets,
        individual_scales=st.session_state.individual_scales,
        individual_offsets=st.session_state.individual_offsets
    )
    
    # 解析実行フラグ
    trigger_ocr_run = False
    
    # JSコンポーネント側からの双方向データ送信の受け取り・状態同期
    if hud_response is not None:
        resp_type = hud_response.get("type")
        resp_data = hud_response.get("data", {})
        
        if resp_type == "update_state":
            # ユーザーによる操作（パラメータ調整やロール切り替えなど）があった場合、OCR完了ロックを解除
            st.session_state.ocr_run_completed = False
            
            # JS側で調整された最新の座標・スライダーの状態をPython側に一瞬で同期
            st.session_state.is_gk = resp_data.get("isGk", False)
            st.session_state.active_items = resp_data.get("activeItems", [])
            st.session_state.global_scale_x = resp_data.get("global_scale_x", 1.0)
            st.session_state.global_scale_y = resp_data.get("global_scale_y", 1.0)
            st.session_state.global_offset_x = resp_data.get("global_offset", [0, 0])[0]
            st.session_state.global_offset_y = resp_data.get("global_offset", [0, 0])[1]
            
            # グループパラメータの同期
            js_grp_offsets = resp_data.get("group_offsets", {})
            js_grp_scales = resp_data.get("group_scales", {})
            for grp in GROUPS.keys():
                st.session_state.group_offsets[grp] = js_grp_offsets.get(grp, [0, 0])
                st.session_state.group_scales[grp] = js_grp_scales.get(grp, [1.0, 1.0])
                
            # ロールに応じた有効な個別パラメータのキーリストを定義して完全同期 (不要なメイン項目のリセットとGK項目の同期漏れを完全封殺！)
            base_detail_items = ["決定力", "キック力", "冷静さ", "ショートパス", "ロングパス", "キック精度", "突破力", "キープ力", "ボールタッチ", "ジャンプ", "コンタクト", "スタミナ", "走力", "敏捷性"]
            if st.session_state.is_gk:
                detail_items = base_detail_items + ["セービング", "反応速度", "1対1"]
            else:
                detail_items = base_detail_items + ["タックル", "パスカット", "マーク"]
                
            js_ind_offsets = resp_data.get("individual_offsets", {})
            js_ind_scales = resp_data.get("individual_scales", {})
            for item in detail_items:
                st.session_state.individual_offsets[item] = js_ind_offsets.get(item, [0, 0])
                st.session_state.individual_scales[item] = js_ind_scales.get(item, [1.0, 1.0])
                
        elif resp_type == "trigger_analysis":
            # 解析実行ボタンがHTML側でクリックされた事を検知
            # 同梱された「最後の最新アライメント座標」をPython側に一括完全同期し、非同期通信競合を100%封殺！
            st.session_state.is_gk = resp_data.get("isGk", False)
            st.session_state.active_items = resp_data.get("activeItems", [])
            st.session_state.global_scale_x = resp_data.get("global_scale_x", 1.0)
            st.session_state.global_scale_y = resp_data.get("global_scale_y", 1.0)
            st.session_state.global_offset_x = resp_data.get("global_offset", [0, 0])[0]
            st.session_state.global_offset_y = resp_data.get("global_offset", [0, 0])[1]
            
            js_grp_offsets = resp_data.get("group_offsets", {})
            js_grp_scales = resp_data.get("group_scales", {})
            for grp in GROUPS.keys():
                st.session_state.group_offsets[grp] = js_grp_offsets.get(grp, [0, 0])
                st.session_state.group_scales[grp] = js_grp_scales.get(grp, [1.0, 1.0])
                
            base_detail_items = ["決定力", "キック力", "冷静さ", "ショートパス", "ロングパス", "キック精度", "突破力", "キープ力", "ボールタッチ", "ジャンプ", "コンタクト", "スタミナ", "走力", "敏捷性"]
            if st.session_state.is_gk:
                detail_items = base_detail_items + ["セービング", "反応速度", "1対1"]
            else:
                detail_items = base_detail_items + ["タックル", "パスカット", "マーク"]
                
            js_ind_offsets = resp_data.get("individual_offsets", {})
            js_ind_scales = resp_data.get("individual_scales", {})
            for item in detail_items:
                st.session_state.individual_offsets[item] = js_ind_offsets.get(item, [0, 0])
                st.session_state.individual_scales[item] = js_ind_scales.get(item, [1.0, 1.0])

            # 二重実行ガードが解除されている場合のみ、実行フラグを立てる
            if not st.session_state.get("ocr_run_completed", False):
                trigger_ocr_run = True


    # --- OCR解析実行処理のハンドリング ---
    if trigger_ocr_run:
        log_status = st.status("OCR解析プロセスを実行中", expanded=True)
        
        with log_status:
            st.write("▶ [INFO] 同期された最新の調整座標に基づいて一括解析を開始します。")
            temp_results = []
            total_imgs = len(st.session_state.target_images)
            
            for idx, (img_name, img) in enumerate(st.session_state.target_images):
                step_prefix = f"[{idx + 1}/{total_imgs}]"
                st.write(f"**{step_prefix} 画像: {img_name} を解析中...**")
                
                try:
                    # トリミング・正規化済みのPIL画像を渡し、再トリミングによる座標ズレを完全に排除！(is_preprocessed=True)
                    result = st.session_state.ocr_engine.extract_all_parameters(
                        image_input=img,
                        active_items=st.session_state.active_items,
                        is_gk=st.session_state.is_gk,
                        group_scales=st.session_state.group_scales,
                        group_offsets=st.session_state.group_offsets,
                        individual_scales=st.session_state.individual_scales,
                        individual_offsets=st.session_state.individual_offsets,
                        global_scale_x=st.session_state.global_scale_x,
                        global_scale_y=st.session_state.global_scale_y,
                        global_offset=(st.session_state.global_offset_x, st.session_state.global_offset_y),
                        is_preprocessed=True  # すでに事前処理済みであることを通知
                    )
                    
                    result["元画像名"] = img_name
                    temp_results.append(result)
                    st.write(f"✅ {step_prefix} [SUCCESS] パラメータの復元に成功しました。")
                    
                except Exception as ex:
                    st.error(f"❌ {step_prefix} [ERROR] 解析中に予期せぬエラーが発生しました: {ex}")
                    import traceback
                    st.code(traceback.format_exc(), language="python")
            
            if temp_results:
                st.session_state.parsed_results.extend(temp_results)
                st.session_state.ocr_run_completed = True  # OCR解析が完了したためフラグをTrueに設定し、二重実行をガード
                log_status.update(label="すべての画像のOCR解析が完了しました。", state="complete", expanded=True)
                st.success("解析結果テーブルを更新しました。画面の下部を確認してください。")
st.markdown('</div>', unsafe_allow_html=True)

# 3. 解析結果のプレビューと編集
if st.session_state.parsed_results:
    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    st.subheader("解析結果の確認と編集")
    st.write("数値を手動で編集する場合は、表のセルをダブルクリックして値を直接編集してください。")
    
    df_results = pd.DataFrame(st.session_state.parsed_results)
    
    # ヘッダー並び順の最適化
    all_columns = df_results.columns.tolist()
    column_order = [
        "元画像名", "総合力",
        "SHO数値", "PAS数値", "DRB数値", "DEF数値", "PHY数値", "SPD数値",
        "決定力", "キック力", "冷静さ",
        "ショートパス", "ロングパス", "キック精度",
        "突破力", "キープ力", "ボールタッチ",
        "タックル", "パスカット", "マーク",
        "セービング", "反応速度", "1対1",
        "ジャンプ", "コンタクト", "スタミナ",
        "走力", "敏捷性"
    ]
    
    actual_order = [col for col in column_order if col in all_columns]
    actual_order += [col for col in all_columns if col not in actual_order]
    df_ordered = df_results[actual_order]
    
    # 編集可能なインタラクティブテーブル
    edited_df = st.data_editor(df_ordered, use_container_width=True, num_rows="dynamic")
    st.markdown('</div>', unsafe_allow_html=True)

    # 4. Apple Numbers風「超速コピペステーション」
    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    st.subheader("超速コピペステーション")
    st.write("スプレッドシートやExcelに貼り付けるためのTSV形式テキスト。右上のコピーアイコンを1タップするだけでクリップボードに格納されます。")
    
    col_horizontal, col_vertical = st.columns(2)
    clean_df = edited_df.fillna("")
    
    with col_horizontal:
        st.markdown("### スプレッドシート行追加用（横展開TSV）")
        st.write("横1行に項目ヘッダーと値が並びます。スプレッドシートの空き行にそのまま貼り付けることができます。")
        
        tsv_h_lines = []
        tsv_h_lines.append("\t".join(clean_df.columns))
        for _, row in clean_df.iterrows():
            tsv_h_lines.append("\t".join([str(val) for val in row]))
            
        tsv_horizontal_str = "\n".join(tsv_h_lines)
        st.code(tsv_horizontal_str, language="tsv")

    with col_vertical:
        st.markdown("### 縦型カルテ入力用（縦展開TSV）")
        st.write("「項目名 [Tab] 数値」の縦並び形式です。縦並びの管理表に一括で流し込めます。")
        
        tsv_v_lines = []
        for _, row in clean_df.iterrows():
            img_name = row.get("元画像名", "Image")
            tsv_v_lines.append(f"--- 【画像: {img_name}】 ---")
            for col in clean_df.columns:
                if col != "元画像名":
                    tsv_v_lines.append(f"{col}\t{row[col]}")
            tsv_v_lines.append("")
            
        tsv_vertical_str = "\n".join(tsv_v_lines)
        st.code(tsv_vertical_str, language="tsv")
    st.markdown('</div>', unsafe_allow_html=True)

    # 5. バックアップ保存・直接書き込み
    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    st.subheader("バックアップ保存と出力")
    
    col_sheet, col_excel, col_clear_res = st.columns([2, 1, 1])
    
    with col_sheet:
        st.markdown("**Googleスプレッドシートへエクスポート**")
        if st.button("Googleスプレッドシートの最終行に追記", use_container_width=True):
            if not credentials_json:
                st.error("Google APIの認証情報をロードしてください。")
            elif not spreadsheet_url:
                st.error("Googleスプレッドシートの共有URLを入力してください。")
            else:
                try:
                    with st.spinner("スプレッドシートとセキュア通信中..."):
                        client = SakatsukuGSheetClient(credentials_info=credentials_json)
                        records_to_write = edited_df.to_dict(orient="records")
                        
                        written_count = 0
                        for record in records_to_write:
                            cleaned_record = {k: v for k, v in record.items() if pd.notna(v) and v != ""}
                            cleaned_record.pop("元画像名", None)
                            
                            row_num = client.append_parameter_data(
                                spreadsheet_url=spreadsheet_url,
                                sheet_name=sheet_name,
                                param_dict=cleaned_record
                            )
                            written_count += 1
                        
                        st.success(f"スプレッドシートに {written_count}件のデータを追記しました。(最終行: {row_num})")
                except Exception as e_gs:
                    st.error(f"エラーが発生しました: {e_gs}")
                    
    with col_excel:
        st.markdown("**ローカル用ダウンロード**")
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            edited_df.to_excel(writer, index=False, sheet_name="サカつく2026_パラメータ")
        excel_data = excel_buffer.getvalue()
        
        st.download_button(
            label="Excel (.xlsx) でダウンロード",
            data=excel_data,
            file_name="sakatsuku_parameters.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with col_clear_res:
        st.markdown("**データテーブルのクリア**")
        if st.button("解析データを空にする", use_container_width=True):
            st.session_state.parsed_results = []
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
