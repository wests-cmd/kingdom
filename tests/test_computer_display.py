import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager

spec=importlib.util.spec_from_file_location('display',Path(__file__).parents[1]/'backend/cluster/computer_display.py')
display=importlib.util.module_from_spec(spec);spec.loader.exec_module(display)


class DisplayTests(unittest.TestCase):
    def test_persisted_names_change_only_display_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            class Database:
                @contextmanager
                def get_connection(self):
                    conn=sqlite3.connect(str(Path(folder)/'names.db'))
                    try:
                        with conn:yield conn
                    finally:conn.close()
            db=Database()
            result={'commander':{'computer':'host'},'knights':[{'node_id':'peer','granted_capabilities':['compute'],'node_state':'DISCONNECTED'}], 'topology':{'nodes':[{'id':'local','label':'This Knight'},{'id':'peer','label':'kingdom-node'}]}}
            display.display_hierarchy(result,db)
            with db.get_connection() as conn:
                conn.executemany('INSERT INTO computer_display_names VALUES(?,?,?)',[('local','bot1','Laptop 2'),('peer','bot2','Laptop 3')])
            actual=display.display_hierarchy(result,db)
            self.assertEqual(actual['commander']['username'],'bot1')
            self.assertEqual(actual['topology']['nodes'][1]['label'],'bot2 · Laptop 3')
            self.assertEqual(actual['knights'][0]['node_id'],'peer')
            self.assertEqual(actual['knights'][0]['node_state'],'DISCONNECTED')
            self.assertEqual(actual['knights'][0]['granted_capabilities'],['compute'])


if __name__=='__main__':unittest.main()
