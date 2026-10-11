"""Predict personal 0–10 ratings for unrated movies from the movies you have rated.

The model starts from crowd quality: each IMDb point above or below the average
of the movies you rated adds or subtracts half a point. Your ratings cover only
popular, well-reviewed movies, so this fixed term keeps poorly reviewed movies
from ranking highly. On top of it, ridge regression learns how each genre and
Metacritic score shift your ratings, with the smoothing chosen by
leave-one-out error. Movies without a Metacritic score are treated as average.
"""
from contextlib import closing
import hashlib
import json
import math
import os
import sqlite3
import tempfile
import threading
from pathlib import Path

import enrichment
import ratings

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'personal_scores.sqlite3'
LOCK = threading.RLock()
MIN_RATINGS = 5
MIN_VOTES = 10000
QUALITY_SLOPE = 0.5
PENALTIES = (3, 10, 30)


def invert(matrix):
    n = len(matrix)
    rows = [row[:] + [float(i == j) for j in range(n)] for i, row in enumerate(matrix)]
    for c in range(n):
        pivot = max(range(c, n), key=lambda r: abs(rows[r][c]))
        rows[c], rows[pivot] = rows[pivot], rows[c]
        scale = rows[c][c]
        rows[c] = [v/scale for v in rows[c]]
        for r in range(n):
            if r != c and rows[r][c]:
                factor = rows[r][c]
                rows[r] = [a - factor*b for a, b in zip(rows[r], rows[c])]
    return [row[n:] for row in rows]


def ridge(X, y, penalty):
    """Weights (intercept unpenalized) and exact leave-one-out residuals."""
    k = len(X[0])
    A = [[sum(x[i]*x[j] for x in X) + (penalty if i == j and i else 0) for j in range(k)] for i in range(k)]
    inverse = invert(A)
    w = [sum(inverse[i][j]*sum(x[j]*t for x, t in zip(X, y)) for j in range(k)) for i in range(k)]
    loo = []
    for x, t in zip(X, y):
        fitted = sum(a*b for a, b in zip(w, x))
        leverage = sum(x[i]*inverse[i][j]*x[j] for i in range(k) for j in range(k))
        loo.append((t - fitted) / (1 - leverage))
    return w, loo


def correlation(a, b):
    ma, mb = sum(a)/len(a), sum(b)/len(b)
    sa, sb = math.sqrt(sum((v-ma)**2 for v in a)), math.sqrt(sum((v-mb)**2 for v in b))
    return sum((x-ma)*(y-mb) for x, y in zip(a, b))/(sa*sb) if sa and sb else None


def fit(rated, pool):
    """rated: {tconst: rating}; pool: [(tconst, genres, imdb, metacritic)]. Returns predictions and a summary."""
    movies = {t: (genres, imdb, metacritic) for t, genres, imdb, metacritic in pool}
    train = [(t, rating) for t, rating in sorted(rated.items()) if t in movies and movies[t][1] is not None]
    summary = {'ratings': len(train), 'minRatings': MIN_RATINGS, 'minVotes': MIN_VOTES}
    if len(train) < MIN_RATINGS:
        return {}, summary
    imdb_mean = sum(movies[t][1] for t, _ in train)/len(train)
    quality = lambda t: QUALITY_SLOPE*((movies[t][1] if movies[t][1] is not None else imdb_mean) - imdb_mean)
    critics = [movies[t][2] for t, _ in train if movies[t][2] is not None]
    critic_mean = sum(critics)/len(critics) if critics else 0
    critic_sd = math.sqrt(sum((v-critic_mean)**2 for v in critics)/len(critics)) if critics else 0
    genres = sorted({g for t, _ in train for g in (movies[t][0] or '').split(',') if g})
    def features(t):
        names = (movies[t][0] or '').split(',')
        x = [1.0] + [float(g in names) for g in genres]
        if critic_sd:
            x.append(((movies[t][2] if movies[t][2] is not None else critic_mean) - critic_mean)/critic_sd)
        return x
    X = [features(t) for t, _ in train]
    y = [rating - quality(t) for t, rating in train]
    fits = {penalty: ridge(X, y, penalty) for penalty in PENALTIES}
    penalty = min(PENALTIES, key=lambda p: sum(abs(e) for e in fits[p][1]))
    w, residuals = fits[penalty]
    actual = [rating for _, rating in train]
    held_out = [rating - e for rating, e in zip(actual, residuals)]
    baseline = [abs(rating - (sum(actual)-rating)/(len(actual)-1)) for rating in actual]
    summary.update({
        'penalty': penalty, 'imdbMean': round(imdb_mean, 2), 'qualitySlope': QUALITY_SLOPE,
        'metacriticEffect': round(w[-1], 2) if critic_sd else None, 'metacriticSd': round(critic_sd, 1),
        'heldOutCorrelation': correlation(held_out, actual),
        'heldOutError': sum(abs(e) for e in residuals)/len(residuals),
        'averageGuessError': sum(baseline)/len(baseline),
        'averageRating': sum(actual)/len(actual),
        'genreEffects': sorted(([g, round(v, 2)] for g, v in zip(genres, w[1:]) if abs(v) >= 0.05), key=lambda e: -e[1]),
    })
    predictions = {}
    for t in movies:
        if movies[t][1] is None:
            continue
        value = sum(a*b for a, b in zip(w, features(t))) + quality(t)
        predictions[t] = round(min(10.0, max(0.0, value)), 1)
    return predictions, summary


def ensure_cache(source=None):
    source = source or ROOT / 'movies.sqlite3'
    rated = ratings.read()
    stamp = source.stat()
    signature = hashlib.sha256(('personal-v2'+json.dumps(rated, sort_keys=True)+str(enrichment.ensure().stat().st_mtime_ns)+str((str(source), stamp.st_mtime_ns, stamp.st_size))).encode()).hexdigest()
    with LOCK:
        if CACHE.exists():
            with closing(sqlite3.connect(CACHE)) as db:
                row = db.execute('SELECT signature, summary FROM cache_info').fetchone()
                if row and row[0] == signature:
                    return CACHE, json.loads(row[1])
        with closing(sqlite3.connect(f'file:{source}?mode=ro', uri=True)) as db:
            enrichment.attach(db)
            db.execute('CREATE TEMP TABLE rated (tconst TEXT PRIMARY KEY)')
            db.executemany('INSERT INTO rated VALUES (?)', ((t,) for t in rated))
            pool = db.execute('SELECT tconst, genres, averageRating, metacritic FROM movies WHERE numVotes >= ? OR tconst IN (SELECT tconst FROM rated)', (MIN_VOTES,)).fetchall()
        predictions, summary = fit(rated, pool)
        fd, name = tempfile.mkstemp(suffix='.sqlite3', dir=CACHE.parent); os.close(fd)
        try:
            with closing(sqlite3.connect(name)) as db:
                db.execute('CREATE TABLE cache_info(signature TEXT, summary TEXT)')
                db.execute('INSERT INTO cache_info VALUES (?,?)', (signature, json.dumps(summary)))
                db.execute('CREATE TABLE predictions(tconst TEXT PRIMARY KEY, predictedRating REAL)')
                db.executemany('INSERT INTO predictions VALUES (?,?)', predictions.items())
                db.execute('CREATE INDEX prediction_order ON predictions(predictedRating, tconst)')
                db.execute('ANALYZE'); db.commit()
            os.replace(name, CACHE)
        finally:
            if os.path.exists(name): os.unlink(name)
        return CACHE, summary


def attach(db):
    with LOCK:
        path, summary = ensure_cache()
        db.execute('ATTACH DATABASE ? AS personal_cache', (str(path),))
        return summary
