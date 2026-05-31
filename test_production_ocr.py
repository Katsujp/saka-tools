# -*- coding: utf-8 -*-
"""本番のOCRエンジンを使用して、ユーザーのGriezmann画像を解析するデバッグスクリプト。
"""

import sys
import cv2
import numpy as np

# 出力のCP932エラーを防止
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(errors='replace')

# プロジェクトのソースコードをインポートできるようにパスを追加
sys.path.append(r"C:\Users\katsu\.gemini\antigravity\scratch\sakatsuku_2026")

from src.ocr_engine import SakatsukuOCREngine

def test_production_griezmann():
    img_path = r"C:\Users\katsu\.gemini\antigravity\brain\b9c269d6-cbdc-48f1-a335-c239d92c584f\media__1780164578058.png"
    
    print("本番OCRエンジンを初期化中...")
    engine = SakatsukuOCREngine()
    
    print(f"画像をロード中: {img_path}")
    # 日本語のパスに対応するため imdecode を使用
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    
    if img is None:
        print("エラー: 画像の読み込みに失敗しました。")
        return
        
    print(f"画像サイズ: {img.shape}")
    
    print("解析を実行中...")
    try:
        results = engine.extract_all_parameters(img)
        print("\n--- 解析結果 ---")
        for key, val in results.items():
            print(f"{key}: {val}")
    except Exception as e:
        print(f"解析中に例外が発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_production_griezmann()
