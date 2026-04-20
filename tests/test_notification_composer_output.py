from media_calendar.models import NotificationComposerOutput


def test_notification_composer_output_model_accepts_required_fields():
    composer_output = NotificationComposerOutput(
        subject_line="Upcoming deadline reminder",
        html_body="<p>Deadline approaching.</p>",
        plain_text_body="Deadline approaching.",
        priority_level="high",
    )

    assert composer_output.subject_line == "Upcoming deadline reminder"
    assert composer_output.html_body == "<p>Deadline approaching.</p>"
    assert composer_output.plain_text_body == "Deadline approaching."
    assert composer_output.priority_level == "high"
