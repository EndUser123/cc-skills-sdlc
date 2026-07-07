"""
wiki_signal_dispatch.py — Stage 4 runner for the signal-extract pipeline.

Reads the chunk _manifest.json produced by wiki_signal_distill.py and emits a
DISPATCH PLAN (markdown) the main Claude session executes. The script itself
never calls an LLM — it is provider-neutral. Two output shapes:

  `--mode plan`   (default): writes a markdown dispatch plan listing one
     Task-tool-callable block per chunk, with the verification prompt pre-filled
     from the chunk's candidates + context snippets. The main session then
     spawns one subagent per block (Claude path) OR pipes each block to /ai-cli
     (local-LLM path).
  `--mode ai-cli`: writes, in addition to the plan, one shell command per chunk
     invoking /ai-cli with the chunk file as the prompt payload. Run the script
     file yourself to dispatch the local-LLM batch.

The plan is the source of truth — even in ai-cli mode, the markdown documents
what each call is verifying and where the output page should land.

Usage:
    python wiki_signal_dispatch.py \\
        --manifest P:/.data/wiki/_incoming/distill_chunks/_manifest.json \\
        --chunks-dir P:/.data/wiki/_incoming/distill_chunks \\
        --out P:/.data/wiki/_incoming/dispatch_plan.md \\
        --vault P:/.data/wiki/concepts \\
        --max-chunks 30
    python wiki_signal_dispatch.py --help
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

PROMPT_TEMPLATE = """\
You are distilling verified wiki concept pages from classifier-extracted
candidate sentences. Each candidate below was mined from a session transcript
and survived noise + durable-signature filters — but it is UNVERIFIED until you
check it against the source context provided.

For EACH candidate in this chunk:
  1. Read its `context_snippet` (the >>>-marked line is the anchor). Confirm the
     claim is real and the surrounding code/text supports it. If the snippet is
     ambiguous, you MAY read the full source at `{source_path}` — but prefer the
     snippet; it is pre-extracted to keep your context small.
  2. If the candidate is NOT durable (session-specific event, already-committed
     fix trace, restatement of an existing principle) → SKIP it. Do not write a
     page for it.
  3. If it IS durable → generalize it into a reusable principle and write ONE
     wiki page to `{vault}/<slug>.md` using the standard wiki format (YAML
     frontmatter with title/created/source/tags/summary, then Summary / Key
     Findings / Related / Sources sections).
  4. Slug: kebab-case, derived from the generalized claim (not the raw sentence).
  5. Cite the source file + line in the Sources section.

Candidates (source: {source_file}):
{candidates_block}

After processing all candidates in this chunk, append one log entry per page
written to P:/.data/wiki/log.md:
  ## [YYYY-MM-DD] signal-distill | <title>
  Source: signal-extract-distill
  Source file: {source_path}
"""


def render_candidate(c: dict) -> str:
    sent = c.get("sentence", "").strip()
    ln = c.get("line_no", 0)
    ctx = c.get("context_snippet", "").rstrip()
    nov = c.get("novelty", 0)
    head = f"### candidate (line {ln}, novelty {nov:.0%})\n- sentence: {sent}\n"
    if ctx:
        head += "- context:\n```\n" + ctx + "\n```\n"
    else:
        head += "- context: (not located in source — read the file to verify)\n"
    return head


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True, help="_manifest.json from wiki_signal_distill.py")
    ap.add_argument("--chunks-dir", required=True, help="Directory holding the chunk .json files")
    ap.add_argument("--out", required=True, help="Output dispatch-plan markdown path")
    ap.add_argument("--vault", default="P:/.data/wiki/concepts", help="Wiki concepts dir (for page-write instructions)")
    ap.add_argument("--max-chunks", type=int, default=0, help="Cap chunks in the plan (0 = all)")
    ap.add_argument("--mode", choices=["plan", "ai-cli"], default="plan",
                    help="plan = markdown dispatch; ai-cli = also emit one /ai-cli shell cmd per chunk")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    chunks_dir = Path(args.chunks_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if args.max_chunks and len(manifest) > args.max_chunks:
        manifest = manifest[: args.max_chunks]

    lines = [
        "# Stage 4 dispatch plan",
        "",
        f"- Chunks: {len(manifest)}",
        f"- Vault: `{args.vault}`",
        f"- Mode: `{args.mode}`",
        "",
        "## How to execute",
        "",
        "**Claude subagents** — for each chunk block below, spawn one Task-tool",
        "subagent with the block as its prompt. Collect written page paths.",
        "",
        "**Local/cheap LLM** — pipe each chunk file to /ai-cli in parallel.",
        "One shell command per chunk is listed under `ai-cli` mode below.",
        "",
        "After all chunks complete, run the QMD update:",
        "```powershell",
        "pwsh -NoProfile -File \"P:/.claude/hooks/scripts/qmd_update_wrapper.ps1\"",
        "```",
        "",
        "---",
        "",
    ]

    ai_cli_cmds: list[str] = []

    for i, entry in enumerate(manifest, 1):
        chunk_path = Path(entry["chunk"])
        if not chunk_path.is_absolute():
            chunk_path = (chunks_dir / chunk_path.name).resolve()
        if not chunk_path.exists():
            lines.append(f"## Chunk {i}: {entry['source_file']} — MISSING\n")
            lines.append(f"  chunk file not found: `{chunk_path}`\n")
            continue
        data = json.loads(chunk_path.read_text(encoding="utf-8"))
        candidates_block = "\n".join(render_candidate(c) for c in data.get("candidates", []))
        prompt = PROMPT_TEMPLATE.format(
            source_file=data["source_file"],
            source_path=data["source_path"],
            vault=args.vault,
            candidates_block=candidates_block,
        )
        lines.append(f"## Chunk {i}: `{data['source_file']}` ({entry['candidate_count']} candidates)")
        lines.append("")
        lines.append(f"chunk file: `{chunk_path}`")
        lines.append("")
        lines.append("```")
        lines.append(prompt.rstrip())
        lines.append("```")
        lines.append("")
        if args.mode == "ai-cli":
            # Quote-safe payload path: write the prompt to a sibling .prompt file
            prompt_file = chunk_path.with_suffix(".prompt.txt")
            prompt_file.write_text(prompt, encoding="utf-8")
            ai_cli_cmds.append(
                f'ai-cli "<prompt-from:{prompt_file}>" --output "{chunk_path.with_suffix(".distilled.md")}"'
            )

    if args.mode == "ai-cli" and ai_cli_cmds:
        lines.append("---")
        lines.append("")
        lines.append("## ai-cli shell commands (run in parallel)")
        lines.append("")
        lines.append("```bash")
        lines.extend(ai_cli_cmds)
        lines.append("```")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote dispatch plan: {out_path}")
    print(f"chunks: {len(manifest)}")
    if args.mode == "ai-cli":
        print(f"ai-cli commands: {len(ai_cli_cmds)}")
    print(f"\nNext: open {out_path} and execute chunk-by-chunk (Claude Task-tool),")
    print("or run the ai-cli block in parallel for the local-LLM path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())