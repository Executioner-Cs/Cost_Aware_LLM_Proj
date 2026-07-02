"""Tests for core/classifier.py"""
import pytest
from core.classifier import classify


@pytest.mark.parametrize("prompt,expected", [
    ("Summarize this meeting note", "simple"),
    ("What is the capital of France?", "simple"),
    ("Write me a poem about autumn", "simple"),
    ("Extract the invoice number and date as JSON", "json_extract"),
    ("Parse this JSON response and get the fields", "json_extract"),
    ("Return structured output with name and age", "json_extract"),
    ("Reason through this architectural tradeoff", "reasoning"),
    ("Analyze why this code is slow", "reasoning"),
    ("Explain step by step how this algorithm works", "reasoning"),
    ("Describe what is in this image", "vision"),
    ("What does this screenshot show?", "vision"),
    ("Describe the photo attached", "vision"),
    ("Call the weather function for London", "tools"),
    ("Use the search API to find results", "tools"),
])
def test_classify(prompt, expected):
    assert classify(prompt) == expected


def test_simple_default():
    assert classify("Hello world") == "simple"


def test_json_extract_priority():
    # json extraction should win over simple
    assert classify("extract all fields as a JSON dict") == "json_extract"
