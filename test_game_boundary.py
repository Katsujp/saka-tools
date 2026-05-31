# -*- coding: utf-8 -*-
"""ウィンドウ自動トリミング（scan_game_boundary）の動作を検証・診断するスクリプト。
"""

import sys
import cv2
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(errors='replace')

sys.path.append(r"C:\Users\katsu\.gemini\antigravity\scratch\sakatsuku_2026")

from src.ocr_engine import SakatsukuOCREngine

def diagnose_boundary():
    # 実際の全体画像 (2.1MB)
    img_path = r"C:\Users\katsu\.gemini\antigravity\brain\b9c269d6-cbdc-48f1-a335-c239d92c584f\.tempmediaStorage\media_b9c269d6-cbdc-48f1-a335-c239d92c584f_1780164764452.png"
    
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print("エラー: 画像のロードに失敗しました。")
        return
    print(f"全体画像サイズ = {img.shape[1]}x{img.shape[0]}")
        
    target_path = img_path
    h_orig, w_orig = img.shape[:2]
    
    engine = SakatsukuOCREngine()
    
    # scan_game_boundary の内部処理をシミュレートし、検出座標をプリント
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. 上部タイトルバー境界Y
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
            
    # 2. 左右および下部
    scan_x_limit = int(w_orig * 0.10)
    left_diffs = []
    for x in range(2, scan_x_limit):
        diff = np.mean(cv2.absdiff(gray[:, x], gray[:, x-1]))
        left_diffs.append((x, diff))
    left_diffs.sort(key=lambda x: x[1], reverse=True)
    best_x_left = 8
    for x, diff in left_diffs[:5]:
        if 2 < x < 40:
            best_x_left = x
            break
            
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
            
    print("\n--- 検出されたウィンドウ境界 ---")
    print(f"上部タイトルバー境界 Y: {best_y} (デフォルト想定: 31)")
    print(f"左側境界 X: {best_x_left} (デフォルト想定: 8)")
    print(f"右側境界 X: {best_x_right} (デフォルト想定: {w_orig - 8})")
    print(f"下部境界 Y: {best_y_bottom} (デフォルト想定: {h_orig - 8})")
    
    crop_w = best_x_right - best_x_left
    crop_h = best_y_bottom - best_y
    print(f"切り出し領域サイズ: {crop_w}x{crop_h}")
    
    # 実際に切り出しと正規化を実行
    cropped = img[best_y:best_y_bottom, best_x_left:best_x_right]
    normalized = cv2.resize(cropped, (1920, 1080), interpolation=cv2.INTER_CUBIC)
    
    save_path = r"C:\Users\katsu\.gemini\antigravity\scratch\sakatsuku_2026\debug_normalized_griezmann.png"
    cv2.imwrite(save_path, normalized)
    print(f"正規化画像をデバッグ保存しました: {save_path}")

if __name__ == "__main__":
    diagnose_boundary()
