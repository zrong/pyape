from flask.testing import FlaskClient


def test_get_user_1(sample_multidb_client: FlaskClient):
    resp = sample_multidb_client.get('/user2/get', query_string={'id': 1, 'bind_key': 'db1'})
    assert resp.status_code == 404

    resp = sample_multidb_client.get('/user2/get', query_string={'id': 2, 'bind_key': 'db2'})
    assert resp.status_code == 404

def test_set_user_1(sample_multidb_client: FlaskClient):
    resp = sample_multidb_client.post('/user2/set', data={'id': 1, 'name': 'zrong1', 'bind_key': 'db1'})
    assert resp.status_code == 200 and b'zrong1' in resp.data

    resp = sample_multidb_client.post('/user2/set', data={'id': 2, 'name': 'zrong2', 'bind_key': 'db2'})
    assert resp.status_code == 200 and b'zrong2' in resp.data


def test_get_user_1_again(sample_multidb_client: FlaskClient):
    resp = sample_multidb_client.get('/user2/get', query_string={'id': 1, 'bind_key': 'db1'})
    assert resp.status_code == 200 and b'zrong1' in resp.data

    resp = sample_multidb_client.get('/user2/get', query_string={'id': 2, 'bind_key': 'db2'})
    assert resp.status_code == 200 and b'zrong2' in resp.data