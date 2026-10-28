# Periodic interface data and verified UI updates

The authenticated owner interface refreshes its subscribed live-data panels on
opening, then every ten minutes. This emits a data refresh event without
remounting the page, clearing editor state, or replacing the document. Existing
faster task and worker polls remain active. Panels using `useLiveData` subscribe
to the event; other independently managed panels retain their existing refresh
behavior. A health request precedes each event and has a 15-second timeout.

Every second successful periodic interval (20 minutes after opening, then every
20 minutes in normal visible/online operation) checks the existing owner-only
UI update endpoints. It reads active status and skips an already selected
package. Automatic application requires a known exact native backend build;
source installations show a review notice instead. The server performs checksum,
inventory and compatibility verification before activation. No native installer,
backend restart, operating-system update, model or new permission is requested.

A verified newly activated component reloads only if the page is online,
visible, and has no populated text/editor/select/file fields or changed check
controls. Input/change events additionally mark the session dirty, including
clearing a field to empty or whitespace; polling and navigation never reset that
mark. This intentionally treats populated settings conservatively. Otherwise a
persistent visible action asks the owner to save work, then explicitly confirm a
reload that warns unsaved edits will be lost. Disabled populated editors also
prevent automatic reload during submission.

The controller has one in-flight cycle and one timer, aborts requests on unmount,
skips work while hidden/offline, and retries failed cycles with a bounded
20/40-minute backoff. Focus/visibility/online events cannot generate request
storms. Returning to the page waits for its existing timer. Skipped cycles do
not advance the update cadence. A failed update cannot claim activation or
trigger reload. Existing manual Updates controls remain available.

Memory Records and individual records use native keyboard-accessible details
controls, initially closed. Memory polling uses ten minutes rather than the
default five seconds; search and explicit storage still fetch immediately.
Search and storage inputs stay outside the list.

Validation: `node --test frontend/tests/periodicRefresh.test.js` and
`npm --prefix frontend run build`. Pure-controller tests cover cadence, deferred
reload, drafts, visibility/offline, bounded backoff, cleanup and server rejection.
These are source tests, not evidence that a published package was downloaded or
that an installed native interface was updated.
