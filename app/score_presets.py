"""Named local snapshots of global scoring settings."""
import json
import os
import tempfile
import threading
import uuid
from pathlib import Path
import global_scoring
PATH=Path(__file__).resolve().parent/'global_presets.json'
LOCK=threading.RLock()

def read():
    with LOCK:
        rows=json.loads(PATH.read_text()) if PATH.exists() else []
        return [dict(row,settings=global_scoring.validate(row['settings'])) for row in rows]

def change(payload):
    with LOCK:
        rows=read();action=payload.get('action');ident=payload.get('id')
        if action not in ('save','update','delete'):raise ValueError('Invalid preset action.')
        existing=next((r for r in rows if r['id']==ident),None)
        if action!='save' and existing is None:raise ValueError('Preset not found.')
        if action=='delete':rows.remove(existing)
        else:
            if not isinstance(payload.get('name'),str) or not isinstance(payload.get('settings'),dict):raise ValueError('Provide a name and scoring settings.')
            name=payload['name'].strip()
            if not name or len(name)>100:raise ValueError('Enter a name up to 100 characters.')
            if any(r['name'].casefold()==name.casefold() and r is not existing for r in rows):raise ValueError('That name already exists. Choose another name or update the selected preset.')
            settings=global_scoring.validate(payload.get('settings'))
            if action=='save':rows.append(dict(id=uuid.uuid4().hex,name=name,settings=settings))
            else:existing.update(name=name,settings=settings)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',dir=PATH.parent,delete=False) as f:
                temporary=f.name;json.dump(rows,f,indent=2);f.flush();os.fsync(f.fileno())
            os.replace(temporary,PATH)
        finally:
            if temporary and os.path.exists(temporary):os.unlink(temporary)
        return rows
