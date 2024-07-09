import json
import logging
import re
import time
from typing import Any
import requests
from lxml import etree
from core.tools.entities.tool_entities import ToolInvokeMessage
from core.tools.errors import ToolParameterValidationError
from core.tools.tool.builtin_tool import BuiltinTool

logger = logging.getLogger(__name__)


class NCBIBlASTTool(BuiltinTool):
    """
    A tool to search for similar sequences in the NCBI database using BLAST.
    api document: https://ncbi.github.io/blast-cloud/dev/api.html
    """
    base_url: str = "https://blast.ncbi.nlm.nih.gov/Blast.cgi?"
    base_efetch_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def put_request(self, query: str, db: str, program: str) -> str | None:
        url = f"{self.base_url}QUERY={query}&DATABASE={db}&PROGRAM={program}&CMD=Put"
        response = requests.put(url)
        response.raise_for_status()

        task_result = etree.HTML(response.content.decode('utf-8'))
        rid = task_result.xpath('//input[@name="RID" and @id="rid"]/@value')
        if not rid:
            print("No RID found")
            return None
        assert len(rid) == 1
        rid = rid[0]
        print("RID: ", rid)
        return rid

    def get_task_status(self, rid: str) -> bool:
        while True:
            response = requests.get(f"{self.base_url}CMD=Get&FORMAT_OBJECT=SearchInfo&RID={rid}")
            response.raise_for_status()
            search_info = etree.HTML(response.content.decode('utf-8'))
            try:
                task_status = search_info.xpath('//*[@id="statInfo"]/@class')[0]
                if task_status == "READY":
                    print("task_status: ", task_status)
                    print("Search finished")
                    break
                else:
                    time.sleep(30)
            except IndexError:
                print("No task status found")
                return False
        return True

    def get_protein_info(self, protein_id: str, db: str = "protein") -> list[str]:
        params = {
            "db": db,
            "id": protein_id,
            "rettype": "gp",
            "retmode": "JSON"
        }
        response = requests.get(self.base_efetch_url, params=params)
        response.raise_for_status()
        content = response.content.decode('utf-8')
        pubmed_ids = re.findall(r'\bPUBMED\s+(\d+)', content)
        return pubmed_ids

    def get_task_result(self, rid: str, num_results: int = 50) -> tuple[list[dict], list[str]]:
        response = requests.get(f"{self.base_url}CMD=Get&RID={rid}&FORMAT_TYPE=HTML")
        response.raise_for_status()
        search_result = etree.HTML(response.content.decode('utf-8'))
        # accession_ids = search_result.xpath('//*[@id="dscTable"]//input[@class="cb"]/@value')
        accession_ids = search_result.xpath('//*[@id="dscTable"]//td[@class="c12 l lim"]/a/text()')  # accession
        percent_identity_score = search_result.xpath('//*[@id="dscTable"]//td[@class="c10"]/text()')  # percent identity
        # percent_identity_score = [float(score.replace("%", "")) for score in percent_identity_score]
        assert len(accession_ids) == len(percent_identity_score)

        results = []
        all_pubmed_ids = []
        for i in range(len(accession_ids)):
            if float(percent_identity_score[i].replace("%", "")) < 90:
                break
            try:
                # get protein references
                pubmed_ids = self.get_protein_info(accession_ids[i])
                if len(pubmed_ids) > 0:
                    add_flag = False
                    for pubmed_id in pubmed_ids:
                        if pubmed_id not in all_pubmed_ids:
                            all_pubmed_ids.append(pubmed_id)
                            add_flag = True
                    # add the result if at least one new pubmed id is found
                    if add_flag:
                        results.append({
                            "accession_id": accession_ids[i],
                            "percent_identity_score": percent_identity_score[i],
                            "pubmed_ids": pubmed_ids
                        })
                if len(all_pubmed_ids) >= num_results:
                    break
            except Exception as e:
                print("Error: ", e)
                continue
            time.sleep(5)
        return results, all_pubmed_ids

    def blast(self, query: str, db: str, program: str, num_results: int = 50, rid: str = '') -> dict:
        """
        Perform a BLAST search with the given query and return the results which include the accession ID, percent identity score, and PubMed IDs.

        Args:
            query (str): The query sequence to search for.
            db (str): The database to search in.
            program (str): The BLAST program to use.
            num_results (int): The number of results to return.
            rid (str): The request ID of the search, if it has already been performed.
        """
        result = {
            "query": query,
        }
        # put request
        if not rid:
            rid = self.put_request(query, db, program)
            time.sleep(5)
        if not rid:
            return result
        result['rid'] = rid
        # get search status
        if not self.get_task_status(rid):
            return result
        time.sleep(5)
        # get search result :
        search_results, pubmed_ids = self.get_task_result(rid, num_results)

        result['results'] = search_results
        result['num_results'] = num_results
        result['pubmed_ids'] = pubmed_ids

        return result

    def _invoke(self, user_id: str, tool_parameters: dict[str, Any]) -> ToolInvokeMessage | list[ToolInvokeMessage]:
        """
        Invokes the PDBCitationsTools with the given user ID and tool parameters.

        Args:
            user_id (str): The ID of the user invoking the tool.
            tool_parameters (dict[str, Any]): The parameters for the tool, including the 'query' parameter.

        Returns:
            ToolInvokeMessage | list[ToolInvokeMessage]: The result of the tool invocation, which can be a single message or a list of messages.
        """
        query = tool_parameters.get("query")
        db = tool_parameters.get("db")
        program = tool_parameters.get("program")
        num_results = tool_parameters.get("num_results")
        rid = tool_parameters.get("rid")
        if not db:
            db = 'nr'
        if not program:
            program = 'blastp'
        if not num_results:
            num_results = 50
        if not query and not rid:
            raise ToolParameterValidationError('query or rid is required.')

        result = self.blast(query, db, program, num_results, rid)
        return self.create_json_message(result)
