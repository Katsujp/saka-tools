# -*- coding: utf-8 -*-
"""Griezmannの切り出し画像を保存して視覚的に座標と切り出し内容を確認するデバッグスクリプト。
"""

import sys
import os
import cv2
import numpy as np

# CP932対策
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')

sys.path.append(r"C:\Users\katsu\.gemini\antigravity\scratch\sakatsuku_2026")

from src.config import DETAIL_PARAM_ROIS, MAIN_PARAM_ROIS, BASIC_INFO_ROIS

def save_crops():
    img_path = r"C:\Users\katsu\.gemini\antigravity\brain\b9c269d6-cbdc-48f1-a335-c239d92c584f\.tempmediaStorage\media_b9c269d6-cbdc-48f1-a335-c239d92c584f_1780164764452.png"
    save_dir = r"C:\Users\katsu\.gemini\antigravity\scratch\sakatsuku_2026\debug_crops"
    os.makedirs(save_dir, exist_ok=True)
    
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print("エラー: 画像のロードに失敗しました。")
        return
        
    # アスペクト比16:9バイパスでの正規化（トリミングなし）
    normalized = cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(os.path.join(save_dir, "normalized_full.png"), normalized)
    
    print("--- クロップ画像を保存中 ---")
    
    # 1. 本番の DETAIL_PARAM_ROIS (Y=453/543/633, W=170)
    for key, roi in DETAIL_PARAM_ROIS.items():
        x, y, w, h = roi
        crop = normalized[y:y+h, x:x+w]
        # ファイル名が日本語にならないようにアルファベットのキー名で保存
        cv2.imwrite(os.path.join(save_dir, f"prod_detail_{key}.png"), crop)
        
    # 2. テストの GOLD_DETAIL_ROIS (Y=445/544/628, W=180)
    gold_detail = {
        "param_01": (730, 445, 180, 38), "param_02": (925, 445, 180, 38), "param_03": (1100, 445, 180, 38),
        "param_04": (1275, 445, 180, 38), "param_05": (1450, 445, 180, 38), "param_06": (1660, 445, 160, 38),
        "param_07": (730, 544, 180, 38), "param_08": (925, 544, 180, 38), "param_09": (1080, 544, 180, 38),
        "param_10": (1275, 544, 180, 38), "param_11": (1450, 544, 180, 38), "param_12": (1660, 544, 160, 38),
        "param_13": (730, 628, 180, 38), "param_14": (925, 628, 180, 38), "param_15": (1100, 628, 180, 38),
        "param_16": (1275, 628, 180, 38), "param_17": (1450, 628, 180, 38)
    }
    for key, roi in gold_detail.items():
        x, y, w, h = roi
        crop = normalized[y:y+h, x:x+w]
        cv2.imwrite(os.path.join(save_dir, f"gold_detail_{key}.png"), crop)
        
    # 3. メイン数値とランク
    for key, roi in MAIN_PARAM_ROIS.items():
        x, y, w, h = roi
        crop = normalized[y:y+h, x:x+w]
        cv2.imwrite(os.path.join(save_dir, f"prod_main_{key}.png"), crop)
        
    gold_main = {
        "SPD_val": (1730, 285, 115, 85),
        "DEF_val": (1385, 285, 100, 85),
        "PHY_val": (1560, 285, 100, 85)
    }
    for key, roi in gold_main.items():
        x, y, w, h = roi
        crop = normalized[y:y+h, x:x+w]
        cv2.imwrite(os.path.join(save_dir, f"gold_main_{key}.png"), crop)

    # 4. 選手名
    x, y, w, h = BASIC_INFO_ROIS["card_name"]
    crop = normalized[y:y+h, x:x+w]
    cv2.imwrite(os.path.join(save_dir, "prod_name.png"), crop)
    
    # 縦書き選手名は反時計回りに90度回転
    rotated = cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)
    cv2.imwrite(os.path.join(save_dir, "prod_name_rotated.png"), rotated)

    print("クロップ画像の保存が完了しました。")

if __name__ == "__main__":
    save_crops()
