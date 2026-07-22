"""Django management command shim package.

These commands wire the runner into the existing Django project. They
are NOT registered automatically — the project owner can opt in by
adding 'backend.importers.neetpg' to INSTALLED_APPS (or by registering
the modules manually).

Each command is a thin wrapper that delegates to `backend.importers.neetpg.runner`.
"""