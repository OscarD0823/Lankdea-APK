from lankdea.i18n import LANGUAGES, language_name, normalize_language, translate


def test_same_twelve_languages_as_reference_interface():
    assert [item.code for item in LANGUAGES] == [
        "es", "en", "pt", "fr", "de", "it", "pl", "tr", "ru", "ja", "ko", "zh"
    ]


def test_core_navigation_is_translated_in_every_language():
    for language in LANGUAGES:
        assert translate("settings", language.code) not in ("", "settings")
        assert translate("lock", language.code) not in ("", "lock")


def test_unknown_language_returns_to_spanish():
    assert normalize_language("xx") == "es"
    assert language_name("xx") == "Español"
