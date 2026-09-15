from app.detector import choose_action, similarity


def test_similarity_and_thresholds():
    assert similarity("Anjali Tripathi", "anjali tripathi") == 1
    assert choose_action(39.99) == "allow"
    assert choose_action(40) == "captcha"
    assert choose_action(80) == "captcha"
    assert choose_action(80.01) == "block"

