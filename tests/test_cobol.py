"""Static analysis tests. No API key or Docker required."""

from __future__ import annotations

from pathlib import Path

from rosetta.cobol import _expand_pic, analyze
from rosetta.differ import normalize
from rosetta.models import IOContract
from rosetta.testgen import boundary_vectors

PROGRAMS = Path(__file__).resolve().parent.parent / "benchmarks" / "programs"


def test_expand_pic_repeat_form():
    assert _expand_pic("9(7)V99") == (9, 2, False, 0)


def test_expand_pic_bare_digits():
    assert _expand_pic("999V9") == (4, 1, False, 0)


def test_expand_pic_signed():
    digits, scale, signed, alpha = _expand_pic("S9(7)V99")
    assert (digits, scale, signed, alpha) == (9, 2, True, 0)


def test_expand_pic_alpha():
    assert _expand_pic("X(16)") == (0, 0, False, 16)


def test_analyze_interest():
    prog = analyze(PROGRAMS / "interest.cbl")
    assert prog.program_id == "INTEREST"
    assert prog.accept_count == 3
    assert prog.display_count == 2
    assert not prog.free_format
    assert "ACCRUE-YEAR" in prog.paragraphs
    names = {f.name: f for f in prog.fields}
    assert names["WS-PRINCIPAL"].digits == 9
    assert names["WS-PRINCIPAL"].scale == 2


def test_analyze_detects_signed_and_alpha():
    prog = analyze(PROGRAMS / "invoice.cbl")
    total = next(f for f in prog.fields if f.name == "WS-TOTAL")
    assert total.signed
    assert total.scale == 2

    card = next(f for f in analyze(PROGRAMS / "checkdig.cbl").fields if f.name == "WS-CARD")
    assert card.alpha_len == 16


def test_condition_names_are_not_storage():
    prog = analyze(PROGRAMS / "checkdig.cbl")
    assert all(f.level != 88 for f in prog.fields)


def test_boundary_vectors_are_deterministic_and_unique():
    contract = IOContract(
        stdin_lines=2,
        stdin_fields=[
            {"order": 0, "name": "A", "type": "numeric", "digits": 3, "scale": 0,
             "signed": True, "width": 0, "domain": ""},
            {"order": 1, "name": "B", "type": "alpha", "digits": 0, "scale": 0,
             "signed": False, "width": 4, "domain": ""},
        ],
    )
    first = boundary_vectors(contract, cap=30)
    second = boundary_vectors(contract, cap=30)
    assert [v.stdin for v in first] == [v.stdin for v in second]
    assert len({v.stdin for v in first}) == len(first)
    assert all(v.stdin.count("\n") == 2 for v in first)
    # Overflow and non-numeric probes must be present: these are the cases
    # naive ports get wrong.
    joined = "".join(v.stdin for v in first)
    assert "9999\n" in joined
    assert "ABC\n" in joined


def test_normalize_strips_trailing_padding_only():
    assert normalize("A  \nB\n\n\n") == "A\nB"
    assert normalize("  A\nB") == "  A\nB"


def test_expand_pic_edited_decimal_point_scales_field():
    # The literal '.' on an edited picture is the decimal point, exactly like V.
    assert _expand_pic("Z(5)9.99") == (8, 2, False, 0)
    assert _expand_pic("ZZ,ZZZ,ZZ9.99") == (10, 2, False, 0)  # 8 integer positions + 2 decimals


def test_edited_picture_is_not_truncated_at_its_decimal_point():
    prog = analyze(PROGRAMS / "payroll.cbl")
    tax_out = next(f for f in prog.fields if f.name == "WS-TAX-OUT")
    assert tax_out.pic == "Z(5)9.99"
    assert tax_out.scale == 2


def test_edited_sign_suffix_survives_parsing():
    prog = analyze(PROGRAMS / "invoice.cbl")
    total_out = next(f for f in prog.fields if f.name == "WS-TOTAL-OUT")
    assert total_out.pic == "ZZ,ZZZ,ZZ9.99CR"


def test_expand_pic_floating_sign_counts_digit_positions():
    # -(5)9 is six positions: one sign and five digits.
    digits, scale, signed, alpha = _expand_pic("-(5)9")
    assert (digits, scale, signed) == (5, 0, True)
    assert _expand_pic("+(5)9")[0] == 5
    assert _expand_pic("-(6)9")[0] == 6


def test_expand_pic_fixed_sign_and_decimals():
    assert _expand_pic("-999.99") == (5, 2, True, 0)


def test_expand_pic_cr_suffix_marks_field_signed():
    assert _expand_pic("ZZZ,ZZ9.99CR")[2] is True
    assert _expand_pic("ZZZ,ZZ9.99DB")[2] is True
    assert _expand_pic("ZZZ,ZZ9.99")[2] is False


def test_multiline_data_items_are_parsed():
    # WS-LEAD and WS-TRAIL wrap their VALUE clause onto a second line.
    prog = analyze(PROGRAMS / "signdisp.cbl")
    names = {f.name for f in prog.fields}
    assert {"WS-VAL", "WS-LEAD", "WS-TRAIL", "WS-ED-MINUS",
            "WS-ED-PLUS", "WS-ABS"} <= names
    lead = next(f for f in prog.fields if f.name == "WS-LEAD")
    assert lead.signed and lead.digits == 5


def test_usage_comp_and_packed_detected():
    prog = analyze(PROGRAMS / "compfield.cbl")
    by_name = {f.name: f for f in prog.fields}
    assert by_name["WS-BIN"].usage == "COMP"
    assert by_name["WS-PACKED"].usage == "COMP-3"
    assert by_name["WS-PACKED"].scale == 2


def test_whole_corpus_parses_and_is_twenty_programs():
    sources = sorted(PROGRAMS.glob("*.cbl"))
    assert len(sources) == 20, f"expected 20 programs, found {len(sources)}"
    for src in sources:
        prog = analyze(src)
        assert prog.program_id and prog.program_id != ""
        assert prog.loc > 0
        assert prog.fields, f"{src.name}: no data fields parsed"
        assert prog.paragraphs, f"{src.name}: no paragraphs found"
        assert prog.display_count > 0, f"{src.name}: writes nothing to stdout"
        # Every program must be verifiable: no construct the harness cannot
        # prove equivalent, or the corpus is measuring the wrong thing.
        assert not prog.unsupported, f"{src.name}: flagged {prog.unsupported}"


def test_program_ids_are_unique():
    ids = [analyze(s).program_id for s in sorted(PROGRAMS.glob("*.cbl"))]
    assert len(set(ids)) == len(ids), "duplicate PROGRAM-ID would collide in out/"


def test_accept_in_a_loop_is_padded_to_the_declared_line_count():
    # bubblesort.cbl has one ACCEPT statement but consumes eight lines.
    contract = IOContract(
        stdin_lines=8,
        stdin_fields=[
            {"order": 0, "name": "WS-NUM", "type": "numeric", "digits": 4,
             "scale": 0, "signed": False, "width": 0, "domain": "table entry"},
        ],
    )
    vectors = boundary_vectors(contract, cap=12)
    assert all(v.stdin.count("\n") == 8 for v in vectors), (
        "vectors must cover every line the program reads"
    )
