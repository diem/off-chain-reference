from libra_address import LibraAddress
from protocol_messages import CommandResponseObject
from business import VASPInfo, BusinessNotAuthorized

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

        # We send all requests through a session to re-use the TLS connection.
        # Keep-alive is automatic within a session.
        self.session = requests.Session()

    def get_url(self, base_url):
        url = f'{self.other_addr.as_str()}/{self.my_addr.as_str()}/process/'
        return urljoin(base_url, url)

    def send_request(self, url, json_request):
        try:
            return self.session.post(url, json=json_request)
        except requests.exceptions.RequestException:
            # This happens in case of (i) a connection error (e.g. DNS failure,
            # refused connection, etc), (ii) timeout, or (iii) if the maximum
            # number of redirections is reached.
            return None

    def close_connection(self):
        self.session.config['keep_alive'] = False


class NetworkServer:

    def __init__(self, vasp):
        self.app = Flask(__name__)
        self.vasp = vasp

        # Register paths.
        self.app.add_url_rule(
            f'/{self.vasp.get_vasp_address().as_str()}/<other_addr>/process/',
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
            # This is a pyOpenSSL X509 object.
            client_certificate = request.environ['peercert']
        except KeyError:
            # This exception is triggered when there is not client certificate.
            # In this case with continue without it, and it is up to the
            # context to decide whether to reject the client's request.
            client_certificate = None

        request_json = request.get_json()

        # Try to open a channel with the other VASP.
        try:
            channel = self.vasp.get_channel(LibraAddress(other_addr))
        except BusinessNotAuthorized:
            # Raised if the other VASP is not an authorised business.
            abort(401)
        except IOError:
            # Raised if there is an error loading resources associated with
            # the other VASP; eg. its certificate.
            abort(500)

        # Verify that the other VASP is authorised to submit the request;
        # ie. that 'other_addr' matches the certificate.
        if not self.vasp.info_context.is_authorised_VASP(
            client_certificate, other_addr
        ):
            abort(403)

        # Process the request and send a response back.
        try:
            response = channel.parse_handle_request(request_json)
        except TypeError:
            # This exception is triggered when the channel cannot load the
            # json request; eg. when the clients sends a json dict instead of
            # a json string.
            abort(400)
        assert response != None
        return response.content
