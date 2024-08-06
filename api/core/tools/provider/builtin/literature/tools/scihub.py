# !/usr/bin/env python3
# _*_ coding:utf-8 _*_
"""
@File     : scihub.py
@Time     : 2024/7/31 9:53
@Author   : Hjw
@License  : (C)Copyright 2018-2025
"""
import os
import requests
from typing import Any, List, Union
from core.tools.tool.builtin_tool import BuiltinTool
from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError


def download(sci_doi_url) -> Union[bytes, None]:
    try:
        response = requests.get(sci_doi_url, allow_redirects=True)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to download PDF: {sci_doi_url}")
        return None
    return response.content


class SciHubAPI:
    scihub_urls = ['https://sci.bban.top/pdf/']
    marker_api_url = 'http://192.168.1.5:8011/convert'
    download_dir = "~/temp/dify/scihub/"

    def __init__(self, scihub_url: str, download_dir: str = None):
        if scihub_url:
            self.scihub_urls = [scihub_url]
        if download_dir:
            self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)

    def download_by_doi(self, doi: str) -> Union[bytes, None]:
        for url in self.scihub_urls:
            pdf = download(url + doi + '.pdf')
            if pdf:
                return pdf
        return None

    def download_and_save(self, doi: str, title: str = None) -> str:
        pdf = self.download_by_doi(doi)
        if not title:
            title = doi
        if pdf:
            save_path = f'{self.download_dir}/{title}.pdf'
            with open(save_path, 'wb') as file:
                file.write(pdf)
            print(f"PDF downloaded successfully and saved: {doi}")
            return save_path
        return ""

    def convert_pdf_to_markdown(self, pdf: bytes, filename: str = None) -> str:
        if not filename:
            filename = 'temp.pdf'
        files = [('pdf_file', (filename, pdf, 'application/pdf'))]
        response = requests.post(self.marker_api_url, files=files, params={'extract_images': False})
        if response.status_code == 200:
            # Save markdown and images
            response_data = response.json()[0]
            markdown_text = response_data['markdown']
            return markdown_text
        return "Failed to convert PDF to markdown."

    def invoke(self, doi, title: str = None, convert: bool = True) -> Union[str, bytes, None]:
        pdf = self.download_by_doi(doi)
        if convert:
            if pdf:
                if not title:
                    title = doi
                pdf_filename = f'{title}.pdf'
                return self.convert_pdf_to_markdown(pdf, pdf_filename)
            return "Failed to download PDF."
        return pdf


class SciHubTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        doi = tool_parameters.get("doi")
        if not doi:
            raise ToolParameterValidationError("DOI is required")

        title = tool_parameters.get("title")
        scihub_url = tool_parameters.get("scihub_url")
        convert = tool_parameters.get("convert")

        scihub = SciHubAPI(scihub_url)

        if convert:
            return self.create_text_message(text=scihub.invoke(doi, title, convert))
        else:
            pdf = scihub.download_by_doi(doi)
            if not pdf:
                msg = "Failed to download PDF"
            else:
                msg = "PDF downloaded successfully"
            return self.create_blob_message(blob=pdf, meta={"title": title, "doi": doi, "message": msg})
