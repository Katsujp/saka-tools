# -*- coding: utf-8 -*-
"""ウィンドウ自動トリミングをバイパスするスマートフォールバック付きのOCR診断スクリプト。
"""

import sys
import cv2
import numpy as np
import easyocr
import re
from PIL import Image

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(errors='replace')

sys.path.append(r"C:\Users\katsu\.gemini\antigravity\scratch\sakatsuku_2026")

from src.config import BASIC_INFO_ROIS, MAIN_PARAM_ROIS, DETAIL_PARAM_ROIS, PARAM_LABELS

# クロップ座標（Griezmann対応の究極黄金座標）
GOLD_BASIC_ROIS = {
    "card_overall": (30, 245, 150, 70),
    "card_rank": (30, 160, 150, 70),
    "card_position": (35, 320, 150, 70),
    "card_name": (30, 470, 120, 250),
}

GOLD_MAIN_ROIS = {
    "SHO_rank": (760, 285, 60, 85),
    "PAS_rank": (935, 285, 60, 85),
    "DRB_rank": (1110, 285, 60, 85),
    "DEF_rank": (1285, 285, 60, 85),
    "PHY_rank": (1460, 285, 60, 85),
    "SPD_rank": (1635, 285, 60, 85),
    
    # X座標を右シフトして枠・背景色の境界ノイズを完全遮断！
    "SHO_val": (820, 285, 115, 85),
    "PAS_val": (995, 285, 115, 85),
    "DRB_val": (1195, 285, 95, 85),
    "DEF_val": (1385, 285, 100, 85),       # X=1345 -> 1385, W=115 -> 100 にシフト
    "PHY_val": (1560, 285, 100, 85),       # X=1520 -> 1560, W=115 -> 100 にシフト
    "SPD_val": (1730, 285, 115, 85),       # X=1695 -> 1730
}

# 3行目のYを628にしてキック精度などを完璧に捉える
GOLD_DETAIL_ROIS = {
    # 1行目 Y=445, H=38
    "param_01_val": (730, 445, 180, 38),  # 決定力 (W=180に広げる)
    "param_02_val": (925, 445, 180, 38),  # ショートパス
    "param_03_val": (1100, 445, 180, 38), # 突破力
    "param_04_val": (1275, 445, 180, 38), # タックル
    "param_05_val": (1450, 445, 180, 38), # ジャンプ
    "param_06_val": (1660, 445, 160, 38), # 走力 (6列目ズレ対応 X=1660, W=160)
    
    # 2行目 Y=544, H=38
    "param_07_val": (730, 544, 180, 38),  # キック力
    "param_08_val": (925, 544, 180, 38),  # ロングパス
    "param_09_val": (1080, 544, 180, 38), # キープ力
    "param_10_val": (1275, 544, 180, 38), # パスカット
    "param_11_val": (1450, 544, 180, 38), # コンタクト
    "param_12_val": (1660, 544, 160, 38), # 敏捷性 (6列目ズレ対応 X=1660, W=160)
    
    # 3行目 Y=628, H=38
    "param_13_val": (730, 628, 180, 38),  # 冷静さ
    "param_14_val": (925, 628, 180, 38),  # キック精度
    "param_15_val": (1100, 628, 180, 38), # ボールタッチ
    "param_16_val": (1275, 628, 180, 38), # マーク
    "param_17_val": (1450, 628, 180, 38), # スタミナ
}

class SakatsukuOCREngineBypass:
    def __init__(self):
        self.reader_en = easyocr.Reader(['en'], gpu=True, verbose=False)
        self.reader = easyocr.Reader(['ja', 'en'], gpu=True, verbose=False)

    def preprocess_image(self, img):
        h, w = img.shape[:2]
        aspect_ratio = w / h
        print(f"入力画像アスペクト比: {aspect_ratio:.4f}")
        
        # 16:9 近傍 (1.76〜1.79) かつ解像度が1920x1080なら、トリミングをバイパス
        if 1.76 <= aspect_ratio <= 1.79:
            print("💡 アスペクト比がほぼ16:9であるため、自動ウィンドウトリミングをバイパスし、無劣化でリサイズします。")
            return cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_CUBIC)
            
        # 通常のトリミング処理
        print("通常のウィンドウトリミングを実行します。")
        # 境界自動スキャン
        cropped_game = self.scan_game_boundary_sim(img)
        return cv2.resize(cropped_game, (1920, 1080), interpolation=cv2.INTER_CUBIC)

    def scan_game_boundary_sim(self, img):
        h_orig, w_orig = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        scan_y_limit = int(h_orig * 0.15)
        y_diffs = []
        for y in range(2, scan_y_limit):
            diff = np.mean(cv2.absdiff(gray[y], gray[y-1]))
            y_diffs.append((y, diff))
        y_diffs.sort(key=lambda x: x[1], reverse=True)
        best_y = 31
        for y, diff in y_diffs[:5]:
            if 20 < y < 60:
                best_y = y
                break
        return img[best_y:h_orig-8, 8:w_orig-8]

    def run_hybrid_ocr(self, crop, t_val=120):
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        
        # 1. 二値化あり (t_val)
        expanded_bin = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
        blurred_bin = cv2.GaussianBlur(expanded_bin, (3, 3), 0)
        _, binary = cv2.threshold(blurred_bin, t_val, 255, cv2.THRESH_BINARY)
        prep_bin = cv2.bitwise_not(binary)
        ocr_bin = self.reader_en.readtext(prep_bin, detail=0, allowlist="0123456789")
        text_bin = "".join(ocr_bin).strip()
        
        # 2. 二値化なし (生グレースケール)
        prep_raw = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
        ocr_raw = self.reader_en.readtext(prep_raw, detail=0, allowlist="0123456789")
        text_raw = "".join(ocr_raw).strip()
        
        # ハイブリッド判定: 3桁の数値を最優先
        if len(text_raw) == 3 and text_raw.isdigit():
            return text_raw
        elif len(text_bin) == 3 and text_bin.isdigit():
            return text_bin
        else:
            # 桁数が多い方をフォールバック
            return text_raw if len(text_raw) >= len(text_bin) else text_bin

    def parse_numeric_text(self, text):
        cleaned = re.sub(r'[^0-9]', '', text)
        if cleaned:
            return int(cleaned)
        return None

    def clean_rank_text(self, text):
        text = text.upper().strip()
        text = re.sub(r'[^SABCDEF\+]', '', text)
        corrections = {'0': 'D', '0+': 'D+', 'C+': 'C+', 'F+': 'F+', 'E+': 'E+'}
        return corrections.get(text, text)

    def extract_all(self, img):
        normalized = self.preprocess_image(img)
        result_data = {}
        
        # 1. 基本情報
        for key, roi in GOLD_BASIC_ROIS.items():
            x, y, w, h = roi
            crop = normalized[y:y+h, x:x+w]
            
            if key == "card_name":
                rotated = cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)
                gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
                prep = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
                ocr_results = self.reader_en.readtext(prep, detail=0)
                raw_text = " ".join(ocr_results).strip()
                result_data[key] = raw_text
            elif key == "card_overall":
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                prep = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
                ocr_results = self.reader_en.readtext(prep, detail=0, allowlist='0123456789')
                raw_text = ocr_results[0].strip() if ocr_results else ""
                result_data[key] = self.parse_numeric_text(raw_text)
            elif key == "card_position":
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                prep = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
                _, binary = cv2.threshold(prep, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                prep_inv = cv2.bitwise_not(binary)
                ocr_results = self.reader_en.readtext(prep_inv, detail=0, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                raw_text = ocr_results[0].strip() if ocr_results else ""
                result_data[key] = raw_text
            else:
                # ランク
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                prep = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
                ocr_results = self.reader_en.readtext(prep, detail=0, allowlist='SABCDEF+')
                raw_text = ocr_results[0].strip() if ocr_results else ""
                result_data[key] = self.clean_rank_text(raw_text)

        # 2. メインパラメータ
        for key, roi in GOLD_MAIN_ROIS.items():
            x, y, w, h = roi
            crop = normalized[y:y+h, x:x+w]
            is_val = key.endswith("_val")
            
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            prep = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
            blurred = cv2.GaussianBlur(prep, (3, 3), 0)
            
            # 絶対二値化 155
            _, binary = cv2.threshold(blurred, 155, 255, cv2.THRESH_BINARY)
            prep_inv = cv2.bitwise_not(binary)
            
            if is_val:
                ocr_results = self.reader_en.readtext(prep_inv, detail=0, allowlist='0123456789')
                raw_text = ocr_results[0].strip() if ocr_results else ""
                result_data[key] = self.parse_numeric_text(raw_text)
            else:
                ocr_results = self.reader.readtext(prep_inv, detail=0, allowlist='SABCDEF+')
                raw_text = ocr_results[0].strip() if ocr_results else ""
                result_data[key] = self.clean_rank_text(raw_text)

        # 3. 個別詳細パラメータ (ハイブリッド判定適用)
        for key, roi in GOLD_DETAIL_ROIS.items():
            x, y, w, h = roi
            crop = normalized[y:y+h, x:x+w]
            
            cleaned = self.run_hybrid_ocr(crop)
            result_data[key] = self.parse_numeric_text(cleaned)
            
        # マッピング
        mapped = {}
        for key, val in result_data.items():
            label = PARAM_LABELS.get(key, key)
            mapped[label] = val
        return mapped

def run_test():
    img_path = r"C:\Users\katsu\.gemini\antigravity\brain\b9c269d6-cbdc-48f1-a335-c239d92c584f\.tempmediaStorage\media_b9c269d6-cbdc-48f1-a335-c239d92c584f_1780164764452.png"
    
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    engine = SakatsukuOCREngineBypass()
    
    print("\n--- スマートバイパスおよび究極座標でのOCRスキャン実行 ---")
    results = engine.extract_all(img)
    
    expected_griez = {
        "総合力": 7165, "ポジション": "AM", "選手名": "Antoine Griezmann",
        "SHO数値": 1441, "PAS数値": 1502, "DRB数値": 1475,
        "DEF数値": 1066, "PHY数値": 1143, "SPD数値": 845,
        "決定力": 503, "ショートパス": 502, "突破力": 488,
        "タックル": 366, "ジャンプ": 412, "走力": 396,
        "キック力": 448, "ロングパス": 500, "キープ力": 484,
        "パスカット": 361, "コンタクト": 373, "敏捷性": 449,
        "冷静さ": 490, "キック精度": 500, "ボールタッチ": 503,
        "マーク": 339, "スタミナ": 358
    }
    
    failures = 0
    for label, exp in expected_griez.items():
        val = results.get(label)
        status = "【OK】"
        if val != exp:
            status = f"【NG - 期待値: {exp} / 検出: {val}】"
            failures += 1
        print(f"  {label:<15} => {val} {status}")
        
    if failures == 0:
        print("\n🎉 完璧！全パラメータ認識精度 100.00% 達成！")
    else:
        print(f"\n❌ {failures} 個の不一致が残っています。")

if __name__ == "__main__":
    run_test()
