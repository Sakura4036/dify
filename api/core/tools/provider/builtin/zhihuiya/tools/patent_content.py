import json
import time
import requests
from typing import List, Any, Union
from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.provider.builtin.zhihuiya.zhihuiya import ZhiHuiYaProvider
from core.tools.tool.builtin_tool import BuiltinTool


def get_text_by_lang(content: List[dict], lang=None):
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
                return c['text']
    return content[0]['text']


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

    def get_title_abstract(self, patent_id: str, patent_number: str):
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
            data["patent_id"] = {
                "patent_id": d['patent_id'],
                "patent_number": d['pn'],
                "patent_type": d['bibliographic_data']['patent_type'],
                "title": get_text_by_lang(d['bibliographic_data']['invention_title']),
                "abstract": get_text_by_lang(d['bibliographic_data']['abstracts']),
            }

        return data

    def get_claim_data(self, patent_id: str, patent_number: str):
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
            data['patent_id']={
                "patent_id": d['patent_id'],
                "patent_number": d['pn'],
                "claims": get_text_by_lang(d['claims']),
                "claim_count": d['claim_count'],
                "pn_related": d['pn_related']
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
            data['patent_id'] = {
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
            return None

        data = {}
        if title_abstract:
            data.update(self.get_title_abstract(patent_id, patent_number))
        if claim:
            data.update(self.get_claim_data(patent_id, patent_number))
        if tech_summary:
            data.update(self.get_tech_summary(patent_id, patent_number, lang))
        return data


class PatentContentTool(BuiltinTool):
    def _invoke(self,
                user_id: str,
                tool_parameters: dict[str, Any],
                ) -> Union[ToolInvokeMessage, list[ToolInvokeMessage]]:
        credentials = tool_parameters.get("credentials")
        patent_id = tool_parameters.get("patent_id")
        patent_number = tool_parameters.get("patent_number")
        lang = tool_parameters.get("lang", "en")
        title_abstract = tool_parameters.get("title_abstract", True)
        claim = tool_parameters.get("claim", False)
        tech_summary = tool_parameters.get("tech_summary", False)

        results = PatentContentAPI(credentials).get_patent_content(patent_id, patent_number, lang, title_abstract, claim, tech_summary)

        return [self.create_json_message(r) for r in results]



