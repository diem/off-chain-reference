from libra_address import LibraAddress
from protocol_messages import CommandResponseObject
from business import VASPInfo

from flask import Flask, request, abort
from flask.views import MethodView
import requests
from urllib.parse import urljoin
import json
import sys


class NetworkClient:
    def __init__(self, my_addr, other_addr):
        self.my_addr = my_addr
        self.other_addr = other_addr

        # We send all requests through a session to reuse the TLS connection.
        # Keep-alive is automatic within a session.
        self.session = requests.Session()

    def get_url(self, base_url):
        url = f'{self.other_addr.plain()}/{self.my_addr.plain()}/process/'
        return urljoin(base_url, url)

    def send_request(self, url, json_request):
        try:
            return self.session.post(url, json=json_request)
        except requests.exceptions.RequestException:
            # This happens in case of a connection error (e.g. DNS failure,
            # refused connection, etc), timeout, or if the maximum number of
            # redirections is reached.
            return None

    def close_connection(self):
        self.session.config['keep_alive'] = False


class NetworkServer:

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


class VASPOffChainApi(MethodView):
    def __init__(self, vasp):
        self.vasp = vasp

    def get(self):
        """ This path is not registered; used by subclasses for debugging. """
        return {"status": "success"}

    def post(self, other_addr):
        try:
            # This is a pyOpenSSL X509 object
            client_certificate = request.environ['peercert']
        except KeyError:
            # This exception is triggered when there is not client certificate.
            # In this case with continue without it, and it is up to the
            # context to decide whether the reject the client's request.
            client_certificate = None

        request_json = request.get_json()
        if not self.vasp.info_context.is_authorised_VASP(
            client_certificate, other_addr
        ):
            abort(401)
        channel = self.vasp.get_channel(LibraAddress(other_addr))
        try:
            response = channel.parse_handle_request(request_json)
        except TypeError:
            # This exception is triggered when the channel cannot load the
            # json request; eg. when the clients sends a json dict instead of
            # a json string.
            abort(400)
        if response != None:
            return response.content
        else:
            return Networking.BUSINESS_INTERUPT_RESPONSE
