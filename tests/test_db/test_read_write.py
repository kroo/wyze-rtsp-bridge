import pathlib

import pytest
from wyzecam import WyzeCredential

from wyze_rtsp_bridge import config
from wyze_rtsp_bridge.db import db


@pytest.fixture
def _conf(tmp_path):
    conf = config.load_config()
    conf.db_path = tmp_path / 'test.db'
    return conf


@pytest.fixture
def _test_creds():
    return WyzeCredential(
        access_token="asdf",
        refresh_token="fdsa",
        user_id='testing',
        phone_id='testing2'
    )


@pytest.fixture
def _db(_conf):
    database = db.WyzeRtspDatabase(_conf)
    yield database
    database.close()


def test_open(_db, _conf):
    _db.open()
    assert pathlib.Path(_conf.db_path).exists()


def test_get_credentials_no_credentials(_db):
    assert db.get_credentials(_db) is None


def test_set_credentials_no_credentials(_db, _test_creds):
    db.set_credentials(_db, _test_creds)
    assert db.get_credentials(_db) is not None


def test_set_credentials_existing_credentials(_db, _test_creds):
    db.set_credentials(_db, _test_creds)

    new_access_token = "something different"
    _test_creds.access_token = new_access_token
    db.set_credentials(_db, _test_creds)
    assert db.get_credentials(_db).access_token == new_access_token
