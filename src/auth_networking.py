from networking import Networking, VASPOffChainApi

import werkzeug.serving
import ssl
import OpenSSL
import requests
import json

class PeerCertWSGIRequestHandler(werkzeug.serving.WSGIRequestHandler):
    def make_environ(self):
        # First call the super class method.
        environ = super(PeerCertWSGIRequestHandler, self).make_environ()

        # Get the cient's certificate.
        x509_binary = self.connection.getpeercert(True)
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_ASN1, x509_binary
        )

        # Add the client's certificate to the environment to make it accessible
        # by Flask's request.
        environ['peercert'] = x509
        return environ


class AuthenticatedNetworking(Networking):
    def __init__(self, vasp, info_context, server_key, server_key_password,
                 server_cert, client_key, client_cert):

        super().__init__(vasp, info_context)

        if __debug__:
            self.app.add_url_rule(
                '/', view_func=VASPOffChainApi.as_view('debug', self.vasp)
            )

        # The server's secret key.
        self.server_key = server_key

        # The password to access the server's key.
        self.server_key_password = server_key_password

        # The server's certificate.
        self.server_cert = server_cert

        # The client's secret key.
        self.client_key = client_key

        # Certificate of the CA that issued the client's certificate.
        self.client_cert = client_cert

    def run(self):
        ssl_context = ssl.create_default_context(
            purpose=ssl.Purpose.CLIENT_AUTH, cafile=self.client_cert
        )
        ssl_context.load_cert_chain(
            certfile=self.server_cert,
            keyfile=self.server_key,
            password=self.server_key_password
        )
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        self.app.run(
            ssl_context=ssl_context, request_handler=PeerCertWSGIRequestHandler
        )

    def send_request(self, url, other_addr, json_request):
        response = requests.post(
            url,
            json=json_request,
            verify=self.server_cert,
            cert=(self.client_cert, self.client_key)
        )
        self._handle_response(other_addr, response)
        if __debug__:
            print('\nREQUEST: ', response.json())
