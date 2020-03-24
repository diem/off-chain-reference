from libra_address import LibraAddress
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

    def __init__(self, vasp):
        self.app = Flask(__name__)
        self.vasp = vasp

        # Register paths.
        self.app.add_url_rule(
            f'/{self.vasp.get_vasp_address().plain()}/<other_addr>/process/',
            view_func=VASPOffChainApi.as_view('vasp_api', self.vasp)
        )

    def run(self):
        self.app.run()

    @staticmethod
    def get_url(base_url, my_addr, other_addr):
        url = f'{other_addr.plain()}/{my_addr.plain()}/process/'
        return urljoin(base_url, url)

    @staticmethod
    def send_request(url, json_request):
        try:
            return requests.post(url, json=json_request)
        except Exception:
            return None


class VASPOffChainApi(MethodView):
    def __init__(self, vasp):
        self.vasp = vasp

    def get(self):
        """ This path is not registered; used by subclasses for debugging. """
        return {"status": "success"}

    def post(self, other_addr):
        try:
            client_certificate = request.environ['peercert']
        except Exception as e:
            client_certificate = None

        if not self.vasp.info_context.is_authorised_VASP(client_certificate):
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
