from aiohttp import web


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


app = web.Application()
app.add_routes([web.get('/', handle)])

if __name__ == '__main__':
    web.run_app(app)
