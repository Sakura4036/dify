import json
import time

import numpy as np
import requests
from typing import List, Any, Union
from bs4 import BeautifulSoup
from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.provider.builtin.zhihuiya.zhihuiya import ZhiHuiYaProvider
from core.tools.tool.builtin_tool import BuiltinTool


def get_text_by_lang(content: List[dict], lang=None, return_key="text"):
    """
    get text by language, if lang is None, return the first text
    """
    if lang is None:
        lang = ["EN", "CN", "JP"]
    if not isinstance(lang, list):
        lang = [lang]
    for la in lang:
        for c in content:
            if c['lang'] == la:
                return c[return_key]
    return content[0][return_key]


def html_to_markdown(html_text: str, return_markdown: bool = False) -> str:
    # 使用BeautifulSoup解析HTML
    soup = BeautifulSoup(html_text, "html.parser")

    if return_markdown:
        # 将sup、sub标签转为相应的Markdown格式
        for sup in soup.find_all("sup"):
            sup.string = f"^{sup.text}^"
        for sub in soup.find_all("sub"):
            sub.string = f"~{sub.text}~"

        sep = "\n\n"
    else:
        sep = "\n"

    # 处理div标签中的内容
    lines = []
    for div in soup.find_all("div"):
        content = div.get_text(strip=True)
        lines.append(content)

    # 将处理后的内容连接成一个字符串并返回
    markdown_text = f"{sep}".join(lines)
    return markdown_text


def update_dict(d: dict, u: dict) -> dict:
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = update_dict(d.get(k, {}), v)
        else:
            d[k] = v
    return d


class PatentContentAPI:
    api_key = ""
    token = ""
    # P011: 简单著录项
    api_simple_bibliography_url = "https://connect.zhihuiya.com/basic-patent-data/simple-bibliography"
    # P018: 权利说明书
    api_claim_url = "https://connect.zhihuiya.com/basic-patent-data/claim-data"
    # P019: 说明书
    api_description_url = "https://connect.zhihuiya.com/basic-patent-data/description-data"
    # P025: 专利技术三要素
    api_tech_summary_url = "https://connect.zhihuiya.com/high-value-data/tech-problem-and-benefit-summary"

    max_limit = 100

    def __init__(self, credentials: dict):
        self.api_key = credentials["api_key"]
        self.token = ZhiHuiYaProvider().get_bearer_token(credentials)

    def get_title_abstract(self, patent_id: str, patent_number: str, lang: str = 'en'):
        if not patent_id or not patent_number:
            return None

        params = {
            "patent_id": patent_id,
            "patent_number": patent_number,
            "apikey": self.api_key
        }

        payload = None

        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer {}".format(self.token)
        }

        response = requests.request("GET", self.api_simple_bibliography_url, params=params, data=payload, headers=headers)
        response.raise_for_status()

        response = response.json()
        if response['error_code'] != 0:
            raise Exception(response['error_msg'])
        data = {}
        for d in response['data']:
            data[d['patent_id']] = {
                "patent_id": d['patent_id'],
                "patent_number": d['pn'],
                "patent_type": d['bibliographic_data']['patent_type'],
                "title": get_text_by_lang(d['bibliographic_data']['invention_title'], lang=lang),
                "abstract": get_text_by_lang(d['bibliographic_data']['abstracts'], lang=lang),
            }

        return data

    def get_claim_data(self, patent_id: str, patent_number: str, lang: str = 'en'):
        if not patent_id or not patent_number:
            return None

        params = {
            "patent_id": patent_id,
            "patent_number": patent_number,
            "replace_by_related": "0",
            "apikey": self.api_key
        }

        payload = None

        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer {}".format(self.token)
        }

        response = requests.request("GET", self.api_claim_url, params=params, data=payload, headers=headers)
        response.raise_for_status()
        response = response.json()
        if response['error_code'] != 0:
            raise Exception(response['error_msg'])

        data = {}
        for d in response['data']:
            data[d['patent_id']] = {
                "patent_id": d['patent_id'],
                "patent_number": d['pn'],
                "claims": html_to_markdown(get_text_by_lang(d['claims'], lang=lang, return_key="claim_text")),
                "claim_count": d['claim_count'],
            }

        return data

    def get_tech_summary(self, patent_id: str, patent_number: str, lang: str = 'en'):
        if not patent_id or not patent_number:
            return None

        params = {
            "lang": lang,
            "patent_id": patent_id,
            "patent_number": patent_number,
            "apikey": self.api_key
        }

        payload = None

        headers = {
            "Content-Type": "application/json",
            "authorization": "Bearer {}".format(self.token),
        }

        response = requests.request("GET", self.api_tech_summary_url, params=params, data=payload, headers=headers)
        response.raise_for_status()
        response = response.json()
        if response['error_code'] != 0:
            raise Exception(response['error_msg'])
        data = {}
        for d in response['data']:
            data[d['patent_id']] = {
                "patent_id": d['patent_id'],
                "patent_number": d['pn'],
                "benefit_summary": d['benefit_summary'],
                "tech_problem_summary": d['tech_problem_summary'],
                "technical_approach_summary": d['technical_approach_summary']
            }
        return data

    def get_patent_content(self, patent_id: str, patent_number: str, lang: str = 'en',
                           title_abstract: bool = True, claim: bool = False, tech_summary: bool = False):
        """
        get patent content by patent_id and patent_number
        :param patent_id: patent_id, multiple patent_id split by ','
        :param patent_number: patent_number, multiple patent_number split by ','
        :param lang: language, default is 'en'
        :param title_abstract: get simple bibliography or not, default is True
        :param claim: get claim data or not, default is True
        :param tech_summary: get tech summary or not, default is False
        """
        if not patent_id or not patent_number:
            raise ValueError("at least one of patent_id and patent_number should be provided")
        if patent_id:
            patent_ids = patent_id.split(',')
            if len(patent_ids) > self.max_limit:
                patent_id_list = np.array_split(patent_ids, len(patent_ids) // self.max_limit + 1)
                patent_id_list = [','.join(p) for p in patent_id_list]
            else:
                patent_id_list = [patent_id]
            patent_number_list = ['' for _ in patent_id_list]
        else:
            patent_numbers = patent_number.split(',')
            if len(patent_numbers) > self.max_limit:
                patent_numbers = np.array_split(patent_numbers, len(patent_numbers) // self.max_limit + 1)
                patent_number_list = [','.join(p) for p in patent_numbers]
            else:
                patent_number_list = [patent_number]
            patent_id_list = ['' for _ in patent_number_list]

        data = {}
        for patent_id_str, patent_number_str in zip(patent_id_list, patent_number_list):
            if title_abstract:
                title_abstract_data = self.get_title_abstract(patent_id_str, patent_number_str, lang)
                data = update_dict(data, title_abstract_data)
            if claim:
                claim_data = self.get_claim_data(patent_id_str, patent_number_str, lang)
                data = update_dict(data, claim_data)
            if tech_summary:
                tech_summary_data = self.get_tech_summary(patent_id_str, patent_number_str, lang)
                data = update_dict(data, tech_summary_data)
        return data


class PatentContentTool(BuiltinTool):
    def _invoke(self,
                user_id: str,
                tool_parameters: dict[str, Any],
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        patent_id = tool_parameters.get("patent_id")
        patent_number = tool_parameters.get("patent_number")
        if not patent_id or not patent_number:
            raise ValueError("at least one of patent_id and patent_number should be provided")

        lang = tool_parameters.get("lang", "en")
        title_abstract = tool_parameters.get("title_abstract", True)
        claim = tool_parameters.get("claim", False)
        tech_summary = tool_parameters.get("tech_summary", False)
        if not title_abstract and not claim and not tech_summary:
            raise ValueError("at least one of title_abstract, claim, tech_summary should be True")

        results = PatentContentAPI(self.runtime.credentials).get_patent_content(patent_id, patent_number, lang, title_abstract, claim, tech_summary)

        return [self.create_json_message(v) for k, v in results.items()]
