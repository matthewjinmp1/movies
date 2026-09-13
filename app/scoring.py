"""Transparent, deterministic SQL scoring of movies that pass the filters."""
import math
import enrichment
from score_settings import validate

def score_components(filters, search='', settings=None):
    settings=validate(settings)
    grouped = {}
    for f in filters:
        grouped.setdefault(f['field'], []).append(f)
    components = []
    def add(key, label, sql, args, rule):
        components.append(dict(key=key, label=label, sql=sql, args=args, rule=rule, weight=settings['weights'].get(key,1)))
    for key, rules in grouped.items():
        if key in enrichment.NUMERIC:
            spec=enrichment.NUMERIC[key]
            if any(f['op']=='missing' for f in rules): continue
            maximum=spec['maximum']
            sql=f'MIN(1.0, MAX(0.0, {key} * 1.0 / {maximum}))'
            if spec['lower']:sql='(1.0 - '+sql+')'
            add(key,spec['label'],sql,[],f'{"Lower" if spec["lower"] else "Higher"} values score higher on a 0–{maximum:g} scale.')
        elif key in enrichment.CATEGORIES:
            selected=sorted({v for f in rules for v in f.get('value',[])})
            if not selected:continue
            sql='('+' + '.join([f'CASE WHEN EXISTS (SELECT 1 FROM json_each({key}) WHERE value=?) THEN 1.0 ELSE 0.0 END']*len(selected))+f') / {len(selected)}'
            add(key,enrichment.CATEGORIES[key]['label'],sql,selected,'Share of selected values matched.')
        elif key == 'genres':
            selected = sorted({g for f in rules for g in (f['value'] if f['op'] in ('any_of','all_of') else [f['value']] if f['op']=='has' else [])})
            if selected:
                matches = '(' + ' + '.join(["CASE WHEN instr(',' || genres || ',', ?) > 0 THEN 1.0 ELSE 0.0 END"]*len(selected)) + ')'
                genre_count = "CASE WHEN genres IS NULL OR genres = '' THEN 0 ELSE 1 + length(genres) - length(replace(genres, ',', '')) END"
                penalty=settings['genrePenalty']
                sql = f'{matches} / ({len(selected)} + ? * (({genre_count}) - {matches}))'
                add(key,'Genres',sql,[','+g+',' for g in selected]+[penalty]+[','+g+',' for g in selected],f'Matched genres ÷ (selected genres + {penalty:g} × extra movie genres). A penalty of 0 ignores extra genres.')
            else: add(key,'Genres','1.0',[],'The genre condition is satisfied.')
        elif key == 'averageRating' and not any(f['op']=='missing' for f in rules):
            power=settings['ratingPower']
            add(key,'IMDb rating','SCOREPOWER(COALESCE(averageRating / 10.0, 0), ?)',[power],f'(IMDb rating ÷ 10) raised to {power:g}. Higher powers penalize lower ratings more.')
        elif key == 'numVotes' and not any(f['op']=='missing' for f in rules):
            cap=settings['votesCap']
            sql='MIN(1.0, LOG10PLUS(COALESCE(numVotes, 0)) / ?)' if settings['votesScale']=='log' else 'MIN(1.0, COALESCE(numVotes, 0) * 1.0 / ?)'
            add(key,'Vote count',sql,[math.log10(cap+1) if settings['votesScale']=='log' else cap],f'{settings["votesScale"].capitalize()} scale; {cap:,.0f} votes earns 100.')
        elif key in ('startYear','runtimeMinutes'):
            low = [float(f['value']) for f in rules if f['op'] in ('gte','eq')]
            high = [float(f['value']) for f in rules if f['op'] in ('lte','eq')]
            label = 'Release year' if key=='startYear' else 'Runtime'
            mode=settings['yearMode' if key=='startYear' else 'runtimeMode']
            if key=='startYear' and mode=='newer' and (low or high):
                if low and high:
                    lo,hi=max(low),min(high)
                    if lo<hi:
                        add(key,label,'MIN(1.0, MAX(0.0, (startYear - ?) * 1.0 / ?))',[lo,hi-lo],f'Favor newer years: {lo:g} scores 0 and {hi:g} scores 100, increasing evenly between them.')
                    else: add(key,label,'1.0',[],'Only one release year can match; it scores 100.')
                elif low:
                    lo=max(low)
                    add(key,label,'MAX(0.0, (startYear - ?) * 1.0 / MAX(1.0, startYear - ? + 10.0))',[lo,lo],f'Favor newer years after {lo:g}: the minimum scores 0; 10 years newer scores 50; newer years approach 100.')
                else:
                    hi=min(high)
                    add(key,label,'MIN(1.0, 10.0 / MAX(1.0, 10.0 + ? - startYear))',[hi],f'Favor newer years up to {hi:g}: the maximum scores 100; 10 years older scores 50.')
            elif mode=='center' and low and high and max(low)<min(high):
                lo, hi = max(low),min(high)
                midpoint, half = (lo+hi)/2,(hi-lo)/2
                edge=settings['rangeEdgeScore']
                add(key,label,f'MAX(0.0, 1.0 - ? * ABS({key} - ?) / ?)',[1-edge/100,midpoint,half],f'Range {lo:g}–{hi:g}: midpoint {midpoint:g} scores 100; either edge scores {edge:g}.')
            else: add(key,label,'1.0',[],'All matching values score 100. Midpoint preference requires both range boundaries and center mode.')
        else:
            label = {'isAdult':'Adult content','averageRating':'Rating availability','numVotes':'Vote availability'}.get(key,key)
            add(key,label,'1.0',[],'The selected condition is satisfied.')
    if search.strip():
        term = search.casefold()
        add('search','Title search',"CASE WHEN CASEFOLD(primaryTitle) = ? OR CASEFOLD(originalTitle) = ? OR tconst = ? THEN 1.0 WHEN instr(CASEFOLD(primaryTitle), ?) = 1 OR instr(CASEFOLD(originalTitle), ?) = 1 THEN 0.9 ELSE 0.7 END",[term]*5,'Exact title or ID: 100; title prefix: 90; other substring match: 70.')
    return components
