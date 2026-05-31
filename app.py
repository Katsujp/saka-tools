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
    
    /* Streamlit再実行時の画面グレーアウトとチラつきを完全に無効化 */
    [data-testid="stAppViewContainer"] [data-testid="stBlock"],
    div.element-container,
    iframe {
        opacity: 1 !important;
        transition: none !important;
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

# 個別オフセット・スケールの初期化 (GK追加項目も含めた全パラメータを完全網羅)
if "individual_offsets" not in st.session_state:
    all_rois = list(DEFAULT_ROIS.keys()) + ["セービング", "反応速度", "1対1"]
    st.session_state.individual_offsets = {item: [0, 0] for item in all_rois}
if "individual_scales" not in st.session_state:
    all_rois = list(DEFAULT_ROIS.keys()) + ["セービング", "反応速度", "1対1"]
    st.session_state.individual_scales = {item: [1.0, 1.0] for item in all_rois}

# リアルタイム同期ログ用セッション初期化
if "sync_logs" not in st.session_state:
    st.session_state.sync_logs = ["システム初期化完了。同期ログの監視を開始します。"]
if "show_debug_log" not in st.session_state:
    st.session_state.show_debug_log = False
if "last_processed_msg_id" not in st.session_state:
    st.session_state.last_processed_msg_id = None
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = "restore_uploader_0"
if "tsv_horizontal" not in st.session_state:
    st.session_state.tsv_horizontal = ""
if "tsv_vertical" not in st.session_state:
    st.session_state.tsv_vertical = ""



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

# --- メインエリア：アプリケーション本体 ---
st.markdown('<div class="main-title">サカつく2026 パラメータOCRリーダー v0.1</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">選手のパラメータタブの中身を読み取るツール</div>', unsafe_allow_html=True)

# 1. 画像のインプットエリア
st.markdown('<div class="apple-card">', unsafe_allow_html=True)
st.subheader("画像ソースのロード")

tab_paste, tab_upload = st.tabs(["クリップボードからペースト", "画像ファイルアップロード"])

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
    
    # アライメント位置情報のローカル保存・復元機能
    st.markdown("<p style='font-size: 13px; font-weight: 600; color: #8e8e93; margin-top: 15px; margin-bottom: 5px;'>アライメント矩形位置情報（ROI）のバックアップ</p>", unsafe_allow_html=True)
    col_save, col_restore = st.columns(2)
    
    with col_save:
        st.write("現在の設定をローカルPCに保存します。")
        # JSONデータを動的作成
        backup_data = {
            "global_scale_x": st.session_state.global_scale_x,
            "global_scale_y": st.session_state.global_scale_y,
            "global_offset_x": st.session_state.global_offset_x,
            "global_offset_y": st.session_state.global_offset_y,
            "group_offsets": st.session_state.group_offsets,
            "group_scales": st.session_state.group_scales,
            "individual_offsets": st.session_state.individual_offsets,
            "individual_scales": st.session_state.individual_scales,
            "is_gk": st.session_state.is_gk,
            "active_items": st.session_state.active_items
        }
        json_string = json.dumps(backup_data, ensure_ascii=False, indent=2)
        st.download_button(
            label="ローカルに保存 (JSON)",
            data=json_string,
            file_name="sakatsuku_alignment.json",
            mime="application/json",
            use_container_width=True
        )
        
    with col_restore:
        st.write("PCから設定ファイルを読み込みます。")
        uploaded_config = st.file_uploader("ローカルから復元", type=["json"], label_visibility="collapsed", key=st.session_state.uploader_key)
        if uploaded_config is not None:
            try:
                config_data = json.load(uploaded_config)
                st.session_state.global_scale_x = config_data.get("global_scale_x", 1.0)
                st.session_state.global_scale_y = config_data.get("global_scale_y", 1.0)
                st.session_state.global_offset_x = config_data.get("global_offset_x", 0)
                st.session_state.global_offset_y = config_data.get("global_offset_y", 0)
                
                # 安全なマッピング取得と補完 (キーの欠落によるバグをフォールバック付きで完全防止)
                all_rois = list(DEFAULT_ROIS.keys()) + ["セービング", "反応速度", "1対1"]
                uploaded_ind_offsets = config_data.get("individual_offsets", {})
                uploaded_ind_scales = config_data.get("individual_scales", {})
                st.session_state.individual_offsets = {
                    item: uploaded_ind_offsets.get(item, [0, 0]) for item in all_rois
                }
                st.session_state.individual_scales = {
                    item: uploaded_ind_scales.get(item, [1.0, 1.0]) for item in all_rois
                }
                
                uploaded_grp_offsets = config_data.get("group_offsets", {})
                uploaded_grp_scales = config_data.get("group_scales", {})
                st.session_state.group_offsets = {
                    grp: uploaded_grp_offsets.get(grp, [0, 0]) for grp in GROUPS.keys()
                }
                st.session_state.group_scales = {
                    grp: uploaded_grp_scales.get(grp, [1.0, 1.0]) for grp in GROUPS.keys()
                }
                
                st.session_state.is_gk = config_data.get("is_gk", False)
                st.session_state.active_items = config_data.get("active_items", [])
                
                # すべての個別パラメータと大項目を完全に網羅して同期 (同期漏れバグを構造的に100%封殺！)
                all_rois = list(DEFAULT_ROIS.keys()) + ["セービング", "反応速度", "1対1"]
                js_ind_offsets = config_data.get("individual_offsets", {})
                js_ind_scales = config_data.get("individual_scales", {})
                for item in all_rois:
                    if item in js_ind_offsets:
                        st.session_state.individual_offsets[item] = js_ind_offsets[item]
                    if item in js_ind_scales:
                        st.session_state.individual_scales[item] = js_ind_scales[item]
                
                # 復元時に ocr_run_completed も False に初期化し、重複排除用のIDもクリアする
                st.session_state.ocr_run_completed = False
                if "last_processed_msg_id" in st.session_state:
                    st.session_state.last_processed_msg_id = None
                
                # キーを動的に変更することで、file_uploader を強制的に空（クリア）にリセットして無限 rerun を根絶！
                st.session_state.uploader_key = f"restore_uploader_{int(time.time())}"
                st.success("アライメント設定をローカルファイルから復元しました！")
                time.sleep(1)
                st.rerun()
            except Exception as e_cfg:
                st.error(f"ファイル解析エラー: {e_cfg}")
                
    # リアルタイム同期ログ表示トグルとログビューアーUI (ON/OFF可能)
    st.markdown("<p style='font-size: 13px; font-weight: 600; color: #8e8e93; margin-top: 15px; margin-bottom: 5px;'>デバッグ & 通信確認</p>", unsafe_allow_html=True)
    st.session_state.show_debug_log = st.checkbox("リアルタイム同期ログを表示", value=st.session_state.show_debug_log)
    if st.session_state.show_debug_log:
        log_text = "\n".join(st.session_state.sync_logs[-10:]) # 直近10件のみ表示
        st.code(log_text, language="text")

    # 解析実行フラグ
    trigger_ocr_run = False
    
    # JSコンポーネント側からの双方向データ送信の受け取り・状態同期
    if hud_response is not None:
        msg_id = hud_response.get("msg_id")
        resp_type = hud_response.get("type")
        resp_data = hud_response.get("data", {})
        
        # 重複排除ガード: すでに処理済みのメッセージIDであれば処理をスキップ
        if msg_id and st.session_state.get("last_processed_msg_id") == msg_id:
            pass
        else:
            if msg_id:
                st.session_state.last_processed_msg_id = msg_id
                
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
                    
                # すべての個別パラメータと大項目を完全に網羅して同期 (同期漏れバグを構造的に100%封殺！)
                all_rois = list(DEFAULT_ROIS.keys()) + ["セービング", "反応速度", "1対1"]
                js_ind_offsets = resp_data.get("individual_offsets", {})
                js_ind_scales = resp_data.get("individual_scales", {})
                for item in all_rois:
                    if item in js_ind_offsets:
                        st.session_state.individual_offsets[item] = js_ind_offsets[item]
                    if item in js_ind_scales:
                        st.session_state.individual_scales[item] = js_ind_scales[item]
                
                # デバッグログの追記 (JSからの動作確認の証跡として機能！)
                js_log = resp_data.get("debug_log")
                if js_log:
                    import datetime
                    now_str = datetime.datetime.now().strftime("%H:%M:%S")
                    st.session_state.sync_logs.append(f"[{now_str}] {js_log}")
                    st.session_state.sync_logs.append(f"[{now_str}] PY: st.session_state updated successfully.")
                    if len(st.session_state.sync_logs) > 30:
                        st.session_state.sync_logs = st.session_state.sync_logs[-30:]
                    
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
                    
                # すべての個別パラメータと大項目を完全に網羅して同期 (同期漏れバグを構造的に100%封殺！)
                all_rois = list(DEFAULT_ROIS.keys()) + ["セービング", "反応速度", "1対1"]
                js_ind_offsets = resp_data.get("individual_offsets", {})
                js_ind_scales = resp_data.get("individual_scales", {})
                for item in all_rois:
                    if item in js_ind_offsets:
                        st.session_state.individual_offsets[item] = js_ind_offsets[item]
                    if item in js_ind_scales:
                        st.session_state.individual_scales[item] = js_ind_scales[item]
                
                # デバッグログの追記 (JSからの動作確認の証跡として機能！)
                js_log = resp_data.get("debug_log")
                if js_log:
                    import datetime
                    now_str = datetime.datetime.now().strftime("%H:%M:%S")
                    st.session_state.sync_logs.append(f"[{now_str}] {js_log}")
                    st.session_state.sync_logs.append(f"[{now_str}] PY: st.session_state (trigger_analysis) updated successfully.")
                    if len(st.session_state.sync_logs) > 30:
                        st.session_state.sync_logs = st.session_state.sync_logs[-30:]
    
                # 新しい明示的な解析ボタン押下イベント（新しい msg_id）なので、二重実行ガードを無視して無条件に実行
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
    
    # 編集前に左端に選択用のチェックボックスカラムを追加
    df_ordered.insert(0, "選択", True)
    
    # 編集可能なインタラクティブテーブル
    edited_df = st.data_editor(df_ordered, use_container_width=True, num_rows="dynamic")
    
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

    # 項目名出力トグルチェックボックス (デフォルトOFF)
    show_headers = st.checkbox("項目名を出力する", value=False)
    
    # コピペステーション展開処理の実行
    if btn_export:
        # 選択された（チェックONの）行のみを抽出 (現在の並び替え順を維持)
        selected_df = edited_df[edited_df["選択"] == True].copy()
        
        # 選択列を除外して通常のデータに
        if "選択" in selected_df.columns:
            selected_df = selected_df.drop(columns=["選択"])
            
        selected_df = selected_df.fillna("")
        
        # 出力対象カラムの選定 (読み取り有効かつ少なくとも1行以上で有効な値が存在する項目のみ)
        output_cols = ["元画像名"]
        for col in selected_df.columns:
            if col == "元画像名":
                continue
            is_active = col in st.session_state.active_items
            has_value = False
            for _, row in selected_df.iterrows():
                if str(row[col]).strip() != "":
                    has_value = True
                    break
            if is_active and has_value:
                output_cols.append(col)
                
        # 横展開TSVの構築
        tsv_h_lines = []
        if show_headers:
            # 項目名（ヘッダー）を出力し、先頭に元画像名も含める
            tsv_h_lines.append("\t".join(output_cols))
            for _, row in selected_df.iterrows():
                tsv_h_lines.append("\t".join([str(row[col]) for col in output_cols]))
        else:
            # 項目名なし、かつ先頭の元画像名自体も完全に非表示
            # output_colsから「元画像名」を除外したリストで出力
            data_cols = [col for col in output_cols if col != "元画像名"]
            for _, row in selected_df.iterrows():
                tsv_h_lines.append("\t".join([str(row[col]) for col in data_cols]))
                
        st.session_state.tsv_horizontal = "\n".join(tsv_h_lines)
        
        # 縦展開TSVの構築
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
                            # 項目名付き
                            tsv_v_lines.append(f"{col}\t{row[col]}")
                        else:
                            # 項目名なし、値のみ
                            tsv_v_lines.append(f"{row[col]}")
            
            # 画像間の区切り改行
            if show_headers:
                tsv_v_lines.append("")
            elif tsv_v_lines and tsv_v_lines[-1] != "":
                tsv_v_lines.append("")
            
        st.session_state.tsv_vertical = "\n".join(tsv_v_lines)
        st.success("コピペステーションに選択データを展開しました！")
        st.rerun()
        
    st.markdown('</div>', unsafe_allow_html=True)

    # 4. Apple Numbers風「超速コピペステーション」
    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    st.subheader("超速コピペステーション")
    st.write("「コピペステーションに展開する」ボタンを押すと、チェックを入れた選択行のみが現在の並び順通りに出力されます。")
    
    col_horizontal, col_vertical = st.columns(2)
    
    with col_horizontal:
        st.markdown("### スプレッドシート行追加用（横展開TSV）")
        st.write("横1行に値が並びます。スプレッドシートの空き行にそのまま貼り付けることができます。")
        if st.session_state.tsv_horizontal:
            st.code(st.session_state.tsv_horizontal, language="tsv")
        else:
            st.info("データが展開されていません。上のボタンを押してください。")

    with col_vertical:
        st.markdown("### 縦型カルテ入力用（縦展開TSV）")
        st.write("「数値」または「項目名 [Tab] 数値」の縦並び形式です。縦並びの管理表に一括で流し込めます。")
        if st.session_state.tsv_vertical:
            st.code(st.session_state.tsv_vertical, language="tsv")
        else:
            st.info("データが展開されていません。上のボタンを押してください。")
    st.markdown('</div>', unsafe_allow_html=True)


