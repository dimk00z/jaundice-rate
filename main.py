from anyio import create_task_group, run
from async_timeout import timeout

import aiohttp
from aiohttp.client_exceptions import ClientConnectorError, ClientError, ClientResponseError
from asyncio.exceptions import TimeoutError
from enum import Enum

from typing import List, Tuple, Dict


from adapters import SANITIZERS
from adapters.exceptions import ArticleNotFound, SanitizerNotFound
from text_tools import split_by_words, calculate_jaundice_rate
from utils.timer import elapsed_timer
from utils.utils import extract_sanitizer_name, extract_title

import pytest
from pymorphy2 import MorphAnalyzer
from utils.utils import load_dictionaries

import logging


TIMEOUT = 3


class ProcessingStatus(Enum):
    OK = 'OK'
    FETCH_ERROR = 'FETCH_ERROR'
    PARSING_ERROR = 'PARSING_ERROR'
    TIMEOUT = 'TIMEOUT'


async def fetch(
        session: aiohttp.client.ClientSession,
        url: str) -> str:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


def get_sanitizer(sanitizer_name: str):
    sanitizer: function = SANITIZERS.get(sanitizer_name)
    if sanitizer is None:
        raise SanitizerNotFound(sanitizer_name)
    return sanitizer


async def process_article(
        session: aiohttp.client.ClientSession,
        morph: MorphAnalyzer,
        charged_words: Tuple[str],
        url: str,
        sites_ratings: List[Dict],
        skip_sanitizer: bool = False):

    yellow_rate = None
    words_count = None
    processing_time = None
    article_title = None
    try:
        async with timeout(TIMEOUT):
            html: str = await fetch(session, url)

            article_title: str = extract_title(html)

            domain_name = extract_sanitizer_name(url=url)
            if skip_sanitizer:
                sanitized_article: str = html
            else:
                sanitizer: function = get_sanitizer(
                    sanitizer_name=domain_name)
                sanitized_article: str = sanitizer(html, plaintext=True)

            with elapsed_timer() as timer:
                article_words: List[str] = await split_by_words(
                    morph=morph,
                    text=sanitized_article,
                    splitting_timeout=TIMEOUT)
            processing_time = round(timer.duration, 3)

            yellow_rate: float = calculate_jaundice_rate(
                article_words=article_words,
                charged_words=charged_words)
            words_count = len(article_words)
            status = ProcessingStatus.OK

    except (ClientConnectorError, ClientError, ClientResponseError):
        article_title: str = 'URL not exist'
        status = ProcessingStatus.FETCH_ERROR

    except (ArticleNotFound, SanitizerNotFound):
        status = ProcessingStatus.PARSING_ERROR

    except TimeoutError:
        status = ProcessingStatus.TIMEOUT

    sites_ratings.append(
        {
            'url': url,
            'title': article_title,
            'rate': yellow_rate,
            'words': words_count,
            'status': status,
            'processing_time': processing_time,
        }
    )


def combine_response(sites_ratings:  List[Dict]) -> None:
    response = []
    for site in sites_ratings:
        response.append(
            {
                'status': site["status"].name,
                'url': site["url"],
                'score': site["rate"],
                'words_count': site["words"],

            }
        )
    return response


async def articles_filter_handler(morph, charged_words, request):
    if request.rel_url.query.get('urls') is None:
        return aiohttp.web.json_response({
            "error": "no one url requested"
        }, status=400)

    urls = request.rel_url.query['urls'].split(',')

    if len(urls) > 10:
        return aiohttp.web.json_response({
            "error": "too many urls in request, should be 10 or less"
        }, status=400)

    sites_ratings: List[Dict] = []
    async with aiohttp.ClientSession() as session:
        async with create_task_group() as tg:
            for url in urls:
                tg.start_soon(
                    process_article, session,
                    morph, charged_words, url,
                    sites_ratings
                )
    response = combine_response(sites_ratings)

    logging.info(f'Response body: {response}')
    return aiohttp.web.json_response(response)


TEST_ARTICLES = (
    'https://inosmi_broken.ru/social/20210424/249625353.html',
    'https://lenta.ru/news/2021/04/26/zemlya/',
    'https://inosmi.ru/social/20210424/249625353.html',
    'https://inosmi.ru/social/20210425/249629422.html',
    'https://inosmi.ru/politic/20210425/249629175.html',
    'https://inosmi.ru/social/20210425/249628917.html',
    'https://inosmi.ru/politic/20210425/249628769.html',
    'https://dvmn.org/media/filer_public/51/83/51830f54-7ec7-4702-847b-c5790ed3724c/gogol_nikolay_taras_bulba_-_bookscafenet.txt'
)
# http://172.25.233.215:8080/?urls=https://inosmi.ru/politic/20210425/249628769.html,https://inosmi.ru/politic/20210425/249629175.html,https://inosmi.ru/social/20210425/249628917.html


# async def main():
#     charged_words = load_dictionaries(
#         path='charged_dict')
#     morph: MorphAnalyzer = MorphAnalyzer()
#     sites_ratings: List[Dict] = []
#     async with aiohttp.ClientSession() as session:
#         async with create_task_group() as tg:
#             for url in TEST_ARTICLES:
#                 tg.start_soon(
#                     process_article, session,
#                     morph, charged_words, url,
#                     sites_ratings
#                 )

# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG)
#     run(main)


@pytest.mark.parametrize('anyio_backend', ['asyncio'])
async def test_too_big_article(anyio_backend):
    url = 'https://dvmn.org/media/filer_public/51/83/51830f54-7ec7-4702-847b-c5790ed3724c/gogol_nikolay_taras_bulba_-_bookscafenet.txt'
    async with aiohttp.ClientSession() as session:
        morph = MorphAnalyzer()
        charged_words = load_dictionaries(
            path='charged_dict')
        sites_ratings = []
        await process_article(
            session,
            morph,
            charged_words,
            url,
            sites_ratings,
            skip_sanitizer=True
        )
    assert len(sites_ratings) == 1
    url_processing = sites_ratings[0]
    assert len(url_processing) == 6
    assert url_processing['url'] == url
    assert url_processing['status'] == ProcessingStatus.TIMEOUT
    assert all(
        [url_processing['rate'] is None, url_processing['words']
            is None, url_processing['processing_time'] == None]
    )
