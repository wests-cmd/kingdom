"""Exercise real PDF text extraction through the governed attachment intake."""
import io

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from backend.runtime.attachments import AttachmentStore
from backend.storage.db import Database


def test_pdf_text_and_provenance_survive_parser_dependency_upgrade(tmp_path):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
        DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 20 100 Td (Kingdom PDF extraction smoke) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    store = AttachmentStore(Database(tmp_path / 'attachments.db'), tmp_path / 'inputs')
    item = store.put('parser-check.pdf', output.getvalue())
    text = store.get(item['id'], True)['text']
    assert item['text_extracted'] is True and item['ocr_performed'] is False
    assert '[PDF page 1]' in text and 'Kingdom PDF extraction smoke' in text
    assert store.raw(item['id']) == output.getvalue()
