import pytest

from app.schemas.owner import google_destination


@pytest.mark.parametrize(
    "url",
    [
        "https://g.page/r/Abc_123-foo/review",
        "https://search.google.com/local/writereview?placeid=ChIJabc",
        "https://www.google.com/search?q=Desi+District+-+Dunwoody+Reviews"
        "&sa=X#lrd=0x88f50b2afa23bd91:0x94b3f222c1cbd14e,3,,,,",
        "https://maps.app.goo.gl/ExampleLink",
        "https://example.com/reviews?source=website#write-review",
        "https://g.page:443/r/abc/review",
    ],
)
def test_supported_google_destinations(url):
    assert google_destination(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://g.page/r/abc/review",
        "https://g.page@evil.com/r/abc/review",
        "https://user@g.page/r/abc/review",
        "https://g.page/r/abc/re\nview",
        "https:///reviews",
        "https://example.com:99999/reviews",
        "https://example.com\\@another.com/reviews",
        "data:text/html,test",
        "/reviews",
    ],
)
def test_invalid_or_non_https_urls_are_rejected(url):
    with pytest.raises(ValueError):
        google_destination(url)
