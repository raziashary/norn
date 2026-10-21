"""Validate Norn's development records; never execute planned runtime commands.

Standard library only. This checks structure, references and status accounting.
Full blueprint fidelity and scientific validity require independent human review.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import unquote


REQUIRED = {
    "README.md", "MASTER_DEV_PLAN.md", "GOAL.md", "PROJECT_MEMORY.md",
    "PROJECT_MAP.md", "PROGRESS.md", "READINESS_MATRIX.md", "ADR_LOG.md",
    "TESTING_GATES.md", "REQUIREMENTS_TRACEABILITY.md", "RESEARCH_PROTOCOL.md",
    "RISKS_AND_OPEN_QUESTIONS.md", "PROJECT_LEARNING.md", "EVIDENCE_LOG.md",
}
DESIGN_ANCHORS = {
    "execution-contract", "scope", "reference-reuse", "architecture", "contracts",
    "canonical-schema", "derived-schema", "identity-time", "write-flow", "read-flow",
    "binding", "learning", "graph-algorithms", "optional-mechanisms", "operations",
    "evaluation", "security", "worked-scenarios", "phase-plan", "atomic-register",
}
TASK_FIELDS = {
    "State", "Files", "Depends", "Source", "Change", "Consumer", "Positive proof",
    "Negative proof", "Gate", "Commands", "Evidence", "Completion",
}
TASK_STATES = {"PLANNED", "IN_PROGRESS", "BLOCKED", "DONE", "DEFERRED"}
GATE_STATES = {"NOT_RUN", "PARTIAL", "PASS", "FAIL", "BLOCKED"}
TASK_ID = re.compile(r"\bP\d{2}-T\d{2}\b")
GATE_ID = re.compile(r"\bG-[A-Z]+\b")


@dataclass(frozen=True)
class CheckResult:
    errors: tuple[str, ...]
    tasks: int
    done: int
    gates: int
    requirements: int
    files: int


def without_fences(text: str) -> str:
    """Leave prose/headings, excluding fenced example links and fake headers."""
    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            char = marker[1][0]
            if fence is None:
                fence = char
            elif fence == char:
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return "\n".join(lines)


def anchors(text: str) -> set[str]:
    clean = without_fences(text)
    result = set(re.findall(r'<a\s+id="([^"]+)"\s*></a>', clean))
    seen: Counter[str] = Counter()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", clean, re.M):
        slug = re.sub(r"[^\w\-\s]", "", heading.lower().replace("`", ""))
        slug = re.sub(r"\s", "-", slug)
        count = seen[slug]
        seen[slug] += 1
        result.add(slug if count == 0 else f"{slug}-{count}")
    return result


def expected_requirements() -> set[str]:
    values = {f"SEC{i:02d}" for i in range(1, 28)}
    for prefix, start, stop in (("I", 1, 11), ("H", 1, 11), ("E", 1, 15),
                                ("B", 0, 6), ("T", 0, 8), ("G", 0, 8),
                                ("S", 0, 3), ("C", 0, 4), ("R", 0, 11),
                                ("ST", 0, 7)):
        values.update(f"{prefix}{i}" for i in range(start, stop))
    values.update(f"REV{i:02d}" for i in range(1, 15))
    values.update(f"OQ{i:02d}" for i in range(1, 13))
    values.update({"CDZ-A", "CDZ-B", "CDZ-C"})
    return values


def field(body: str, name: str) -> str:
    match = re.search(rf"^- \*\*{re.escape(name)}:\*\*[ \t]*(.+)$", body, re.M)
    return match[1].strip() if match else ""


def validate(root: Path) -> CheckResult:
    errors: list[str] = []
    root = root.resolve()
    for name in sorted(REQUIRED):
        if not (root / name).is_file():
            errors.append(f"missing-document: {name}")
    texts = {p: p.read_text(encoding="utf-8") for p in sorted(root.rglob("*.md"))}
    navigation = root.parent / "README.md"
    if navigation.is_file():
        texts[navigation] = navigation.read_text(encoding="utf-8")
    else:
        errors.append("missing-document: parent docs/README.md")
    instructions = root.parent.parent / "AGENTS.md"
    if instructions.is_file():
        texts[instructions] = instructions.read_text(encoding="utf-8")
    anchor_cache: dict[Path, set[str]] = {}
    for unique in ("PROJECT_MEMORY.md", "PROJECT_MAP.md", "GOAL.md"):
        if len(list(root.rglob(unique))) != 1:
            errors.append(f"single-authority: expected exactly one {unique}")
    for path, raw in texts.items():
        explicit = re.findall(r'<a\s+id="([^"]+)"\s*></a>', without_fences(raw))
        if len(explicit) != len(set(explicit)):
            errors.append(f"duplicate-anchor: {path.name}")
        clean = without_fences(raw)
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", clean):
            target = target.strip().strip("<>")
            if re.match(r"^[a-zA-Z][\w+.-]*://", target) or target.startswith("mailto:"):
                continue
            name, _, fragment = target.partition("#")
            resolved = (path.parent / unquote(name)).resolve() if name else path
            if not resolved.exists():
                errors.append(f"broken-link: {path.name} -> {target}")
            elif fragment and resolved.is_file() and resolved.suffix == ".md":
                if resolved not in anchor_cache:
                    anchor_cache[resolved] = anchors(resolved.read_text(encoding="utf-8"))
                if unquote(fragment) not in anchor_cache[resolved]:
                    errors.append(f"broken-anchor: {path.name} -> {target}")
    mdp = texts.get(root / "MASTER_DEV_PLAN.md", "")
    absent = DESIGN_ANCHORS - anchors(mdp)
    if absent:
        errors.append("missing-design: " + ", ".join(sorted(absent)))
    matches = list(re.finditer(r"^### (P\d{2}-T\d{2}) — (.+)$", mdp, re.M))
    ids = [m[1] for m in matches]
    duplicates = [key for key, n in Counter(ids).items() if n > 1]
    if duplicates:
        errors.append("duplicate-task: " + ", ".join(duplicates))
    if not matches:
        errors.append("missing-tasks: no atomic register")
    bodies = {m[1]: mdp[m.end():matches[i+1].start() if i+1 < len(matches) else len(mdp)]
              for i, m in enumerate(matches)}
    gate_text = texts.get(root / "TESTING_GATES.md", "")
    gate_matches = list(re.finditer(r"^## (G-[A-Z]+) — (.+)$", gate_text, re.M))
    gate_ids = [m[1] for m in gate_matches]
    if len(set(gate_ids)) != len(gate_ids):
        errors.append("duplicate-gate: definitions must be unique")
    gate_states: dict[str, str] = {}
    gate_tasks: dict[str, set[str]] = {}
    for i, m in enumerate(gate_matches):
        body = gate_text[m.end():gate_matches[i+1].start() if i+1 < len(gate_matches) else len(gate_text)]
        state = field(body, "State").rstrip(".")
        gate_states[m[1]] = state
        if state not in GATE_STATES:
            errors.append(f"invalid-gate-state: {m[1]} {state}")
        refs = set(TASK_ID.findall(field(body, "Owning atomic tasks")))
        gate_tasks[m[1]] = refs
        if not refs or not refs <= set(ids):
            errors.append(f"invalid-gate-tasks: {m[1]}")
    states: dict[str, str] = {}
    dependencies: dict[str, set[str]] = {}
    for tid, body in bodies.items():
        for name in sorted(TASK_FIELDS):
            if not field(body, name):
                errors.append(f"missing-task-field: {tid} {name}")
        state = field(body, "State").rstrip(".")
        states[tid] = state
        if state not in TASK_STATES:
            errors.append(f"invalid-task-state: {tid} {state}")
        boxes = re.findall(rf"^- \[([ x])\] \*\*{tid}\*\*$", body, re.M)
        if len(boxes) != 1 or (boxes[0] == "x") != (state == "DONE"):
            errors.append(f"checkbox-state: {tid}")
        dependencies[tid] = set(TASK_ID.findall(field(body, "Depends")))
        if not dependencies[tid] and field(body, "Depends").rstrip(".") != "NONE":
            errors.append(f"missing-dependencies: {tid}")
        if not dependencies[tid] <= set(ids):
            errors.append(f"undefined-dependency: {tid}")
        gates = set(GATE_ID.findall(field(body, "Gate")))
        if not gates or not gates <= set(gate_ids):
            errors.append(f"undefined-gate: {tid}")
        files = re.findall(r"`([^`]+)`", field(body, "Files"))
        if not files or any(Path(f).is_absolute() or ".." in Path(f).parts for f in files):
            errors.append(f"invalid-file-ownership: {tid}")
        if state == "DONE" and field(body, "Evidence").startswith("NOT_RUN"):
            errors.append(f"false-done: {tid} has no executed evidence")
        if state == "DONE":
            for filename in files:
                if not (root.parent.parent / filename).is_file():
                    errors.append(f"missing-done-file: {tid} {filename}")
        if state == "DEFERRED" and not all(word in body.lower() for word in ("reason", "owner", "destination")):
            errors.append(f"unowned-deferral: {tid}")
    remaining = {tid: set(dependencies.get(tid, set())) & set(ids) for tid in ids}
    ready = [tid for tid, deps in remaining.items() if not deps]
    visited: set[str] = set()
    while ready:
        node = ready.pop()
        visited.add(node)
        for dependent, deps in remaining.items():
            if node in deps:
                deps.remove(node)
                if not deps and dependent not in visited:
                    ready.append(dependent)
    for node in sorted(set(ids) - visited):
        errors.append(f"dependency-cycle: {node}")
    for tid in ids:
        if states.get(tid) == "DONE" and any(states.get(d) != "DONE" for d in dependencies[tid]):
            errors.append(f"unfinished-dependency: {tid}")
    adr = texts.get(root / "ADR_LOG.md", "")
    adr_ids = re.findall(r"^## (ADR-\d{4}) —", adr, re.M)
    if len(adr_ids) != len(set(adr_ids)):
        errors.append("duplicate-adr: definitions must be unique")
    for path, raw in texts.items():
        for aid in set(re.findall(r"\bADR-\d{4}\b", raw)):
            if aid not in adr_ids:
                errors.append(f"undefined-adr: {path.name} {aid}")
    trace = texts.get(root / "REQUIREMENTS_TRACEABILITY.md", "")
    trace_ids: list[str] = []
    for line in trace.splitlines():
        if not line.startswith("| "):
            continue
        cols = [s.strip() for s in line.strip("|").split("|")]
        if not cols or cols[0] not in expected_requirements():
            continue
        trace_ids.append(cols[0])
        if len(cols) != 6:
            errors.append(f"invalid-trace-row: {cols[0]}")
            continue
        tasks = set(TASK_ID.findall(cols[3]))
        gates = set(GATE_ID.findall(cols[4]))
        if not tasks or not tasks <= set(ids) or not gates or not gates <= set(gate_ids):
            errors.append(f"invalid-trace-reference: {cols[0]}")
    if len(trace_ids) != len(set(trace_ids)):
        errors.append("duplicate-requirement: traceability")
    missing = expected_requirements() - set(trace_ids)
    if missing:
        errors.append("missing-coverage: " + ", ".join(sorted(missing)))
    progress = texts.get(root / "PROGRESS.md", "")
    phase_ids = re.findall(r"^## (P\d{2}) —", mdp, re.M)
    if len(phase_ids) != len(set(phase_ids)):
        errors.append("duplicate-phase: MDP")
    for pid in phase_ids:
        tasks = [t for t in ids if t.startswith(pid + "-")]
        match = re.search(rf"^\| {pid} \| (\d+) \| (\d+) \| (\d+) \|", progress, re.M)
        expected = (len(tasks), sum(states.get(t) == "DONE" for t in tasks),
                    sum(states.get(t) == "DEFERRED" for t in tasks))
        if not match or tuple(map(int, match.groups())) != expected:
            errors.append(f"stale-progress-count: {pid} expected {expected}")
    total = re.search(r"Total atomic tasks: (\d+)\. Total completed: (\d+)\.", progress)
    done = sum(state == "DONE" for state in states.values())
    if not total or tuple(map(int, total.groups())) != (len(ids), done):
        errors.append("stale-total-count: progress register")
    runtime_exists = (root.parent.parent / "src" / "norn").exists()
    for gid, state in gate_states.items():
        if state == "PASS" and any(states.get(tid) != "DONE" for tid in gate_tasks[gid]):
            errors.append(f"false-runtime-gate: {gid} has unfinished owning tasks")
    if not runtime_exists:
        for gid, state in gate_states.items():
            if gid != "G-DOC" and state != "NOT_RUN":
                errors.append(f"false-runtime-gate: {gid}")
        for line in texts.get(root / "READINESS_MATRIX.md", "").splitlines():
            if line.startswith("| ") and "Development suite" not in line:
                if re.search(r"\|\s*(?:PASS|VERIFIED|DONE|IMPLEMENTED)\s*\|", line):
                    errors.append("false-runtime-readiness: absent source")
    return CheckResult(tuple(errors), len(ids), sum(v == "DONE" for v in states.values()),
                       len(gate_ids), len(trace_ids), len(texts))


def completion_without_evidence(text: str) -> str:
    """Damage an actual completed card, independent of the currently active phase."""
    cards = list(re.finditer(r"^### P\d{2}-T\d{2} — .+$", text, re.M))
    for index, card in enumerate(cards):
        end = cards[index + 1].start() if index + 1 < len(cards) else len(text)
        body = text[card.end():end]
        if field(body, "State").rstrip(".") == "DONE":
            changed = re.sub(r"^- \*\*Evidence:\*\*.*$", "- **Evidence:** NOT_RUN.",
                             body, count=1, flags=re.M)
            return text[:card.end()] + changed + text[end:]
    raise ValueError("self-test needs a completed baseline card")


def self_test(root: Path) -> int:
    baseline = validate(root)
    if baseline.errors:
        print("SELF-TEST baseline invalid:")
        print("\n".join(baseline.errors))
        return 1
    cases = [
        ("missing document", "missing-document", "README.md", None),
        ("missing local target", "broken-link", "README.md", lambda s: s + "\n[bad](absent.md)\n"),
        ("missing anchor", "broken-anchor", "README.md", lambda s: s + "\n[bad](MASTER_DEV_PLAN.md#absent)\n"),
        ("duplicate task", "duplicate-task", "MASTER_DEV_PLAN.md", lambda s: s + "\n### P00-T01 — Duplicate\n"),
        ("missing consumer", "missing-task-field", "MASTER_DEV_PLAN.md", lambda s: re.sub(r"^- \*\*Consumer:\*\*.*\n", "", s, count=1, flags=re.M)),
        ("missing negative proof", "missing-task-field", "MASTER_DEV_PLAN.md", lambda s: re.sub(r"^- \*\*Negative proof:\*\*.*\n", "", s, count=1, flags=re.M)),
        ("false completed task", "false-done", "MASTER_DEV_PLAN.md", completion_without_evidence),
        ("undefined dependency", "undefined-dependency", "MASTER_DEV_PLAN.md", lambda s: s.replace("- **Depends:** NONE.", "- **Depends:** P99-T99.", 1)),
        ("cyclic dependency", "dependency-cycle", "MASTER_DEV_PLAN.md", lambda s: s.replace("- **Depends:** NONE.", "- **Depends:** P00-T02.", 1)),
        ("undefined gate", "undefined-gate", "MASTER_DEV_PLAN.md", lambda s: s.replace("- **Gate:** G-DOC.", "- **Gate:** G-NOSUCH.", 1)),
        ("missing coverage", "missing-coverage", "REQUIREMENTS_TRACEABILITY.md", lambda s: re.sub(r"^\| SEC01 .*\n", "", s, flags=re.M)),
        ("stale count", "stale-progress-count", "PROGRESS.md", lambda s: s.replace("| P00 | 6 |", "| P00 | 600 |", 1)),
        ("false runtime", "false-runtime-gate", "TESTING_GATES.md", lambda s: re.sub(r"(## (?!G-DOC)G-[^\n]*\n\n- \*\*State:\*\*) (?:NOT_RUN|PARTIAL|FAIL|BLOCKED)", r"\1 PASS", s, count=1)),
        ("unknown ADR", "undefined-adr", "GOAL.md", lambda s: s + "\nADR-9999\n"),
        ("duplicate authority", "single-authority", "PROJECT_MEMORY.md", "DUPLICATE"),
    ]
    failed = 0
    for name, category, filename, mutate in cases:
        with tempfile.TemporaryDirectory(prefix="norn-docs-control-") as tmp:
            copied = Path(tmp) / "docs" / "development"
            shutil.copytree(root, copied, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(root.parent / "vision", copied.parent / "vision")
            if (root.parent / "README.md").is_file():
                shutil.copy2(root.parent / "README.md", copied.parent / "README.md")
            if (root.parent.parent / "AGENTS.md").is_file():
                shutil.copy2(root.parent.parent / "AGENTS.md", copied.parent.parent / "AGENTS.md")
            for directory in ("src", "benchmark", "tests"):
                source = root.parent.parent / directory
                if source.is_dir():
                    shutil.copytree(source, copied.parent.parent / directory,
                                    ignore=shutil.ignore_patterns("__pycache__"))
            for filename_root in ("pyproject.toml", "uv.lock"):
                source = root.parent.parent / filename_root
                if source.is_file():
                    shutil.copy2(source, copied.parent.parent / filename_root)
            copied_baseline = validate(copied)
            if copied_baseline.errors:
                print(f"FAIL copied baseline before {name}: {copied_baseline.errors}")
                failed += 1
                continue
            target = copied / filename
            if mutate is None:
                target.unlink()
            elif mutate == "DUPLICATE":
                other = copied / "duplicate"
                other.mkdir()
                shutil.copy2(target, other / filename)
            else:
                original = target.read_text(encoding="utf-8")
                changed = mutate(original)
                if changed == original:
                    print(f"FAIL control did not mutate: {name}")
                    failed += 1
                    continue
                target.write_text(changed, encoding="utf-8")
            result = validate(copied)
            if not any(e.startswith(category + ":") for e in result.errors):
                print(f"FAIL {name}: expected {category}, got {result.errors}")
                failed += 1
            else:
                print(f"PASS rejects {name} ({category})")
    print(f"Self-tests: {len(cases)-failed}/{len(cases)} intended rejection controls")
    return int(bool(failed))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test(args.root.resolve())
    result = validate(args.root)
    if result.errors:
        print("\n".join(result.errors))
        print(f"FAIL: {len(result.errors)} documentation errors")
        return 1
    print(f"PASS: {result.files} Markdown files; {result.tasks} atomic tasks "
          f"({result.done} DONE); {result.gates} gates; {result.requirements} coverage rows")
    print("Structural evidence only; runtime and scientific validity require their owning proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
