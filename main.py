import aiohttp
import asyncio

from urllib.parse import urlparse

from adapters import SANITIZERS


def extract_sanitazer_name(url: str) -> str:
    domain: str = urlparse(url).netloc
    return '_'.join(domain.split('.'))


async def fetch(session: aiohttp.client.ClientSession,
                url: str) -> str:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def main():
    url: str = 'https://inosmi.ru/social/20210424/249625353.html'
    sanitazer_name: str = extract_sanitazer_name(url=url)
    sanitizer: function = SANITIZERS.get(sanitazer_name)

    async with aiohttp.ClientSession() as session:
        html: str = await fetch(session, url)
        print(sanitizer(html, plaintext=True))

if __name__ == '__main__':
    asyncio.run(main())
