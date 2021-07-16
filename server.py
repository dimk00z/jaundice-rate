import logging
import pymorphy2
import functools
from aiohttp import web

from main import articles_filter_handler
from utils.utils import load_dictionaries


logger = logging.getLogger('server')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)

    morph = pymorphy2.MorphAnalyzer()

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
