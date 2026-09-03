# Builtins
from logging import info, warning

# External
from flask import Blueprint, render_template, redirect, url_for, request, abort
from flask_login import login_required, current_user

# Internal
from extensions import rss, sched, acl
from forms import AssignCorrectionForm
from framework.accesscontrol import UserPermission

RssPageController = Blueprint('RssPageController', __name__)

# TODO: Create db table for RSS updates

@RssPageController.before_request
def check_perms():
    if not acl.check_permission(UserPermission.ACCESS_RSS): abort(403)

@RssPageController.route('/changes')
@login_required
def rss_changes():
    return render_template('changes.j2', changes=rss.updates, form=AssignCorrectionForm())

@RssPageController.route('/changes/ignore')
@login_required
def ignore_update():
    uuid = request.args.get('u', None)
    if not uuid:
        return redirect(url_for('RssPageController.rss_changes'))
    title = rss.remove_update(uuid)
    if not title:
        warning(f'Removing non-existent RSS Update with UUID {uuid}')
    else:
        info(f'RSS Update {uuid} ({title}) ignored by {current_user.nickname} (ID: {current_user.get_id()})')
    return redirect(url_for('RssPageController.rss_changes'))

@RssPageController.route('/changes/forceupdate')
@login_required
def refresh():
    sched.run_job('Fetch RSS updates')
    return redirect(url_for('RssPageController.rss_changes'))