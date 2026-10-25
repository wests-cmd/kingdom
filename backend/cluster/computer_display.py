"""Owner-managed display labels. Never used for authentication or routing."""
import getpass


def display_hierarchy(result, database):
    with database.get_connection() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS computer_display_names(node_id TEXT PRIMARY KEY, username TEXT NOT NULL, computer TEXT NOT NULL)')
        names = {row[0]: {'username': row[1], 'computer': row[2]} for row in conn.execute('SELECT node_id,username,computer FROM computer_display_names')}
        conn.commit()
    local = names.get('local', {'username': getpass.getuser(), 'computer': result['commander']['computer']})
    result['commander'].update(username=local['username'], display_computer=local['computer'])
    labels = {'local': local['username'] + ' · ' + local['computer']}
    for node in result['knights'] + result.get('archived_knights', []):
        name = names.get(node['node_id'])
        if name:
            node.update(display_username=name['username'], display_computer=name['computer'])
            labels[node['node_id']] = name['username'] + ' · ' + name['computer']
    for node in result.get('topology', {}).get('nodes', []):
        if node['id'] in labels:
            node['label'] = labels[node['id']]
    return result
