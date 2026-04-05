"""
ingest.py — Main ingestion script for the math competition problem bank.

Usage examples:
    # Ingest problems from a PDF
    python ingest.py --file ictm_2023_algebra1.pdf --competition ICTM --year 2023 --event "Algebra 1"
    python ingest.py --file aime_2023.pdf --competition AIME --year 2023
    python ingest.py --file amc10_2023.pdf --competition AMC10 --year 2023

    # Ingest a solutions-only PDF (matches to existing problems by position)
    python ingest.py --file amc10_2023_solutions.pdf --competition AMC10 --year 2023 --solutions-only

    # Point at a different database file
    python ingest.py --file ictm_2023_algebra1.pdf --competition ICTM --year 2023 --db ../problems.db
"""

import argparse
import sys
from pathlib import Path

import pdfplumber

from db import get_connection, get_competition_id, insert_problem, attach_topics, attach_solutions_to_existing
from parser import parse_problems, parse_solutions


ANSWER_FORMATS = {
    "ICTM":  "numeric",
    "NSML":  "numeric",
    "AMC10": "multiple_choice",
    "AMC12": "multiple_choice",
    "AIME":  "numeric",
    "ARML":  "numeric",
}


def extract_text(pdf_path: Path) -> str:
    """Extract all text from a PDF using pdfplumber."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
    return text.strip()


def ingest_problems(args, conn):
    competition_id = get_competition_id(conn, args.competition)
    answer_format = ANSWER_FORMATS[args.competition]

    print(f"Extracting text from {args.file}...")
    text = extract_text(Path(args.file))
    if not text:
        print("ERROR: No text could be extracted from this PDF.")
        print("It may be a scanned image. Manual entry required.")
        sys.exit(1)

    print(f"Sending to LLM for parsing ({args.competition} {args.year})...")
    problems = parse_problems(text, args.competition, args.year, args.event, answer_format)

    if not problems:
        print("ERROR: No problems could be extracted from this text.")
        sys.exit(1)

    print(f"LLM returned {len(problems)} problems.")

    inserted = 0
    flagged = 0

    for p in problems:
        review_status = "approved" if p.get("confident", False) else "pending"
        if not p.get("confident", False):
            flagged += 1

        problem_row = {
            "competition_id":      competition_id,
            "problem_text":        p["problem_text"],
            "answer":              p.get("answer"),
            "answer_format":       answer_format,
            "choices":             p.get("choices"),
            "solution_text":       None,
            "image_path":          None,
            "comp_event":          args.event,
            "comp_year":           args.year,
            "comp_problem_number": p.get("problem_number"),
            "comp_difficulty":     p.get("comp_difficulty"),
            "review_status":       review_status,
            "review_notes":        p.get("review_notes"),
        }

        problem_id = insert_problem(conn, problem_row)
        attach_topics(conn, problem_id, p.get("topics", []))
        inserted += 1

    conn.commit()
    print(f"\nDone. {inserted} problems inserted.")
    print(f"  {inserted - flagged} approved (confident parses)")
    print(f"  {flagged} pending (flagged for review)")


def ingest_solutions(args, conn):
    competition_id = get_competition_id(conn, args.competition)

    if args.competition.lower().strip() != "ictm" and args.event:
        args.event = None 

    print(f"Extracting text from {args.file}...")
    text = extract_text(Path(args.file))

    if not text:
        print("ERROR: No text could be extracted from this PDF.")
        sys.exit(1)

    print(f"Sending to LLM for solution parsing...")
    solutions = parse_solutions(text, args.competition, args.year, args.event)
    if not solutions:
        print("ERROR: No solutions could be extracted from this text.")
        sys.exit(1)

    print(f"LLM returned {len(solutions)} solutions.")

    matched, unmatched = attach_solutions_to_existing(
        conn, competition_id, args.year, args.event, solutions
    )
    conn.commit()

    print(f"\nDone. {matched} solutions matched to existing problems.")
    if unmatched > 0:
        print(f"  WARNING: {unmatched} solutions had no matching problem row.")
        print(f"  Run the problems PDF first, then re-run solutions.")


def main():
    parser = argparse.ArgumentParser(description="Ingest competition problems into problems.db")

    parser.add_argument("--file",         required=True,  help="Path to the PDF file")
    parser.add_argument("--competition",  required=True,  choices=list(ANSWER_FORMATS.keys()),
                        help="Competition short name: ICTM, NSML, AMC10, AMC12, AIME, ARML")
    parser.add_argument("--year",         required=True,  type=int, help="Contest year e.g. 2023")
    parser.add_argument("--event",        default=None,
                        help="ICTM event name e.g. 'Algebra 1' (optional for other competitions)")
    parser.add_argument("--solutions-only", action="store_true",
                        help="PDF contains only solutions — match to existing problems by position")
    parser.add_argument("--db",           default="../problems.db",
                        help="Path to problems.db (default: ../problems.db)")

    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"ERROR: File not found: {args.file}")
        sys.exit(1)

    if not Path(args.db).exists():
        print(f"ERROR: Database not found: {args.db}")
        print("Run: sqlite3 problems.db \".read schema.sql\" from the repo root first.")
        sys.exit(1)

    conn = get_connection(args.db)

    try:
        if args.solutions_only:
            ingest_solutions(args, conn)
        else:
            ingest_problems(args, conn)
    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
