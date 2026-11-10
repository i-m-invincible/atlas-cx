"""Canonical text and offset-preserving MiniLM chunk boundaries."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal, Protocol

MAX_TEXT = 200_000
MAX_UPLOAD = 1024 * 1024
CONTENT_TOKENS = 180
OVERLAP = 30
ENCODER_LIMIT = 256
SourceKind = Literal["pasted", "txt", "markdown"]
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*#*\s*$")
HTML = re.compile(r"^\s*(?:<!doctype\s+html\b|<(?:html|head|body|script)\b)", re.I)


def normalize(value: str) -> str:
    text = "".join(
        c
        for c in value.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
        if c in "\n\t" or unicodedata.category(c) not in {"Cc", "Cs"}
    )
    if not text.strip() or len(text) > MAX_TEXT:
        raise ValueError("Enter 1 to 200,000 characters of UTF-8 text")
    return text


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def decode_upload(raw: bytes, filename: str) -> tuple[str, SourceKind, str]:
    name = PurePosixPath(filename.replace("\\", "/")).name
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in {".txt", ".md", ".markdown"} or len(name) > 200:
        raise ValueError("Choose a .txt, .md, or .markdown file")
    if b"\x00" in raw or raw.startswith((b"%PDF-", b"PK\x03\x04")):
        raise ValueError("Choose plain UTF-8 text or Markdown")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("The file must use UTF-8 encoding") from None
    if HTML.match(decoded) or any(
        unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in decoded
    ):
        raise ValueError("Choose plain UTF-8 text or Markdown")
    return normalize(decoded), "txt" if suffix == ".txt" else "markdown", name


class Tokenizer(Protocol):
    def offsets(self, text: str) -> list[tuple[int, int]]: ...

    def count(self, text: str, *, specials: bool = False) -> int: ...


@dataclass(frozen=True)
class Passage:
    ordinal: int
    heading_path: tuple[str, ...]
    start: int
    end: int
    content: str
    token_count: int
    encoder_text: str


def sections(text: str) -> list[tuple[int, int, tuple[str, ...]]]:
    """Split headings outside fenced blocks, keeping all original text in slices."""
    result: list[tuple[int, int, tuple[str, ...]]] = []
    path: list[tuple[int, str]] = []
    start = offset = 0
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        line_start = line.lstrip()
        if line_start.startswith(("```", "~~~")):
            marker = line_start[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
        match = HEADING.fullmatch(line.rstrip("\r\n")) if fence is None else None
        if match:
            if offset > start:
                result.append((start, offset, tuple(title for _, title in path)))
            depth, heading = len(match[1]), match[2].strip()
            path = [(level, title) for level, title in path if level < depth]
            path.append((depth, heading))
            start = offset
        offset += len(line)
    if start < len(text):
        result.append((start, len(text), tuple(title for _, title in path)))
    return result


def split(text: str, tokenizer: Tokenizer) -> list[Passage]:
    passages: list[Passage] = []
    for start, stop, path in sections(text):
        section = text[start:stop]
        offsets = tokenizer.offsets(section)
        prefix = " / ".join(path)
        # Heading metadata remains exact. Only the model prefix is bounded.
        heading_tokens = tokenizer.offsets(prefix)
        if len(heading_tokens) > 60:
            prefix = prefix[: heading_tokens[59][1]]
        prefix = prefix + "\n" if prefix else ""
        paragraph_starts = [match.end() for match in re.finditer(r"\n[ \t]*\n+", section)]
        index = 0
        while index < len(offsets):
            end = min(index + CONTENT_TOKENS, len(offsets))
            if end < len(offsets):
                # Prefer a complete paragraph near the token limit. Long paragraphs
                # use a sliding token window with exact source offsets.
                paragraph_end = next(
                    (
                        i
                        for i in range(end, index + 89, -1)
                        if any(
                            offsets[i - 1][1] <= cut <= offsets[i][0] for cut in paragraph_starts
                        )
                    ),
                    None,
                )
                if paragraph_end is not None:
                    end = paragraph_end
            while end > index:
                left, right = offsets[index][0], offsets[end - 1][1]
                quote = section[left:right]
                count = tokenizer.count(quote)
                if (
                    0 < count <= CONTENT_TOKENS
                    and tokenizer.count(prefix + quote, specials=True) <= ENCODER_LIMIT
                ):
                    break
                end -= 1
            if end == index:
                raise ValueError("A source passage cannot be encoded within the model limit")
            passages.append(
                Passage(
                    len(passages), path, start + left, start + right, quote, count, prefix + quote
                )
            )
            if end == len(offsets):
                break
            index = max(index + 1, end - OVERLAP)
    if not passages:
        raise ValueError("No indexable text")
    return passages
