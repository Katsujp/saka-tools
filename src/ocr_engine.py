# -*- coding: utf-8 -*-
"""サカつく2026 パラメータ画面画像解析・OCRモジュール。

OpenCVを使用した画像前処理（二値化、リサイズ、ROI切り出し）と、
EasyOCRを用いた高精度なテキスト抽出を行います。
"""

import re
import cv2
import numpy as np
import easyocr
import threading
from PIL import Image
from src.config import BASE_WIDTH, BASE_HEIGHT, BASIC_INFO_ROIS, MAIN_PARAM_ROIS, DETAIL_PARAM_ROIS, PARAM_LABELS, DEFAULT_ROIS, GROUPS, GK_ALIASES


class SakatsukuOCREngine:
    """サカつく2026のパラメータ画面を解析するOCRエンジンクラス。"""
    
    def __init__(self):
        """OCRエンジンおよび言語モデルの初期化を行います。"""
        # マルチスレッド環境下でのCUDA競合を防ぐためのロックオブジェクト
        self.lock = threading.Lock()
        # 英語・日本語の読み取りに対応したEasyOCRのリーダーを初期化 (GPUがあれば自動使用)
        # verbose=Falseを指定することで、初回ダウンロード時のコンソールでのUnicodeEncodeErrorを回避します
        self.reader = easyocr.Reader(['ja', 'en'], gpu=True, verbose=False)
        # 英語専用（数値およびアルファベット項目）のリーダーを初期化し、日本語モデルとの干渉（0の消失など）を100%防止！
        self.reader_en = easyocr.Reader(['en'], gpu=True, verbose=False)

    def scan_game_boundary(self, img):
        """画像外周の輝度・色差変化を縦横スキャンし、ゲーム画面の正確な4辺座標を1px単位で自動検出します。"""
        h_orig, w_orig = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. 上部タイトルバーの境界Y座標を特定 (0〜15%の範囲)
        scan_y_limit = int(h_orig * 0.15)
        y_diffs = []
        for y in range(2, scan_y_limit):
            diff = np.mean(cv2.absdiff(gray[y], gray[y-1]))
            y_diffs.append((y, diff))
        
        y_diffs.sort(key=lambda x: x[1], reverse=True)
        best_y = 31 # デフォルトのWindows 11タイトルバー厚み
        for y, diff in y_diffs[:5]:
            if 20 < y < 60:
                best_y = y
                break
                
        # 2. 左右および下部ウィンドウ枠の境界座標を特定
        scan_x_limit = int(w_orig * 0.10)
        # 左側スキャン
        left_diffs = []
        for x in range(2, scan_x_limit):
            diff = np.mean(cv2.absdiff(gray[:, x], gray[:, x-1]))
            left_diffs.append((x, diff))
        left_diffs.sort(key=lambda x: x[1], reverse=True)
        best_x_left = 8 # デフォルト
        for x, diff in left_diffs[:5]:
            if 2 < x < 40:
                best_x_left = x
                break
                
        # 右側スキャン
        right_diffs = []
        for x in range(w_orig - 2, w_orig - scan_x_limit, -1):
            diff = np.mean(cv2.absdiff(gray[:, x], gray[:, x+1]))
            right_diffs.append((x, diff))
        right_diffs.sort(key=lambda x: x[1], reverse=True)
        best_x_right = w_orig - 8
        for x, diff in right_diffs[:5]:
            if w_orig - 40 < x < w_orig - 2:
                best_x_right = x
                break

        # 下部スキャン
        bottom_diffs = []
        for y in range(h_orig - 2, h_orig - int(h_orig * 0.05), -1):
            diff = np.mean(cv2.absdiff(gray[y], gray[y+1]))
            bottom_diffs.append((y, diff))
        bottom_diffs.sort(key=lambda x: x[1], reverse=True)
        best_y_bottom = h_orig - 8
        for y, diff in bottom_diffs[:5]:
            if h_orig - 25 < y < h_orig - 2:
                best_y_bottom = y
                break

        # 3. アスペクト比フィッティングは行わず、検出された実際の表示領域そのものを切り出す
        # (引き伸ばし歪みがある場合、それを維持してリサイズした方が1920x1080時のアライメントが正確に一致します)
        crop_x = best_x_left
        crop_y = best_y
        crop_w = best_x_right - best_x_left
        crop_h = best_y_bottom - best_y
        
        if crop_w <= 0 or crop_h <= 0 or crop_w > w_orig or crop_h > h_orig:
            return img
            
        return img[crop_y:crop_y+crop_h, crop_x:crop_x+crop_w]

    def preprocess_image(self, image_np, is_preprocessed=False):
        """入力画像からウィンドウ外枠・タイトルバーを自動トリミングし、基準解像度 (1920x1080) に正規化します。

        Args:
            image_np (numpy.ndarray): OpenCV形式のBGR画像
            is_preprocessed (bool): すでにトリミング・正規化済みの画像であるか。Trueの場合は境界スキャンとリサイズをバイパスします

        Returns:
            numpy.ndarray: トリミングおよびリサイズされた画像
        """
        if is_preprocessed:
            # すでにトリミング・正規化済みの画像であるため、そのまま返す（余計な再検出や拡大による画質・座標ブレを完全に排除）
            return image_np
            
        # 1. 境界自動スキャナにより、ゲーム表示部を切り出す
        cropped_game = self.scan_game_boundary(image_np)
        
        # 2. 高品位な基準解像度へリサイズ
        normalized = cv2.resize(cropped_game, (BASE_WIDTH, BASE_HEIGHT), interpolation=cv2.INTER_CUBIC)
        return normalized

    def crop_roi(self, image_np, roi_coords):
        """指定された座標 (X_START, Y_START, WIDTH, HEIGHT) で画像を切り出します。"""
        x, y, w, h = roi_coords
        return image_np[y:y+h, x:x+w]

    def calculate_dynamic_roi(self, item_name, is_gk, group_scales, group_offsets, individual_scales, individual_offsets, global_scale_x, global_scale_y, global_offset):
        """デフォルト座標から、グローバル、グループ、個別の縦横独立スケールおよびX/Yオフセットを積算適用した動的座標(ROI)を算出します。"""
        # GK項目のエイリアス解決 (タックル/パスカット/マークの位置をセービング/反応速度/1対1にマッピング)
        default_key = item_name
        if is_gk:
            reverse_gk = {v: k for k, v in GK_ALIASES.items()}
            default_key = reverse_gk.get(item_name, item_name)
            
        if default_key not in DEFAULT_ROIS:
            return None
            
        def_x, def_y, def_w, def_h = DEFAULT_ROIS[default_key]
        
        # 1. 所属グループの特定
        grp_name = "overall"
        for g_k, items in GROUPS.items():
            resolved_items = []
            for it in items:
                if is_gk and it in GK_ALIASES:
                    resolved_items.append(GK_ALIASES[it])
                else:
                    resolved_items.append(it)
            if item_name in resolved_items:
                grp_name = g_k
                break
                
        # 2. 各レベルのスケール値の積算 (縦横独立)
        grp_scale = group_scales.get(grp_name, (1.0, 1.0))
        indiv_scale = individual_scales.get(item_name, (1.0, 1.0))
        
        total_scale_x = global_scale_x * grp_scale[0] * indiv_scale[0]
        total_scale_y = global_scale_y * grp_scale[1] * indiv_scale[1]
        
        # 3. 各レベルのオフセット値の取得
        grp_offset = group_offsets.get(grp_name, (0, 0))
        indiv_offset = individual_offsets.get(item_name, (0, 0))
        
        # 4. 最終座標の算出 (スケールはサイズW, Hにのみ適用され、位置X, Yには干渉しない。丸め処理はJS側のMath.roundと完全に一致するよう四捨五入round()に統一)
        final_x = round(def_x + global_offset[0] + grp_offset[0] + indiv_offset[0])
        final_y = round(def_y + global_offset[1] + grp_offset[1] + indiv_offset[1])
        final_w = round(def_w * total_scale_x)
        final_h = round(def_h * total_scale_y)
        
        # 画像サイズ(1920x1080)のバウンディング制限
        final_x = max(0, min(final_x, BASE_WIDTH - 1))
        final_y = max(0, min(final_y, BASE_HEIGHT - 1))
        final_w = max(1, min(final_w, BASE_WIDTH - final_x))
        final_h = max(1, min(final_h, BASE_HEIGHT - final_y))
        
        return (final_x, final_y, final_w, final_h)

    def generate_preview_image(self, image_np, active_items, is_gk, group_scales, group_offsets, individual_scales, individual_offsets, global_scale_x, global_scale_y, global_offset):
        """現在設定されている座標で、画像上に極細のApple Blueの枠線を描画したプレミアムなプレビュー画像を生成します。"""
        # 境界自動スキャナおよび基準解像度 (1920x1080) 正規化
        normalized_img = self.preprocess_image(image_np)
        preview_img = normalized_img.copy()
        
        # Apple Pro基準の上品な単一色調スキーム (BGR)
        color_active = (255, 113, 10)  # Apple SF Pro Blue (RGB: 10, 132, 255)
        color_text = (255, 255, 255)    # 純白の極小テキスト
        
        for item_name in active_items:
            roi = self.calculate_dynamic_roi(
                item_name, is_gk, 
                group_scales, group_offsets, 
                individual_scales, individual_offsets, 
                global_scale_x, global_scale_y, global_offset
            )
            if not roi:
                continue
                
            x, y, w, h = roi
            
            # 洗練された極細 (1px) の矩形枠の描画 (ノイズのないシャープなデザイン)
            cv2.rectangle(preview_img, (x, y), (x + w, y + h), color_active, 1)
            
            # クールな略称英語ラベルの超省スペース表示
            short_labels = {
                "総合力": "OVR", "SHO数値": "SHO", "PAS数値": "PAS", "DRB数値": "DRB", "DEF数値": "DEF", "PHY数値": "PHY", "SPD数値": "SPD",
                "決定力": "Fin", "キック力": "Pow", "冷静さ": "Cmp",
                "ショートパス": "Pas-S", "ロングパス": "Pas-L", "キック精度": "Acc",
                "突破力": "Pen", "キープ力": "Kee", "ボールタッチ": "Tch",
                "タックル": "Tcl", "パスカット": "Int", "マーク": "Mrk",
                "セービング": "Sav", "反応速度": "Rct", "1対1": "1v1",
                "ジャンプ": "Jmp", "コンタクト": "Cnt", "スタミナ": "Sta",
                "走力": "Run", "敏捷性": "Agi"
            }
            lbl = short_labels.get(item_name, item_name[:3])
            
            # 極小でシャープなラベルプレート (Apple UI)
            text_size = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.32, 1)[0]
            # プレート背景をAppleのSystem Settings設定色である深色グレー (#1c1c1e) に統一
            cv2.rectangle(preview_img, (x, y - text_size[1] - 4), (x + text_size[0] + 4, y), (30, 30, 28), -1)
            cv2.putText(preview_img, lbl, (x + 2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.32, color_text, 1, cv2.LINE_AA)
            
        # Streamlit用のRGB画像に変換してリターン
        return cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)



    def detect_rank_plus(self, crop_img):
        """ランク画像内の特定領域のピクセル輝度を解析し、プラス記号(+)の有無を100%確実に検出します。
        
        Args:
            crop_img (numpy.ndarray): クロップされたランクBGR画像 (サイズ: 150x70)
            
        Returns:
            bool: プラス記号(+)が存在する場合はTrue、それ以外はFalse
        """
        try:
            gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
            # D+などの「+」が存在する領域を切り出す (クロップ画像は150x70)
            # X: 82px〜135px, Y: 17px〜52px
            plus_roi = gray[17:52, 82:135]
            _, thresh = cv2.threshold(plus_roi, 160, 255, cv2.THRESH_BINARY)
            white_pixels = np.sum(thresh == 255)
            ratio = (white_pixels / plus_roi.size) * 100
            return ratio >= 2.0  # 2.0%以上の白ピクセル割合で「+」ありと判定
        except Exception:
            return False

    def apply_ocr_preprocess(self, crop_img, is_numeric=True, is_detail=False, thresh_val=None):
        """OCR認識率を最大化するため、絶対閾値二値化による前処理を行います。

        Args:
            crop_img (numpy.ndarray): クロップされたBGR画像
            is_numeric (bool): 数字専用の処理を行うか
            is_detail (bool): 個別詳細パラメータ用の処理を行うか
            thresh_val (int, optional): 明示的な二値化閾値。省略時はデフォルト値を使用

        Returns:
            numpy.ndarray: 前処理後の二値化画像 (白背景に黒文字)
        """
        # 1. グレースケール化
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        
        # 2. ランチョス補間で3.5倍に超拡大 (エッジを鮮明に保ち、余計なモヤモヤノイズを排除してEasyOCRの文字識別率を最大化)
        expanded = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_LANCZOS4)
        
        # 3. ガウシアンブラーによるノイズ平滑化
        blurred = cv2.GaussianBlur(expanded, (3, 3), 0)
        
        if is_numeric:
            # 数字領域は絶対二値化を適用。
            if thresh_val is None:
                # 個別能力値はフォントが細く掠れやすいため閾値を 130 に下げ、総合力やメイン数値は 155 で完璧に分離！
                thresh_val = 130 if is_detail else 155
            _, binary = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)
        else:
            # テキスト領域は全体コントラストに応じて自動で大津の二値化
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
        # 4. 反転して「白背景に黒文字」に強制統一 (EasyOCRが最も得意とする形式)
        binary_inv = cv2.bitwise_not(binary)
        return binary_inv

    def parse_numeric_text(self, text):
        """読み取ったテキストから数値のみを抽出し、整数として返します。"""
        # 不要な文字（カンマ、ドット、スペース、記号等）を排除
        cleaned = re.sub(r'[^0-9]', '', text)
        if cleaned:
            return int(cleaned)
        return None

    def clean_rank_text(self, text):
        """ランク文字（S, A, B, C, D, E, F, +）を正規化します。"""
        # OCRで誤認識しやすいケースを修正
        text = text.upper().strip()
        text = re.sub(r'[^SABCDEF\+]', '', text)
        
        # 誤読補正の辞書定義
        corrections = {
            '0': 'D', '0+': 'D+', 'C+': 'C+', 'F+': 'F+', 'E+': 'E+'
        }
        return corrections.get(text, text)

    def extract_all_parameters(self, image_input, active_items=None, is_gk=False, 
                              group_scales=None, group_offsets=None, 
                              individual_scales=None, individual_offsets=None, 
                              global_scale_x=1.0, global_scale_y=1.0, global_offset=(0, 0),
                              is_preprocessed=False):
        """動的な座標調整値および有効項目マスクを適用し、画像からパラメータ値のみを高精度抽出します。"""
        # マルチスレッド環境におけるCUDAリソース競合・メモリ破損を100%防止するための排他制御（スレッドロック）
        with self.lock:
            # 引数のデフォルト処理
            if active_items is None:
                active_items = list(DEFAULT_ROIS.keys())
                if is_gk:
                    active_items = [GK_ALIASES.get(x, x) for x in active_items]
                    
            if group_scales is None:
                group_scales = {}
            if group_offsets is None:
                group_offsets = {}
            if individual_scales is None:
                individual_scales = {}
            if individual_offsets is None:
                individual_offsets = {}

            # 画像の読み込みと変換
            if isinstance(image_input, str):
                image_np = cv2.imread(image_input)
            elif isinstance(image_input, Image.Image):
                image_np = cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
            else:
                image_np = image_input.copy()

            # ウィンドウ枠などを自動トリミングし、1920x1080に正規化した画像を取得（二重トリミングを回避）
            normalized_img = self.preprocess_image(image_np, is_preprocessed)
            
            result_data = {}

            # 検出されたすべてのテキスト要素から、正当な3桁または4桁の数値（100〜9999）を安全に狙い撃ちで抽出するアルゴリズム
            def find_valid_numeric_result(ocr_results_list):
                for res_text in ocr_results_list:
                    val = self.parse_numeric_text(res_text)
                    if val is not None and 100 <= val <= 9999:
                        return val
                return None

            # 有効な各項目について動的ROIを算出し、OCR処理を実行
            for item_name in active_items:
                roi = self.calculate_dynamic_roi(
                    item_name, is_gk, 
                    group_scales, group_offsets, 
                    individual_scales, individual_offsets, 
                    global_scale_x, global_scale_y, global_offset
                )
                if not roi:
                    result_data[item_name] = None
                    continue
                    
                crop = self.crop_roi(normalized_img, roi)
                
                is_overall = (item_name == "総合力")
                is_category = (item_name in ["SHO数値", "PAS数値", "DRB数値", "DEF数値", "PHY数値", "SPD数値"])
                
                if is_overall:
                    # 総合力: 二値化なし生グレースケール3.5倍ランチョス拡大 + 英語モデル (ボケ排除)
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    prep_img = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_LANCZOS4)
                    ocr_results = self.reader_en.readtext(prep_img, detail=0, allowlist='0123456789')
                    result_data[item_name] = find_valid_numeric_result(ocr_results)
                    
                elif is_category:
                    # カテゴリー数値: 閾値155二値化 + 英語モデル (LANCZOS拡大適用)
                    prep_img = self.apply_ocr_preprocess(crop, is_numeric=True)
                    ocr_results = self.reader_en.readtext(prep_img, detail=0, allowlist='0123456789')
                    result_data[item_name] = find_valid_numeric_result(ocr_results)
                    
                else:
                    # 個別詳細能力値: 二値化なし生グレースケール3.5倍ランチョス超拡大のみ + 英語モデル (モヤボケ偽エッジを排除)
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    prep_img = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_LANCZOS4)
                    ocr_results = self.reader_en.readtext(prep_img, detail=0, allowlist='0123456789')
                    result_data[item_name] = find_valid_numeric_result(ocr_results)

            # 全項目の中で、OFF（指定なし）の項目については明示的に None を設定して結果に含める
            # (スプレッドシートやコピー用テキストの列数を一定に維持するため)
            all_possible_items = list(DEFAULT_ROIS.keys())
            if is_gk:
                all_possible_items = [GK_ALIASES.get(x, x) for x in all_possible_items]
            
        final_result = {}
        for item in all_possible_items:
            final_result[item] = result_data.get(item, None)

        return final_result

    def get_cropped_images_dict(self, image_np, active_items, is_gk, 
                               group_scales, group_offsets, 
                               individual_scales, individual_offsets, 
                               global_scale_x, global_scale_y, global_offset):
        """デバッグおよびプレビュー表示用に、現在有効な全パラメータの動的クロップ画像(PILオブジェクト)を返します。"""
        normalized_img = self.preprocess_image(image_np)
        cropped_dict = {}

        for item_name in active_items:
            roi = self.calculate_dynamic_roi(
                item_name, is_gk, 
                group_scales, group_offsets, 
                individual_scales, individual_offsets, 
                global_scale_x, global_scale_y, global_offset
            )
            if not roi:
                continue
            crop = self.crop_roi(normalized_img, roi)
            # OpenCV BGRからRGBに変換しPIL Imageにする
            cropped_dict[item_name] = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))

        return cropped_dict


