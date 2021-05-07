import aiofiles

from typing import List, Tuple
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup, element


def extract_sanitizer_name(url: str) -> str:
    domain: str = urlparse(url).netloc
    return '_'.join(domain.split('.'))


def extract_title(html: str) -> str:
    soup: BeautifulSoup = BeautifulSoup(html, 'html.parser')
    meta_title_tag: element.Tag = soup.find("meta",  {"property": "og:title"})
    if meta_title_tag:
        return meta_title_tag["content"]


def load_dictionaries(path: str = 'charged_dict') -> Tuple[str]:
    dictionary_directory = Path.joinpath(Path('.'), path)
    dictionary: List[str] = []
    for dictionary_file in dictionary_directory.iterdir():
        with open(file=dictionary_file, mode='r') as file:
            file_content: str = file.read()
            dictionary.extend((file_content.strip().split('\n')))
    return tuple(dictionary)
