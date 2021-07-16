from anyio import create_task_group
from async_timeout import timeout

import aiohttp
from aiohttp.client_exceptions import ClientConnectorError,\
    ClientError, ClientResponseError
from asyncio.exceptions import TimeoutError
from enum import Enum

from typing import List, Tuple, Dict


from adapters import SANITIZERS
from adapters.exceptions import ArticleNotFound, SanitizerNotFound
from text_tools import split_by_words, calculate_jaundice_rate
from utils.timer import elapsed_timer
from utils.utils import extract_sanitizer_name, extract_title, is_url

import pytest
from pymorphy2 import MorphAnalyzer
from utils.utils import load_dictionaries
import functools
from aiohttp import web
import logging


TIMEOUT = 3

logger = logging.getLogger('server')


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
            article: str = html if skip_sanitizer else get_sanitizer(
                sanitizer_name=domain_name)(html, plaintext=True)

            with elapsed_timer() as timer:
                article_words: List[str] = await split_by_words(
                    morph=morph,
                    text=article,
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

    if not all(is_url(url) for url in urls):
        return aiohttp.web.json_response({
            "error": "should contain urls only"
        }, status=400)
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

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)

    morph = MorphAnalyzer()

    charged_words = load_dictionaries(
        path='charged_dict')

    prepared_articles_filter_handler = functools.partial(
        articles_filter_handler,
        morph,
        charged_words
    )
    app = web.Application()
    app.add_routes([web.get('/',
                            prepared_articles_filter_handler)])
    web.run_app(app)


@pytest.mark.parametrize(
    'expected_status_per_url',
    [
        {'https://inosmi.ru/social/20210424/249625353.html':
            (ProcessingStatus.OK,)},
        {
            'https://inosmi.ru/social/20210424/249625353.html': (
                ProcessingStatus.OK,),
            'https://inosmi.ru/social/20210425/249629422.html': (
                ProcessingStatus.OK,)
        },
        {
            'https://inosmi_broken.ru/social/20210424/249625353.html': (
                ProcessingStatus.FETCH_ERROR,
                ProcessingStatus.TIMEOUT)
        },
        {
            'some_url': (
                ProcessingStatus.FETCH_ERROR,
                ProcessingStatus.TIMEOUT),
            'https://ru.ru': (
                ProcessingStatus.FETCH_ERROR, ProcessingStatus.TIMEOUT),
            'https://httpstat.us/500': (ProcessingStatus.FETCH_ERROR, ),
            'https://httpstat.us/400': (ProcessingStatus.FETCH_ERROR, )
        },
        {
            'https://absent_url.org': (ProcessingStatus.FETCH_ERROR,
                                       ProcessingStatus.TIMEOUT),
            'https://inosmi.ru/social/20210424/249625353.html': (
                ProcessingStatus.OK,),
            'http://example.com': (ProcessingStatus.PARSING_ERROR,
                                   ProcessingStatus.TIMEOUT),
            'https://inosmi.ru/social/20210425/249629422.html': (
                ProcessingStatus.OK,),
            'some_url': (ProcessingStatus.FETCH_ERROR,
                         ProcessingStatus.TIMEOUT),
        },
    ],
)
@pytest.mark.parametrize('anyio_backend', ['asyncio'])
async def test_process_article(anyio_backend, expected_status_per_url):
    url_results = []
    async with aiohttp.ClientSession() as session:
        morph = MorphAnalyzer()
        charged_words = charged_words = load_dictionaries(
            path='charged_dict')

        async with create_task_group() as task_group:
            for url in expected_status_per_url:
                await task_group.spawn(
                    process_article,
                    session,
                    morph,
                    charged_words,
                    url,
                    url_results,
                )

    assert len(url_results) == len(expected_status_per_url)

    for url_result in url_results:
        assert len(url_result) == 6
        assert url_result['url'] in expected_status_per_url
        expected_statuses = expected_status_per_url[url_result['url']]
        print(url_result['url'], url_result['status'])
        assert url_result['status'] in expected_statuses
        if url_result['status'] == ProcessingStatus.OK:
            assert all([url_result['rate'], url_result['words'],
                       url_result['processing_time']])
        else:
            assert all(
                [url_result['rate'] is None,
                 url_result['words'] is None,
                 url_result['processing_time'] is None]
            )


@pytest.mark.parametrize('anyio_backend', ['asyncio'])
async def test_too_big_article(anyio_backend):
    url = 'https://dvmn.org/media/filer_public/51/83/51830f54-7ec7-4702-847b-c5790ed3724c/gogol_nikolay_taras_bulba_-_bookscafenet.txt'
    async with aiohttp.ClientSession() as session:
        morph = MorphAnalyzer()
        charged_words = load_dictionaries(
            path='charged_dict')
        url_results = []
        await process_article(
            session,
            morph,
            charged_words,
            url,
            url_results,
            skip_sanitizer=True
        )
    assert len(url_results) == 1
    url_processing = url_results[0]
    assert len(url_processing) == 6
    assert url_processing['url'] == url
    assert url_processing['status'] == ProcessingStatus.TIMEOUT
    assert all(
        [url_processing['rate'] is None, url_processing['words']
            is None, url_processing['processing_time'] is None]
    )
