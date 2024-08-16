# !/usr/bin/env python3
# _*_ coding:utf-8 _*_
"""
@File     : utils.py
@Time     : 2024/8/16 10:59
@Author   : Hjw
@License  : (C)Copyright 2018-2025
"""
import re


def extract_abstract(text: str) -> str:
    if not text:
        return ''
    # Define a regex pattern to match the content inside <jats:p> after <jats:title>Abstract</jats:title>
    pattern = r'<jats:title>Abstract</jats:title>\s*<jats:p>(.*?)</jats:p>'

    # Search for the pattern in the provided text
    match = re.search(pattern, text, re.DOTALL)

    # If a match is found, return the content; otherwise, return None
    if match:
        return match.group(1)
    return ''


def convert_time_str_to_seconds(time_str: str) -> int:
    # example: 1s -> 1,  1m30s -> 90, 1h30m -> 5400, 1h30m30s -> 5430
    time_str = time_str.lower().strip().replace(' ', '')
    seconds = 0
    if 'h' in time_str:
        hours, time_str = time_str.split('h')
        seconds += int(hours) * 3600
    if 'm' in time_str:
        minutes, time_str = time_str.split('m')
        seconds += int(minutes) * 60
    if 's' in time_str:
        seconds += int(time_str.replace('s', ''))
    return seconds


def get_basic_info(paper: dict) -> dict:
    result = {
        "title": paper.get('title', [''])[0],
        'doi': paper.get('DOI', ''),
        'url': paper.get('URL', ''),
        'abstract': extract_abstract(paper.get('abstract', ''))
    }

    for link in paper.get('link', []):
        if link['content-type'] == "application/pdf":
            result['pdf_url'] = link['URL']
            break
        else:
            # "text/html" or 'unspecified' or "text/xml" or "text/plain"
            result['html_url'] = link['URL']

    return result