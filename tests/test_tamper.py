from p2p_share.tamper import TamperControl


def test_unarmed_returns_data_unchanged():
    t = TamperControl()
    assert t.apply("f", 0, b"abc") == (b"abc", False)


def test_once_tampers_first_request_only():
    t = TamperControl()
    t.arm("f", 2, once=True)
    data, tampered = t.apply("f", 2, b"abc")
    assert tampered and data != b"abc" and data[1:] == b"bc"
    assert t.apply("f", 2, b"abc") == (b"abc", False)
    assert t.state() is None


def test_persistent_tampers_every_time():
    t = TamperControl()
    t.arm("f", 2, once=False)
    assert t.apply("f", 2, b"abc")[1] is True
    assert t.apply("f", 2, b"abc")[1] is True
    assert t.state() == {"file_id": "f", "index": 2, "once": False}


def test_other_chunk_untouched():
    t = TamperControl()
    t.arm("f", 2)
    assert t.apply("f", 3, b"abc") == (b"abc", False)
    assert t.apply("g", 2, b"abc") == (b"abc", False)


def test_disarm():
    t = TamperControl()
    t.arm("f", 2)
    t.disarm()
    assert t.apply("f", 2, b"abc") == (b"abc", False)
