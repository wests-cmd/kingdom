"""Content-addressed, compressed task inputs; uploaded code is never executed."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import time
import tempfile
from threading import RLock
import zipfile
import zlib

MAX_FILE = 20 * 1024 * 1024
MAX_TEXT = 2_000_000
TEXT_EXT = {'.txt', '.md', '.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.yaml', '.yml', '.csv', '.log', '.html', '.css', '.xml', '.toml', '.ini', '.sql', '.sh', '.ps1'}


def compact_text(text, query='', budget=24000):
    """Extractive context with source offsets; retain originals for later retrieval."""
    if len(text) <= budget:
        return {'text': text, 'compacted': False, 'original_characters': len(text), 'retained_characters': len(text)}
    terms = set(re.findall(r'\w+', query.lower()))
    chunks = [(index, text[index:index+1800]) for index in range(0, len(text), 1800)]
    ranked = sorted(chunks, key=lambda item: (len(terms & set(re.findall(r'\w+', item[1].lower()))), -item[0]), reverse=True)
    selected, used = [], 0
    for offset, chunk in ranked:
        if used + len(chunk) + 40 > budget: continue
        selected.append((offset, chunk)); used += len(chunk) + 40
    output = '\n'.join(f'[source characters {offset}:{offset+len(chunk)}]\n{chunk}' for offset, chunk in sorted(selected))
    return {'text': output, 'compacted': True, 'original_characters': len(text), 'retained_characters': len(output),
            'notice': 'Extractive context, not a complete summary. Original bytes remain retrievable.'}


class AttachmentStore:
    write_lock = RLock()
    def __init__(self, database, root='data/attachments'):
        self.db, self.root = database, Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db.get_connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS task_attachments(id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL, text_blob BLOB NOT NULL)')
            conn.commit()

    def put(self, filename, data):
        if not isinstance(data, bytes) or not data or len(data) > MAX_FILE:
            raise ValueError('Choose a non-empty file up to 20 MB')
        filename = filename.replace('\\', '/').split('/')[-1][:180]
        if not filename or any(ord(c) < 32 for c in filename): raise ValueError('Invalid filename')
        extension = Path(filename).suffix.lower()
        text, kind, details = '', 'text', {}
        if extension == '.zip':
            kind = 'zip'; members = []
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 500 or sum(e.file_size for e in entries) > 64 * 1024 * 1024:
                    raise ValueError('ZIP exceeds 500 entries or 64 MB expanded')
                for entry in entries:
                    path = PurePosixPath(entry.filename.replace('\\', '/'))
                    if path.is_absolute() or '..' in path.parts or ':' in entry.filename or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError('ZIP contains unsafe paths or symbolic links')
                    if entry.flag_bits & 1 or entry.file_size > 8 * 1024 * 1024 or entry.file_size > max(1, entry.compress_size) * 200:
                        raise ValueError('ZIP contains encrypted, oversized or excessively compressed entries')
                    members.append({'name': entry.filename, 'bytes': entry.file_size})
                    if not entry.is_dir() and path.suffix.lower() in TEXT_EXT:
                        content = archive.read(entry).decode('utf-8', errors='replace')
                        text += f'\n[ZIP member: {entry.filename}]\n' + content
                        if len(text) > MAX_TEXT: raise ValueError('ZIP text exceeds extraction budget')
            details['members'] = members
        elif extension == '.pdf':
            from pypdf import PdfReader, apply_configuration
            if not data.startswith(b'%PDF-'): raise ValueError('Invalid PDF signature')
            with apply_configuration(maximum_declared_stream_length=8*1024*1024,
                    array_based_stream_maximum_output_length=8*1024*1024, zlib_maximum_output_length=8*1024*1024,
                    lzw_maximum_output_length=8*1024*1024, run_length_maximum_output_length=8*1024*1024,
                    page_tree_maximum_entries=2000, page_tree_maximum_depth=30, xform_maximum_invocations_per_extraction=100):
                reader = PdfReader(io.BytesIO(data))
                if reader.is_encrypted or len(reader.pages) > 200: raise ValueError('PDF must be unencrypted and at most 200 pages')
                kind = 'pdf'; details['pages'] = len(reader.pages)
                extracted = False
                for index, page in enumerate(reader.pages):
                    stream = page.get_contents()
                    if stream is not None and len(stream.get_data()) > 8 * 1024 * 1024: raise ValueError('PDF page content is too large')
                    page_text = page.extract_text() or ''
                    extracted = extracted or bool(page_text.strip())
                    text += f'\n[PDF page {index+1}]\n' + page_text
                    if len(text) > MAX_TEXT: raise ValueError('PDF text exceeds extraction budget')
            details['text_extracted'] = extracted
            details['ocr_performed'] = False
        elif extension in {'.jpg', '.jpeg', '.png', '.webp'}:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > 40_000_000: raise ValueError('Image dimensions exceed 40 megapixels')
                image.verify()
                details.update(width=image.width, height=image.height, format=image.format)
            kind = 'image'; text = f'[Image {filename}: {details["width"]} x {details["height"]}. Visual content requires a vision-capable model.]'
        elif extension in TEXT_EXT:
            text = data.decode('utf-8')
            if '\x00' in text or len(text) > MAX_TEXT: raise ValueError('Unsupported binary or oversized text')
        else:
            raise ValueError('Supported inputs: ZIP, PDF, JPG/PNG/WebP, text, source code, JSON, YAML and CSV')
        ident = hashlib.sha256(data).hexdigest()
        compressed = zlib.compress(data, 6)
        codec, stored = ('zlib', compressed) if len(compressed) < len(data) else ('raw', data)
        target = self.root / ident
        with self.write_lock:
            if not target.exists():
                used = sum(path.stat().st_size for path in self.root.iterdir() if path.is_file())
                if used + len(stored) > 512*1024*1024: raise ValueError('Attachment storage budget of 512 MB is full')
                with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as handle:
                    handle.write(stored)
                    temporary = Path(handle.name)
                temporary.replace(target)
        metadata = {'id': ident, 'filename': filename, 'kind': kind, 'bytes': len(data), 'stored_bytes': len(stored),
                    'codec': codec, 'sha256': ident, 'created_at': time.time(), **details}
        with self.db.get_connection() as conn:
            conn.execute('INSERT OR IGNORE INTO task_attachments VALUES(?,?,?)', (ident, json.dumps(metadata), zlib.compress(text.encode())))
            conn.commit()
        return self.get(ident)

    def get(self, ident, with_text=False):
        if not re.fullmatch(r'[a-f0-9]{64}', ident): raise ValueError('Invalid attachment identity')
        with self.db.get_connection() as conn:
            row = conn.execute('SELECT metadata_json,text_blob FROM task_attachments WHERE id=?', (ident,)).fetchone()
        if not row: raise KeyError('Attachment not found')
        item = json.loads(row[0])
        if with_text: item['text'] = zlib.decompress(row[1]).decode()
        return item

    def raw(self, ident):
        item = self.get(ident); stored = (self.root / ident).read_bytes()
        data = zlib.decompress(stored) if item['codec'] == 'zlib' else stored
        if hashlib.sha256(data).hexdigest() != ident: raise ValueError('Attachment integrity check failed')
        return data

    def context(self, identifiers, query, budget=24000):
        if len(identifiers) > 20: raise ValueError('Use at most 20 attachments per task')
        text = '\n'.join(f'[Untrusted attachment {ident}]\n' + self.get(ident, True)['text'] for ident in dict.fromkeys(identifiers))
        return compact_text(text, query, budget)
