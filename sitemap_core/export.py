"""Filter entries and write them out as CSV or plain text."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Iterable, Iterator, TextIO

from .classify import ARTICLE, TYPE_LABELS
from .extract import Entry

FIELDS = ("site", "url", "lastmod", "source_sitemap", "type")
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass
class Filter:
    types: frozenset[str] | None = frozenset({ARTICLE})  # None = every type
    include: tuple[str, ...] = ()       # URL must contain at least one of these
    exclude: tuple[str, ...] = ()       # URL must contain none of these
    date_from: str = ""                 # YYYY-MM-DD, compared with lastmod
    date_to: str = ""
    skip_sources: frozenset[str] = frozenset()
    # Sites listed here ignore `types`: used when a site has no detectable articles.
    fallback_sites: frozenset[str] = field(default_factory=frozenset)

    def matches(self, entry: Entry) -> bool:
        if entry.source in self.skip_sources:
            return False
        if self.types is not None and entry.type not in self.types and entry.site not in self.fallback_sites:
            return False
        url = entry.url.lower()
        if self.include and not any(k.lower() in url for k in self.include):
            return False
        if self.exclude and any(k.lower() in url for k in self.exclude):
            return False
        if self.date_from or self.date_to:
            day = entry.lastmod[:10]
            if not day:
                return False
            if self.date_from and day < self.date_from:
                return False
            if self.date_to and day > self.date_to:
                return False
        return True

    def apply(self, entries: Iterable[Entry]) -> Iterator[Entry]:
        return (e for e in entries if self.matches(e))


def safe_cell(value: str) -> str:
    """Neutralise spreadsheet formula injection: '=cmd' becomes "'=cmd"."""
    return "'" + value if value.startswith(_FORMULA_PREFIXES) else value


def csv_rows(entries: Iterable[Entry], lang: str = "zh") -> Iterator[list[str]]:
    labels = TYPE_LABELS.get(lang, TYPE_LABELS["en"])
    yield list(FIELDS)
    for e in entries:
        yield [safe_cell(e.site), safe_cell(e.url), safe_cell(e.lastmod), safe_cell(e.source),
               labels.get(e.type, e.type)]


def write_csv(entries: Iterable[Entry], out: TextIO, lang: str = "zh") -> int:
    """Write entries as CSV to an open text file. Returns the number of data rows."""
    writer = csv.writer(out, lineterminator="\r\n")
    count = -1
    for row in csv_rows(entries, lang):
        writer.writerow(row)
        count += 1
    return count


def write_txt(entries: Iterable[Entry], out: TextIO) -> int:
    count = 0
    for e in entries:
        out.write(e.url + "\n")
        count += 1
    return count
