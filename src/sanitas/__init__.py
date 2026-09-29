import sys
import os

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine


def redact(text: str) -> str:
    results = AnalyzerEngine().analyze(text=text, language="en")
    return AnonymizerEngine().anonymize(text=text, analyzer_results=results).text


def main() -> None:
    print(redact(sys.stdin.read()))
