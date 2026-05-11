# Development instructions

## Code structure

### /
- The root directory contains instructions, config files for any linters, formatters, containers or python package managers
- `App.py` is the entry point which initializes the app, connects to the database, loads blueprints and config and starts the WSGI server
- `extensions.py` - Singleton instances of all used Flask extensions, for the lack of a better solution
- `crypto.py` - Hashing and cryptographic helpers
- `forms.py` - WTForms form definitions
- `constants.py` - Global constants
- `db.py` - Peewee ORM model definitions and some miscellaneous database code
- `utils.py` - Helper functions that don't fit elsewhere

### /templates
- Contains Jinja2 HTML templates used to render the UI
- `/auth` - Pages related to authentication
- `/backups` - Pages related to the automatic backup system
- `/debug` - Debug pages
- `/embeds` - Templates for the user badges, designed to be embedded on Wikidot. New themes can be added here and should be automatically loaded.
- `/errors` - Error pages
- `/partials` - HTML snippets and templates intended to be loaded using JS or jinja includes

### /temp
- Temporary files, will be created at runtime
- `/avatar` - Discord profile picture cache
- `/snapshots` - Snapshots of original pages for each translation, to be included in the next backup.
> [!IMPORTANT]
> If you just set up a new instance of SCUTTLE or for any reason wiped the snapshot directory, you should run "Make all snapshots" in the debug menu, or "Extract snapshots from latest backup" if you've already made a backup.

### /tasks
- Tasks to be run periodically through APScheduler

### /static
- Static resources, you should ideally configure your web server to serve these directly

### /scripts
- Miscellaneous scripts used for development

### /framework
- Code for the SCUTTLE's subsystems, such as the dynamic navigation menu and the role system, and configuration files intended to be changed by the developer rather than the user.
- `/api/schemas` - Defines [JSON Schemas](https://json-schema.org/) for validating API requests
- `/templates` - Smaller templates used as components of pages
- `/config` - Subsystem configuration files, see `Config.MD` inside the directory for details

### /data
- Persistent storage, contains the SQLite database and all other persistent data SCUTTLE generates.
- `/crypto` - Contains PGP signing keys used to sign backups. These are generated on startup, but you should be able to supply your own keys stored as ASCII Armored text files (`scuttle.asc`, `scuttle.pub.asc`)
> [!IMPORTANT]
> If you are running SCUTTLE in a container, make sure this directory is accessible and set up as either a persistent volume or a bind mount. The database stores hashed passwords, adjust permissions accordingly

### /connectors
- Modules used for interacting with external APIs and services, such as Discord or Wikidot

### /blueprints
- Modules used for the actual application, each module must define a single Flask blueprint class, which will be loaded in App.py