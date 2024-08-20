# !/usr/bin/env python3
# _*_ coding:utf-8 _*_
"""
@File     : pdf_download.py
@Time     : 2024/8/15 16:35
@Author   : Hjw
@License  : (C)Copyright 2018-2025
"""

import shutil
import traceback
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
import time
import os

from typing import Any, List, Union

from core.tools.provider.builtin.crossref.tools.query_title import CrossRefQueryTitleAPI
from core.tools.provider.builtin.semantic.tools.semantic_scholar import SemanticScholarBatchAPI
from core.tools.tool.builtin_tool import BuiltinTool
from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError


def create_driver(executable_path: str, download_dir: str, chrome_options: Options = None):
    print("executable_path", executable_path)
    print("download_dir", download_dir)
    if not chrome_options:
        chrome_options = Options()
        prefs = {
            'download.default_directory': os.path.abspath(download_dir),
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            "plugins.always_open_pdf_externally": True,
            'safebrowsing.enabled': False,
            'safebrowsing.disable_download_protection': True
        }
        chrome_options.add_experimental_option('prefs', prefs)
        chrome_options.add_argument("--mute-audio")  # 将浏览器静音
        # chrome_options.add_experimental_option("detach", True)  # 当程序结束时，浏览器不会关闭
        # -----linux系统没有安装桌面，必须开启无界面浏览器-------
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
    chrome_service = ChromeService(executable_path=executable_path)
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    return driver


def sanitize_filename(filename: str, ext: str = None) -> str:
    # Step 1: Remove non-ASCII characters
    filename = re.sub(r'[^\x00-\x7F]+', '', filename)

    # Step 2: Replace invalid characters for Windows and Linux
    # Windows invalid: \ / : * ? " < > |
    # Linux invalid: /
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
    filename = re.sub(invalid_chars, '_', filename)

    # Step 3: Strip whitespace from the beginning and end
    filename = filename.strip()

    # Step 4: Return a default name if the filename is empty
    if not filename:
        filename = "default_filename"
    # Step 5: Add the extension if it exists
    if ext:
        filename = f"{filename}.{ext}"

    return filename


def get_latest_file(folder_path: str) -> str:
    # Step 1: Get all entries in the folder
    entries = os.listdir(folder_path)
    entries = [os.path.join(folder_path, entry) for entry in entries]
    # Step 2: Filter out directories, only keep files
    files = [entry for entry in entries if os.path.isfile(entry)]

    # Step 3: Check if the folder is empty or has no files
    if not files:
        return ''

    # Step 4: Find the file with the latest modification time
    latest_file = max(files, key=lambda f: os.path.getmtime(f))

    # Step 5: Return the filepath of the latest file
    return latest_file


def exist_crdownload_file(dirpath):
    for filename in os.listdir(dirpath):
        # 检查文件是否以 .crdownload 结尾
        if filename.endswith('.crdownload') or filename.endswith('.tmp'):
            return filename
    return ''


def clean_cache_download_files(dirpath):
    for filename in os.listdir(dirpath):
        # 检查文件是否以 .crdownload 结尾
        if filename.endswith('.crdownload') or filename.endswith('.tmp'):
            os.remove(os.path.join(dirpath, filename))


def wait_for_download(directory, pre_latest_file, max_retries=10, check_interval=1, download_timeout=120):
    retries = 0

    while retries < max_retries:
        latest_file = get_latest_file(directory)

        if latest_file != pre_latest_file:
            if latest_file.endswith('.crdownload') or latest_file.endswith('.tmp'):
                # 找到了 .crdownload 文件，进入下载等待逻辑
                start_time = time.time()

                while True:
                    # 如果 .crdownload 文件不存在了，表示下载完成
                    # 返回True, 和最新文件
                    if not os.path.exists(latest_file):
                        return True, get_latest_file(directory)

                    # 如果超时，则返回 False, 和缓冲文件
                    if time.time() - start_time > download_timeout:
                        try:
                            os.remove(latest_file)
                        except Exception as e:
                            print(f"Error while removing file: {latest_file}")
                            print(traceback.format_exc())
                        return False, ''

                    # 每隔一段时间检查一次
                    time.sleep(check_interval)
            else:
                # 下载完成
                # 返回True, 和最新文件
                return True, latest_file

        # 如果没有新增文件或者最新文件不是 .crdownload 文件，等待并重试
        retries += 1
        time.sleep(check_interval)

    # 如果重试次数达到最大值仍未找到 .crdownload 文件，则返回 False
    return False, ''


def get_doi_from_title(title: str) -> str:
    paper = CrossRefQueryTitleAPI("jiawen.huang@matwings.com").query(title, rows=1, fuzzy_query=False)
    if paper:
        return paper[0].get('doi', '')
    return ''


def check_filepath(name: str, ext: str, dirpath:str) -> str:
    filename = sanitize_filename(name, ext)
    for fn in os.listdir(dirpath):
        if filename == fn:
            return os.path.join(dirpath, fn)
    return ''


class PDFDownloader:
    scihub_url_template: str = 'https://sci.bban.top/pdf/{}.pdf'
    unpaywall_url_template: str = 'https://api.unpaywall.org/v2/{}?email=sdsxlwf@email.com'
    crossref_url_template: str = 'https://api.crossref.org/works/{}'
    semantic_api: object = SemanticScholarBatchAPI()

    def __init__(self, executable_path: str, marker_api: str = None, download_dir: str = None, timeout=60, interval=1):
        self.executable_path = executable_path
        self.marker_api = marker_api

        self.download_dir = download_dir or '../data/download'
        self.markdown_dir = os.path.join(self.download_dir, 'markdown')
        self.pdf_download_dir = os.path.join(self.download_dir, 'pdf')
        os.makedirs(self.markdown_dir, exist_ok=True)
        os.makedirs(self.pdf_download_dir, exist_ok=True)

        self.fail_download_doi_file = os.path.join(self.download_dir, 'fail_download_doi.txt')
        if os.path.exists(self.fail_download_doi_file):
            self.fail_download_doi_set = set(open(self.fail_download_doi_file).read().splitlines())
        else:
            self.fail_download_doi_set = set()

        self.timeout = timeout
        self.interval = interval
        self.chrome_driver = create_driver(executable_path, self.pdf_download_dir)

        self.last_pdf_file = get_latest_file(self.pdf_download_dir)

    def download_by_url(self, url: str, filename: str) -> str:
        self.chrome_driver.get(url)

        success, file_path = wait_for_download(self.pdf_download_dir, self.last_pdf_file, self.timeout, self.interval)
        if not success:
            return ''
        print("latest filepath:", file_path)
        if file_path == self.last_pdf_file:
            return ''

        # rename the file
        new_file_path = os.path.join(self.pdf_download_dir, filename)
        print("download filepath:", new_file_path)
        shutil.move(file_path, new_file_path)
        self.last_pdf_file = new_file_path
        return new_file_path

    def get_url_from_scihub(self, doi: str):
        url = self.scihub_url_template.format(doi)
        return url

    def get_url_from_unpaywall(self, doi: str):
        url = self.unpaywall_url_template.format(doi)
        response = requests.get(url, allow_redirects=True)
        if response.status_code == 200:
            best_oa_location = response.json().get('best_oa_location')
            if best_oa_location:
                url = best_oa_location.get('url_for_pdf')
                return url
        return ''

    def get_url_from_crossref(self, doi: str, title: str = ''):
        # not use
        # if not doi and title:
        #     crossref_api = CrossRefQueryTitleAPI("jiawen.huang@matwings.com")
        #     # search paper by title
        #     search_paper = crossref_api.query(query=title, fuzzy_query=False, return_type='basic')
        #     if search_paper:
        #         return search_paper[0].get("pdf_url") or search_paper[0].get("url")

        url = self.crossref_url_template.format(doi)
        try:
            response = requests.get(url)
            response.raise_for_status()
            response = response.json()
            if response['status'] != 'ok':
                return ''
            for link in response['message'].get('link', []):
                if link['content-type'] == "application/pdf":
                    return link['URL']
            return response['message'].get('URL', '')

        except Exception as e:
            traceback.print_exc()
            return ''

    def _download(self, doi: str, url: str):
        filename = sanitize_filename(doi, 'pdf')

        urls = [
            url,
            self.get_url_from_scihub(doi),
            self.get_url_from_crossref(doi),
            self.get_url_from_unpaywall(doi),
        ]
        for url in urls:
            if not url:
                continue
            filepath = self.download_by_url(url, filename)
            if filepath:
                return filepath, url
        return '', ''

    def convert_pdf_to_markdown(self, filepath: str, ) -> str:
        filename = os.path.basename(filepath)
        markdown_filename = os.path.splitext(filename)[0] + '.md'
        markdown_filepath = os.path.join(self.markdown_dir, markdown_filename)
        if os.path.exists(markdown_filepath):
            print("load markdown from cache:", markdown_filepath)
            with open(markdown_filepath, 'r', encoding='utf-8') as rf:
                return rf.read()

        print("convert_pdf_to_markdown:", filepath, markdown_filepath)
        with open(filepath, 'rb') as rf:
            pdf = rf.read()

        files = [('pdf_file', (filename, pdf, 'application/pdf'))]
        response = requests.post(self.marker_api, files=files, params={'extract_images': False})
        if response.status_code == 200:
            # Save markdown and images
            response_data = response.json()[0]
            markdown_text = response_data['markdown']

            with open(markdown_filepath, 'w', encoding='utf-8') as wf:
                wf.write(markdown_text)

            return markdown_text
        return "Failed to convert PDF to markdown."

    def download(self, doi: str, title: str = None, url: str = None, convert: bool = False):
        """
        Download PDF for a paper.
        :param doi: DOI of the paper.
        :param title: Title of the paper.
        :param url: PDF URL of the paper.
        :param convert: whether convert pdf to markdown
        """
        if not doi and not title:
            raise ValueError("DOI or title is required.")
        if not doi:
            if title:
                paper = CrossRefQueryTitleAPI("jiawen.huang@matwings.com").query(title, rows=1, fuzzy_query=False)
                if paper:
                    paper = paper[0]
                    doi = paper.get("doi")
                    title = paper.get("title")
                    url = url or paper.get("pdf_url") or paper.get("url")
                else:
                    print("Cannot find paper by title, DOI is required.")
                    print("title:", title)
                    # raise ValueError("Cannot find paper by title, DOI is required.")
                    return {
                        'doi': '',
                        'title': title,
                        'url': url or '',
                    }

        paper = {
            'doi': doi,
            'title': title or '',
            'url': url or '',
        }
        if doi in self.fail_download_doi_set:
            print("find in failed list, skip:", doi)
            return paper

        filepath = check_filepath(doi, ext='pdf', dirpath=self.pdf_download_dir)
        if filepath:
            print("load pdf from cache:", filepath)
            paper['pdf_path'] = filepath
        else:
            filepath, url = self._download(doi, url)
            if filepath:
                paper['pdf_path'] = filepath
                paper['url'] = url
            else:
                # add to failed list
                self.fail_download_doi_set.add(doi)

        if filepath and convert:
            paper['markdown'] = self.convert_pdf_to_markdown(filepath)

        return paper

    def batch_download(self, doi, title, url, convert: bool = False):
        length = 0
        if doi:
            doi_list = doi.strip().split('\n')
            print("doi_list:", doi_list)
            length = len(doi_list)
        if title:
            title_list = title.strip().split('\n')
            print("title_list:", title_list)
            if length:
                if len(title_list) != length:
                    raise ValueError("The number of DOI and title should be the same.")
            else:
                length = len(title_list)
        if url:
            url_list = url.strip().split('\n')
            print("url_list:", url_list)
            if length and len(url_list) != length:
                raise ValueError("The number of DOI and URL should be the same.")
        if not length:
            raise ValueError("DOI or title is required.")

        if not doi:
            doi_list = [''] * length
        if not title:
            title_list = [''] * length
        if not url:
            url_list = [''] * length

        results = []
        for i in range(length):
            result = self.download(doi_list[i].strip(), title_list[i].strip(), url_list[i].strip(), convert)
            results.append(result)

        # save failed doi list
        with open(self.fail_download_doi_file, 'w', encoding='utf-8') as wf:
            for doi in self.fail_download_doi_set:
                wf.write(doi + '\n')
        return results

    def close(self):
        self.chrome_driver.quit()
        self.chrome_driver = None


class PDFDownloaderTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        executable_path = self.runtime.credentials['chrome_executable_path']
        download_dir = self.runtime.credentials['chrome_download_dir']
        marker_api = self.runtime.credentials['marker_api']

        doi = tool_parameters.get('doi')
        title = tool_parameters.get('title')
        if not doi and not title:
            raise ToolParameterValidationError("DOI or title is required")
        url = tool_parameters.get('url')

        convert = tool_parameters.get('convert', False)

        downloader = PDFDownloader(executable_path, marker_api, download_dir)
        results = downloader.batch_download(doi, title, url, convert)
        downloader.close()

        return [self.create_json_message(result) for result in results]
