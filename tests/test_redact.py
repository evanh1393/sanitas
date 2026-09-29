from sanitas import redact


def test_redacts_ssn():
    assert "536-22-8134" not in redact("SSN 536-22-8134")


def test_keeps_plain_text():
    assert redact("The report is ready") == "The report is ready."
