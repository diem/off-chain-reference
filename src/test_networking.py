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
    other_addr = LibraAddress.encode_to_Libra_address(b'A'*16)
    responses_json = client.post('/process', json=simple_request_json)
    responses = json.loads(responses_json.data)
    assert len(responses) == 2
    assert 'success' in responses[1]
