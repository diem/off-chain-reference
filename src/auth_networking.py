from networking import NetworkClient, NetworkServer, VASPOffChainApi

import werkzeug.serving
import ssl
import OpenSSL
import requests
import json


class AuthNetworkClient(NetworkClient):
    def __init__(self, my_addr, other_addr, server_cert, client_cert, client_key):
        super().__init__(my_addr, other_addr)

        self.server_cert = server_cert
        self.client_cert = client_cert
        self. client_key = client_key

    def send_request(self, url, json_request):
        try:
            return requests.post(
                url,
                json=json_request,
                verify=self.server_cert,
                cert=(self.client_cert, self.client_key)
            )
        except requests.exceptions.RequestException:
            # This happens in case of (i) a connection error (e.g. DNS failure,
            # refused connection, etc), (ii) timeout, or (iii) if the maximum
            # number of redirections is reached.
            return None


class PeerCertWSGIRequestHandler(werkzeug.serving.WSGIRequestHandler):
    def make_environ(self):
        environ = super(PeerCertWSGIRequestHandler, self).make_environ()

        # Get the cient's certificate.
        x509_binary = self.connection.getpeercert(True)
        x509 = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_ASN1, x509_binary
        )

        # Add the client's certificate to the environment to make it accessible
        # in the Flask's request.
        environ['peercert'] = x509
        return environ


class AuthNetworkServer(NetworkServer):
    def __init__(self, vasp, server_key, server_cert, client_cert):

        super().__init__(vasp)

        if __debug__:
            self.app.add_url_rule(
                '/', view_func=VASPOffChainApi.as_view('debug', self.vasp)
            )

        # The server's secret key.
        self.server_key = server_key

        # The password to access the server's key.
        self.server_key_password = None

        # The server's certificate.
        self.server_cert = server_cert

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
