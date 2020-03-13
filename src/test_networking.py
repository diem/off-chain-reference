from networking import app
from protocol import LibraAddress
from test_sample_service import simple_request_json
from payment_logic import PaymentCommand
from protocol_messages import CommandResponseObject

import pytest
import json

@pytest.fixture
def client():
    app.testing = True # Propagate server errors to the client
    with app.test_client() as c:
        yield c


def test_index(client):
    response = client.get('/')
    assert response.status_code == 200


def test_process(client, simple_request_json):
    addr = LibraAddress.encode_to_Libra_address(b'B'*16)
    other_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
    url = '/'+addr.plain()+'/'+other_addr.plain()+'/process/'
    responses_json = client.post(url, json=simple_request_json)
    response = json.loads(responses_json.data)
    assert response['status'] == 'success'
