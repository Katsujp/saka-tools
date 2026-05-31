# -*- coding: utf-8 -*-
"""サカつく2026 パラメータ自動読み取りツール Streamlit アプリケーション。

画像のアップロード、クリップボードペースト、高精度OCR解析、データの編集・確認、
Googleスプレッドシートへの直接書き込み、およびローカルExcel/CSVダウンロード機能を提供します。
"""

import json
import os
import io
import pandas as pd
import streamlit as st
import numpy as np
from PIL import Image, ImageGrab
import cv2

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

# 画像オブジェクトの読み込み先
target_images = []

with tab_upload:
    uploaded_files = st.file_uploader(
        "パラメータ画面のスクリーンショット画像を選択（複数対応）",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True
    )
    if uploaded_files:
        for file in uploaded_files:
            img = Image.open(file)
            target_images.append((file.name, img))

with tab_paste:
    st.write("1. ゲーム中の選手パラメータ画面で `Win + Shift + S` などを使って画面をキャプチャ（クリップボードにコピー）します。")
    st.write("2. 下記のボタンをクリックすると、クリップボードに保存されている最新の画像が自動的に読み込まれます。")
    
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        if st.button("📋 クリップボードから画像を読み込む"):
            try:
                # Pillowを用いたローカルクリップボード画像取得
                pasted_img = ImageGrab.grabclipboard()
                if isinstance(pasted_img, Image.Image):
                    target_images.append(("Clipboard_Image", pasted_img))
                    st.success("クリップボードから画像を正常に取得しました！")
                else:
                    st.error("クリップボードに画像が見つかりませんでした。画像をキャプチャしてから再度お試しください。")
            except Exception as e:
                st.error(f"クリップボード取得エラー: {e}\n（ローカルホスト環境でのみ動作します）")

# --- 画像の解析実行 ---
if target_images:
    st.write("---")
    st.subheader(f"🔍 読み込み画像 ({len(target_images)}枚) の解析")
    
    # 解析実行ボタン
    if st.button("🚀 画像のOCR解析を開始"):
        with st.spinner("画像の画像前処理およびOCR解析を実行中..."):
            temp_results = []
            
            for img_name, img in target_images:
                # OCRエンジンで解析
                try:
                    result = st.session_state.ocr_engine.extract_all_parameters(img)
                    result["元画像名"] = img_name
                    temp_results.append(result)
                except Exception as ex:
                    st.error(f"ファイル {img_name} の解析中にエラーが発生しました: {ex}")
            
            if temp_results:
                # 解析結果をセッションに追加
                st.session_state.parsed_results.extend(temp_results)
                st.success(f"{len(temp_results)}件の選手パラメータの解析が完了しました！")

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
        if target_images:
            selected_img_name = st.selectbox("画像を選択", [name for name, _ in target_images])
            selected_img = [img for name, img in target_images if name == selected_img_name][0]
            
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
            st.rerun()
