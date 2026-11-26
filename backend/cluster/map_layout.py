"""Local presentation only: no membership, hosting, trust or task changes."""
import json
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

View = Literal['network','teams','work']
Identity = Annotated[str, StringConstraints(min_length=1,max_length=300,
    pattern=r'^(knight|apprentice|frame):[^\x00-\x1f]+$')]
Coordinate = Annotated[int, Field(strict=True,ge=0,le=100000)]
Extent = Annotated[int, Field(strict=True,ge=32,le=20000)]


class Placement(BaseModel):
    model_config=ConfigDict(extra='forbid')
    x:Coordinate
    y:Coordinate
    w:Extent|None=None
    h:Extent|None=None


class LayoutUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version:int=Field(strict=True,ge=0,le=2147483646)
    positions:dict[Identity,Placement]=Field(max_length=1000)


class LayoutConflict(ValueError):
    pass


class MapLayouts:
    def __init__(self,database):
        self.db=database
        with self.db.get_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS command_map_layouts(
                view TEXT PRIMARY KEY, version INTEGER NOT NULL, positions TEXT NOT NULL)""")
            conn.commit()

    @staticmethod
    def validate_view(view):
        if view not in {'network','teams','work'}:raise ValueError('Unknown map view')

    def read(self,view):
        self.validate_view(view)
        with self.db.get_connection() as conn:
            row=conn.execute('SELECT version,positions FROM command_map_layouts WHERE view=?',(view,)).fetchone()
        return {'view':view,'version':row[0] if row else 0,
                'positions':json.loads(row[1]) if row else {}}

    def save(self,view,update):
        self.validate_view(view)
        update=LayoutUpdate.model_validate(update)
        positions={key:value.model_dump(exclude_none=True) for key,value in update.positions.items()}
        with self.db.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("INSERT OR IGNORE INTO command_map_layouts VALUES(?,0,'{}')",(view,))
            result=conn.execute('UPDATE command_map_layouts SET version=version+1,positions=? WHERE view=? AND version=?',
                (json.dumps(positions,sort_keys=True),view,update.version))
            if result.rowcount!=1:raise LayoutConflict('Another editor saved this layout. Reload before saving.')
            conn.commit()
        return {'view':view,'version':update.version+1,'positions':positions}
