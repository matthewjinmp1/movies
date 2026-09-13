import copy
import math
import enrichment

DEFAULTS = {
    'weights': {key:1 for key in ['genres','averageRating','startYear','numVotes','runtimeMinutes','isAdult','search']},
    'genrePenalty':1,
    'ratingPower':1,
    'votesScale':'log',
    'votesCap':10000000,
    'yearMode':'center',
    'runtimeMode':'center',
    'rangeEdgeScore':50,
}

DEFAULTS['weights'].update({key:1 for key in (*enrichment.NUMERIC,*enrichment.CATEGORIES)})

def validate(value=None):
    result=copy.deepcopy(DEFAULTS)
    if value is None: return result
    if not isinstance(value,dict) or set(value)-set(DEFAULTS): raise ValueError('Invalid scoring settings.')
    for key,v in value.items():
        if key=='weights':
            if not isinstance(v,dict) or set(v)-set(DEFAULTS['weights']): raise ValueError('Invalid scoring weights.')
            for field,weight in v.items():
                number(weight,0,10)
                result[key][field]=weight
        elif key in ('votesScale','yearMode','runtimeMode'):
            allowed=('log','linear') if key=='votesScale' else ('center','uniform','newer') if key=='yearMode' else ('center','uniform')
            if v not in allowed: raise ValueError('Invalid scoring mode.')
            result[key]=v
        else:
            lo,hi={'genrePenalty':(0,3),'ratingPower':(0.25,4),'votesCap':(1,1000000000),'rangeEdgeScore':(0,100)}[key]
            number(v,lo,hi);result[key]=v
    return result

def number(value,lo,hi):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not lo<=value<=hi:
        raise ValueError(f'Scoring value must be between {lo} and {hi}.')
