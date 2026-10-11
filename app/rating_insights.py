"""Correlations between your personal ratings and each movie stat."""
import json
import math

# Derived, filter-dependent, or duplicate fields would only echo the ratings or each other.
SKIPPED = {'myRating', 'predictedRating', 'filterScore', 'globalRank', 'endYear'}
# Counts and money span orders of magnitude, so Pearson uses their logarithm.
LOGGED = {'numVotes', 'budget', 'revenue'}
# Keywords are left out: movies have up to 100 each, so hundreds would be tested and many would correlate by chance.
CATEGORY_GROUPS = ('certification', 'language', 'country', 'productionCompanies')
MIN_MOVIES = 5
MIN_GROUP = 3
# A category value must cover this share of rated movies; rarer keywords and companies are mostly chance.
MIN_SHARE = 0.15


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0]*len(values)
    i = 0
    while i < len(order):
        j = i
        while j+1 < len(order) and values[order[j+1]] == values[order[i]]:
            j += 1
        for k in range(i, j+1):
            result[order[k]] = (i+j)/2
        i = j+1
    return result


def pearson(a, b):
    ma, mb = sum(a)/len(a), sum(b)/len(b)
    sa, sb = math.sqrt(sum((v-ma)**2 for v in a)), math.sqrt(sum((v-mb)**2 for v in b))
    return sum((x-ma)*(y-mb) for x, y in zip(a, b))/(sa*sb) if sa and sb else None


def p_value(rho, n):
    """Two-sided p-value for a Spearman correlation (Fisher z approximation)."""
    if n <= 3 or rho is None:
        return None
    z = math.atanh(max(-0.999999, min(0.999999, rho))) * math.sqrt((n-3)/1.06)
    return math.erfc(abs(z)/math.sqrt(2))


def stat(label, group, pairs, logged=False):
    if len(pairs) < MIN_MOVIES:
        return None
    xs = [math.log10(x+1) if logged else x for x, _ in pairs]
    ys = [y for _, y in pairs]
    rho = pearson(ranks(xs), ranks(ys))
    if rho is None:
        return None
    return {'label':label, 'group':group, 'movies':len(pairs), 'spearman':round(rho, 3),
            'pearson':round(pearson(xs, ys), 3), 'p':p_value(rho, len(pairs))}


def correlations(db, columns):
    """db must have the movies view, global_cache, and my_ratings attached."""
    rows = [dict(r) for r in db.execute('SELECT * FROM movies JOIN my_ratings USING(tconst) JOIN global_cache.scores USING(tconst)')]
    result = []
    for key, label, kind in columns:
        if kind == 'number' and key not in SKIPPED:
            result.append(stat(label, 'Movie stats', [(r[key], r['myRating']) for r in rows if r.get(key) is not None], key in LOGGED or key.endswith('Votes')))
    def binary(group, label, has):
        count = sum(has(r) for r in rows)
        if MIN_GROUP <= count <= len(rows)-MIN_GROUP:
            result.append(stat(label, group, [(float(has(r)), r['myRating']) for r in rows]))
    for genre in sorted({g for r in rows for g in (r['genres'] or '').split(',') if g}):
        binary('Genre', genre, lambda r, g=genre: g in (r['genres'] or '').split(','))
    labels = dict((key, label) for key, label, _ in columns)
    for key in CATEGORY_GROUPS:
        with_data = [(set(json.loads(r[key])), r['myRating']) for r in rows if r.get(key)]
        minimum = max(MIN_GROUP, math.ceil(MIN_SHARE*len(with_data)))
        for value in sorted({v for values, _ in with_data for v in values}):
            count = sum(value in values for values, _ in with_data)
            if minimum <= count <= len(with_data)-MIN_GROUP:
                result.append(stat(value, labels[key], [(float(value in values), rating) for values, rating in with_data]))
    result = sorted((r for r in result if r), key=lambda r: -abs(r['spearman']))
    # Benjamini-Hochberg q-values: the false-discovery rate if every stat at or below this p were called real.
    tested = sorted((r for r in result if r['p'] is not None), key=lambda r: r['p'])
    q = 1.0
    for i in range(len(tested)-1, -1, -1):
        q = min(q, tested[i]['p']*len(tested)/(i+1))
        tested[i]['q'] = q
    return {'ratings':len(rows), 'tested':len(tested), 'stats':result}
