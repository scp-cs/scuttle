
# The SCUTTLE Translation Tracker System
Named after [RAISA's famous cautionary tale](https://scp-wiki.wikidot.com/scuttle), SCUTTLE provides a user friendly way for tracking our members' contributions to the translation project.

Details on the scoring system can be found on our [Discord](https://discord.gg/A6U2fCUJs6).

## Features

- Stores article metadata (name, translator, wiki page, word count and bonus translator points)
    - Shows a leaderboard for branch members to view
    - Allows searching
    - API for integration with other tools
    - Shows overall statistics of all translated pages
- Notifies branch administrators of users eligible for new discord roles over channel webhooks
- Stores user info (nickname, Wikidot ID, Discord username)
    - Automatically fetches nicknames and profile avatars from Discord
- Automatically fetches new articles from RSS feeds
- Updates article corrections based on RSS feeds
- Login using classic credentials or Discord OAuth
- Integrates with our fork of [WikiComma](https://gitlab.com/DBotThePony/wikicomma)
  - Provides a UI to configure backup settings and manage past backups
  - Automatically schedules and runs backups at set intervals
  - Integrates with [Portainer](https://www.portainer.io/) to run WikiComma safely inside a container
  - Cryptographically signs backups using PGP and calculates checksums
  - Saves snapshots of original articles when a translation is published and includes them in backups
  - Sends a backup summary over Discord Webhooks on completion
- Generates embeddable badges for members' personal files which update in real time, support for different themes
- Fully Dockerized

## Planned features

- [ ] Note system for moderators
- [ ] Automatic word counting (hard >w<)
- [ ] Improve responsivity on mobile and smaller windows
- [ ] Localization (Low-prio for now, if you want to use SCUTTLE on your branch, let us know!)
- [ ] Integrated modern backup tool to replace WikiComma
- [ ] A backup browser for viewing and restoring archived pages

## Installation (manual)
### 1. Clone the repository
```bash
git clone https://github.com/scp-cs/translatordb_web.git
cd translatordb_web
```
### 2. Create a config file
*config.json*
```
{
    "DEBUG": false,
    "SECRET_KEY": "[SECRET KEY USED BY FLASK]",
    "DISCORD_TOKEN": "[YOUR DISCORD APP TOKEN]"
    "DISCORD_CLIENT_SECRET": "[YOUR DISCORD OAUTH SECRET]",
    "DISCORD_CLIENT_ID": [YOUR DISCORD APP ID],
    "DISCORD_REDIRECT_URI": "https://your-app-url.xyz/oauth/callback",
    "DISCORD_WEBHOOK_URL": [A WEBHOOK TO YOUR ADMIN/LOG CHANNEL],
    "DISCORD_ROLEMASTER_ID": [DISCORD ID OF THE PERSON RESPONSIBLE FOR ROLES],
    "RSS_MONITOR_CHANNELS": [
        "http://your-wiki.wikidot.com/feed/site-changes.xml",
        "http://your-wanderers-library.wikidot.com/feed/site-changes.xml",
        "http://your-backrooms-or-whatever.wikidot.com/feed/site-changes.xml"
    ],
    "FIX_PROXY": [true / false],
    "BACKUP": {
        "WIKICOMMA_START_METHOD": ["container" / "command"],
        "PORTAINER": {
            "URL": [PORTAINER API URL],
            "USER": [PORTAINER USER],
            "PASSWORD": [PORTAINER PASSWORD],
            "ENV_ID": [PORTAINER ENVIRONMENT ID],
            "CONTAINER_NAME": [CONTAINER NAME]
        },
        "SELF_ADDRESS": [URL],
        "BACKUP_COMMON_PATH": [PATH],
        "BACKUP_ARCHIVE_PATH": [PATH],
        "WIKICOMMA_CONFIG_PATH": [PATH],
        "START_CMD": [WIKICOMMA START COMMAND],
        "save_snapshots": [true / false]
    }
}
```
`DISCORD_TOKEN`, `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET` can be found on your [Discord Developer Portal](https://discord.com/developers/applications).
> [!NOTE]
> Keep in mind that your redirect URI must *exactly* match one of the URIs entered on the developer portal, even when testing locally. Login attempts will fail otherwise.

`DISCORD_WEBHOOK_URL` - A webhook that will be used to send notifications and alerts, you can generate one in your server settings.

`DISCORD_ROLEMASTER_ID` - User ID of the moderator responsible for roles.

`RSS_MONITOR_CHANNELS` - An RSS feed URL for each one of your sites.

`SECRET_KEY` should be a reasonably long random string and never shared with anyone. You can generate one, for example, using the Python `secrets` library:
```python
import secrets
print(secrets.token_urlsafe(24))
```
### 3. Define the initial admin user
```bash
export SCP_INIT_USER=administrator
export SCP_INIT_PASSWORD=password
```
### 4. Run the app
```bash
python App.py
```

## Installation (Docker)
SCUTTLE is available as a prebuilt container image on [DockerHub](https://hub.docker.com/r/x10102/translatordb)
> [!WARNING]
> If you're running SCUTTLE behind a reverse proxy and communicating over HTTP internally, the environment variable `OAUTHLIB_INSECURE_TRANSPORT` has to be set, any requests to the app will fail otherwise.
```bash
docker run -d -p 8080:8080 -v /your/log/path:/app/translatordb.log -v /your/data/path:/app/data/scp.db -v /your/config/path:/app/config.json:ro --name scuttle x10102/translatordb
```

## Configuring Backups
To manage wiki backups with SCUTTLE, you must use our [WikiComma fork](https://github.com/scp-cs/wikicomma), modified to send status updates over HTTP POST requests during the backup. Configuration is mostly the same as the original version, see the project's README file for details.

### 1. Create an archive directory
Create the *"BACKUP"* key in the config file as per the example. Create a new directory, ensuring SCUTTLE has write permissions, and place the path into the *"BACKUP_ARCHIVE_PATH"* key. The 7z archives containing the finished backups will be stored here. 

### 2. Point SCUTTLE to WikiComma's files
Set the *"BACKUP_COMMON_PATH"* to the same directory as *"base_directory"* in your WikiComma config and *"WIKICOMMA_CONFIG_PATH"* to the file itself. **Please keep in mind that your config file will be overwritten.**

### 3. Choose how to start WikiComma
WikiComma can be started either using a simple shell command, or the Portainer API, if you have a Portainer instance running. Set the *"WIKICOMMA_START_METHOD"* key to *"command"* or *"container"* accordingly.

#### 3a. Command
Set the *"START_CMD"* key to your command, simple as that! **This command will be ran exactly as-is**, for security reasons, please make sure the config file cannot be modified by third parties.

#### 3b. Portainer
Create a new user on your portainer instance with access rights to only the WikiComma container. Then set the corresponding key's to their credentials, along with the container name, API URL and environment ID (You can find it in the URL on your Portainer dashboard).

### 4. You're good to go!
Enjoy your shiny new backup management system! New features are coming soon.
