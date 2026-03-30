"""Tests for LLM and NER anonymizer stub behavior."""

import pytest

from vibelens.config.anonymize import AnonymizeConfig
from vibelens.ingest.anonymize.base import BaseAnonymizer
from vibelens.ingest.anonymize.llm_anonymizer.anonymizer import LLMAnonymizer
from vibelens.ingest.anonymize.ner_anonymizer.anonymizer import NERAnonymizer
from vibelens.models.trajectories import Agent, Step, Trajectory


def _make_trajectory() -> Trajectory:
    return Trajectory(
        session_id="stub-test",
        agent=Agent(name="test"),
        steps=[Step(step_id="s1", source="user", message="hello")],
    )


def test_llm_anonymizer_instantiates() -> None:
    config = AnonymizeConfig(enabled=True)
    anon = LLMAnonymizer(config)
    print(f"  LLMAnonymizer created: {anon}")
    assert anon is not None


def test_ner_anonymizer_instantiates() -> None:
    config = AnonymizeConfig(enabled=True)
    anon = NERAnonymizer(config)
    print(f"  NERAnonymizer created: {anon}")
    assert anon is not None


def test_llm_anonymizer_raises_not_implemented() -> None:
    config = AnonymizeConfig(enabled=True)
    anon = LLMAnonymizer(config)
    with pytest.raises(NotImplementedError, match="LLM-based"):
        anon.anonymize_trajectory(_make_trajectory())


def test_ner_anonymizer_raises_not_implemented() -> None:
    config = AnonymizeConfig(enabled=True)
    anon = NERAnonymizer(config)
    with pytest.raises(NotImplementedError, match="NER-based"):
        anon.anonymize_trajectory(_make_trajectory())


def test_both_inherit_base_anonymizer() -> None:
    assert issubclass(LLMAnonymizer, BaseAnonymizer)
    assert issubclass(NERAnonymizer, BaseAnonymizer)
    print("  Both stubs inherit BaseAnonymizer")
