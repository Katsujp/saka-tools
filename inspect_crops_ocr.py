# -*- coding: utf-8 -*-
"""保存されたクロップ画像に対して個別にOCRを実行し、読み取り不良の原因を診断するスクリプト。
"""

import sys
import os
import cv2
import numpy as np
import easyocr

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')

sys.path.append(r"C:\Users\katsu\.gemini\antigravity\scratch\sakatsuku_2026")

def run_diagnostics():
    reader_en = easyocr.Reader(['en'], gpu=True, verbose=False)
    crop_dir = r"C:\Users\katsu\.gemini\antigravity\scratch\sakatsuku_2026\debug_crops"
    
    # 診断対象のファイルリスト
    targets = [
        # メイン SPD 数値 (期待値: 845)
        ("prod_main_SPD_val.png", "845"),
        ("gold_main_SPD_val.png", "845"),
        
        # 個別冷静さ (期待値: 490)
        ("prod_detail_param_13_val.png", "490"),
        ("gold_detail_param_13.png", "490"),
        
        # 個別キック精度 (期待値: 500)
        ("prod_detail_param_14_val.png", "500"),
        ("gold_detail_param_14.png", "500"),
        
        # 個別スタミナ (期待値: 358)
        ("prod_detail_param_17_val.png", "358"),
        ("gold_detail_param_17.png", "358"),
    ]
    
    print("==================================================")
    print("🔍 クロップ画像 個別OCR詳細診断")
    print("==================================================")
    
    for filename, expected in targets:
        path = os.path.join(crop_dir, filename)
        if not os.path.exists(path):
            print(f"ファイルが見つかりません: {filename}")
            continue
            
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        print(f"\n📂 ファイル: {filename} (サイズ: {w}x{h}, 期待値: {expected})")
        
        # 1. 生グレースケール 3.5倍
        prep_raw = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
        res_raw = reader_en.readtext(prep_raw, detail=0, allowlist='0123456789')
        print(f"  [生グレースケール3.5倍] => '{''.join(res_raw).strip()}'")
        
        # 2. 二値化あり (t=120) 3.5倍
        expanded = cv2.resize(gray, (0, 0), fx=3.5, fy=3.5, interpolation=cv2.INTER_CUBIC)
        blurred = cv2.GaussianBlur(expanded, (3, 3), 0)
        _, binary = cv2.threshold(blurred, 120, 255, cv2.THRESH_BINARY)
        prep_bin_120 = cv2.bitwise_not(binary)
        res_bin_120 = reader_en.readtext(prep_bin_120, detail=0, allowlist='0123456789')
        print(f"  [二値化 t=120]         => '{''.join(res_bin_120).strip()}'")
        
        # 3. 二値化あり (t=155) 3.5倍
        _, binary_155 = cv2.threshold(blurred, 155, 255, cv2.THRESH_BINARY)
        prep_bin_155 = cv2.bitwise_not(binary_155)
        res_bin_155 = reader_en.readtext(prep_bin_155, detail=0, allowlist='0123456789')
        print(f"  [二値化 t=155]         => '{''.join(res_bin_155).strip()}'")
        
        # 4. 二値化あり (t=100) 3.5倍 (フォントの細い3行目用の低い閾値)
        _, binary_100 = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY)
        prep_bin_100 = cv2.bitwise_not(binary_100)
        res_bin_100 = reader_en.readtext(prep_bin_100, detail=0, allowlist='0123456789')
        print(f"  [二値化 t=100]         => '{''.join(res_bin_100).strip()}'")

if __name__ == "__main__":
    run_diagnostics()
