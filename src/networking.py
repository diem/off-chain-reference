from sample_service import sample_vasp
from protocol import LibraAddress
from protocol_messages import CommandResponseObject

from flask import Flask, jsonify, request
from markupsafe import escape
import json

app = Flask(__name__)
app.vasp = sample_vasp(LibraAddress.encode_to_Libra_address(b'B'*16))


@app.route('/')
def index():
    return jsonify(status='OK', message='Hello, world!')


@app.route('/'+app.vasp.my_addr.plain()+'/<other_addr>/process/', methods=['POST'])
def process(other_addr):
    other_addr = escape(other_addr).striptags()
    request_json = request.get_json()
    app.vasp.process_request(LibraAddress(other_addr), request_json)
    responses = app.vasp.collect_messages()

    responses_json = []
    for command in responses:
        if str(command.type) == str(CommandResponseObject):
            responses_json.append(command.content)

    assert len(responses_json) == 1
    return responses_json[0]
