from re import S
from anyio import create_task_group, run
from async_timeout import timeout

import aiohttp
from aiohttp.client_exceptions import ClientConnectorError, ClientError, ClientResponseError
from asyncio.exceptions import TimeoutError
from enum import Enum

from typing import List, Tuple, Dict

from pymorphy2 import MorphAnalyzer

from adapters import SANITIZERS
from adapters.exceptions import ArticleNotFound
from text_tools import split_by_words, calculate_jaundice_rate
from utils.timer import elapsed_timer
from utils.utils import extract_sanitizer_name, load_dictionaries, extract_title

import logging

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
TIMEOUT = 10


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
        raise ArticleNotFound(sanitizer_name)
    return sanitizer


async def process_article(
        session: aiohttp.client.ClientSession,
        morph: MorphAnalyzer,
        charged_words: Tuple[str],
        url: str,
        sites_ratings: List[Dict]):

    yellow_rate = None
    words_count = None
    processing_time = None
    article_title = None
    try:
        async with timeout(TIMEOUT):
            html: str = await fetch(session, url)

            article_title: str = extract_title(html)

            domain_name = extract_sanitizer_name(url=url)
            if domain_name == 'dvmn_org':
                sanitized_article = html
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

    except ArticleNotFound:
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


def output_sites_results(sites_ratings:  List[Dict]) -> None:
    for site in sites_ratings:
        logging.info(F'Url: {site["url"]}')
        logging.info(f'Заголовок статьи:{site["title"]}')
        logging.info('Рейтинг:', site['rate'])
        logging.info('Слов в статье:', site['words'])
        logging.info('Статус:', site['status'].name)
        if site["processing_time"]:
            logging.info(f'Анализ закончен за {site["processing_time"]} сек.')


async def main():
    charged_words = await load_dictionaries(
        path='charged_dict')
    morph: MorphAnalyzer = MorphAnalyzer()
    sites_ratings: List[Dict] = []
    async with aiohttp.ClientSession() as session:
        async with create_task_group() as tg:
            for url in TEST_ARTICLES:
                tg.start_soon(
                    process_article, session,
                    morph, charged_words, url,
                    sites_ratings
                )
    output_sites_results(sites_ratings)


async def articles_filter_handler(request):
    charged_words = await load_dictionaries(
        path='charged_dict')
    morph: MorphAnalyzer = MorphAnalyzer()
    sites_ratings: List[Dict] = []
    async with aiohttp.ClientSession() as session:
        async with create_task_group() as tg:
            for url in TEST_ARTICLES:
                tg.start_soon(
                    process_article, session,
                    morph, charged_words, url,
                    sites_ratings
                )
    output_sites_results(sites_ratings)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run(main)
