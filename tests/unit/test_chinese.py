from app.domain.chinese import normalize_chinese_text


def test_traditional_body_character_has_stable_simplified_key():
    assert normalize_chinese_text("體") == "体"
