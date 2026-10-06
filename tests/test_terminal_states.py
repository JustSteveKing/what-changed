from typing import get_args

from what_changed.contract import EXIT_CODES, USAGE_EXIT_CODE, TerminalState


def test_has_the_six_agreed_states() -> None:
    assert get_args(TerminalState) == ("completed", "failed", "stream_closed", "timed_out", "cancelled", "declined")


def test_every_state_has_a_distinct_exit_code_not_shared_with_usage_errors() -> None:
    codes = [EXIT_CODES[state] for state in get_args(TerminalState)]
    assert len(set(codes)) == len(codes)
    assert USAGE_EXIT_CODE not in codes
