"""Deterministic COBOL static analysis.

The LLM is good at translation and bad at counting. Anything that can be
established by parsing - how many ACCEPTs there are, what a PIC clause means
numerically, whether the source is fixed or free format - is established here,
and the parsed facts override the model's opinion downstream.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import CobolField, CobolProgram

_PROGRAM_ID = re.compile(r"\bPROGRAM-ID\s*\.\s*([A-Za-z0-9_-]+)", re.I)
_PARAGRAPH = re.compile(r"^\s{0,10}([A-Za-z][A-Za-z0-9-]*)\s*\.\s*$")
_SELECT = re.compile(r"\bSELECT\s+([A-Za-z0-9-]+)", re.I)
# `rest` must run to the period that ENDS the clause, not the first period in
# it: an edited picture such as `Z(5)9.99` contains one, and stopping early
# silently drops the decimal places.
_DATA_ITEM = re.compile(
    r"^\s*(\d{2})\s+([A-Za-z0-9-]+)(?P<rest>.*?)\.\s*$",
    re.I,
)
_PIC = re.compile(r"\bPIC(?:TURE)?\s+(?:IS\s+)?([A-Z0-9()VSXZ9,.+\-/*$]+)", re.I)
_USAGE = re.compile(r"\bUSAGE\s+(?:IS\s+)?([A-Z0-9-]+)|\b(COMP-[0-9]|COMP|BINARY|PACKED-DECIMAL|DISPLAY)\b", re.I)

# Constructs this version does not attempt to prove equivalent.
_UNSUPPORTED = {
    "REDEFINES": r"\bREDEFINES\b",
    "GO TO": r"\bGO\s+TO\b",
    "ALTER": r"\bALTER\b",
    "SORT": r"\bSORT\b",
    "CALL": r"\bCALL\s+",
    "EXEC SQL": r"\bEXEC\s+SQL\b",
    "EXEC CICS": r"\bEXEC\s+CICS\b",
    "COPY": r"^\s*COPY\s+",
}


def _expand_pic(pic: str) -> tuple[int, int, bool, int]:
    """Return (digits, scale, signed, alpha_len) for a PIC string.

    Handles the repeat form 9(5)V99, bare 99999, S for sign, X(n) for
    alphanumeric. Returns alpha_len > 0 only for alphanumeric pictures.
    """
    p = pic.upper().rstrip(".")
    signed = p.startswith("S") or "S" in p[:2]
    p = p.lstrip("S")

    def _count(segment: str, char: str) -> int:
        total = 0
        for m in re.finditer(rf"{re.escape(char)}(?:\((\d+)\))?", segment):
            total += int(m.group(1)) if m.group(1) else 1
        return total

    if "X" in p or "A" in p:
        return 0, 0, False, _count(p, "X") + _count(p, "A")

    # V is the implied decimal point on a storage picture. On an edited picture
    # the literal '.' plays the same role, so it has to scale the field too.
    if "V" in p:
        left, _, right = p.partition("V")
    elif "." in p:
        left, _, right = p.rpartition(".")
    else:
        left, right = p, ""

    int_digits = _count(left, "9") + _count(left, "Z") + _count(left, "*")
    frac_digits = _count(right, "9") + _count(right, "Z") + _count(right, "*")

    # Floating sign insertion: in -(5)9 or +(5)9 every sign position is also a
    # digit position except one, which holds the sign itself. Counting only the
    # 9s reports a 5-digit field as holding one digit, which would make the
    # generated test vectors far too narrow.
    float_sign = _count(left, "-") + _count(left, "+")
    float_sign_frac = _count(right, "-") + _count(right, "+")
    if float_sign or float_sign_frac:
        signed = True
        int_digits += float_sign
        frac_digits += float_sign_frac
        # exactly one position across the picture is the sign
        if int_digits:
            int_digits -= 1
        elif frac_digits:
            frac_digits -= 1

    # A trailing CR or DB symbol only prints for a negative value, so the field
    # is signed even though no sign character appears in the picture.
    if "CR" in p or "DB" in p:
        signed = True

    return int_digits + frac_digits, frac_digits, signed, 0


def _is_free_format(lines: list[str]) -> bool:
    """Fixed-format COBOL reserves cols 1-6 for sequence numbers and starts code
    at col 8. If meaningful code consistently begins before col 8, call it free.
    """
    code_lines = [l for l in lines if l.strip() and not l.lstrip().startswith("*")]
    if not code_lines:
        return True
    early = 0
    for line in code_lines:
        indent = len(line) - len(line.lstrip())
        if indent < 6:
            early += 1
    return early > len(code_lines) * 0.5


def _logical_data_lines(lines: list[str]) -> list[str]:
    """Rejoin data items that span several physical lines.

    A data description entry ends at its period, not at the end of a line, and
    real legacy source wraps long ones freely:

        01  WS-LEAD   PIC S9(5) SIGN IS LEADING SEPARATE
                                VALUE ZERO.

    Matching line by line silently drops every wrapped item, which is worse
    than failing: the brief handed to the model would be missing fields it has
    to translate. Joining stops at PROCEDURE DIVISION, so statements are left
    alone.
    """
    out: list[str] = []
    buf: list[str] = []
    for line in lines:
        if re.search(r"\bPROCEDURE\s+DIVISION\b", line, re.I):
            break
        stripped = line.strip()
        if not stripped:
            continue
        buf.append(stripped)
        if stripped.endswith("."):
            out.append(" ".join(buf))
            buf = []
    if buf:
        out.append(" ".join(buf))
    return out


def _strip_comments(lines: list[str], free: bool) -> list[str]:
    out = []
    for line in lines:
        if free:
            if line.lstrip().startswith("*>") or line.lstrip().startswith("*"):
                continue
            out.append(line)
        else:
            if len(line) > 6 and line[6] in {"*", "/"}:
                continue
            out.append(line)
    return out


def analyze(path: str | Path) -> CobolProgram:
    p = Path(path)
    source = p.read_text(errors="replace")
    raw_lines = source.splitlines()
    free = _is_free_format(raw_lines)
    lines = _strip_comments(raw_lines, free)
    body = "\n".join(lines)
    upper = body.upper()

    pid_match = _PROGRAM_ID.search(body)
    program_id = pid_match.group(1).upper() if pid_match else p.stem.upper()

    fields: list[CobolField] = []
    for line in _logical_data_lines(lines):
        m = _DATA_ITEM.match(line)
        if not m:
            continue
        level = int(m.group(1))
        name = m.group(2).upper()
        rest = m.group("rest") or ""
        if level in (88,):  # condition names carry no storage
            continue
        pic_m = _PIC.search(rest)
        pic = pic_m.group(1) if pic_m else None
        usage_m = _USAGE.search(rest)
        usage = (usage_m.group(1) or usage_m.group(2)).upper() if usage_m else None
        digits = scale = alpha = 0
        signed = False
        if pic:
            digits, scale, signed, alpha = _expand_pic(pic)
        fields.append(
            CobolField(
                name=name,
                level=level,
                pic=pic,
                usage=usage,
                digits=digits,
                scale=scale,
                signed=signed,
                alpha_len=alpha,
            )
        )

    paragraphs: list[str] = []
    in_proc = False
    for line in lines:
        if re.search(r"\bPROCEDURE\s+DIVISION\b", line, re.I):
            in_proc = True
            continue
        if not in_proc:
            continue
        pm = _PARAGRAPH.match(line.rstrip())
        if pm:
            nm = pm.group(1).upper()
            if nm not in {"EXIT", "END-IF", "STOP"} and not nm.endswith("DIVISION"):
                paragraphs.append(nm)

    unsupported = [name for name, rx in _UNSUPPORTED.items() if re.search(rx, upper, re.M)]

    return CobolProgram(
        path=str(p),
        program_id=program_id,
        source=source,
        free_format=free,
        loc=len([l for l in raw_lines if l.strip()]),
        accept_count=len(re.findall(r"\bACCEPT\b", upper)),
        display_count=len(re.findall(r"\bDISPLAY\b", upper)),
        fields=fields,
        paragraphs=paragraphs,
        file_selects=[m.upper() for m in _SELECT.findall(body)],
        unsupported=unsupported,
    )


def brief(prog: CobolProgram) -> str:
    """Compact, factual description handed to the model alongside the source."""
    lines = [
        f"PROGRAM-ID: {prog.program_id}",
        f"Source format: {'free' if prog.free_format else 'fixed'}",
        f"Non-blank lines: {prog.loc}",
        f"ACCEPT statements (stdin reads): {prog.accept_count}",
        f"DISPLAY statements (stdout writes): {prog.display_count}",
    ]
    if prog.file_selects:
        lines.append("File SELECTs: " + ", ".join(prog.file_selects))
    if prog.paragraphs:
        lines.append("Paragraphs: " + ", ".join(prog.paragraphs[:40]))
    if prog.unsupported:
        lines.append("Constructs flagged for review: " + ", ".join(prog.unsupported))
    numeric = [f for f in prog.fields if f.digits]
    if numeric:
        lines.append("Numeric fields (name PIC -> digits,scale,signed):")
        for f in numeric[:40]:
            lines.append(
                f"  {f.name} PIC {f.pic} usage={f.usage or 'DISPLAY'} "
                f"-> digits={f.digits} scale={f.scale} signed={f.signed}"
            )
    alpha = [f for f in prog.fields if f.alpha_len]
    if alpha:
        lines.append("Alphanumeric fields (fixed width, space padded):")
        for f in alpha[:40]:
            lines.append(f"  {f.name} PIC {f.pic} -> width={f.alpha_len}")
    return "\n".join(lines)
