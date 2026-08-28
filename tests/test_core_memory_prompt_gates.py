#!/usr/bin/env python3
"""Tests for core memory prompt gates."""

from kaskade.memory.prompt_gates import should_include_core_block


def test_weekend_hobbies_keyword():
    assert should_include_core_block("Weekend Hobbies", channel_id="personal-dm", user_message="went hiking today")
    assert not should_include_core_block("Weekend Hobbies", channel_id="work-chat", user_message="sprint planning")


def test_about_me_always_in_config_absent():
    assert should_include_core_block("ABOUT ME", channel_id="work-chat", user_message="")
