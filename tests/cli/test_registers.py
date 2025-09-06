"""The register commands."""

from __future__ import annotations

from tests.cli.conftest import Invoke


def a_grower(invoke: Invoke, code: str = "HOLB") -> None:
    invoke("party", "add", code, "Holbeach Grange", "--role", "grower", "--holding", "12/345")


def test_a_party_goes_in_and_comes_back(invoke: Invoke) -> None:
    a_grower(invoke)
    result = invoke("party", "list")
    assert result.exit_code == 0
    assert "HOLB" in result.output
    assert "Holbeach Grange" in result.output


def test_a_party_that_is_shown_says_everything(invoke: Invoke) -> None:
    a_grower(invoke)
    result = invoke("party", "show", "HOLB")
    assert "role      grower" in result.output
    assert "holding   12/345" in result.output
    assert "trading   yes" in result.output


def test_a_holding_on_somebody_who_is_not_a_grower_is_refused(invoke: Invoke) -> None:
    result = invoke(
        "party", "add", "BRWY", "Sheldrake", "--role", "customer", "--holding", "12/345"
    )
    assert result.exit_code != 0


def test_the_same_code_twice_is_refused(invoke: Invoke) -> None:
    a_grower(invoke)
    result = invoke("party", "add", "HOLB", "Somebody Else", "--role", "merchant")
    assert result.exit_code != 0


def test_closing_a_party_stops_them_trading(invoke: Invoke) -> None:
    a_grower(invoke)
    invoke("party", "close", "HOLB", on="2025-11-04")
    result = invoke("party", "show", "HOLB", on="2025-11-05")
    assert "trading   no" in result.output


def test_the_party_list_narrows_by_role(invoke: Invoke) -> None:
    a_grower(invoke)
    invoke("party", "add", "BRWY", "Sheldrake", "--role", "customer")
    result = invoke("party", "list", "--role", "customer")
    assert "BRWY" in result.output
    assert "HOLB" not in result.output


def test_the_party_list_can_leave_out_the_closed(invoke: Invoke) -> None:
    a_grower(invoke)
    invoke("party", "close", "HOLB", on="2025-11-04")
    result = invoke("party", "list", "--trading", on="2025-11-05")
    assert "HOLB" not in result.output


def test_a_variety_goes_on_the_list(invoke: Invoke) -> None:
    invoke("variety", "add", "LAUR", "Laureate", "--approval", "approved")
    result = invoke("variety", "list")
    assert "Laureate" in result.output
    assert "approved" in result.output


def test_a_variety_starts_under_test_by_default(invoke: Invoke) -> None:
    invoke("variety", "add", "NEWY", "New One")
    assert "under_test" in invoke("variety", "show", "NEWY").output


def test_a_variety_under_test_is_not_on_the_list(invoke: Invoke) -> None:
    invoke("variety", "add", "NEWY", "New One")
    result = invoke("variety", "show", "NEWY")
    assert "on list   no" in result.output


def test_promoting_a_variety_moves_it(invoke: Invoke) -> None:
    invoke("variety", "add", "NEWY", "New One")
    invoke("variety", "promote", "NEWY", "provisional")
    assert "provisional" in invoke("variety", "show", "NEWY").output


def test_withdrawing_a_variety_dates_it(invoke: Invoke) -> None:
    invoke("variety", "add", "LAUR", "Laureate", "--approval", "approved")
    invoke("variety", "withdraw", "LAUR", on="2025-11-04")
    result = invoke("variety", "show", "LAUR", on="2025-11-05")
    assert "withdrawn 2025-11-04" in result.output
    assert "on list   no" in result.output


def test_a_withdrawn_variety_does_not_come_back(invoke: Invoke) -> None:
    invoke("variety", "add", "LAUR", "Laureate", "--approval", "approved")
    invoke("variety", "withdraw", "LAUR")
    result = invoke("variety", "promote", "LAUR", "approved")
    assert result.exit_code != 0


def test_promoting_to_withdrawn_is_not_even_an_option(invoke: Invoke) -> None:
    invoke("variety", "add", "LAUR", "Laureate", "--approval", "approved")
    result = invoke("variety", "promote", "LAUR", "withdrawn")
    assert result.exit_code == 2


def test_a_steep_takes_a_charge(invoke: Invoke) -> None:
    result = invoke("vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45")
    assert result.exit_code == 0
    assert "45.0t" in result.output


def test_a_box_takes_an_area_and_a_depth(invoke: Invoke) -> None:
    result = invoke(
        "vessel", "add", "G1", "box 1", "--kind", "box", "--area", "170", "--depth", "90"
    )
    assert result.exit_code == 0
    assert "84.2t" in result.output


def test_a_steep_with_a_bed_depth_is_refused(invoke: Invoke) -> None:
    result = invoke(
        "vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45", "--depth", "90"
    )
    assert result.exit_code != 0


def test_a_box_shows_what_it_holds_at_a_depth(invoke: Invoke) -> None:
    invoke("vessel", "add", "G1", "box 1", "--kind", "box", "--area", "170", "--depth", "90")
    result = invoke("vessel", "show", "G1")
    assert "at 30cm" in result.output
    assert "at 90cm" in result.output


def test_a_steep_shows_no_bed(invoke: Invoke) -> None:
    invoke("vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45")
    result = invoke("vessel", "show", "S1")
    assert "bed" not in result.output


def test_retiring_a_vessel_takes_it_out_of_service(invoke: Invoke) -> None:
    invoke("vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45")
    invoke("vessel", "retire", "S1", on="2025-11-04")
    result = invoke("vessel", "list", on="2025-11-05")
    assert "no" in result.output


def test_the_vessel_list_narrows_by_kind(invoke: Invoke) -> None:
    invoke("vessel", "add", "S1", "steep 1", "--kind", "steep", "--charge", "45")
    invoke("vessel", "add", "G1", "box 1", "--kind", "box", "--area", "170", "--depth", "90")
    result = invoke("vessel", "list", "--kind", "box")
    assert "G1" in result.output
    assert "S1" not in result.output


def test_every_register_group_is_in_the_help(invoke: Invoke) -> None:
    result = invoke("--help")
    for group in ("party", "variety", "vessel"):
        assert group in result.output
