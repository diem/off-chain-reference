from sample_service import sample_vasp
from protocol import LibraAddress

from flask import Flask, jsonify, request
import json

app = Flask(__name__)
app.vasp = sample_vasp(LibraAddress.encode_to_Libra_address(b'B'*16))


@app.route('/')
def index():
    return jsonify(status='OK', message='Hello, world!')


@app.route('/process', methods=['POST'])
def process():
    request_json = request.get_json()

    # Recover client's address
    # This seems ugly -- fix it.
    diff = json.loads(request_json)['command']['diff']
    sender_addr = diff['sender']['address']
    receiver_addr = diff['receiver']['address']
    other_addr = [sender_addr, receiver_addr][app.vasp.my_addr == sender_addr]

    app.vasp.process_request(LibraAddress(other_addr), request_json)
    responses = app.vasp.collect_messages()
    responses_json = [command.content for command in responses]
    return jsonify(responses_json)


@app.route('/process', methods=['POST'])
def process():
    request_json = request.get_json()

    # Recover client's address
    # This seems ugly -- fix it.
    diff = json.loads(request_json)['command']['diff']
    sender_addr = diff['sender']['address']
    receiver_addr = diff['receiver']['address']
    other_addr = [sender_addr, receiver_addr][app.vasp.my_addr == sender_addr]

    app.vasp.process_request(LibraAddress(other_addr), request_json)
    responses = app.vasp.collect_messages()
    responses_json = [command.content for command in responses]
    return jsonify(responses_json)
