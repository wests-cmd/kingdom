# Portable skills across harnesses

Kingdom accepts SKILL.md instructions independently of its portable skill map.
The existing map v1 remains preferences only. A map skill_id can match the name
of an imported document; it does not activate the document or install its tools.

Use the owner-authenticated integration API:

1. POST `/skill-documents/preview` with `content` (Markdown), `source` (an inert
   provenance label, e.g. a Discord attachment identifier), and `harness`
   (`generic`, `hermes`, `claude`, or another lowercase identifier).
2. Review the returned document and POST `/skill-documents/confirm` with the
   preview_id and checksum. Previews expire after five minutes and are single use.
3. GET `/skill-documents/{skill_id}/export` for interoperable Markdown and its
   provenance envelope. API paths use the same prefix as `/skillmaps`.

Markdown requires YAML frontmatter `name` (lowercase skill identifier) and
`description`, followed by a nonempty instruction body. Other harness metadata
is ignored; export emits only name and description. Embedded commands and links
remain text. No fetch, package install, code execution, permission grant, model
training, or automatic prompt injection occurs during import. Scripts, assets,
and referenced files are not transferred by this document-only adapter.

The envelope is schema_version `1.0`, skill_id, name, description, instructions,
provenance `{source, harness, sha256}`, trust `untrusted`, and execution_enabled
`false`. The provenance digest identifies the original uploaded Markdown;
normalized exports can have different bytes. Source and harness are supplied
labels, not verified publisher identities. Discord content follows the same
untrusted boundary. Reviewed executable adapters and runtime governance remain
separate requirements for acting on any instruction.

Documents persist in Kingdom SQLite, scoped to the importing identity. They may
contain private context: do not publish exports without reviewing them for secrets.
