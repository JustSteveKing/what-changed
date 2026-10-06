from eval.urls import is_well_formed, normalise_url


def test_tracking_only_differences_are_the_same_page() -> None:
    a = "https://magecomp.com/blog/laravel-13-queue-job-attributes/?srsltid=AU7gw4WwY6FidIclYBm3iVLYPd2iq29kF3xqlgze1ezYUNLmpeT2-n1t"
    b = "https://magecomp.com/blog/laravel-13-queue-job-attributes/?srsltid=AU7gw4VZOSLsCoMjoSIMwepqRF93WcVoIIsufxa7MTqUhkCaJjuv2hDh"
    assert normalise_url(a) == normalise_url(b)
    assert normalise_url("http://www.Laravel.com/docs/#x") == normalise_url("https://laravel.com/docs")
    assert normalise_url("https://x.dev/a?utm_source=t&page=2") == "https://x.dev/a?page=2"


def test_meaningful_differences_are_kept() -> None:
    assert normalise_url("https://x.dev/a?page=2") != normalise_url("https://x.dev/a?page=3")


def test_malformed_urls_are_rejected() -> None:
    assert is_well_formed("https://laravel.com/docs")
    assert not is_well_formed("laravel.com/docs")
    assert not is_well_formed("ftp://laravel.com")
    assert not is_well_formed("https://localhost")
