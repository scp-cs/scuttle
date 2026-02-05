import os
from logging import error
from flask import render_template_string
from typing import Any
from jinja2.exceptions import TemplateError
from werkzeug.routing import BuildError
from flask import current_app

class FrameworkError(RuntimeError):
    pass

def render_template_file(file: str | bytes | os.PathLike, **context: Any) -> str | None:
    try:
        with open(file, 'r', encoding="utf-8") as template:
            template_str = template.read()
            with current_app.app_context():
                return render_template_string(template_str, **context)
    except TemplateError as e:
        error(f"Error rendering template: {str(e)}")
        return None
    except BuildError as e:
        # TODO: Change the error message here
        error(f"Failed to build menu: Invalid handler ({str(e)})")
    except Exception as e:
        error(f"Failed to open template file {file}: {str(e)}")
        return None