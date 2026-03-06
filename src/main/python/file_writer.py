
from pathlib import Path

from imap_tools import MailMessage

from renderer import MailRenderer, RenderedFile

class EmailFileWriter:
    _renderer: MailRenderer
    _out_dir: str

    def __init__(self, out_dir: str, renderer: MailRenderer):
        self._out_dir = out_dir
        self._renderer = renderer

    def _write(self, rendered_file: RenderedFile):
        out_path = Path(self._out_dir).joinpath(rendered_file.filename)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(rendered_file.content)

    def write_custom(self, msg: MailMessage):
        self._write(self._renderer.render_custom(msg))

    def write_headers(self, msg: MailMessage):
        self._write(self._renderer.render_headers(msg))

    def write_body_text(self, msg: MailMessage):
        self._write(self._renderer.render_body_text(msg))

    def write_body_html(self, msg: MailMessage):
        self._write(self._renderer.render_body_html(msg))

    def write_attachments(self, msg: MailMessage):
        for rendered_file in self._renderer.render_attachments(msg):
            self._write(rendered_file)
