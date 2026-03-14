#!/usr/bin/env python3
"""
Maintenance-Eye Bug Tracker Utility
Standardized tool for managing BUG_REPORT.md across different AI agents.
"""

import argparse
import re
from pathlib import Path

BUG_REPORT_PATH = Path(__file__).parent.parent / "BUG_REPORT.md"


def load_bug_report():
    if not BUG_REPORT_PATH.exists():
        return ""
    return BUG_REPORT_PATH.read_text()


def save_bug_report(content):
    BUG_REPORT_PATH.write_text(content)


def get_next_id(content, prefix="C"):
    ids = re.findall(rf"{prefix}-(\d+)", content)
    if not ids:
        return f"{prefix}-001"
    next_num = max(int(i) for i in ids) + 1
    return f"{prefix}-{next_num:03d}"


def add_bug(description, severity, component, impact):
    content = load_bug_report()

    # Determine ID prefix based on severity
    prefix = "C" if severity.lower() == "critical" else "H" if severity.lower() == "high" else "M"
    bug_id = get_next_id(content, prefix)

    new_row = f"| **{bug_id}** | {component} | {description} | {impact} |"

    # Find the right section to insert
    section_map = {
        "critical": "## 1. Critical Bugs",
        "high": "## 2. Architectural Misalignments",  # In current BUG_REPORT format
        "medium": "## 3. Missing Features & UX Gaps",
    }

    section_header = section_map.get(severity.lower(), "## 1. Critical Bugs")

    if section_header in content:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith(section_header):
                # Find the table header and insert after it
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith("|---"):
                        lines.insert(j + 1, new_row)
                        break
                break
        content = "\n".join(lines)
    else:
        content += (
            f"\n\n{section_header}\n\n"
            "| ID | Component | Issue | Impact |\n"
            "|:---|:---|:---|:---|\n"
            f"{new_row}"
        )

    # Update total count
    total_issues = len(re.findall(r"\| \*\*.*-\d+\*\* \|", content))
    content = re.sub(r"\*\*Total Issues\*\*: \d+", f"**Total Issues**: {total_issues}", content)

    save_bug_report(content)
    print(f"Added bug {bug_id} to BUG_REPORT.md")


def update_status(bug_id, status):
    content = load_bug_report()
    escaped_bug_id = re.escape(bug_id)
    pattern = re.compile(rf"\*\*{escaped_bug_id}\*\*(?:\s+\([^)]+\))?")

    if not pattern.search(content):
        print(f"Bug ID {bug_id} not found.")
        return

    replacement = f"**{bug_id}** ({status})"
    updated_content = pattern.sub(replacement, content, count=1)
    save_bug_report(updated_content)
    print(f"Updated status for {bug_id} to {status}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Maintenance-Eye bugs.")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("description")
    add_parser.add_argument("--severity", choices=["critical", "high", "medium"], default="medium")
    add_parser.add_argument("--component", default="General")
    add_parser.add_argument("--impact", default="TBD")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("bug_id")
    update_parser.add_argument("--status", required=True)

    args = parser.parse_args()

    if args.command == "add":
        add_bug(args.description, args.severity, args.component, args.impact)
    elif args.command == "update":
        update_status(args.bug_id, args.status)
    else:
        parser.print_help()
