"""Count lines of code in this project's Git-tracked files, grouped by language."""
import argparse
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANGUAGES = {'.py':'Python', '.js':'JavaScript', '.html':'HTML', '.css':'CSS', '.command':'Shell', '.sh':'Shell'}
DOCS = {'.md':'Markdown', '.txt':'Text'}


def tracked_files():
    # Git's list skips ignored downloads, databases, and personal settings.
    output = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout
    return [ROOT / name for name in output.decode().split('\0') if name]


def count(path):
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    blank = sum(not line.strip() for line in lines)
    return len(lines), blank


def table(title, rows):
    print(f'\n{title}')
    print(f'  {"":<12}{"Files":>7}{"Lines":>9}{"Blank":>8}{"Code":>9}')
    for name, (files, lines, blank) in rows:
        print(f'  {name:<12}{files:>7,}{lines:>9,}{blank:>8,}{lines-blank:>9,}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', action='store_true', help='Also list every counted file, largest first.')
    args = parser.parse_args()
    totals = defaultdict(lambda: [0, 0, 0])
    per_file = []
    for path in tracked_files():
        group = LANGUAGES.get(path.suffix) or DOCS.get(path.suffix)
        if not group or not path.is_file():
            continue
        lines, blank = count(path)
        totals[group][0] += 1
        totals[group][1] += lines
        totals[group][2] += blank
        per_file.append((lines-blank, lines, path.relative_to(ROOT), group))
    code = sorted(((name, totals[name]) for name in set(LANGUAGES.values()) if name in totals), key=lambda row: -row[1][1])
    total = [sum(row[1][i] for row in code) for i in range(3)]
    table('Code', code + [('Total', total)])
    docs = [(name, totals[name]) for name in DOCS.values() if name in totals]
    if docs:
        table('Documentation', docs)
    if args.files:
        print('\nFiles (code lines, total lines)')
        for code_lines, lines, path, group in sorted(per_file, key=lambda row: (-row[0], str(row[2]))):
            print(f'  {code_lines:>7,}{lines:>8,}  {path}  ({group})')
    print('\nCode lines exclude blank lines. Counts cover files tracked by Git.')


if __name__ == '__main__':
    main()
