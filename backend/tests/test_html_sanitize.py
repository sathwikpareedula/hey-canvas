from app.text.html_sanitize import html_to_plain_text


def test_html_to_plain_text_strips_tags_and_scripts() -> None:
    text = html_to_plain_text(
        "<p>Quiz <strong>3</strong></p><script>alert(1)</script><p>Topics: kinematics</p>"
    )
    assert "Quiz 3" in text
    assert "kinematics" in text
    assert "alert" not in text
