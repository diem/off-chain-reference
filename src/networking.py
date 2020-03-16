from protocol import LibraAddress
from protocol_messages import CommandResponseObject

from flask import Flask, request
from flask.views import MethodView


class Networking:
    def __init__(self, vasp):
        self.app = Flask(__name__)
        self.vasp = vasp

        # Register paths.
        self.app.add_url_rule(
            '/'+self.vasp.my_vasp_addr().plain()+'/<other_addr>/process/',
            view_func=VASPOffChainApi.as_view('vasp_api', self.vasp)
        )


class VASPOffChainApi(MethodView):
    def __init__(self, vasp):
        self.vasp = vasp

    def post(self, other_addr):
        request_json = request.get_json()
        channel = self.vasp.get_channel(LibraAddress(other_addr))
        response = channel.parse_handle_request(request_json)
        assert str(response.type) == str(CommandResponseObject)
        return response.content
