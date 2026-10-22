import io

import pytest

from p2p_share.protocol import MAX_LINE_BYTES, ProtocolError, receive_message


def test_eof_raises():
    with pytest.raises(ProtocolError):
        receive_message(io.StringIO(""))


def test_invalid_json_raises():
    with pytest.raises(ProtocolError):
        receive_message(io.StringIO("not json\n"))


def test_json_array_raises():
    with pytest.raises(ProtocolError):
        receive_message(io.StringIO("[1,2]\n"))


def test_oversized_line_raises():
    with pytest.raises(ProtocolError):
        receive_message(io.StringIO("x" * (MAX_LINE_BYTES + 10)))


def test_valid_object_returned():
    assert receive_message(io.StringIO('{"type":"GET_CATALOG"}\n')) == {"type": "GET_CATALOG"}
