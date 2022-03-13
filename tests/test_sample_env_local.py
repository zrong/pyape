from flask.testing import FlaskClient


def test_get_user_1(sample_local_client: FlaskClient):
    resp = sample_local_client.get('/user/get', query_string={'id': 1})
    assert resp.status_code == 404

def test_set_user_1(sample_local_client: FlaskClient):
    resp = sample_local_client.post('/user/set', data={'id': 1, 'name': 'zrong'})
    assert resp.status_code == 200 and b'zrong' in resp.data


def test_get_user_1_again(sample_local_client: FlaskClient):
    resp = sample_local_client.get('/user/get', query_string={'id': 1})
    assert resp.status_code == 200 and b'zrong' in resp.data