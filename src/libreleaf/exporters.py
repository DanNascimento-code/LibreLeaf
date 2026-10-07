import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol


class Recordable(Protocol):
    def to_record(self) -> dict[str, Any]: ...


def export_records(items: Iterable[Recordable], output_path: Path) -> int:
    """Atomically export normalized records to JSON or CSV."""

    records = [item.to_record() for item in items]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    try:
        if output_path.suffix.lower() == ".json":
            temporary.write_text(
                json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        elif output_path.suffix.lower() == ".csv":
            _write_csv(records, temporary)
        else:
            raise ValueError("Export path must end in .json or .csv")
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return len(records)


def _write_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    fieldnames = list(records[0]) if records else []
    with output_path.open("w", encoding="utf-8", newline="") as file:
        if not fieldnames:
            return
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, list | dict)
                    else value
                    for key, value in record.items()
                }
            )
