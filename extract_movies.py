import csv
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
titles = set()
total = movies = 0
with gzip.open(root / 'title.basics.tsv.gz', 'rt', encoding='utf-8', newline='') as source:
    rows = csv.DictReader(source, delimiter='\t', quoting=csv.QUOTE_NONE)
    with (root / 'movies.csv').open('w', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=rows.fieldnames)
        writer.writeheader()
        for row in rows:
            total += 1
            if row['titleType'] != 'movie':
                continue
            writer.writerow(row)
            titles.add(row['primaryTitle'])
            movies += 1

with (root / 'movie_titles.txt').open('w', encoding='utf-8') as output:
    for title in sorted(titles, key=lambda value: (value.casefold(), value)):
        output.write(title + '\n')

summary = {
    'processed_at_utc': datetime.now(timezone.utc).isoformat(),
    'source': 'https://datasets.imdbws.com/title.basics.tsv.gz',
    'source_records': total,
    'movie_records': movies,
    'unique_primary_titles': len(titles),
    'filter': 'titleType == movie; no year, language, or adult-content filter',
}
(root / 'download_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
