import sys
from functools import cache

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine


@cache
def _analyzer() -> AnalyzerEngine:
    return AnalyzerEngine()


def detect(text: str) -> list[RecognizerResult]:
    return _analyzer().analyze(text=text, language="en")


def redact(text: str) -> str:
    return AnonymizerEngine().anonymize(text=text, analyzer_results=detect(text)).text


def main() -> None:
    print(redact(sys.stdin.read()))
