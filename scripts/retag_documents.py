#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_mapping(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.items()
    elif isinstance(payload, list):
        items = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            doc_id = str(row.get("doc_id", "")).strip()
            topic_id = str(row.get("topic_id", "")).strip()
            if doc_id and topic_id:
                items.append((doc_id, topic_id))
    else:
        raise ValueError("Mapping file must be a JSON object or list.")

    mapping: dict[str, str] = {}
    for key, value in items:
        doc_id = str(key).strip()
        topic_id = str(value).strip()
        if not doc_id or not topic_id:
            continue
        mapping[doc_id] = topic_id
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="Retag course documents in state.json with explicit doc->topic mappings.")
    parser.add_argument("--state-file", default="data/state.json", help="Path to bridge state file.")
    parser.add_argument(
        "--mapping-file",
        required=True,
        help="JSON mapping file: either {\"doc_id\":\"topic_id\"} or [{\"doc_id\":\"...\",\"topic_id\":\"...\"}].",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to state file.")
    args = parser.parse_args()

    state_path = Path(args.state_file).resolve()
    mapping_path = Path(args.mapping_file).resolve()
    if not state_path.exists():
        print(f"State file not found: {state_path}")
        return 1
    if not mapping_path.exists():
        print(f"Mapping file not found: {mapping_path}")
        return 1

    state = json.loads(state_path.read_text(encoding="utf-8"))
    documents = state.get("documents")
    if not isinstance(documents, list):
        print("No 'documents' array found in state file.")
        return 1

    mapping = _load_mapping(mapping_path)
    if not mapping:
        print("Mapping file contains no valid doc_id/topic_id pairs.")
        return 1

    changed = 0
    skipped = 0
    missing = set(mapping.keys())
    for document in documents:
        if not isinstance(document, dict):
            continue
        doc_id = str(document.get("doc_id", "")).strip()
        if not doc_id:
            continue
        if doc_id not in mapping:
            continue
        target_topic = mapping[doc_id]
        current_topic = str(document.get("topic_id", "")).strip()
        missing.discard(doc_id)
        if current_topic == target_topic:
            skipped += 1
            continue
        document["topic_id"] = target_topic
        changed += 1

    print(f"State file: {state_path}")
    print(f"Mapping file: {mapping_path}")
    print(f"Mapped docs: {len(mapping)}")
    print(f"Changed: {changed}")
    print(f"Already correct: {skipped}")
    print(f"Missing doc_ids in state: {len(missing)}")
    if missing:
        for doc_id in sorted(missing):
            print(f"  - {doc_id}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to write changes.")
        return 0

    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print("Changes written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
