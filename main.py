import aiohttp
import asyncio

from urllib.parse import urlparse
from pymorphy2 import MorphAnalyzer

from adapters import SANITIZERS
from text_tools import split_by_words, calculate_jaundice_rate


def extract_sanitizer_name(url: str) -> str:
    domain: str = urlparse(url).netloc
    return '_'.join(domain.split('.'))


async def fetch(session: aiohttp.client.ClientSession,
                url: str) -> str:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def main():
    url: str = 'https://inosmi.ru/social/20210424/249625353.html'
    sanitizer_name: str = extract_sanitizer_name(url=url)
    sanitizer: function = SANITIZERS.get(sanitizer_name)
    charged_words: list[str] = [
        'украина',
        'военный',
        'война',
    ]
    morph: MorphAnalyzer = MorphAnalyzer()

    async with aiohttp.ClientSession() as session:
        html: str = await fetch(session, url)
        sanitized_article: str = sanitizer(html, plaintext=True)

        article_words: list[str] = split_by_words(
            morph=morph, text=sanitized_article)
        yellow_rate: float = calculate_jaundice_rate(
            article_words=article_words,
            charged_words=charged_words)
            
        print('Рейтинг: ', yellow_rate)
        print('Слов в статье:', len(article_words))

if __name__ == '__main__':
    asyncio.run(main())
