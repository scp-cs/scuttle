# Builtins
import json, os, subprocess
from logging import warning, info, error, debug
from dataclasses import dataclass
from typing import List, Dict
from jsonschema import validate
from threading import Lock
from datetime import datetime, timedelta
import textwrap

# Internal
from connectors.portainer import PortainerError
from extensions import portainer, webhook
from connectors.wikicomma import Status, Message, MessageType, ErrorKind, generate_config
from db import WikiCommaConfig, Wiki, Backup, User
from crypto import sign_file, get_fingerprint
from framework.api.schemas.backup_schema import status_message_schema, backup_config_schema
import utils

# External
import urllib.parse
from flask import Blueprint, redirect, render_template, url_for, current_app, jsonify, request, abort, send_file, flash, has_request_context
from flask_login import current_user, login_required
from playhouse.shortcuts import model_to_dict
import py7zr
import hashlib

# TODO: This blueprint is way too cluttered, move most of the backup logic to a separate file

@dataclass
class BackupStatus:
    wiki_tag: str
    messages: List[Message]
    total_articles: int = 0
    finished_articles: int = 0
    postponed_articles: int = 0
    total_errors: int = 0
    status: Status = Status.Other

@dataclass
class StatusMutex:
    mutex: Lock
    status: BackupStatus

statuses: Dict[str, StatusMutex] = {}

AutobackupController = Blueprint("AutobackupController", __name__)

# Tiny hack that allows us to call the backup_start route function in the automatically sheduled task, bypassing login
@AutobackupController.record_once
def setup_backup_route(setup_state):
    setup_state.app.add_url_rule('/backup/start', view_func=login_required(backup))

def finish_backup():
    if Backup.get_or_none(Backup.is_finished == False) is None:
        # Don't think that this can actually happen but it's better to handle it regardless
        error("No backups to finish!")
        # If it does happen then I messed up somehow
        # TODO: Remove this at some point
        webhook.send_text("Unexpected state encountered while finishing backup (definitely a bug), please review application logs")
        return

    snapshot_count = 0

    info(f"Saving backup")
    archive_path = os.path.join(current_app.config['BACKUP']['BACKUP_ARCHIVE_PATH'], "current.7z")
    try:
        with py7zr.SevenZipFile(archive_path, 'w') as archive:
            archive.writeall(current_app.config['BACKUP']['BACKUP_COMMON_PATH'], 'backup')
            # Add all snapshots to the backup
            snapshot_path = os.path.join(os.getcwd(), 'temp', 'snapshots')
            if utils.config_has_key(current_app.config, "BACKUP.save_snapshots", True) and os.path.isdir(snapshot_path):
                archive.writeall(snapshot_path, 'snapshots')
                snapshot_count = utils.count_files_rec(snapshot_path)
        # Hash the archive with SHA-1 and save that for later
        with open(archive_path, 'rb') as archive:
            hash = hashlib.sha1(archive.read()).hexdigest()
    except Exception as e:
        error("Couldn't compress backup (check config paths)")
        error(str(e))
        # Let the admin know that something went wrong
        webhook.send_text("```Záloha selhala (nepodařilo se vytvořit archiv)```")
        statuses.clear()
        # The backup will stil be marked as "in-progress" here, the status has to be cleared on the devtools page
        return
    else:
        # Don't know what the purpose of the else block is here but scared to change it
        # Give the archive a unique name and mark the backup as finished
        archive = os.path.join(current_app.config['BACKUP']['BACKUP_ARCHIVE_PATH'], f'{hash}.7z')
        info(f"Archive hash is: {hash}")
        os.rename(archive_path, archive)
        Backup.update(sha1=hash).where(Backup.is_finished == False).execute()

    signature = sign_file(archive)
    signed = True
    if not signature:
        error('Signing backup failed')
        signed = False
    else:
        with open(archive+'.asc', 'w') as sig_file:
            sig_file.write(str(signature))

    # Build a report that will be sent to Discord through the webhook
    backup_done_message = f"```Záloha dokončena v {datetime.now().strftime('%H:%M:%S %d-%m-%y')}:\n\n"

    # Add an article count and error count for each wiki
    for wiki in statuses.values():
        status = wiki.status
        backup_done_message += f"{status.wiki_tag}\nZálohováno {status.finished_articles} z {status.total_articles} článků\n"
        backup_done_message += f"Zaznamenáno {status.total_errors} chyb\n\n"

    # Add the current snapshot count
    if utils.config_has_key(current_app.config, "BACKUP.save_snapshots", True):
        backup_done_message += f"Uloženo {snapshot_count} snímků původních stránek\n\n"

    # Add the signing key fingerprint
    if not signed:
        backup_done_message += "Zálohu se nepodařilo podepsat!\n"
    else:
        readable_fp = ' '.join(textwrap.wrap(str(get_fingerprint()), 4))
        backup_done_message += f"Soubor je podepsán pomocí klíče s otiskem {readable_fp}, před obnovením zkontrolujte signaturu!\n\n"

    # Add the archive hash
    backup_done_message += f"Kontrolní součet archivu je {hash}\n\n"
    backup_done_message += "Administrace Záznamů a Informační Bezpečnosti vám přeje hezký den!```" # Be polite :3

    # Send it
    webhook.send_text(backup_done_message)
    statuses.clear()
    Backup.update(is_finished=True).where(Backup.is_finished == False).execute()

@AutobackupController.route('/backups', methods=["GET"])
@login_required
def backup_index():
    last_backup = Backup.select().order_by(Backup.date.desc()).first()
    interval = current_app.config.get("BACKUP", {}).get("BACKUP_INTERVAL")
    if interval is not None and last_backup is not None:
        next_backup = (last_backup.date + timedelta(seconds=interval)).strftime("%d.%m.%Y")
        last_backup = last_backup.date.strftime("%d.%m.%Y")
    else:
        last_backup = next_backup = 'N/A'
    return render_template('backups/backup_index.j2', wikis=Wiki.select().where(Wiki.is_active==True),\
                            backups=Backup.select().order_by(Backup.date.desc()).prefetch(User),
                            last_backup=last_backup,
                            next_backup=next_backup)

@AutobackupController.route('/backup/<int:backup_id>/delete')
@login_required
def backup_delete(backup_id: int):
    # TODO: 2FA
    info(f"Backup ID {backup_id} deleted by user {current_user.nickname} (ID: {current_user.get_id()})")
    Backup.delete_by_id(backup_id)
    # TODO: Delete the actual archive
    # (Maybe schedule a task to purge deleted backups after some time to allow time for restore?)
    # Also add a confirmation dialog
    return redirect(url_for('AutobackupController.backup_index'))

@AutobackupController.route('/backup/<int:backup_id>/download')
@login_required
def backup_download(backup_id: int):
    backup = Backup.get_or_none(Backup.id == backup_id) or abort(404)
    archive_path = current_app.config['BACKUP']['BACKUP_ARCHIVE_PATH']
    backup_path = os.path.join(archive_path, f'{backup.sha1}.7z')
    download_name = backup.date.strftime("backup-%d-%m-%y.7z")
    if not os.path.exists(backup_path): abort(404)
    return send_file(backup_path, as_attachment=True, download_name=download_name)

@AutobackupController.route('/backup/<int:backup_id>/download_signature')
@login_required
def backup_download_sig(backup_id: int):
    backup = Backup.get_or_none(Backup.id == backup_id) or abort(404)
    archive_path = current_app.config['BACKUP']['BACKUP_ARCHIVE_PATH']
    signature_path = os.path.join(archive_path, f'{backup.sha1}.7z.asc')
    download_name = backup.date.strftime("backup-%d-%m-%y.7z.asc")
    if not os.path.exists(signature_path):
        flash("Podpis neexistuje (huh)")
        return redirect(url_for('AutobackupController.backup_index'))
    return send_file(signature_path, as_attachment=True, download_name=download_name)

# TODO: This doesn't require auth for now as logging wikicomma in would be a pain in the ass
# Theoretical worst case: someone could force trigger the post-backup process while Wikicomma is still running
# This would mess up the app state but the files themselves would be intact
@AutobackupController.route('/backup/status', methods=["GET", "POST"])
def backup_status():
    if request.method == "GET":
        return jsonify([s.status for s in statuses.values()])
    try:
        message = json.loads(json.loads(request.data))
        validate(message, status_message_schema)
        tag = message['tag']
        message_type = MessageType(message['type'])
        current_message = Message(message_type, tag)
    except Exception as e:
        error(f"Received invalid status message")
        error(str(e))
    match message_type:
        case MessageType.Handshake:
            info(f"WikiComma client for {tag} connected")
        case MessageType.Preflight:
            current_message.total = message['total']
            info(f"Counting {current_message.total} articles for {current_message.tag}")
            with statuses[tag].mutex:
                statuses[tag].status.total_articles = current_message.total
                statuses[tag].status.messages.append(current_message)
        case MessageType.Progress:
            backup_phase = Status(message['status'])
            with statuses[tag].mutex:
                if backup_phase == Status.PagesMain:
                    statuses[tag].status.finished_articles = message['done']
                    statuses[tag].status.postponed_articles = message['postponed']
                if statuses[tag].status.status != Status.Done:
                    statuses[tag].status.status = backup_phase
                current_message.status = backup_phase
                statuses[tag].status.messages.append(current_message)
        case MessageType.ErrorFatal:
            current_message.error_kind = ErrorKind(message['errorKind'])
            current_message.error_message = str(current_message.error_kind)
            error(f"Encountered fatal error: {current_message.error_message}")
            with statuses[tag].mutex:
                statuses[tag].status.status = Status.FatalError
                statuses[tag].status.messages.append(current_message)
        case MessageType.ErrorNonfatal:
            current_message.error_kind = ErrorKind(message['errorKind'])
            current_message.error_message = str(current_message.error_kind)
            error(f"Encountered non-fatal error: {current_message.error_message}")
            with statuses[tag].mutex:
                statuses[tag].status.messages.append(current_message)
        case MessageType.FinishSuccess:
            info(f"Backup finished for site {tag}")
            with statuses[tag].mutex:
                statuses[tag].status.status = Status.Done
                statuses[tag].status.messages.append(current_message)
            # for w in list(statuses.values()):
            #    debug(f"Tag: {w.status.wiki_tag}; Status: {w.status.status}; Finished: {w.status.finished_articles}; Total: {w.status.total_articles}; Errors: {w.status.total_errors}; Last message: {w.status.messages[-1]}")
            if all([w.status.status == Status.Done for w in statuses.values()]):
                # TODO: This does not run after the first backup is done? Only fixed by a restart
                # Makes no sense since the dict is cleared in the finish_backup function
                info(f"Backup finished")
                finish_backup()
        case _:
            warning("Received message of unknown/unused type")
            return "Unknown type", 400
    return "OK"

@AutobackupController.route('/backup/config', methods=["GET", "POST"])
@login_required
def backup_config():
    if request.method == "GET":
        current_config = model_to_dict(WikiCommaConfig.get_or_create()[0], recurse=True, exclude={WikiCommaConfig.id})
        wikis = [model_to_dict(w) for w in Wiki.select().where(Wiki.is_active == True)]
        return jsonify({"config": current_config, "wikis": wikis}), 200
    try:
        path = current_app.config.get("BACKUP").get("WIKICOMMA_CONFIG_PATH")
        if not path:
            raise RuntimeError("Cesta ke konfiguračnímu souboru není nastavena")
        # Parse the payload and make sure it's valid
        data = json.loads(request.data)
        validate(data, schema=backup_config_schema)
        # There's always just a single row in the WikiCommaConfig table
        current_config = WikiCommaConfig.get_or_create()[0]
        current_config.blacklist = data['blacklist']
        current_config.http_proxy = data['http_proxy']
        current_config.socks_proxy = data['socks_proxy']
        current_config.delay = data['delay']
        current_config.ratelimit_refill = data['ratelimit_refill']
        current_config.ratelimit_size = data['ratelimit_size']
        current_config.save()
        
        # TODO: Should validate the URLs and normalize them (scheme, trailing slash, remove path)
        # Add the new wiki list
        # We don't want to drop the previous wikis from the database as the backup model references them
        if data['wikis'] is not None:
            wiki_urls = data['wikis'].strip().split('\n')
            # We upsert the new URLs and mark them as active
            for wiki in wiki_urls:
                # Skip possible blank lines
                if not wiki: continue
                row, is_new = Wiki.get_or_create(url=wiki, name=str(urllib.parse.urlparse(wiki).netloc).split('.')[0])
                if not is_new:
                    row.is_active = True
                    row.save()
            # Then loop over them again and mark the ones not in the new list as inactive
            for wiki in Wiki.select():
                if wiki.url not in wiki_urls:
                    wiki.is_active = False
                    wiki.save()
        else:
            Wiki.update(is_active=False).execute()
        generate_config(path)
        # Log it just in case
        info(f"Accepted new WikiComma config by {current_user.nickname} (ID: {current_user.get_id()})")
        return "Konfigurace uložena", 200
    except Exception as e:
        error(f"Config couldn't be updated: {str(e)}")
        return f"Konfiguraci nelze uložit ({str(e)})", 400

def backup():
    if Backup.get_or_none(Backup.is_finished == False) is not None:
        if has_request_context():
            # We want to flash the message to the user starting the backup
            # But if the backup is automatically scheduled, there is no user and no session to flash to
            flash("Backup is already running!")
        return redirect(url_for('AutobackupController.backup_index'))

    # Check that we know how to start the backup
    start_method = current_app.config.get('BACKUP', {}).get('WIKICOMMA_START_METHOD')
    if start_method not in ['container', 'command']:
        error("WikiComma start method not set or invalid")
        return "WikiComma start method not set or invalid", 500
    
    # Check that we know where to put the backup once it's done
    if 'BACKUP_ARCHIVE_PATH' not in current_app.config['BACKUP'] or 'BACKUP_COMMON_PATH' not in current_app.config['BACKUP']:
        error("One or more backup paths are missing")
        return "Backup common or archive path missing from config", 500
    
    info("Preparing to start backup")

    # Check that we can login to Portainer if we're running WikiComma in a container
    if start_method == 'container':
        if not portainer.is_initialized():
            error("Portainer connector is not initialized, can't proceed")
            return "Konfigurace Portaineru chybí. Nelze pokračovat.", 500
        try:
            portainer.login()
        except PortainerError as e:
            error(f"Cannot login to portainer ({str(e)})")
            return "Přihlášení k portaineru selhalo. Nelze pokračovat", 500
        info('Successfully logged in to portainer')
    else:
        # Otherwise make sure we have a valid start command
        start_command = current_app.config.get('BACKUP', {}).get('START_CMD')
        if not start_command:
            error("Invalid start command")
            return "Invalid start command", 500

    # Iterate over the wiki list, create status objects and mutexes
    for wiki in Wiki.select().where(Wiki.is_active == True):
        statuses[wiki.name] = StatusMutex(Lock(), BackupStatus(wiki.name, messages=[], status=Status.Other))
        debug(f"SynchronizedStatus created for {wiki.name}")

    info(f"{Wiki.select().where(Wiki.is_active == True).count()} sites are marked for backup")

    # Save to the database
    backup = Backup()
    if current_user:
        backup.author = current_user
    backup.date = datetime.now()
    backup.is_finished = False
    backup.save()

    # TODO: Add BackupHasWiki entries

    info('Attempting to start WikiComma')
    if start_method == 'container':
        try:
            info(f"Starting container \"{portainer.get_name()}\"")
            portainer.start_container()
        except PortainerError as e:
            error(f"Couldn't start container, stopping backup ({str(e)})")
            backup.delete_instance()
            return "Chyba: Kontejner nelze spustit", 500
    else:
        try:
            info(f"Running command: {start_command}")
            # subprocess.run(start_command, shell=True).check_returncode()
            # TODO: This shouldn't block
            os.system(start_command)
        except subprocess.CalledProcessError:
            error("Command failed, stopping backup")
            backup.delete_instance()
            return "Chyba: Spouštěcí příkaz skončil s chybou", 500

    info('WikiComma started')
    return "Záloha byla spuštěna"

