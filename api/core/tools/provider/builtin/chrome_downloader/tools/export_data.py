# !/usr/bin/env python3
# _*_ coding:utf-8 _*_
"""
@File     : export_data.py
@Time     : 2024/8/20 14:08
@Author   : Hjw
@License  : (C)Copyright 2018-2025
"""

import json
import traceback
import os
import pandas as pd
from typing import Union, Any
from datetime import datetime
from core.tools.tool.builtin_tool import BuiltinTool
from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError


class ExportDataAPI:
    def __init__(self, export_dir: str):
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)

    def export_data(self, data: str, file_type: str, file_name: str = None, encoding='utf-8'):
        """
        export data to file
        :param data: data to export
        :param file_type: file type, support 'txt', 'json', 'csv', 'excel'
        :param file_name: file name, if None, use current time as file name
        :param encoding: encoding of the file
        """
        if not file_name.strip():
            file_name = datetime.now().strftime("%Y%m%d_%H%M%S")

        if not file_name.endswith('.' + file_type):
            file_name += '.' + file_type
        print("filename", file_name)
        save_path = os.path.join(self.export_dir, file_name)
        try:
            if file_type == 'txt' or file_type == 'md':
                with open(save_path, 'w', encoding=encoding) as f:
                    f.write(str(data))
            elif file_type == 'json':
                data = json.loads(data)
                with open(save_path, 'w', encoding=encoding) as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            elif file_type == 'csv' or file_type == 'xlsx':
                data = json.loads(data)
                if isinstance(data, dict):
                    data = [data]
                df = pd.DataFrame(data)
                if file_type == 'csv':
                    df.to_csv(save_path, index=False, encoding=encoding)
                else:
                    df.to_excel(save_path, index=False)
            else:
                raise ValueError("Unsupported file type.")
        except Exception as e:
            traceback.print_exc()
            raise ToolParameterValidationError(f"Failed to export data(type {type(data)}) to {file_type} file: {str(e)}")

        return save_path


class ExportDataTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        download_dir = self.runtime.credentials['chrome_download_dir']
        export_dir = os.path.join(download_dir, 'export')
        download_api = self.runtime.credentials['download_api']

        data = tool_parameters['data']
        file_type = tool_parameters['filetype']
        file_name = tool_parameters.get('filename')

        api = ExportDataAPI(export_dir)
        save_path = api.export_data(data, file_type, file_name)
        url = download_api + save_path
        print("export url:", url)
        return self.create_text_message(url)
