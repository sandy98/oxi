
async def test_app(scope, _, send):
    path = scope.get('path')
    name = path[1:].title() if path != "/" else "World!" 
    response = f"<h1>Hello, {name}!</h1>".encode('latin-1')
    headers = [
                (b'content-length', str(len(response)).encode('latin-1')),
                (b'content-type', b'text/html; charset=latin-1')
               ] 
    startdict = {
        'type': 'http.response.start',
        'status': 200,
        'headers': headers
    }
    bodydict = {
        'type': 'http.response.body',
        'body': response,
        'more_body': False
    }

    await send(startdict)
    return await send(bodydict)

async def not_found(scope, _, send):
    path = scope.get('path')
    response = f"<h3>No sea pelotudo, {path} no existe!</h3>".encode('latin-1')
    headers = [
                (b'content-length', str(len(response)).encode('latin-1')),
                (b'content-type', b'text/html; charset=latin-1')
               ] 
    startdict = {
        'type': 'http.response.start',
        'status': 404,
        'headers': headers
    }
    bodydict = {
        'type': 'http.response.body',
        'body': response,
        'more_body': False
    }

    await send(startdict)
    return await send(bodydict)

def wsgi_app(environ, start_response):
    path = environ.get('PATH_INFO')
    name = path[1:].title() if path != "/" else "World!" 
    response = f"<h1>Hello, {name}!</h1>".encode('latin-1')
    headers = [
                (b'content-length', str(len(response)).encode('latin-1')),
                (b'content-type', b'text/html; charset=latin-1')
               ] 

    start_response("200 OK", headers)
    return response
