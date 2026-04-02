
from pathlib import Path

from imap_tools import MailMessage

from renderer import MailRenderer, RenderedFile
from ids import IdDatabase

class EmailFileWriter:
    _renderer: MailRenderer
    _id_db: IdDatabase
    _out_dir: str

    def __init__(self, out_dir: str, renderer: MailRenderer, id_db: IdDatabase):
        self._out_dir = out_dir
        self._renderer = renderer
        self._id_db = id_db

    def _write(self, rendered_file: RenderedFile):
        out_path = Path(self._out_dir).joinpath(rendered_file.filename)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(rendered_file.content)

    def write_custom(self, msg: MailMessage):
        self._write(self._renderer.render_custom(msg, self._id_db.next_custom()))

    def write_headers(self, msg: MailMessage):
        self._write(self._renderer.render_headers(msg, self._id_db.next_headers()))

    def write_body_text(self, msg: MailMessage):
        self._write(self._renderer.render_body_text(msg, self._id_db.next_body_text()))

    def write_body_html(self, msg: MailMessage):
        self._write(self._renderer.render_body_html(msg, self._id_db.next_body_html()))

    def write_attachments(self, msg: MailMessage):
        for rendered_file in self._renderer.render_attachments(msg, self._id_db.next_attachment):
            self._write(rendered_file)
