
from dataclasses import dataclass
from typing import Callable, Iterator, Tuple
from os import environ
from pathlib import Path

from imap_tools import MailMessage, MailAttachment
from jinja2 import Template

from ids import FileIds

# pylint too few public methods: dataclass
# pylint: disable=R0902
@dataclass
class PrerenderedMailInfo:

    FILENAME_SAFE_SPECIAL_CHARS ="._-+ ,()=?@§€"

    raw: MailMessage
    global_id: int
    """a counter that is incremented for every generated file"""
    file_id: int
    """a counter that is incremented for every generated file of the same type (e.g. body text, headers, attachments, custom)"""
    uid: str
    """the IMAP UID of the mail, or a timestamp if the UID is not available"""
    timestamp: int
    filename_safe_subject: str
    filename_safe_date: str
    filename_safe_recipients_list: str
    filename_safe_to_list: str
    filename_safe_cc_list: str
    filename_safe_bcc_list: str

    @staticmethod
    def render(msg: MailMessage, ids: FileIds) -> "PrerenderedMailInfo":

        to_list = ",".join(msg.to) if msg.to is not None else ""
        cc_list = ",".join(msg.cc) if msg.cc is not None else ""
        bcc_list = ",".join(msg.bcc) if msg.bcc is not None else ""
        recipients_list = ",".join(filter(lambda s: s != "", [to_list, cc_list, bcc_list]))

        return PrerenderedMailInfo(
            raw=msg,
            global_id=ids.global_id,
            file_id=ids.file_specific_id,
            uid=msg.uid if msg.uid is not None else str(int(msg.date.timestamp() * 1000)),
            timestamp=int(msg.date.timestamp() * 1000),
            filename_safe_subject=PrerenderedMailInfo.make_filename_safe(msg.subject, "no_subject"),
            filename_safe_date=msg.date.strftime("%Y-%m-%dT%H-%M-%S-%f"),
            filename_safe_recipients_list=PrerenderedMailInfo.make_filename_safe(recipients_list, "no_recipients"),
            filename_safe_to_list=PrerenderedMailInfo.make_filename_safe(to_list, "no_to"),
            filename_safe_cc_list=PrerenderedMailInfo.make_filename_safe(cc_list, "no_cc"),
            filename_safe_bcc_list=PrerenderedMailInfo.make_filename_safe(bcc_list, "no_bcc")
        )

    @staticmethod
    def make_filename_safe(s: str, default: str) -> str:
        """We explicitly do not allow '/' (slashes) here to prevent path-traversal"""
        if s == "":
            return default
        return "".join(c if c.isalnum() or c in PrerenderedMailInfo.FILENAME_SAFE_SPECIAL_CHARS else "_" for c in s)

@dataclass
class PrerenderedAttachmentInfo:

    mail: PrerenderedMailInfo
    raw: MailAttachment
    full_filename: str
    base_filename: str # without extension
    extension: str
    actual_size: int
    size: int
    filename_safe_content_id: str
    filename_safe_content_type: str
    filename_safe_content_disposition: str

    @staticmethod
    def render(msg: MailMessage, attachment: MailAttachment, ids: FileIds) -> "PrerenderedAttachmentInfo":
        mail = PrerenderedMailInfo.render(msg, ids)

        safe_filename = PrerenderedMailInfo.make_filename_safe(attachment.filename, "no_filename")

        return PrerenderedAttachmentInfo(
            mail=mail,
            raw=attachment,
            full_filename=safe_filename,
            base_filename=safe_filename.rsplit(".", 1)[0] if "." in safe_filename else safe_filename,
            extension=safe_filename.rsplit(".", 1)[1] if "." in safe_filename else "",
            actual_size=len(attachment.payload),
            size=attachment.size,
            filename_safe_content_id=PrerenderedMailInfo.make_filename_safe(attachment.content_id, "no_content_id"),
            filename_safe_content_type=PrerenderedMailInfo.make_filename_safe(attachment.content_type, "no_content_type"),
            filename_safe_content_disposition=PrerenderedMailInfo.make_filename_safe(attachment.content_disposition, "no_content_disposition")
        )

@dataclass
class RenderedFile:
    filename: str
    content: bytes
    info: PrerenderedMailInfo | PrerenderedAttachmentInfo

    def __init__(self, filename: str, content: bytes, info: PrerenderedMailInfo | PrerenderedAttachmentInfo):
        self.filename = filename
        self.content = content
        self.info = info

class MailRenderer:
    _headers_filename: Template
    _body_text_filename: Template
    _body_html_filename: Template
    _attachment_filename: Template
    _custom_filename: Template
    _custom: Template
    _log: Template

    def __init__(self, base_dir: str):
        self._headers_filename = MailRenderer._load_template(base_dir, "headers_filename")
        self._body_text_filename = MailRenderer._load_template(base_dir, "body_text_filename")
        self._body_html_filename = MailRenderer._load_template(base_dir, "body_html_filename")
        self._attachment_filename = MailRenderer._load_template(base_dir, "attachment_filename")
        self._custom_filename = MailRenderer._load_template(base_dir, "custom_filename")
        self._custom = MailRenderer._load_template(base_dir, "custom")
        self._log = MailRenderer._load_template(base_dir, "log")

    @staticmethod
    def _load_template(base_dir: str, name: str) -> Template:
        p = Path(base_dir , name + ".jinja")
        e = "template_" + name.lower()

        if e in environ:
            return Template(environ[e])

        with open(p, "r", encoding="utf-8") as f:
            return Template(f.read())

    @staticmethod
    def _make_oneline(s: str) -> str:
        s = s.strip()
        return " ".join(s.splitlines())

    def render_headers_filename(self, msg: MailMessage|PrerenderedMailInfo, ids: FileIds) -> str:
        info = PrerenderedMailInfo.render(msg, ids) if not isinstance(msg, PrerenderedMailInfo) else msg
        out = self._headers_filename.render({**info.__dict__})
        out = MailRenderer._make_oneline(out)
        return out

    def render_body_text_filename(self, msg: MailMessage|PrerenderedMailInfo, ids: FileIds) -> str:
        info = PrerenderedMailInfo.render(msg, ids) if not isinstance(msg, PrerenderedMailInfo) else msg
        out = self._body_text_filename.render({**info.__dict__})
        out = MailRenderer._make_oneline(out)
        return out

    def render_body_html_filename(self, msg: MailMessage|PrerenderedMailInfo, ids: FileIds) -> str:
        info = PrerenderedMailInfo.render(msg, ids) if not isinstance(msg, PrerenderedMailInfo) else msg
        out = self._body_html_filename.render({**info.__dict__})
        out = MailRenderer._make_oneline(out)
        return out

    def render_attachment_filenames(self, msg: MailMessage, ids: FileIds) -> Iterator[str]:
        for a in msg.attachments:
            yield self.render_attachment_filename((msg, a), ids)

    def render_attachment_filename(self, msg: Tuple[MailMessage, MailAttachment] | PrerenderedAttachmentInfo, ids: FileIds) -> str:
        info = PrerenderedAttachmentInfo.render(msg[0], msg[1], ids) if not isinstance(msg, PrerenderedAttachmentInfo) else msg
        out = self._attachment_filename.render({**info.mail.__dict__, **info.__dict__})
        out = MailRenderer._make_oneline(out)
        return out

    def render_custom_filename(self, msg: MailMessage|PrerenderedMailInfo, ids: FileIds) -> str:
        info = PrerenderedMailInfo.render(msg, ids) if not isinstance(msg, PrerenderedMailInfo) else msg
        out = self._custom_filename.render({**info.__dict__})
        out = MailRenderer._make_oneline(out)
        return out

    def render_custom(self, msg: MailMessage, ids: FileIds) -> RenderedFile:
        info = PrerenderedMailInfo.render(msg, ids)
        filename = self.render_custom_filename(info, ids)
        content = self._custom.render({**info.__dict__}).encode("utf-8")
        return RenderedFile(filename, content, info)

    def render_body_text(self, msg: MailMessage, ids: FileIds) -> RenderedFile:
        info = PrerenderedMailInfo.render(msg, ids)
        filename = self.render_body_text_filename(info, ids)
        return RenderedFile(filename, msg.text.encode("utf-8"), info)

    def render_body_html(self, msg: MailMessage, ids: FileIds) -> RenderedFile:
        info = PrerenderedMailInfo.render(msg, ids)
        filename = self.render_body_html_filename(info, ids)
        return RenderedFile(filename, msg.html.encode("utf-8"), info)

    def render_headers(self, msg: MailMessage, ids: FileIds) -> RenderedFile:
        content = "\n".join(f"{k}: {v}" for k, v in msg.headers.items())
        info = PrerenderedMailInfo.render(msg, ids)
        filename = self.render_headers_filename(info, ids)
        return RenderedFile(filename, content.encode("utf-8"), info)

    def render_attachments(self, msg: MailMessage, ids_generator: Callable[[], FileIds]) -> Iterator[RenderedFile]:
        for a in msg.attachments:
            ids = ids_generator()
            info = PrerenderedAttachmentInfo.render(msg, a, ids)
            filename = self.render_attachment_filename(info, ids)
            yield RenderedFile(filename, a.payload, info)

    def render_log(self, msg: MailMessage, ids: FileIds) -> str:
        info = PrerenderedMailInfo.render(msg, ids)
        out = self._log.render({**info.__dict__})
        return MailRenderer._make_oneline(out)
