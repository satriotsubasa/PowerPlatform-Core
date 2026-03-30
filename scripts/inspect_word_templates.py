#!/usr/bin/env python3
"""Inspect Word templates and summarize content controls."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from powerplatform_common import discover_repo_context, repo_root

WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
WORD_TEMPLATE_SUFFIXES = {".docx", ".dotx"}
WORD_PART_PREFIX = "word/"
WORD_PART_SUFFIXES = {".xml"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect .docx or .dotx files and summarize content controls for document-template work.",
    )
    parser.add_argument("--path", help="Template file or directory to inspect. Defaults to the inferred Word Templates area.")
    parser.add_argument("--repo-root", default=".", help="Repository root used when inferring the Word Templates area.")
    parser.add_argument("--recurse", action="store_true", help="Recurse when the target path is a directory.")
    parser.add_argument("--summary-only", action="store_true", help="Return per-file summaries without full control detail.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    target = resolve_target_path(repo, args.path)
    files = collect_template_files(target, recurse=args.recurse)

    documents = [inspect_template(path, repo=repo, summary_only=args.summary_only) for path in files]
    payload = {
        "success": True,
        "mode": "inspect-word-templates",
        "target": str(target),
        "documentCount": len(documents),
        "documents": documents,
    }

    output_text = json.dumps(payload, indent=2)
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text + "\n", encoding="utf-8")
    print(output_text)
    return 0


def resolve_target_path(repo: Path, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path)
        return candidate.resolve() if candidate.is_absolute() else (repo / candidate).resolve()

    context = discover_repo_context(repo)
    inferred = context.get("inferred", {})
    relative = inferred.get("word_templates_area")
    if isinstance(relative, str) and relative.strip():
        return (repo / relative).resolve()

    raise RuntimeError(
        "Could not infer a Word Templates area from this repo. Pass --path explicitly."
    )


def collect_template_files(target: Path, *, recurse: bool) -> list[Path]:
    if target.is_file():
        if target.suffix.lower() not in WORD_TEMPLATE_SUFFIXES:
            raise RuntimeError(f"Unsupported template file type: {target.suffix}")
        return [target]

    if not target.is_dir():
        raise RuntimeError(f"Target path does not exist: {target}")

    iterator: Iterable[Path]
    if recurse:
        iterator = target.rglob("*")
    else:
        iterator = target.iterdir()

    files = sorted(
        path for path in iterator
        if path.is_file() and path.suffix.lower() in WORD_TEMPLATE_SUFFIXES
    )
    if not files:
        raise RuntimeError(f"No .docx or .dotx files found under {target}")
    return files


def inspect_template(path: Path, *, repo: Path, summary_only: bool) -> dict[str, object]:
    controls = []
    duplicate_tags: dict[str, int] = {}
    duplicate_aliases: dict[str, int] = {}

    with zipfile.ZipFile(path) as archive:
        for part_name in sorted(archive.namelist()):
            lower = part_name.lower()
            if not lower.startswith(WORD_PART_PREFIX) or Path(lower).suffix not in WORD_PART_SUFFIXES:
                continue
            if "/theme/" in lower or "/fonttable" in lower or "/styles" in lower:
                continue
            with archive.open(part_name) as stream:
                try:
                    root = ET.parse(stream).getroot()
                except ET.ParseError:
                    continue
            controls.extend(extract_content_controls(root, part_name))

    for control in controls:
        tag = control.get("tag")
        alias = control.get("alias")
        if isinstance(tag, str) and tag:
            duplicate_tags[tag] = duplicate_tags.get(tag, 0) + 1
        if isinstance(alias, str) and alias:
            duplicate_aliases[alias] = duplicate_aliases.get(alias, 0) + 1

    document = {
        "path": str(path),
        "relativePath": str(path.relative_to(repo)) if path.is_relative_to(repo) else str(path),
        "fileName": path.name,
        "controlCount": len(controls),
        "duplicateTags": sorted(name for name, count in duplicate_tags.items() if count > 1),
        "duplicateAliases": sorted(name for name, count in duplicate_aliases.items() if count > 1),
        "contentControlNames": sorted(
            {
                value
                for control in controls
                for value in (control.get("alias"), control.get("tag"))
                if isinstance(value, str) and value
            }
        ),
    }
    if not summary_only:
        document["controls"] = controls
    return document


def extract_content_controls(root: ET.Element, part_name: str) -> list[dict[str, object]]:
    controls = []
    for sdt in root.findall(".//w:sdt", WORD_NAMESPACE):
        properties = sdt.find("w:sdtPr", WORD_NAMESPACE)
        content = sdt.find("w:sdtContent", WORD_NAMESPACE)
        alias = attribute_value(properties, "alias", "val")
        tag = attribute_value(properties, "tag", "val")
        title = attribute_value(properties, "placeholder", "docPart")
        controls.append(
            {
                "part": part_name,
                "alias": alias,
                "tag": tag,
                "title": title,
                "type": infer_content_control_type(properties),
                "textSample": extract_text_sample(content),
            }
        )
    return controls


def attribute_value(properties: ET.Element | None, child_name: str, attribute_name: str) -> str | None:
    if properties is None:
        return None
    child = properties.find(f"w:{child_name}", WORD_NAMESPACE)
    if child is None:
        return None
    return child.attrib.get(f"{{{WORD_NAMESPACE['w']}}}{attribute_name}")


def infer_content_control_type(properties: ET.Element | None) -> str:
    if properties is None:
        return "unknown"
    for type_name in [
        "repeatingSection",
        "repeatingSectionItem",
        "date",
        "dropDownList",
        "comboBox",
        "picture",
        "checkbox",
        "richText",
        "text",
        "group",
    ]:
        if properties.find(f"w:{type_name}", WORD_NAMESPACE) is not None:
            return type_name
    if properties.find("w:dataBinding", WORD_NAMESPACE) is not None:
        return "dataBinding"
    return "generic"


def extract_text_sample(content: ET.Element | None) -> str | None:
    if content is None:
        return None
    texts = [
        node.text.strip()
        for node in content.findall(".//w:t", WORD_NAMESPACE)
        if node.text and node.text.strip()
    ]
    if not texts:
        return None
    sample = " ".join(texts)
    return sample[:200]


if __name__ == "__main__":
    raise SystemExit(main())
