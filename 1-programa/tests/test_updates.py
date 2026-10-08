import pytest
import requests

from lankdea.updates import API_URL, check_latest_release, version_tuple


class FakeHTTP:
    def __init__(self, status=200, tag="v3.2.1", **extra):
        self.status_code = status
        self.payload = {"tag_name": tag, "assets": [
            {"name": f"Lankdea-{tag.removeprefix('v')}-Completo-Windows-Android.zip"}
        ], **extra}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError()

    def json(self):
        return self.payload


def test_newer_version_uses_numeric_comparison_and_no_credentials():
    http = FakeHTTP(tag="v3.10.0")
    result = check_latest_release("3.9.0", http=http)
    assert result.state == "available"
    assert http.calls[0][0] == API_URL
    assert "Authorization" not in http.calls[0][1]["headers"]
    assert "timeout" in http.calls[0][1]


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_private_missing_or_unavailable_release_is_not_an_internet_error(status):
    result = check_latest_release(http=FakeHTTP(status=status))
    assert result.state == "unavailable"
    assert "sin Internet" not in result.message


@pytest.mark.parametrize("tag", ["v3.2.0", "v3.1.1"])
def test_no_downgrade(tag):
    assert check_latest_release("3.2.0", http=FakeHTTP(tag=tag)).state == "current"


def test_rejects_incomplete_prerelease_and_invalid_responses():
    for http in [FakeHTTP(assets=[]), FakeHTTP(prerelease=True), FakeHTTP(tag="evil"), FakeHTTP(assets=None)]:
        assert check_latest_release(http=http).state == "unavailable"


def test_offline_does_not_raise():
    class Offline:
        def get(self, *args, **kwargs):
            raise requests.ConnectionError()
    assert check_latest_release(http=Offline()).state == "unavailable"


@pytest.mark.parametrize("bad", ["3.2", "3.2.0-beta", "../3.2.0", "3.02.0"])
def test_version_format_is_strict(bad):
    with pytest.raises(ValueError):
        version_tuple(bad)
