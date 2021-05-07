import logging
import pymorphy2
from aiohttp import web
import functools
from main import articles_filter_handler
from utils.utils import load_dictionaries

logger = logging.getLogger('server')


async def handle(request):

    if request.rel_url.query.get('urls') is None:
        return web.json_response({
            "error": "no one url requested"
        }, status=400)

    urls = request.rel_url.query['urls'].split(',')

    if len(urls) > 10:
        return web.json_response({
            "error": "too many urls in request, should be 10 or less"
        }, status=400)

    return web.json_response({
        'urls': urls})


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
    app.add_routes([web.get('/', prepared_articles_filter_handler)])
    web.run_app(app)
