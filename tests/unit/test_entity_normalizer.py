import pytest

from app.services.entity_normalizer import EntityNormalizer


def test_normalizer_keeps_raw_text_and_derives_case_space_forms():
    result = EntityNormalizer().normalize(" Sad  Overlxrd ")

    assert result.raw == " Sad  Overlxrd "
    assert result.canonical_text == "sad overlxrd"
    assert result.compact_text == "sadoverlxrd"
    assert result.chinese_canonical == "sad overlxrd"


def test_normalizer_uses_project_traditional_simplified_rules():
    traditional = EntityNormalizer().normalize("周杰倫")
    simplified = EntityNormalizer().normalize("周杰伦")

    assert traditional.chinese_canonical == simplified.chinese_canonical
    assert traditional.compact_text == simplified.compact_text


def test_normalizer_handles_bounded_punctuation_without_destructive_raw_rewrite():
    result = EntityNormalizer().normalize("SASIOVERLXRD — live?")

    assert result.raw == "SASIOVERLXRD — live?"
    assert result.canonical_text == "sasioverlxrd live"
    assert result.compact_text == "sasioverlxrdlive"


def test_normalizer_does_not_reject_legitimate_one_character_entities():
    result = EntityNormalizer().normalize("光")

    assert result.canonical_text == "光"
    assert result.compact_text == "光"


@pytest.mark.parametrize("value", ["", "   ", "bad\nvalue", "x" * 301])
def test_normalizer_rejects_empty_control_or_oversized_input(value):
    with pytest.raises(ValueError):
        EntityNormalizer().normalize(value)
