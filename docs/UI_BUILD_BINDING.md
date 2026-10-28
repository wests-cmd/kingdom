# Native build and saved interface compatibility

A saved UI component can otherwise hide the bundled interface after a native update. Semver alone does not distinguish two tested builds both labeled 1.2.4. The owner reproduced this on Laptop 1: the backend reported the updated native version while `active.json` still selected an older interface package.

UI selections now record the exact native build revision. A frozen backend ignores an active selection bound to a different build, or an older unbound selection, and serves its bundled interface. Files and the old pointer remain available for inspection; status explains the inactive component. Rollback cannot revive an interface from an incompatible native build. New native UI packages must explicitly list the installed revision in `compatible_backend_builds`; release packaging writes the reviewed commit there.

Source/development instances without a frozen build identity retain version-based compatibility. Unknown build identity is not proof of current software. The sidebar additionally shows the backend's reported build revision, and the general connection badge says “Local app” to distinguish backend availability from peer availability. Source revisions and build-input manifests are provenance evidence, not independent proof of every installed byte.

Laptop 1's immediate repair used the normal owner API to clear the stale saved selection, installed the CI-tested native package and verified the installed backend executable against its artifact digest. The source guard described above must be present in the next frozen backend to enforce future selection invalidation automatically.
