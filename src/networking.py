from protocol import LibraAddress
from protocol_messages import CommandResponseObject
from business import VASPInfo

from flask import Flask, request, abort
from flask.views import MethodView
import requests
from urllib.parse import urljoin
import json
import sys


class Networking:

    BUSINESS_INTERUPT_RESPONSE = {"status": "interupt"}

    def __init__(self, vasp, context):
        self.app = Flask(__name__)
        self.vasp = vasp
        self.context = context

        # Register paths.
        self.app.add_url_rule(
            f'/{self.vasp.get_vasp_address().plain()}/<other_addr>/process/',
            view_func=VASPOffChainApi.as_view(
                'vasp_api', self.vasp, self.context
            )
        )

    def run(self):
        self.app.run()

    def get_url(self, other_addr):
        base_url = self.context.get_peer_base_url(other_addr)
        my_addr = self.vasp.get_vasp_address()
        url = f'{other_addr.plain()}/{my_addr.plain()}/process/'
        return urljoin(base_url, url)

    def send_request(self, url, other_addr, json_request):
        try:
            response = requests.post(url, json=json_request)
            self._handle_response(other_addr, response)
        except Exception:
            pass

    def _handle_response(self, other_addr, response):
        channel = self.vasp.get_channel(other_addr)
        channel.parse_handle_response(json.dumps(response.json()))


class VASPOffChainApi(MethodView):
    def __init__(self, vasp, context):
        self.vasp = vasp
        self.context = context

    def get(self):
        """ This path is not registered; used by subclasses for debugging. """
        return {"status": "success"}

    def post(self, other_addr):
        try:
            client_certificate = request.environ['peercert']
        except Exception as e:
            client_certificate = None

        if not self.context.is_authorised_VASP(client_certificate):
            abort(401)
        request_json = request.get_json()
        channel = self.vasp.get_channel(LibraAddress(other_addr))
        try:
            response = channel.parse_handle_request(request_json)
        except Exception:
            abort(400)
        if response != None:
            return response.content
        else:
            return Networking.BUSINESS_INTERUPT_RESPONSE
