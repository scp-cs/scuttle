from http import HTTPStatus
from logging import critical, warning, error, info
from flask import Blueprint, redirect, url_for, current_app, request, render_template, send_from_directory, flash, abort
from flask_login import login_required, current_user
from db import Backup
from datetime import datetime
import os

from connectors.wikidotsite import snapshot_all
from connectors.portainer import PortainerError
from extensions import sched, webhook, portainer

DebugToolsController = Blueprint('DebugToolsController', __name__)

@DebugToolsController.before_request
def log_debug_access():
    if not current_app.config['DEBUG'] and not current_user.is_anonymous:
        warning(f'Debug endpoint {request.full_path} accessed by {current_user.nickname} (ID: {current_user.get_id()})')

@DebugToolsController.route('/debug/nickupdate')
@login_required
def nickupdate():
    sched.run_job('Fetch nicknames')
    flash("Aktualizace spuštěna na pozadí!")
    return redirect(request.referrer or url_for('LeaderboardController.index'))

@DebugToolsController.route('/debug/avupdate')
@login_required
def avdownload():
    sched.run_job('Download avatars')
    flash("Aktualizace spuštěna na pozadí!")
    return redirect(request.referrer or url_for('LeaderboardController.index'))

@DebugToolsController.route('/debug/rssupdate')
@login_required
def updaterss():
    sched.run_job('Fetch RSS updates')
    flash("Aktualizace spuštěna na pozadí!")
    return redirect(request.referrer or url_for('LeaderboardController.index'))

@DebugToolsController.route('/debug')
@login_required
def debug_index():
    return render_template('debug/tools.j2')

@DebugToolsController.route('/debug/test_webhook')
@login_required
def webhook_testing():
    try:
        webhook.send_text('TEST MESSAGE')
        flash("Testovací webhook odeslán!")
    except Exception as e:
        flash("Testovací webhook se nepodařilo odeslat (zkontrolujte logy)")
        error(f"Sending test webhook failed with error ({str(e)})")
    return redirect(request.referrer or url_for('LeaderboardController.index'))
    
@DebugToolsController.route('/debug/db/export')
@login_required
def export_database():
    download_name=datetime.strftime(datetime.now(), 'scp_%d_%m_%Y.db')
    flash("Databáze exportována!")
    return send_from_directory(os.path.join(os.getcwd(), 'data'), 'scp.db', as_attachment=True, download_name=download_name)

@DebugToolsController.route('/debug/backup/test_portainer')
@login_required
def test_portainer_login():
    try:
        portainer.login()
        flash("Přihlášení úspěšné!")
    except PortainerError as e:
        flash(f"Přihlášení neúspěšné! ({str(e)})")
    return redirect(request.referrer or url_for("DebugToolsController.debug_index"))

@DebugToolsController.route('/debug/backup/kill_container')
@login_required
def kill_wikicomma_container():
    try:
        portainer.kill_container()
        flash("Kontejner ukončen (SIGKILL)")
    except PortainerError as e:
        flash(f"Kontejner se nepodařilo ukončit! ({str(e)})")
    return redirect(request.referrer or url_for("DebugToolsController.debug_index"))

@DebugToolsController.route('/debug/backup/start_container')
@login_required
def start_wikicomma_container():
    try:
        portainer.start_container()
        flash("Kontejner spuštěn")
    except PortainerError as e:
        flash(f"Kontejner se nepodařilo spustit! ({str(e)})")
    return redirect(request.referrer or url_for("DebugToolsController.debug_index"))

@DebugToolsController.route('/debug/raise_error')
@login_required
def raise_error():
    error("Error handling test")
    abort(HTTPStatus.INTERNAL_SERVER_ERROR)

@DebugToolsController.route('/debug/raise_unhandled')
@login_required
def raise_unhandled():
    info('Raising unhandled exception')
    raise RuntimeError("teehee :3")

@DebugToolsController.route('/debug/export_pubkey')
@login_required
def export_pubkey():
    info(f"Public key exported by user {current_user.nickname}")
    return send_from_directory(os.path.join(os.getcwd(), 'data', 'crypto'), 'scuttle.pub.asc', as_attachment=True)

@DebugToolsController.route('/debug/raise_critical')
@login_required
def raise_critical_error():
    critical("Critical error handling test")
    abort(HTTPStatus.INTERNAL_SERVER_ERROR)

@DebugToolsController.route('/debug/backup/forceend')
def force_end_backup():
    Backup.update(is_finished=True).execute()
    flash("Záloha ukončena")
    return redirect(request.referrer or url_for('LeaderboardController.index'))

@DebugToolsController.route('/debug/backup/snapshot_all')
def make_all_snapshots():
    snapshot_all()
    flash("Snímky vytvořeny")
    return redirect(request.referrer or url_for('LeaderboardController.index'))