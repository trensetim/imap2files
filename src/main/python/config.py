from dataclasses import dataclass
from os import environ, getcwd
from typing import Literal, Union

type ProcessedMailDispositionType = Union[
    Literal["delete"],
    Literal["move"],
    Literal["mark_seen"],
    Literal["mark_answered"],
    Literal["mark_flagged"],
    Literal["noop"]
]

# pylint too many instance attributes: this is a dataclass
# pylint: disable=R0902
@dataclass
class Configuration:
    """Configuration for the application"""

    _DEFAULT_MAIL_FOLDER = "INBOX"
    _DEFAULT_MAIL_FILTER = "UNSEEN"
    _DEFAULT_MAIL_IDLE_TIMEOUT_SEC = 1500
    """"25min: Most mail servers have an idle timeout of 30min, so we want to be below that"""
    _DEFAULT_MAIL_DISPOSITION = "mark_seen"
    _DEFAULT_MAIL_DISPOSITION_MOVE_FOLDER = "Trash"
    _DEFAULT_MAIL_PORT = 993 # imap via tls
    _DEFAULT_CACHE_SIZE = 100

    mail_server: str
    mail_port: int
    mail_user: str
    mail_password: str
    mail_folder: str
    mail_filter: str
    """RFC3501/6.4.4 and RFC5032 query string"""
    mail_idle_timeout_sec: int

    mail_disposition: ProcessedMailDispositionType
    mail_disposition_move_folder: str

    cache_start_fresh: bool
    """Ignores the cache database file on boot"""
    cache_path: str
    """Where to store the cache database file to"""
    cache_size: int
    """How many entries to keep in the cache database to reduce duplicate processing of the same mail"""

    templates_base_dir: str
    """Where to load the jinja templates from. The individual file names are hardcoded"""

    output_write_headers: bool
    output_write_html: bool
    output_write_text: bool
    output_write_custom: bool
    output_write_attachments: bool

    output_base_dir: str = "output"

    # pylint too many args: this is a data class
    # pylint: disable=R0913
    # pylint: disable=R0914
    # pylint: disable=R0917
    def __init__(self,
                 mail_server: str,
                 mail_port: int,
                 mail_user: str,
                 mail_password: str,
                 mail_folder: str | None,
                 mail_filter: str | None,
                 mail_idle_timeout_sec: int | None,

                 mail_disposition: ProcessedMailDispositionType | None,
                 mail_disposition_move_folder: str | None,

                 cache_start_fresh: bool,
                 cache_path: str,
                 cache_size: int | None,

                 templates_base_dir: str,

                 output_base_dir: str,
                 output_write_headers: bool,
                 output_write_html: bool,
                 output_write_text: bool,
                 output_write_custom: bool,
                 output_write_attachments: bool,
                 ):
        self.mail_server = mail_server
        self.mail_port = mail_port
        self.mail_user = mail_user
        self.mail_password = mail_password
        self.mail_folder = mail_folder if mail_folder is not None else Configuration._DEFAULT_MAIL_FOLDER
        self.mail_filter = mail_filter if mail_filter is not None else Configuration._DEFAULT_MAIL_FILTER
        self.mail_idle_timeout_sec = mail_idle_timeout_sec if mail_idle_timeout_sec is not None and mail_idle_timeout_sec>0 else Configuration._DEFAULT_MAIL_IDLE_TIMEOUT_SEC

        self.mail_disposition = mail_disposition if mail_disposition is not None else Configuration._DEFAULT_MAIL_DISPOSITION
        self.mail_disposition_move_folder = mail_disposition_move_folder if mail_disposition_move_folder is not None else Configuration._DEFAULT_MAIL_DISPOSITION_MOVE_FOLDER

        self.cache_start_fresh = cache_start_fresh
        self.cache_path = cache_path
        self.cache_size = cache_size if cache_size is not None and cache_size > 0 else Configuration._DEFAULT_CACHE_SIZE

        self.templates_base_dir = templates_base_dir

        self.output_base_dir = output_base_dir
        self.output_write_headers = output_write_headers
        self.output_write_html = output_write_html
        self.output_write_text = output_write_text
        self.output_write_custom = output_write_custom
        self.output_write_attachments = output_write_attachments

    @staticmethod
    def from_env():
        """Create a Configuration object from environment variables"""
        workdir = environ.get("workdir", getcwd())
        enabled_writers = environ.get("output_write", "all").lower()

        return Configuration(
            mail_server=environ["mail_server"],
            mail_port=int(environ.get("mail_port", str(Configuration._DEFAULT_MAIL_PORT))),
            mail_user=environ["mail_user"],
            mail_password=environ["mail_password"],
            mail_folder=environ.get("mail_folder", "INBOX"),
            mail_filter=environ.get("mail_filter", Configuration._DEFAULT_MAIL_FILTER),
            mail_idle_timeout_sec=int(environ.get("mail_idle_timeout_sec", str(Configuration._DEFAULT_MAIL_IDLE_TIMEOUT_SEC))),

            mail_disposition=environ.get("mail_disposition", Configuration._DEFAULT_MAIL_DISPOSITION).lower(),
            mail_disposition_move_folder=environ.get("mail_disposition_move_folder", Configuration._DEFAULT_MAIL_DISPOSITION_MOVE_FOLDER),

            cache_start_fresh=(environ.get("cache_start_fresh", "0").lower() in ["1", "yes", "true"]) or environ.get("cache_start_fresh", "") == "",
            cache_path=environ.get("cache_path", f"{workdir}/imap2files.cachedb"),
            cache_size=int(environ.get("cache_size", str(Configuration._DEFAULT_CACHE_SIZE))),

            templates_base_dir=environ.get("templates_base_dir", f"{workdir}/templates"),

            output_base_dir=environ.get("output_base_dir", f"{workdir}/output"),
            output_write_headers=(("headers" in enabled_writers) or enabled_writers == "all"),
            output_write_html=(("html" in enabled_writers) or enabled_writers == "all"),
            output_write_text=(("text" in enabled_writers) or enabled_writers == "all"),
            output_write_custom=(("custom" in enabled_writers) or enabled_writers == "all"),
            output_write_attachments=(("attachments" in enabled_writers) or enabled_writers == "all"),
        )
