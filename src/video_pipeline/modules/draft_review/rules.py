from __future__ import annotations

from collections import Counter
import re
from typing import Any

from ...models import Issue


RULE_VERSION = "draft-review/0.1"
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PRIVATE_URL_PATTERN = re.compile(r"\b(?:localhost|127\.0\.0\.1|[a-z0-9-]+\.(?:test|local))\b", re.IGNORECASE)


def deterministic_issues(media: dict[str, Any], script: str) -> list[Issue]:
    issues: list[Issue] = []
    height = int(media.get("height") or 0)
    if height and height < 1080:
        issues.append(Issue(
            timestamp_sec=0,
            title="Confirm the final export resolution",
            problem=f"This review file is {media.get('width', 0)}×{height}. Small interface text may be difficult to judge.",
            fix="Use the intended delivery export for the final check, or confirm that this is only a review proxy.",
            severity="needs_decision", category="delivery", confidence=1.0, source="local_rule",
        ))

    audio = media.get("audio", {})
    loudness = audio.get("integrated_lufs") if audio.get("available") else None
    if loudness is not None and loudness < -24:
        issues.append(Issue(
            timestamp_sec=0,
            title="Dialogue may be too quiet",
            problem=f"The local loudness scan measured approximately {loudness:.1f} LUFS for the complete mix.",
            fix="Listen against a normal published video, then raise and normalize the voice mix if it is noticeably quieter. Check for clipping after the change.",
            severity="suggestion", category="audio", confidence=0.85, source="local_rule",
        ))

    issues.extend(_privacy_issues(media.get("ocr", [])))
    issues.extend(_repetition_issues(media.get("transcript", [])))
    issues.extend(_script_coverage_issues(media.get("transcript", []), script))
    return issues


def _privacy_issues(records: list[dict[str, Any]]) -> list[Issue]:
    issues = []
    last_time = -30.0
    for item in records:
        text = item.get("text", "")
        matches = EMAIL_PATTERN.findall(text)
        if not matches:
            continue
        time_sec = float(item.get("time_sec", 0))
        if time_sec - last_time < 8:
            continue
        last_time = time_sec
        issues.append(Issue(
            timestamp_sec=time_sec,
            title="Possible account information is visible",
            problem="The screen-text scan found what appears to be an email address. The report intentionally does not repeat it.",
            fix="Inspect this frame and blur the account information if it belongs to a real person or production account.",
            severity="required", category="privacy", confidence=0.9,
            evidence_frame=item.get("frame"), source="local_rule",
        ))
    return issues


def _repetition_issues(segments: list[dict[str, Any]]) -> list[Issue]:
    issues = []
    for segment in segments:
        text = re.sub(r"[^a-z0-9' ]+", " ", segment.get("text", "").lower())
        words = text.split()
        found = None
        for size in range(5, 1, -1):
            for index in range(0, len(words) - size * 2 + 1):
                if words[index:index + size] == words[index + size:index + size * 2]:
                    found = " ".join(words[index:index + size])
                    break
            if found:
                break
        if found:
            issues.append(Issue(
                timestamp_sec=float(segment.get("start_sec", 0)),
                title="Possible repeated take",
                problem=f"The phrase “{found}” appears twice in immediate succession.",
                fix="Listen to this sentence and remove the repeated take if it is an edit mistake.",
                severity="required", category="a_roll", confidence=0.95, source="local_rule",
            ))
    return issues


def _tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "and", "or", "to", "of", "in", "is", "it", "this", "that", "you", "your", "we", "our"}
    return {word for word in re.findall(r"[a-z0-9]{2,}", text.lower()) if word not in stop}


def _script_coverage_issues(segments: list[dict[str, Any]], script: str) -> list[Issue]:
    if not segments:
        return []
    transcript_text = " ".join(item.get("text", "") for item in segments)
    transcript_tokens = _tokens(transcript_text)
    chunks = [line.strip(" #-*\t") for line in script.splitlines() if len(_tokens(line)) >= 7]
    missing = []
    for line in chunks:
        terms = _tokens(line)
        coverage = len(terms & transcript_tokens) / max(len(terms), 1)
        if coverage < 0.35:
            missing.append(line)
        if len(missing) == 6:
            break
    if not missing:
        return []
    return [Issue(
        timestamp_sec=0,
        title="Some approved-script lines may be absent",
        problem=f"The word-level check could not confidently find {len(missing)} script line(s) in the transcript. This can also happen when the host paraphrases or transcription is imperfect.",
        fix="Compare the report's unmatched script excerpts with the recording and restore a clean take only when the meaning is genuinely missing.",
        severity="needs_decision", category="script", confidence=0.55, source="local_rule",
        evidence_frame=None,
    )]


def deduplicate_issues(issues: list[Issue]) -> list[Issue]:
    chosen: list[Issue] = []
    for item in sorted(issues, key=lambda issue: (issue.timestamp_sec, issue.title.lower())):
        signature = set(re.findall(r"[a-z0-9]+", (item.title + " " + item.problem).lower()))
        duplicate = False
        for prior in chosen:
            if abs(prior.timestamp_sec - item.timestamp_sec) > 5:
                continue
            prior_signature = set(re.findall(r"[a-z0-9]+", (prior.title + " " + prior.problem).lower()))
            similarity = len(signature & prior_signature) / max(len(signature | prior_signature), 1)
            if similarity >= 0.7:
                duplicate = True
                if item.confidence > prior.confidence:
                    chosen.remove(prior)
                    chosen.append(item)
                break
        if not duplicate:
            chosen.append(item)
    for index, item in enumerate(sorted(chosen, key=lambda issue: issue.timestamp_sec), 1):
        item.issue_id = f"ISSUE-{index:03d}"
    return sorted(chosen, key=lambda issue: issue.timestamp_sec)
