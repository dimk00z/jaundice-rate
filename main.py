import aiohttp
import asyncio
import aiofiles
from anyio import create_task_group, run

from bs4 import BeautifulSoup, element

from typing import List, Tuple

from urllib.parse import urlparse
from pymorphy2 import MorphAnalyzer
from pathlib import Path

from adapters import SANITIZERS
from text_tools import split_by_words, calculate_jaundice_rate

TEST_ARTICLES = (
    'https://inosmi.ru/social/20210424/249625353.html',
    'https://inosmi.ru/social/20210425/249629422.html',
    'https://inosmi.ru/politic/20210425/249629175.html',
    'https://inosmi.ru/social/20210425/249628917.html',
    'https://inosmi.ru/politic/20210425/249628769.html',
)


def extract_title(html: str) -> str:
    soup: BeautifulSoup = BeautifulSoup(html, 'html.parser')
    meta_title_tag: element.Tag = soup.find("meta",  {"property": "og:title"})
    return meta_title_tag["content"]


def extract_sanitizer_name(url: str) -> str:
    domain: str = urlparse(url).netloc
    return '_'.join(domain.split('.'))


async def load_dictionaries(path: str) -> Tuple[str]:
    dictionary_directory = Path.joinpath(Path('.'), path)
    dictionary: List[str] = []
    for dictionary_file in dictionary_directory.iterdir():
        async with aiofiles.open(file=dictionary_file, mode='r') as file:
            file_content: str = await file.read()
            dictionary.extend((file_content.strip().split('\n')))
    return tuple(dictionary)


async def fetch(
        session: aiohttp.client.ClientSession,
        url: str) -> str:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_article(
        session, morph, charged_words, url):

    sanitizer_name: str = extract_sanitizer_name(url=url)
    sanitizer: function = SANITIZERS.get(sanitizer_name)

    html: str = await fetch(session, url)
    article_title = extract_title(html)
    sanitized_article: str = sanitizer(html, plaintext=True)

    article_words: List[str] = split_by_words(
        morph=morph, text=sanitized_article)
    yellow_rate: float = calculate_jaundice_rate(
        article_words=article_words,
        charged_words=charged_words)
    words_count = len(article_words)

    if article_title:
        print(f'Заголовок статьи:{article_title}')
    print('Рейтинг:', yellow_rate)
    print('Слов в статье:', words_count)


async def main():
    charged_words = await load_dictionaries(
        path='charged_dict')
    morph: MorphAnalyzer = MorphAnalyzer()
    async with aiohttp.ClientSession() as session:
        async with create_task_group() as tg:
            for url in TEST_ARTICLES:
                tg.start_soon(process_article, session,
                              morph, charged_words, url)
    print('All tasks finished!')

if __name__ == '__main__':
    run(main)
