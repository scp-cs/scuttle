from typing import Any
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, BooleanField, ValidationError, HiddenField, SelectMultipleField
from wtforms.validators import EqualTo, Length, url, NumberRange, InputRequired
from wtforms.widgets import ListWidget, CheckboxInput
from flask import flash
from framework.accesscontrol import UserPermission

class FlaskFormEx(FlaskForm):
    def validate_and_flash(self) -> bool:
        """
        Validates the form and flashes all validation errors.
        Returns the result of validate_on_submit
        """
        if not self.validate_on_submit():
            for e in self.errors.values():
                flash(e[0], category="error")
            return False
        return True

# Can be used like a normal WTForms validator
class DiscordID():
    def __call__(self, form, field) -> Any:
        if len(field.data) not in [18, 19]:
            raise ValidationError('Discord ID musí mít 18 nebo 19 znaků')
        try:
            a = int(field.data)
        except ValueError:
            raise ValidationError('Discord ID může obsahovat pouze číslice')

class LoginForm(FlaskFormEx):
    username = StringField('Uživatelské Jméno', validators=[InputRequired()])
    password = PasswordField('Heslo', validators=[InputRequired()])
    submit = SubmitField('Přihlásit')

class PasswordChangeForm(FlaskFormEx):
    password = PasswordField('Heslo', validators=[EqualTo('password_confirm', "Hesla se musí shodovat"), Length(6, message="Heslo musí mít 6 - 64 znaků")])
    password_confirm = PasswordField('Potvrdit heslo')
    submit = SubmitField('Změnit heslo')

class NewArticleForm(FlaskFormEx):
    title = StringField('Název', validators=[InputRequired(message="Zadejte název článku")])
    translator = StringField('Překladatel')
    words = IntegerField('Počet slov', validators=[InputRequired(message="Zadejte počet slov")])
    bonus = IntegerField('Bonusové body', default=0)
    link = StringField('Odkaz')
    excluded = BooleanField('Vyloučit z počítání bodů', default=False)
    submit = SubmitField('Odeslat')

class EditArticleForm(NewArticleForm):
    pass

class NewUserForm(FlaskFormEx):
    nickname = StringField('Přezdívka', validators=[InputRequired()])
    wikidot = StringField('Wikidot ID', validators=[InputRequired()])
    discord = StringField('Discord ID', validators=[DiscordID()])
    can_login = BooleanField('Administrátor')
    permissions = IntegerField('Oprávnění')
    submit = SubmitField('Přidat')

class EditUserForm(NewUserForm):
    nickname = StringField('Přezdívka', validators=[InputRequired()])
    wikidot = StringField('Wikidot ID', validators=[InputRequired()])
    discord = StringField('Discord ID', validators=[DiscordID()])
    submit = SubmitField('Uložit')

class PasswordChangeForm(FlaskFormEx):
    pw = PasswordField('Heslo', validators=[InputRequired()])
    pw_confirm = PasswordField('Potvrzení hesla', validators=[InputRequired(), EqualTo('pw', message="Hesla se musí shodovat")])
    submit = SubmitField('Potvrdit')

class AssignCorrectionForm(FlaskFormEx):
    article_id = HiddenField('id', validators=[NumberRange(0, message="ID musí být číslo")])
    corrector_id = HiddenField('corrector')
    guid = HiddenField('guid')
    link = HiddenField('link')
    title = HiddenField('title')
    submit = SubmitField('Přiřadit')

class PermissionEditForm(FlaskFormEx):
    perms = SelectMultipleField("Oprávnění",
            choices=[
                (UserPermission.MASTER_ADMIN, "MASTER ADMIN", {"description": "Uděluje všechna ostatní oprávnění a umožňuje je přidávat ostatním uživatelům"}),
                (UserPermission.MANAGE_ARTICLE_SELF, "SPRÁVA VLASTNÍCH ČLÁNKŮ", {"description": "Umožňuje uživateli přidávat, upravovat a mazat své vlastní články"}),
                (UserPermission.MANAGE_ARTICLE_ALL, "SPRÁVA VŠECH ČLÁNKŮ", {"description": "Umožňuje přidávat, upravovat a mazat články ostatních uživatelů a přiřazovat korekce"}),
                (UserPermission.MANAGE_USERS, "SPRÁVA UŽIVATELŮ", {"description": "Umožňuje přidávat, upravovat a mazat uživatele"}),
                (UserPermission.DEBUG_LOW, "VÝVOJÁŘ 1", {"description": "Umožňuje provádět bezpečné vývojářské operace"}),
                (UserPermission.DEBUG_HIGH, "VÝVOJÁŘ 2", {"description": "Umožňuje provádět veškeré vývojářské operace a přidělovat některá oprávnění"}),
                (UserPermission.VIEW_BACKUPS, "ZOBRAZENÍ ZÁLOH", {"description": "Umožňuje prohlížet a stahovat zálohy z archivu"}),
                (UserPermission.MANAGE_BACKUPS, "SPRÁVA ZÁLOH", {"description": "Umožňuje mazat zálohy, konfigurovat a spouštět WikiComma"}),
                (UserPermission.MANAGE_BOT, "SPRÁVA BOTA", {"description": "Umožňuje spravovat Discord bota"}),
                (UserPermission.ACCESS_RSS, "PŘÍSTUP RSS", {"description": "Umožňuje přidávat články pomocí RSS"}),
                (UserPermission.ADMIN, "ADMIN", {"description": "Umožňuje provádět obvyklé administrátorské činnosti"}),
                (UserPermission.API, "API", {"description": "Umožňuje přistupovat k zabezpečeným API endpointům, vytvářet a deaktivovat osobní API klíče"}),
            ],
            coerce=int,
            widget=ListWidget(prefix_label=False),
            option_widget=CheckboxInput())
    submit = SubmitField('Potvrdit')