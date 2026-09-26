from ytlyrics.core.monitor import parse_request


def test_basic_command():
    p = parse_request("!lyrics Ariana Grande - positions")
    assert p is not None
    assert p.artist == "Ariana Grande"
    assert p.title == "positions"


def test_missing_command_rejected():
    assert parse_request("bu şarkıyı çok seviyorum") is None
    assert parse_request("lyrics someone - something") is None


def test_pitch_and_bg():
    p = parse_request("!lyrics Daft Punk - Around the World pitch -2 bg sunset")
    assert p is not None
    assert p.pitch == -2.0
    assert p.bg_preset == "sunset"
    assert p.title == "Around the World"


def test_title_only():
    p = parse_request("!lyrics Blinding Lights")
    assert p is not None
    assert p.artist == ""
    assert p.title == "Blinding Lights"


def test_title_by_artist():
    p = parse_request("!lyrics Shape of You by Ed Sheeran")
    assert p is not None
    assert p.title == "Shape of You"
    assert p.artist == "Ed Sheeran"


def test_unicode_separators():
    p = parse_request("!lyrics Sezen Aksu – Gülümse")
    assert p is not None
    assert p.artist == "Sezen Aksu"
    assert p.title == "Gülümse"


def test_case_insensitive_command():
    p = parse_request("!LYRICS Billie Eilish - bad guy")
    assert p is not None
    assert p.artist == "Billie Eilish"


def test_colon_separator():
    p = parse_request("!lyrics Moby: Porcelain")
    assert p is not None
    assert p.artist == "Moby"
    assert p.title == "Porcelain"


def test_empty_after_command():
    assert parse_request("!lyrics") is None
