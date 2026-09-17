"""relook CLI: drop a PDF/DOCX in, get structured JSON out.

    relook samples/                 # process every supported file once
    relook samples/leave.pdf        # process a single file
    relook samples/ --watch         # keep polling the folder for new files

This is the phase-1 pipeline: no database, no review UI yet. Each run writes
one JSON file per document to output/, named after the source file, so you
can inspect the AI's output directly and start building a labeled set of
corrections once a human starts reviewing them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from .classify import analyze_document, result_to_record
from .parsing import UnsupportedDocumentError, is_supported, load_content_blocks, page_count
from .taxonomy import Taxonomy, load_taxonomy

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"
DEFAULT_POLL_SECONDS = 5


def iter_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.iterdir() if p.is_file() and is_supported(p))


def process_file(
    client: anthropic.Anthropic,
    taxonomy: Taxonomy,
    source: Path,
    output_dir: Path,
) -> bool:
    """Returns True on success, False if this file failed (and was skipped)."""
    pages = page_count(source)
    label = f"{source.name}" + (f" ({pages} pages)" if pages else "")
    print(f"-> {label}")

    try:
        blocks = load_content_blocks(source)
        result = analyze_document(client, blocks, taxonomy)
    except UnsupportedDocumentError as e:
        print(f"   skipped: {e}")
        return False
    except anthropic.APIStatusError as e:
        print(f"   API error ({e.status_code}): {e.message}")
        return False
    except anthropic.APIConnectionError:
        print("   network error -- check your connection and retry")
        return False
    except (RuntimeError, json.JSONDecodeError) as e:
        print(f"   analysis failed: {e}")
        return False

    record = result_to_record(result, taxonomy, source)
    output_path = output_dir / f"{source.stem}.json"
    output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    flag = " [NEEDS HUMAN]" if result.needs_human else ""
    print(
        f"   {result.category} (confidence {result.confidence:.2f}){flag}\n"
        f"   {result.summary}\n"
        f"   -> {output_path}"
    )
    return True


def run_once(client: anthropic.Anthropic, taxonomy: Taxonomy, inputs: list[Path], output_dir: Path) -> None:
    files: list[Path] = []
    for path in inputs:
        files.extend(iter_input_files(path))

    if not files:
        print("No supported files found (looking for .pdf, .docx, .txt, .md)")
        return

    ok = sum(process_file(client, taxonomy, f, output_dir) for f in files)
    print(f"\n{ok}/{len(files)} documents processed -> {output_dir}")


def run_watch(
    client: anthropic.Anthropic,
    taxonomy: Taxonomy,
    watch_dir: Path,
    output_dir: Path,
    poll_seconds: int,
) -> None:
    print(f"Watching {watch_dir} for new files (Ctrl+C to stop)...")
    seen: set[Path] = set()

    try:
        while True:
            for source in iter_input_files(watch_dir):
                if source in seen:
                    continue
                process_file(client, taxonomy, source, output_dir)
                seen.add(source)
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("\nStopped.")


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path, help="Files and/or directories to process")
    parser.add_argument("--taxonomy", type=Path, default=None, help="Path to a taxonomy YAML (default: config/taxonomy.yaml)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory to write result JSON (default: output/)")
    parser.add_argument("--watch", action="store_true", help="Keep polling the (single) input directory for new files")
    parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS, help="Polling interval in --watch mode")
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    taxonomy = load_taxonomy(args.taxonomy)
    client = anthropic.Anthropic()

    if args.watch:
        if len(args.paths) != 1 or not args.paths[0].is_dir():
            parser.error("--watch requires exactly one directory argument")
        run_watch(client, taxonomy, args.paths[0], args.output, args.poll_seconds)
    else:
        run_once(client, taxonomy, args.paths, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
