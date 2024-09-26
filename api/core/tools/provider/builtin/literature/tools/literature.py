import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Optional

import numpy as np
import requests
from xml.etree import ElementTree as ET

from core.tools.provider.builtin.semantic.tools.semantic_scholar import SemanticScholarBatchAPI
from core.tools.tool.builtin_tool import BuiltinTool
from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError
from core.tools.provider.builtin.wos.tools.wos_search import WosSearchAPI
from core.tools.provider.builtin.semantic.tools.semantic_bulk_search import SemanticBulkSearchAPI

logger = logging.getLogger(__name__)


def semantic_bulk_search(query: str,
                         year: str = '1960-',
                         document_type: str = '',
                         fields_of_study: str = '',
                         fields: str = 'title,abstract,externalIds,year,publicationTypes',
                         num_results: int = 50,
                         filtered: bool = False) -> list[dict]:
    """
    Paper relevance search on Semantic Scholar. API documentation: https://api.semanticscholar.org/api-docs#tag/Paper-Data/operation/get_graph_paper_relevance_search

    return example:
    [
        {
            "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
            "externalIds": {
            "DOI": "10.1145/3292500.3330665",
            "ArXiv": "1905.12616",
            "PubMed": "31199361",
            },
            "title": "Construction of the Literature Graph in Semantic Scholar",
            "abstract": "We describe a deployed scalable system ...",
        }
    ]
    """
    result = SemanticBulkSearchAPI().query(query, year, document_type, fields_of_study, fields, num_results, filtered)
    print("semantic_bulk_search result num:", len(result))
    for i, r in enumerate(result):
        r['semantic_order'] = i
        if 'externalIds' not in r:
            r['externalIds'] = {}
        if 'openAccessPdf' in r and r['openAccessPdf']:
            r['openAccessPdf'] = r['openAccessPdf'].get('url', '')
        r['doi'] = r['externalIds'].get('DOI', '')
        r['pmid'] = r['externalIds'].get('PubMed', '')
        r['types'] = r.get('publicationTypes', [])
        r['year'] = r.get('year', '')
        if 'publicationTypes' in r:
            del r['publicationTypes']
        if 'paperId' in r:
            del r['paperId']
        del r['externalIds']
    return result


def wos_search(api_key: str,
               query: str,
               query_type: str = 'TS',
               year: str = "",
               document_type: str = '',
               limit: int = 50,
               sort_field: str = 'RS+D') -> list[dict]:
    """
    Search literatures on Web of Science. API documentation: https://developer.clarivate.com/apis/wos-search
    return example:
    [
        {
            "uid":'xxx',
            "title": "Construction of the Literature Graph in Semantic Scholar",
            "doi": "10.1145/3292500.3330665",
            'pmid': '31199361',
        }
    ]
    """
    result = WosSearchAPI(api_key).search(query, query_type, year, document_type, limit, sort_field)
    print("wos_search result num:", len(result))
    for i, r in enumerate(result):
        r['wos_order'] = i
    return result


def merge_and_deduplicate(list_a: list[dict], list_b: list[dict]) -> list[dict]:
    # 合并两个列表
    combined_list = list_a + list_b

    # 使用一个字典来存储去重后的结果，键是(doi, pmid, title)的组合，值是文献信息字典
    merged_dict = {}

    for entry in combined_list:
        doi = entry.get('doi')
        pmid = entry.get('pmid')
        title = entry.get('title')
        abstract = entry.get('abstract')

        # 根据优先级确定去重的键
        if doi:
            key = doi.lower()
        elif pmid:
            key = pmid.lower()
        elif title:
            key = title.lower()
        else:
            continue

        if key in merged_dict:
            # update entry
            for k, v in entry.items():
                if k not in merged_dict[key] or not merged_dict[key][k]:
                    merged_dict[key][k] = v
        else:
            # 创建新条目，并初始化orders列表
            new_entry = entry.copy()
            # entry中可能不包含abstract字段
            new_entry['abstract'] = abstract
            merged_dict[key] = new_entry

    # 将字典转换回列表形式
    deduplicated_list = list(merged_dict.values())

    print("merge_and_deduplicate result num:", len(deduplicated_list))
    # print("example of merged_and_deduplicated result: ", deduplicated_list[0])

    return deduplicated_list


class PaperSearchAPI:
    """
    A tool for searching literatures on Semantic Scholar.
    """
    wos_api_key: str = None
    pubmed_search_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
    pubmed_fetch_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?"
    max_retry: int = 5
    sleep_time: float = 1.0

    def __init__(self, api_key: str = None):
        self.wos_api_key = api_key

    def pubmed_search_urllib(self, pmid: str):
        url = self.pubmed_fetch_url + f"db=pubmed&id={pmid}&retmode=xml"
        retry = 0
        while True:
            try:
                result = urllib.request.urlopen(url)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and retry < self.max_retry:
                    # Too Many Requests error
                    # wait for an exponentially increasing amount of time
                    print(
                        f"Too Many Requests, "
                        f"waiting for {self.sleep_time:.2f} seconds..."
                    )
                    time.sleep(self.sleep_time)
                    self.sleep_time *= 2
                    retry += 1
                else:
                    raise e

        xml_text = result.read().decode("utf-8")

        # Get title
        title = ""
        if "<ArticleTitle>" in xml_text and "</ArticleTitle>" in xml_text:
            start_tag = "<ArticleTitle>"
            end_tag = "</ArticleTitle>"
            title = xml_text[
                    xml_text.index(start_tag) + len(start_tag): xml_text.index(end_tag)
                    ]

        # Get abstract
        abstract = ""
        if "<AbstractText>" in xml_text and "</AbstractText>" in xml_text:
            start_tag = "<AbstractText>"
            end_tag = "</AbstractText>"
            abstract = xml_text[
                       xml_text.index(start_tag) + len(start_tag): xml_text.index(end_tag)
                       ]

        # Get publication date
        # pub_date = ""
        # if "<PubDate>" in xml_text and "</PubDate>" in xml_text:
        #     start_tag = "<PubDate>"
        #     end_tag = "</PubDate>"
        #     pub_date = xml_text[
        #                xml_text.index(start_tag) + len(start_tag): xml_text.index(end_tag)
        #                ]

        # Return article as dictionary
        article = {
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
        }
        return article

    def pubmed_search_requests_xml(self, pmid_list: str | list, ) -> list[dict]:
        if isinstance(pmid_list, list):
            pmid_list = ",".join(str(pmid) for pmid in pmid_list)
        # 构建请求URL
        url = self.pubmed_fetch_url + f"db=pubmed&id={pmid_list}&retmode=xml"

        retry = 0
        while True:
            try:
                # 发送HTTP GET请求
                response = requests.get(url)
                if response.status_code == 429:
                    print(
                        f"Too Many Requests, "
                        f"waiting for {self.sleep_time:.2f} seconds..."
                    )
                    time.sleep(self.sleep_time)
                    self.sleep_time *= 2
                    retry += 1
                elif response.status_code != 200:
                    response.raise_for_status()
                else:
                    break
            except Exception as e:
                print(f"Error in pubmed_search_requests_xml: {e}")
                return []

        # 解析返回的XML数据
        root = ET.fromstring(response.content)

        # 输出摘要信息
        result = []
        for article in root.findall(".//PubmedArticle"):
            pmid = article.find(".//PMID").text
            title = article.find(".//ArticleTitle")
            title_text = title.text if title is not None else ""
            abstract = article.find(".//AbstractText")
            abstract_text = abstract.text if abstract is not None else ""

            result.append({
                "pmid": pmid,
                "title": title_text,
                "abstract": abstract_text,
            })
        return result

    def pubmed_search_requests(self, pmid_list: str | list, ) -> list[dict]:
        if isinstance(pmid_list, list):
            pmid_list = ",".join(str(pmid) for pmid in pmid_list)
        # 构建请求URL
        url = self.pubmed_fetch_url + f"db=pubmed&id={pmid_list}&retmode=xml"

        retry = 0
        while True:
            try:
                # 发送HTTP GET请求
                response = requests.get(url)
                if response.status_code == 429:
                    print(
                        f"Too Many Requests, "
                        f"waiting for {self.sleep_time:.2f} seconds..."
                    )
                    time.sleep(self.sleep_time)
                    self.sleep_time *= 2
                    retry += 1
                elif response.status_code != 200:
                    response.raise_for_status()
                else:
                    break
            except Exception as e:
                print(f"Error in pubmed_search_requests for pmid {pmid_list}: ", e)
                # raise e
                return []

        xml_text = response.content.decode("utf-8")
        abstracts = re.findall(r'<AbstractText>(.*?)</AbstractText>', xml_text, re.DOTALL)
        titles = re.findall(r'<ArticleTitle>(.*?)</ArticleTitle>', xml_text, re.DOTALL)
        # 输出摘要信息
        result = []
        for pmid, title, abstract in zip(pmid_list, titles, abstracts):
            title_text = title if title is not None else ""
            abstract_text = abstract if abstract is not None else ""
            result.append({
                "pmid": pmid,
                "title": title_text,
                "abstract": abstract_text,
            })
        return result

    def get_pmid_by_doi(self, doi: str) -> str:
        esearch_url = self.pubmed_search_url + f"db=pubmed&term={doi}[DOI]"
        try:
            esearch_response = requests.get(esearch_url)
            esearch_tree = ET.fromstring(esearch_response.content)
            pmid = esearch_tree.findtext('IdList/Id')
        except Exception as e:
            print(f"Error in get_pmid_by_doi for doi {doi}: {e}")
            return ""
        return pmid

    def search(self, query: str,
               year: str = '',
               document_type: str = '',
               fields_of_study: str = '',
               fields: str = 'title,abstract,externalIds,openAccessPdf,year,publicationTypes',
               wos_num: int = 80,
               semantic_num: int = 20,
               filtered: bool = True) -> list[dict]:
        """
        Search literature using SemanticScholar and Web of Science.
        """
        # first, use SemanticScholar to search literature
        # filtered set False to get all results
        semantic_result = semantic_bulk_search(query, year, document_type, fields_of_study, fields, semantic_num, filtered=False)

        # second, use Web of Science to search literature
        wos_result = wos_search(self.wos_api_key, query, query_type='TS', year=year, document_type=document_type, limit=wos_num)

        # third, merge the results
        result = []
        without_abstract_doi = []
        without_abstract_pmid = []
        filtered_result = []
        for r in merge_and_deduplicate(semantic_result, wos_result):
            if not r['abstract']:
                if r['doi']:
                    without_abstract_doi.append(r)
                elif r['pmid']:
                    without_abstract_pmid.append(r)
                else:
                    filtered_result.append(r)
                    print(f"Warning: no DOI or PMID for the following result: {r['title']}")
            else:
                # add the result to the final list if it has an abstract
                result.append(r)
        print(f"Found {len(result)} results with abstracts.")
        print(f"Found {len(without_abstract_doi)} results without abstracts but with DOIs.")
        print(f"Found {len(without_abstract_pmid)} results without abstracts but with PMIDs.")

        # get abstracts with doi by SemanticScholar
        if without_abstract_doi:
            search_dois = [r['doi'] for r in without_abstract_doi]
            search_doi_str = [f"DOI:{doi}" for doi in search_dois]
            if len(search_doi_str) > 500:
                doi_str_list = np.array_split(search_doi_str, len(search_doi_str) // 500 + 1)
                doi_search_results = []
                for doi_str in doi_str_list:
                    doi_search_results.extend(SemanticScholarBatchAPI().query(doi_str, fields, filtered=True))
            else:
                doi_search_results = SemanticScholarBatchAPI().query(search_doi_str, fields, filtered=True)
            print(f"Found {len(doi_search_results)} results with abstracts by DOI.")

            remove_index = []
            for search_result in doi_search_results:
                index = search_doi_str.index(search_result['id'])
                r = without_abstract_doi[index]
                r['title'] = search_result['title']
                r['abstract'] = search_result['abstract']
                result.append(r)
                remove_index.append(index)

            without_abstract_doi = [r for i, r in enumerate(without_abstract_doi) if i not in remove_index]
            print(f"Found {len(without_abstract_doi)} results without abstracts by DOI.")

        # fourth, use PubMed to search literature whose abstracts are not available in SemanticScholar and Web of Science
        if without_abstract_doi:
            # get PMIDs by DOIs
            for r in without_abstract_doi:
                try:
                    pmid = self.get_pmid_by_doi(r['doi'])
                    if pmid:
                        r['pmid'] = pmid
                        without_abstract_pmid.append(r)
                    else:
                        filtered_result.append(r)
                except Exception as e:
                    print(f"Error: {e}")
                    filtered_result.append(r)
        if without_abstract_pmid:
            print(f"Found {len(without_abstract_pmid)} results without abstracts but with PMIDs.")
            pmids = [r['pmid'] for r in without_abstract_pmid]
            pubmed_result = self.pubmed_search_requests(pmids)
            if not pubmed_result:
                filtered_result.extend(without_abstract_pmid)
            else:
                for r, pubmed_r in zip(without_abstract_pmid, pubmed_result):
                    if pubmed_r['abstract']:
                        r['title'] = pubmed_r['title']
                        r['abstract'] = pubmed_r['abstract']
                        result.append(r)
                    else:
                        filtered_result.append(r)

        for r in result:
            r['url'] = f"https://doi.org/{r['doi']}" if r['doi'] else f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}"

        if not filtered:
            for r in filtered_result:
                if r['doi']:
                    r['url'] = f"https://doi.org/{r['doi']}"
                elif r['pmid']:
                    r['url'] = f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}"
                else:
                    r['url'] = ''
                if not r.get('title'):
                    r['title'] = ''
                if not r.get('abstract'):
                    r['abstract'] = ''

            result.extend(filtered_result)

        print(f"Total number of results: {len(result)}")
        return result


class LiteratureSearchTool(BuiltinTool):
    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        Invokes the SemanticScholar search tool with the given user ID and tool parameters.

        Args:
            user_id (str): The ID of the user invoking the tool.
            tool_parameters (dict[str, Any]): The parameters for the tool, including the 'query' parameter.

        Returns:
            ToolInvokeMessage | list[ToolInvokeMessage]: The result of the tool invocation, which can be a single message or a list of messages.
        """
        query = tool_parameters.get('query')
        if not query:
            raise ToolParameterValidationError('query is required.')

        if not query:
            raise ToolParameterValidationError('query is required.')

        year = tool_parameters.get('year')
        if not year:
            year = "1960-{}".format(datetime.now().year)

        document_type = tool_parameters.get('document_type', 'All')

        fields_of_study = tool_parameters.get('fields_of_study')
        if not fields_of_study:
            fields_of_study = 'Medicine,Biology,Chemistry'

        wos_num = tool_parameters.get('wos_num')
        if not wos_num:
            wos_num = 80
        semantic_num = tool_parameters.get('semantic_num')
        if not semantic_num:
            semantic_num = 20

        fields = tool_parameters.get('fields')
        if not fields:
            fields = 'title,abstract,externalIds,openAccessPdf,year,publicationTypes'

        filtered = tool_parameters.get('filtered', True)

        api_key = tool_parameters.get('wos_api_key')
        if not api_key:
            api_key = self.runtime.credentials['wos_api_key']

        result = PaperSearchAPI(api_key).search(query, year, document_type, fields_of_study, fields=fields,
                                                wos_num=wos_num, semantic_num=semantic_num, filtered=filtered)

        # return self.create_text_message(json.dumps(result))
        return [self.create_json_message(r) for r in result]
