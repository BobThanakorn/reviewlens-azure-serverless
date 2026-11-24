import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError

from common.storage import BlobStore


def make_store():
    service = MagicMock()
    return BlobStore(service), service, service.get_blob_client.return_value


def http_error(status: int) -> HttpResponseError:
    err = HttpResponseError(message="x")
    err.status_code = status
    return err


def test_read_text_decodes_utf8():
    store, service, blob = make_store()
    blob.download_blob.return_value.readall.return_value = "ไทย".encode()
    assert store.read_text("c", "n") == "ไทย"
    service.get_blob_client.assert_called_with("c", "n")


def test_exists_delegates():
    store, _, blob = make_store()
    blob.exists.return_value = True
    assert store.exists("c", "n") is True


def test_write_text_reports_existing_when_not_overwriting():
    store, _, blob = make_store()
    assert store.write_text("c", "n", "x") is True
    blob.upload_blob.assert_called_with(b"x", overwrite=True)
    blob.upload_blob.side_effect = ResourceExistsError("exists")
    assert store.write_text("c", "n", "x", overwrite=False) is False


def test_list_names_sorted_with_prefix():
    store, service, _ = make_store()
    service.get_container_client.return_value.list_blobs.return_value = [
        SimpleNamespace(name="b"), SimpleNamespace(name="a"),
    ]  # fmt: skip
    assert store.list_names("c", "p") == ["a", "b"]
    service.get_container_client.return_value.list_blobs.assert_called_with(name_starts_with="p")


def test_read_json_with_etag():
    store, _, blob = make_store()
    downloader = blob.download_blob.return_value
    downloader.readall.return_value = json.dumps({"next_chunk": 4}).encode()
    downloader.properties.etag = '"0x1"'
    assert store.read_json_with_etag("c", "n") == ({"next_chunk": 4}, '"0x1"')


def test_read_json_missing_blob():
    store, _, blob = make_store()
    blob.download_blob.side_effect = ResourceNotFoundError("nope")
    assert store.read_json_with_etag("c", "n") == (None, None)


def test_conditional_write_uses_if_not_modified():
    store, _, blob = make_store()
    assert store.write_json_if_match("c", "n", {"a": 1}, '"0x1"') is True
    kwargs = blob.upload_blob.call_args.kwargs
    assert kwargs["etag"] == '"0x1"'
    assert kwargs["match_condition"] == MatchConditions.IfNotModified


def test_create_only_when_no_etag():
    store, _, blob = make_store()
    assert store.write_json_if_match("c", "n", {"a": 1}, None) is True
    assert blob.upload_blob.call_args.kwargs == {"overwrite": False}
    blob.upload_blob.side_effect = ResourceExistsError("exists")
    assert store.write_json_if_match("c", "n", {"a": 1}, None) is False


def test_412_is_a_lost_race_not_an_error():
    store, _, blob = make_store()
    blob.upload_blob.side_effect = http_error(412)
    assert store.write_json_if_match("c", "n", {}, '"0x1"') is False


def test_other_http_errors_propagate():
    store, _, blob = make_store()
    blob.upload_blob.side_effect = http_error(500)
    with pytest.raises(HttpResponseError):
        store.write_json_if_match("c", "n", {}, '"0x1"')
