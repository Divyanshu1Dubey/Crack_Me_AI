"""manage.py entry points for the recall importer commands.

Django only discovers commands in an installed app's ``management/commands``
folder. The installed app is ``importers``; the commands themselves live in
``importers/neetpg/management/commands/``, which Django never scans, so every
documented ``manage.py neetpg_*`` command answered "Unknown command". Each
module here re-exports one of them.
"""
