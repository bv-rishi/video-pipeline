from __future__ import annotations

from collections import Counter
import html
from pathlib import Path
from typing import Iterable

from .models import ReviewResult
from .util import timestamp, write_json


def write_reports(result: ReviewResult, job_dir: Path) -> None:
    write_json(job_dir / "report.json", result.to_dict())
    (job_dir / "report.md").write_text(_markdown(result), encoding="utf-8")
    (job_dir / "report.html").write_text(_html(result), encoding="utf-8")


def _markdown(result: ReviewResult) -> str:
    counts = Counter(issue.severity for issue in result.issues)
    lines = [
        f"# Video review: {result.title}", "",
        f"Editor: **{result.editor}**  ",
        f"Status: **{result.status.replace('_', ' ').title()}**  ",
        f"Required: **{counts['required']}** · Suggestions: **{counts['suggestion']}** · Needs decision: **{counts['needs_decision']}**",
        "", "## Timestamped findings", "",
    ]
    if not result.issues:
        lines.extend(["No supported issues were returned. Check the warnings and confirm that transcription, OCR, and GLM all ran.", ""])
    for issue in result.issues:
        lines.extend([
            f"### {timestamp(issue.timestamp_sec)} — {issue.title}", "",
            f"**{issue.severity.replace('_', ' ').title()} · {issue.category} · confidence {issue.confidence:.0%}**", "",
            issue.problem, "", f"**Change:** {issue.fix}", "",
        ])
        if issue.evidence_frame:
            lines.extend([f"Evidence: `analysis/frames/{issue.evidence_frame}`", ""])
    if result.warnings:
        lines.extend(["## Run warnings", ""] + [f"- {item}" for item in result.warnings] + [""])
    lines.extend([
        "## Editor handoff", "",
        f"After making the required changes, mark the batch ready for {result.reviewer_label} with `video-pipeline ready --batch-id BATCH_ID`.",
        "This release relies on the editor's confirmation and does not recheck the revised video.", "",
    ])
    return "\n".join(lines)


def _html(result: ReviewResult) -> str:
    counts = Counter(issue.severity for issue in result.issues)
    cards = []
    for issue in result.issues:
        image = ""
        if issue.evidence_frame:
            source = html.escape(f"analysis/frames/{issue.evidence_frame}", quote=True)
            image = f'<a class="evidence" href="{source}"><img loading="lazy" src="{source}" alt="Evidence at {timestamp(issue.timestamp_sec)}"></a>'
        cards.append(f"""
        <article class="issue {html.escape(issue.severity)}">
          <div class="time">{timestamp(issue.timestamp_sec)}</div>
          <div class="copy">
            <div class="labels"><span>{html.escape(issue.severity.replace('_', ' '))}</span><span>{html.escape(issue.category)}</span><span>{issue.confidence:.0%} confidence</span></div>
            <h2>{html.escape(issue.title)}</h2>
            <p>{html.escape(issue.problem)}</p>
            <p class="fix"><strong>Change:</strong> {html.escape(issue.fix)}</p>
          </div>{image}
        </article>""")
    warning_html = "".join(f"<li>{html.escape(item)}</li>" for item in result.warnings)
    empty = "<p class='empty'>No supported issues were returned. Confirm that all analysis stages ran before treating this as a clean review.</p>" if not cards else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Video review — {html.escape(result.title)}</title>
<style>
:root{{--ink:#17202a;--muted:#667085;--paper:#f6f6f1;--card:#fff;--required:#c9362b;--decision:#a15c00;--suggestion:#2563a7}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1080px;margin:auto;padding:48px 24px 80px}} h1{{font-size:clamp(34px,5vw,58px);line-height:1.03;margin:0 0 12px;letter-spacing:-.035em}}
.intro{{color:var(--muted);font-size:18px}} .summary{{display:flex;gap:12px;flex-wrap:wrap;margin:28px 0 42px}} .metric{{background:var(--card);padding:14px 18px;border-radius:14px;box-shadow:0 1px 3px #0001}}
.metric b{{font-size:24px;margin-right:7px}} .issue{{display:grid;grid-template-columns:80px 1fr minmax(0,260px);gap:22px;background:var(--card);padding:22px;border-radius:16px;margin:16px 0;border-left:5px solid var(--suggestion);box-shadow:0 2px 8px #0000000d}}
.issue.required{{border-left-color:var(--required)}} .issue.needs_decision{{border-left-color:var(--decision)}} .time{{font:700 17px ui-monospace,SFMono-Regular,monospace;padding-top:3px}}
.labels{{display:flex;gap:8px;flex-wrap:wrap}} .labels span{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);background:#f1f3f5;border-radius:999px;padding:4px 8px}}
h2{{font-size:21px;line-height:1.25;margin:10px 0 7px}} p{{margin:7px 0}} .fix{{background:#f6f8fa;padding:10px 12px;border-radius:9px}} .evidence img{{display:block;width:100%;border-radius:10px;border:1px solid #ddd}}
.warnings{{margin-top:40px;padding:20px;background:#fff7e6;border-radius:14px}} code{{word-break:break-all}} .empty{{padding:24px;background:white;border-radius:14px}}
@media(max-width:760px){{.issue{{grid-template-columns:1fr}} .evidence img{{max-width:420px}}}}
</style></head><body><main>
<h1>{html.escape(result.title)}</h1>
<p class="intro">Editor: {html.escape(result.editor)} · {html.escape(result.status.replace('_',' ').title())} · {html.escape(result.completed_at)}</p>
<section class="summary"><div class="metric"><b>{counts['required']}</b> required</div><div class="metric"><b>{counts['suggestion']}</b> suggestions</div><div class="metric"><b>{counts['needs_decision']}</b> need a decision</div></section>
{empty}{''.join(cards)}
{f'<section class="warnings"><h2>Run warnings</h2><ul>{warning_html}</ul></section>' if warning_html else ''}
<section class="warnings"><h2>Editor handoff</h2><p>Make the required changes, then mark the batch ready for {html.escape(result.reviewer_label)}. This release uses the editor's confirmation and does not automatically recheck the revision.</p></section>
</main></body></html>"""
