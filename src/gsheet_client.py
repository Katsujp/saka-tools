# -*- coding: utf-8 -*-
"""Googleスプレッドシート連携モジュール。

gspreadライブラリを使用し、認証情報を用いて指定されたスプレッドシートへの
データ追記やシート自動生成を行います。
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from src.config import PARAM_LABELS

# Google DriveおよびSheets APIのスコープ定義
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

class SakatsukuGSheetClient:
    """Googleスプレッドシートとの通信およびデータ追加を行うクライアントクラス。"""

    def __init__(self, credentials_info=None, credentials_filepath=None):
        """スプレッドシートクライアントを初期化します。

        Args:
            credentials_info (dict, optional): 認証用JSON辞書データ
            credentials_filepath (str, optional): 認証用JSONファイルのパス
        """
        self.client = None
        self.credentials = None

        if credentials_info:
            # 辞書データから認証
            self.credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, SCOPES)
        elif credentials_filepath:
            # ファイルパスから認証
            self.credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_filepath, SCOPES)
        
        if self.credentials:
            self.client = gspread.authorize(self.credentials)

    def is_connected(self):
        """Google APIとの認証接続が確立されているかを返します。"""
        return self.client is not None

    def append_parameter_data(self, spreadsheet_url, sheet_name, param_dict):
        """解析されたパラメータデータをスプレッドシートの最終行に追記します。

        Args:
            spreadsheet_url (str): 対象スプレッドシートの共有URL
            sheet_name (str): 対象シート名（例: "選手データ"）
            param_dict (dict): 抽出されたパラメータ辞書 (キーは日本語ラベル)

        Returns:
            int: 追記された行番号
        """
        if not self.is_connected():
            raise ConnectionError("Googleスプレッドシートクライアントが認証されていません。")

        # スプレッドシートを開く
        spreadsheet = self.client.open_by_url(spreadsheet_url)
        
        # 指定されたシートが存在しない場合は自動作成
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="40")

        # 現在のシートのヘッダー行を取得
        headers = worksheet.row_values(1)

        # デフォルトのヘッダーカラムリスト（出力順序の美しさを確保）
        default_headers = [
            "選手名", "ポジション", "ランク", "総合力",
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
            "走力", "敏捷性",
            "セービング", "反応速度", "1対1"
        ]

        # シートが完全に空、またはヘッダーが存在しない場合はヘッダーを書き込む
        if not headers:
            worksheet.append_row(default_headers)
            headers = default_headers

        # ヘッダーの定義順に合わせて、パラメータ辞書からデータをリスト化
        # スプレッドシート側のカラム定義を尊重し、ヘッダーに存在する項目のみマッピング
        row_data = []
        for header in headers:
            # 辞書から値を取得（存在しない場合は空欄）
            val = param_dict.get(header, "")
            row_data.append(val)

        # もしヘッダーにない項目が辞書に含まれている場合（新規の列追加など）
        # ただし、ヘッダーの自動拡張は行わず、定義済みのカラムに対してのみ書き込む設計とする

        # スプレッドシートの最終行に追記
        result = worksheet.append_row(row_data, value_input_option="USER_ENTERED")
        
        # 追記されたセルの情報から行番号を抽出して返す
        # 通常、append_rowは更新された行のセル数を返します
        updated_cells = result.get('updates', {}).get('updatedRange', '')
        # 例: "Sheet1!A4:AG4" のような文字列から行番号 "4" を抽出
        row_num = 1
        if updated_cells:
            import re
            match = re.search(r'A(\d+):', updated_cells)
            if match:
                row_num = int(match.group(1))
            else:
                match = re.search(r'(\d+)$', updated_cells)
                if match:
                    row_num = int(match.group(1))

        return row_num
