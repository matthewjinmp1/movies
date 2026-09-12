# IMDb movie titles — personal use

Information courtesy of
IMDb
(https://www.imdb.com).
Used with permission.

Source: https://datasets.imdbws.com/title.basics.tsv.gz
Ratings source: https://datasets.imdbws.com/title.ratings.tsv.gz
Documentation: https://data.imdb.com/non-commercial-datasets/
Usage terms: https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX

- `title.basics.tsv.gz`: original compressed IMDb dataset, including all title types.
- `movie_titles.txt`: alphabetically sorted unique primary movie titles, one per line. Movies sharing the exact same title appear once here.
- `movies.csv`: one row per IMDb movie record, preserving all source columns and IDs, including films with identical titles. Missing metadata retains IMDb's `\N` marker.
- `download_summary.json`: processing date, counts, source, and filter.
- `title.ratings.tsv.gz`: original compressed ratings dataset with IMDb ID (`tconst`), weighted rating (`averageRating`), and vote count (`numVotes`). Includes all rated title types, not just movies; not yet merged into `movies.csv`.
- `ratings_download_summary.json`: ratings download date, verified record count, fields, and file size.

The extraction selects only `titleType == movie`; shorts, TV movies, series, episodes, and other formats are excluded. No language, year, release-status, or adult-content filter is applied.

These files are for individual personal, noncommercial use under IMDb's terms.

## Local movie browser

### Set up after cloning

GitHub contains the application code and documentation only. IMDb downloads, generated exports/databases, and personal settings stay on your computer and are excluded by `.gitignore`.

For personal, noncommercial use under the IMDb terms linked above, run these commands from the repository folder (Python 3.9+ and curl required). Downloads can be large; allow time for extraction and indexing:

```sh
curl --fail --location --retry 3 https://datasets.imdbws.com/title.basics.tsv.gz --output title.basics.tsv.gz.part
mv title.basics.tsv.gz.part title.basics.tsv.gz
curl --fail --location --retry 3 https://datasets.imdbws.com/title.ratings.tsv.gz --output title.ratings.tsv.gz.part
mv title.ratings.tsv.gz.part title.ratings.tsv.gz
python3 extract_movies.py
python3 app/import_data.py
python3 app/launch.py
```

Run each command only after the previous one succeeds. To refresh the data later, stop the app and repeat these steps. The import uses the ratings file's local modification date as the snapshot date; it does not require a download-summary file. Your saved stars and scoring/filter settings remain local across data rebuilds. Record counts vary with each download.

### Run the app

Double-click `Start Movie Browser.command` to start the app and open http://localhost:3002/ in your default browser. Keep the terminal window open while using the app; press Control+C to stop it. Launching it again reuses the running movie browser.

Alternatively, run `python3 app/launch.py`. Use `python3 app/server.py` to start the server without opening a browser.
The server listens only on this computer. No packages or external services are required.
The launcher always uses port 3002. To run the server on another port, use `python3 app/server.py --port 3003`.

The Chat tab uses the OpenRouter chat-completions API with `deepseek/deepseek-v4-flash-0731`. Copy `.env.example` to `.env` and set `OPENROUTER_KEY` before starting the app. The key stays on the local server and is never sent to the browser or committed to GitHub. Chat requests may incur OpenRouter charges according to your account.

The app joins all 756,513 movie records with ratings by IMDb ID, including 348,202 movies with ratings. It preserves unrated movies and keeps the original downloaded files unchanged.

- Use Columns to toggle any of the 11 source fields. At least one remains visible.
- In Columns, use the left/right arrows next to a visible column to change its table position. The menu lists visible columns in table order, and the order is saved in this browser. Reset restores the default columns and order.
- Click any column header or choose a field in Sort to sort ascending or descending. Missing values always sort last.
- Search by primary title, original title, or IMDb ID.
- Use Choose filters to show or hide custom controls for genres, IMDb rating, vote count, release year, runtime, and adult content. Hiding a control removes its condition.
- Select multiple genres and match any or all selected genres. Other active filters are combined with AND.
- Set minimum ratings or votes, year and runtime ranges, or rated/unrated availability. Blank values leave that field unrestricted. There are no dedicated filters for IMDb ID, title type, or end year; use search for movie names or IDs.
- Select 25, 50, 100, or 250 rows per page; jump directly to a page or use the navigation buttons.
- Column, sorting, page-size, and visible-filter preferences are saved in this browser. Search, filter values, and visible filters are automatically saved in `app/filters.json` and restored on refresh or restart. Clear all resets values while leaving the chosen controls visible.

`app/movies.sqlite3` is a generated index. To refresh after replacing the source snapshots, stop the server, run `python3 app/import_data.py`, and restart the server. This does not download new data.

Run integration checks with `python3 -m unittest discover -s app -p 'test_*.py'`.

### Filter score

Filter score is a computed, sortable column (0–100), calculated across all matching movies before pagination. Existing filters remain strict. It is not an IMDb rating or probability. No active filter/search means no score. Click a score for its per-field breakdown, or expand How filter score works for the current rules.

By default, each active field has weight 1 (a year range counts once). Use Scoring settings to change each weight from 0–10; 0 removes the field from the weighted average. With no active positive weights, scores are blank. Genre score is matched selected genres divided by the union of selected and movie genres (selected genres plus unselected movie genres). Extra unselected genres reduce the score. For Comedy + Drama: Comedy/Drama scores 100, Comedy/Drama/Horror scores 66.7, and Comedy/Horror scores 33.3. Rating score is rating divided by 10; vote score is log10(votes + 1) divided by log10(cap + 1), capped at 1 (default cap: 10 million). A two-sided year/runtime range gives 100 at the midpoint and 50 at either boundary; one-sided limits and exact categorical choices count as fully satisfied. Unrated-only is a satisfied availability choice. Search adds a title-match component: exact match 100, prefix 90, other substring 70. Final scores are rounded to one decimal, with IMDb ID providing stable tie ordering.

The Google search column searches the movie title and release year in the same tab. Use the browser Back button to return to the movie list. The previous page and table scroll position are restored; the column can be hidden in Columns.

Scoring settings also control the extra-genre penalty (0–3), rating exponent (0.25–4), logarithmic or linear votes and full-score cap, midpoint or uniform year/runtime preferences, and the range-edge score. Apply scoring recalculates the full result set and saves settings in `app/filters.json`. Reset defaults restores the original scoring without changing filter values.

Release year preference also supports **Favor newer years**. Within a two-sided year range, the minimum scores 0 and the maximum 100. With only a minimum, a movie 10 years newer scores 50 and later years approach 100; with only a maximum, the maximum scores 100 and 10 years older scores 50. A single exact year scores 100. This applies only when a release-year filter is active.

### Global score

Global rank is the movie's position by Global score across the full library, independent of filters or the Starred view. Rank 1 is best. Equal displayed scores share a rank, with gaps afterward (1, 1, 3). Movies without a Global score have no rank. The column can be hidden, moved, or sorted; selecting it in Sort defaults to best rank first.

The Global score column ranks preferences independently of filters, searches, pagination, and the Starred view. Open Global score settings to assign genre points (−10 to +10), field weights (0–10), numeric preferences, and a missing-data score. Genre points are averaged across every genre on the movie, including unassigned genres at 0. Thriller 3 and Horror −1 yields 1 point for a Thriller/Horror movie.

Genre averages and numeric preferences can use library-wide percentiles: 100 × (movies below + half the tied movies) / movies with known values. Missing values are excluded from percentile populations and get the configured missing score. Tied values share a score; a constant population scores 50. Fixed genre scaling maps −10/0/+10 points to 0/50/100. Rating, votes, release year, and runtime can favor higher values, lower values, or closeness to a target. Fixed numeric scoring uses low/high anchors or a target and distance to zero, clamped to 0–100. Adult/non-adult scores are set directly.

The overall score is the weighted mean of field scores. Zero-weight fields have no effect; all weights zero gives a blank score. Defaults weight rating 3, genres/votes/year 1, and runtime/adult 0. Genre points start at 0. Click a Global score for its breakdown. Save & apply persists to `app/global_scoring.json`; Rank by global score sorts using the saved settings. The derived `app/global_scores.sqlite3` cache rebuilds when settings or the movie snapshot change. No external requests are needed.
