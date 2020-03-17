from protocol import LibraAddress
from protocol_messages import CommandResponseObject
from business import VASPInfo

from flask import Flask, request
from flask.views import MethodView
import requests
from urllib.parse import urljoin
import json


class Networking:
    def __init__(self, vasp, info_context):
        self.app = Flask(__name__)
        self.vasp = vasp
        self.info_context = info_context

        # Register paths.
        self.app.add_url_rule(
            f'/{self.vasp.get_vasp_address().plain()}/<other_addr>/process/',
            view_func=VASPOffChainApi.as_view('vasp_api', self.vasp)
        )

    def run(self):
        self.app.run()

    def get_url(self, other_addr):
        base_url = self.info_context.get_base_url()
        my_addr = self.vasp.get_vasp_address()
        url = f'{other_addr.plain()}/{my_addr.plain()}/process/'
        return urljoin(base_url, url)

    def send_request(self, url, other_addr, json_request):
        # TODO: Where to handle network errors? Here or in channel?
        response = requests.post(url, json=json_request)
        channel = self.vasp.get_channel(other_addr)
        channel.parse_handle_response(json.dumps(response.json()))


class VASPOffChainApi(MethodView):
    def __init__(self, vasp):
        self.vasp = vasp

    def post(self, other_addr):
        request_json = request.get_json()
        channel = self.vasp.get_channel(LibraAddress(other_addr))
        response = channel.parse_handle_request(request_json)
        assert str(response.type) == str(CommandResponseObject)
        return response.content
