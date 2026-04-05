"""
db.py — Database interface for the problem bank.
All reads and writes to problems.db go through here.
"""

import sqlite3
import json
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_competition_id(conn: sqlite3.Connection, short_name: str) -> int:
    row = conn.execute(
        "SELECT competition_id FROM competitions WHERE short_name = ?",
        (short_name,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown competition '{short_name}'. Check competitions table.")
    return row["competition_id"]


def get_or_create_topic(conn: sqlite3.Connection, topic_name: str) -> int:
    row = conn.execute(
        "SELECT topic_id FROM topics WHERE name = ?", (topic_name,)
    ).fetchone()
    if row:
        return row["topic_id"]
    cur = conn.execute("INSERT INTO topics (name) VALUES (?)", (topic_name,))
    return cur.lastrowid


def insert_problem(conn: sqlite3.Connection, problem: dict) -> int:
    """
    Insert a single parsed problem. Returns the new problem_id.
    problem dict keys:
        competition_id, problem_text, answer, answer_format,
        choices_json (optional), solution_text (optional),
        image_path (optional), comp_event (optional),
        comp_year (optional), comp_problem_number (optional),
        comp_difficulty (optional), review_status, review_notes (optional)
    """
    conn.execute("""
        INSERT INTO problems (
            competition_id, problem_text, answer, answer_format,
            choices_json, solution_text, image_path,
            comp_event, comp_year, comp_problem_number,
            comp_difficulty, review_status, review_notes
        ) VALUES (
            :competition_id, :problem_text, :answer, :answer_format,
            :choices_json, :solution_text, :image_path,
            :comp_event, :comp_year, :comp_problem_number,
            :comp_difficulty, :review_status, :review_notes
        )
    """, {
        "competition_id":      problem["competition_id"],
        "problem_text":        problem["problem_text"],
        "answer":              problem.get("answer"),
        "answer_format":       problem["answer_format"],
        "choices_json":        json.dumps(problem["choices"]) if problem.get("choices") else None,
        "solution_text":       problem.get("solution_text"),
        "image_path":          problem.get("image_path"),
        "comp_event":          problem.get("comp_event"),
        "comp_year":           problem.get("comp_year"),
        "comp_problem_number": problem.get("comp_problem_number"),
        "comp_difficulty":     problem.get("comp_difficulty"),
        "review_status":       problem.get("review_status", "pending"),
        "review_notes":        problem.get("review_notes"),
    })
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def attach_topics(conn: sqlite3.Connection, problem_id: int, topic_names: list[str]):
    for name in topic_names:
        topic_id = get_or_create_topic(conn, name)
        conn.execute("""
            INSERT OR IGNORE INTO problem_topics (problem_id, topic_id)
            VALUES (?, ?)
        """, (problem_id, topic_id))


def attach_solutions_to_existing(
    conn: sqlite3.Connection,
    competition_id: int,
    comp_year: int,
    comp_event: str | None,
    solutions: list[dict]
):
    query = """
        SELECT problem_id, comp_problem_number FROM problems
        WHERE competition_id = ?
          AND comp_year = ?
          AND solution_text IS NULL
          {}
    """.format("AND comp_event = ?" if comp_event else "AND comp_event IS NULL")

    params = [competition_id, comp_year]
    if comp_event:
        params.append(comp_event)

    rows = conn.execute(query, params).fetchall()
    problem_map = {row["comp_problem_number"]: row["problem_id"] for row in rows}

    matched = 0
    unmatched = 0
    for solution in solutions:
        prob_num = solution["problem_number"]
        sol_text = solution["solution_text"]
        if prob_num in problem_map:
            conn.execute(
                "UPDATE problems SET solution_text = ? WHERE problem_id = ?",
                (sol_text, problem_map[prob_num])
            )
            matched += 1
        else:
            unmatched += 1

    return matched, unmatched