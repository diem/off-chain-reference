from .libra_address import LibraAddress
from .protocol_messages import CommandResponseObject
from .business import VASPInfo, BusinessNotAuthorized

from flask import Flask, request, abort
from werkzeug.serving import WSGIRequestHandler

from flask.views import MethodView
import requests
from urllib.parse import urljoin
from json import dumps, loads
import sys
import logging


class NetworkClient:
    def __init__(self, channel):
        self.channel = channel

        # We send all requests through a session to re-use the TLS connection.
        # Keep-alive is automatic within a session.
        self.session = requests.Session()

    def get_url(self, base_url):
        my_addr = self.channel.get_my_address()
        my_other = self.channel.get_other_address()
        url = f'{my_addr.as_str()}/{my_other.as_str()}/process/'
        return urljoin(base_url, url)

    def send_request(self, url, json_request):
        logging.debug(f'Connect to {url}')
        try:
            response = self.session.post(url, json=json_request)
        except requests.exceptions.RequestException as e:
            # This happens in case of (i) a connection error (e.g. DNS failure,
            # refused connection, etc), (ii) timeout, or (iii) if the maximum
            # number of redirections is reached.
            logging.warning(f'RequestException: {e}')
            return False

        try:
            decoded_response = response.content.decode('utf-8')
        except UnicodeError as e:
            logging.warning(f'UnicodeError: {e}')
            return False

        self.channel.parse_handle_response(decoded_response)
        return True

    def close_connection(self):
        self.session.config['keep_alive'] = False


class NetworkServer:

    def __init__(self, vasp):
        # Set the app name to be the address of the VASP
        app_name = vasp.get_vasp_address().as_str()
        self.app = Flask(app_name)
        self.vasp = vasp

        # Register paths.
        route = f'/{self.vasp.get_vasp_address().as_str()}/<other_addr>/process/'
        logging.debug(f'Register route {route}')
        self.app.add_url_rule(
            route,
            view_func=VASPOffChainApi.as_view('process', self.vasp)
        )

    def run(self, host='0.0.0.0', port=80):
        # Ensures that the connection is kept alive
        WSGIRequestHandler.protocol_version = "HTTP/1.1"
        self.app.run(host=host, port=port)


class VASPOffChainApi(MethodView):
    def __init__(self, vasp):
        self.vasp = vasp

    def get(self):
        """ This path is not registered; used by subclasses for debugging. """
        return {"status": "success"}

    def post(self, other_addr):
        logging.debug(f'Data Received {other_addr}')
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
        except BusinessNotAuthorized as e:
            # Raised if the other VASP is not an authorised business.
            logging.debug(f'Not Authorized {e}')
            abort(401)
        except IOError as e:
            # Raised if there is an error loading resources associated with
            # the other VASP; eg. its certificate.
            logging.debug(f'IO Error {e}')
            abort(500)

        # Verify that the other VASP is authorised to submit the request;
        # ie. that 'other_addr' matches the certificate.
        if not self.vasp.info_context.is_authorised_VASP(
            client_certificate, other_addr):
            logging.debug(f'Not Authorized')
            abort(403)

        # Process the request and send a response back.
        try:
            response = channel.parse_handle_request(dumps(request_json))
        except TypeError as e:
            # This exception is triggered when the channel cannot load the
            # json request; eg. when the clients sends a json dict instead of
            # a json string.
            logging.debug(f'Type Error {e}')
            import traceback
            traceback.print_exc()
            abort(400)

        assert response != None
        return response.content
