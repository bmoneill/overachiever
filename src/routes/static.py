from flask import send_from_directory, make_response

from .. import app

@app.route('/static/<path:filename>')
def static(filename):
    resp = make_response(send_from_directory('static/', filename))
    resp.headers['Cache-Control'] = 'max-age=1209600'
    return resp
