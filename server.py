from aiohttp import web


async def handle(request):
    if request.rel_url.query.get('urls'):
        data = {'urls': request.rel_url.query['urls'].split(',')}
        return web.json_response(data)
    return web.Response(text="No one url has been requested")


app = web.Application()
app.add_routes([web.get('/', handle)])

if __name__ == '__main__':
    web.run_app(app)
