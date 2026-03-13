from http import HTTPStatus
from logging import critical, warning, error, info, debug
from flask import Blueprint, redirect, url_for, current_app, request, render_template, send_from_directory, flash, abort, send_file
from flask_login import login_required, current_user
from db import Backup, User, Article
from datetime import datetime
import os
import py7zr
import io
import requests
from lxml import etree
from os import path, getcwd
from urllib.parse import urlparse, urlunparse

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

@DebugToolsController.route('/debug/invalidate_avatar_cache')
@login_required
def av_cache_invalidate():
    User.update(avatar_hash=None).execute()
    flash("Cache zneplatněna, příští aktualizace stáhne všechny avatary")
    return redirect(url_for('DebugToolsController.debug_index'))

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
    if not portainer.is_authenticated():
        portainer.login()
    try:
        portainer.kill_container()
        flash("Kontejner ukončen (SIGKILL)")
    except PortainerError as e:
        flash(f"Kontejner se nepodařilo ukončit! ({str(e)})")
    return redirect(request.referrer or url_for("DebugToolsController.debug_index"))

@DebugToolsController.route('/debug/backup/start_container')
@login_required
def start_wikicomma_container():
    if not portainer.is_authenticated():
        portainer.login()
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
@login_required
def force_end_backup():
    Backup.update(is_finished=True).execute()
    flash("Záloha ukončena")
    return redirect(request.referrer or url_for('LeaderboardController.index'))

@DebugToolsController.route('/debug/backup/snapshot_all')
@login_required
def make_all_snapshots():
    snapshot_all()
    flash("Snímky vytvořeny")
    return redirect(request.referrer or url_for('LeaderboardController.index'))

@DebugToolsController.route("/debug/extract_snapshots")
@login_required
def extract_snapshots():
    last_backup = Backup.select().order_by(Backup.date.desc()).first()
    backup_filename = str(last_backup.sha1) + '.7z'
    backup_path = os.path.join(current_app.config['BACKUP']['BACKUP_ARCHIVE_PATH'], backup_filename)
    snapshot_path = os.path.join(os.getcwd(), 'temp')
    if not os.path.exists(backup_path):
        flash("Chyba integrity (poslední záloha neexistuje v archivu)")
        return redirect(request.referrer or url_for("DebugToolsController.debug_index"))
    archive = py7zr.SevenZipFile(backup_path, mode='r')
    info(f"Extracting snapshots from latest backup archive ({backup_filename})")
    try:
        with archive:
            archive.extract(path=snapshot_path, recursive=True, targets=['snapshots'])
    except Exception as e:
        flash(f"Chyba při extrakci ({str(e)})")
        error(f"Extraction failed ({str(e)})")
    else:
        flash(f"Soubory extrahovány do {snapshot_path}")
        info(f"Files extracted succesfully")
    return redirect(request.referrer or url_for("DebugToolsController.debug_index"))

@DebugToolsController.route('/debug/normalize_links')
@login_required
def normalize_links():
    # Removes trailing newlines from all links in the database
    # And sets the URL scheme to HTTP
    updated_count = 0
    for a in Article.select():
        link: str = a.link
        oldlink = link
        if not a:
            warning(f'Link missing for {a.name}')
            continue
        link = link.removesuffix('\n')
        parsed = urlparse(link)
        link = parsed._replace(scheme='http').geturl()
        # Only save the new link if it doesn't match the old one
        if oldlink != link:
            debug(f"{oldlink.encode('unicode_escape').decode('utf-8')} -> {link}")
            a.link = link
            a.save()
            updated_count += 1
    flash(f"{updated_count} odkazů upraveno")
    return redirect(url_for('DebugToolsController.debug_index'))

# TODO: Make this go both ways - mark pages that are present in DB but missing on site
@DebugToolsController.route('/debug/compare_sitemap')
@login_required
def compare_sitemap():
    ignored_prefixes = ['nav:', 'system:', 'fragment:', 'component:', 'theme:', 'search:', 'css:', 'legal:', 'info:', 'forum:']
    wikis = [w['target_wiki'] for w in current_app.config['MONITORED_WIKIS']]
    links = []

    for wiki in wikis:
        sitemap_url = f"http://{wiki}.wikidot.com/sitemap.xml"
        sitemap_fetch = requests.get(sitemap_url)
        if(sitemap_fetch.status_code != HTTPStatus.OK):
            error(f"Fetch sitemap failed for {wiki}")
            continue
        try:
            sitemap_tree = etree.fromstring(sitemap_fetch.text.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            error(f"Error parsing sitemap for {wiki}: {str(e)}")
            continue
        # The sitemap is a <urlset> tag containing <url> tags
        # The url tags always have a <loc> tag as the first child, containing the actual link
        # Some of the urls may also have a <lastmod> tag containing the last modified date
        for site in sitemap_tree:
            links.append(site[0].text)

    temp_file_path = path.join(getcwd(), 'temp', 'sitemap_compare.txt')
    sys_page_count = 0
    missing_page_count = 0

    with open(temp_file_path, 'w') as logfile:
        for link in links:
            slug: str = urlparse(link).path.removeprefix('/')
            if slug.startswith(tuple(ignored_prefixes)):
                sys_page_count += 1
                continue
            if not Article.get_or_none(Article.link ** f'%{slug}'):
                missing_page_count += 1
                logfile.write(f"MISSING - {link} ({slug})\n")
        logfile.write('\n' + 50*'=' + '\n')
        logfile.write(f"{missing_page_count} pages missing from database\n")
        logfile.write(f"{sys_page_count} system pages ignored\n")

    flash("Protokol odeslán ke stažení")
    return send_file(temp_file_path, download_name="sitemap_compare.txt", as_attachment=True)