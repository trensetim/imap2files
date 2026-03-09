#!/usr/bin/env python3

import asyncio
import threading
import sys
from signal import SIGINT, SIGTERM, signal

from config import Configuration
from file_writer import EmailFileWriter
from imap_tools import MailBox, MailMessage, MailMessageFlags
from mail_process_cache import MailProcessCache
from renderer import MailRenderer

CONFIGURATION = Configuration.from_env()
CACHE = MailProcessCache(CONFIGURATION.cache_path, CONFIGURATION.cache_size)
RENDERER = MailRenderer(CONFIGURATION.templates_base_dir)
DEBUG_WRITER = EmailFileWriter(CONFIGURATION.output_base_dir, RENDERER)

def consume(msg: MailMessage):
    if CONFIGURATION.output_write_custom:
        DEBUG_WRITER.write_custom(msg)
    if CONFIGURATION.output_write_headers:
        DEBUG_WRITER.write_headers(msg)
    if CONFIGURATION.output_write_text:
        DEBUG_WRITER.write_body_text(msg)
    if CONFIGURATION.output_write_html:
        DEBUG_WRITER.write_body_html(msg)
    if CONFIGURATION.output_write_attachments:
        DEBUG_WRITER.write_attachments(msg)

def dispose(mailbox: MailBox, msg: MailMessage):
    if CONFIGURATION.mail_disposition == "delete":
        mailbox.delete([msg.uid])
    elif CONFIGURATION.mail_disposition == "move":
        mailbox.move([msg.uid], CONFIGURATION.mail_disposition_move_folder)
    elif CONFIGURATION.mail_disposition == "mark_seen":
        mailbox.flag([msg.uid], MailMessageFlags.SEEN, True)
    elif CONFIGURATION.mail_disposition == "mark_answered":
        mailbox.flag([msg.uid], MailMessageFlags.ANSWERED, True)
    elif CONFIGURATION.mail_disposition == "mark_flagged":
        mailbox.flag([msg.uid], MailMessageFlags.FLAGGED, True)
    elif CONFIGURATION.mail_disposition == "noop":
        pass
    else:
        raise ValueError(f"Invalid mail disposition: {CONFIGURATION.mail_disposition}")

async def fetch(mailbox: MailBox):
    messages = mailbox.fetch(criteria=CONFIGURATION.mail_filter, mark_seen=False, bulk=False)
    for msg in messages:
        if not CACHE.has(msg):
            print(RENDERER.render_log(msg))
            consume(msg)
            dispose(mailbox, msg)
            await CACHE.add(msg)

def open_mailbox():
    return MailBox(CONFIGURATION.mail_server, timeout=CONFIGURATION.mail_connect_timeout_sec).login(CONFIGURATION.mail_user, CONFIGURATION.mail_password)

async def run_idle_cycle():
    with open_mailbox() as mailbox:
        mailbox.folder.set(CONFIGURATION.mail_folder)

        # initial catch-up: Since the last idle cycle there might have been new mails
        await fetch(mailbox)

        # Wait for the immediate next event: in high-throughput mailboxes this would be a little inefficient
        # (ie. not waiting for multiple events and then do batch processing).
        # but e-mail inherently is not designed as a high-throughput system anyways, so we expect not more than one event per idle cycle anyways.
        mailbox.idle.wait(timeout=CONFIGURATION.mail_idle_timeout_sec)

        # Drop return value: no matter whether we return by timeout or by receiving events:
        # we scan here completely again, because there is a time delay between receiving the event and fetching,
        # so we need to continuously play catch-up. The "IDLE" is just there to play catch-up faster than the regular
        # scan interval by the initial catch-up above.
        await fetch(mailbox)

# ======= Startup and shutdown =======

def register_shutdown_event():
    evt = threading.Event()
    signal(SIGINT, lambda *_: evt.set())
    signal(SIGTERM, lambda *_: evt.set())
    return evt

def assert_connectable():
    def try_connect():
        with open_mailbox() as mailbox:
            mailbox.folder.set(CONFIGURATION.mail_folder)

            # test whether we can fetch mails at all
            iterator = mailbox.fetch(limit=1, mark_seen=False, bulk=False)
            for _ in iterator:
                pass # just consume the iterator for test
    try:
        try_connect()
        print("Connection to mail server established")
    except Exception as e: # pylint: disable=W0718
        print(f"Failed to connect to mail server: {e}")
        sys.exit(1)

async def init_cache():
    if not CONFIGURATION.cache_start_fresh:
        await CACHE.try_load()
        print(f"Loaded {len(CACHE)} cache entries")
    else:
        print("Starting with a fresh cache")

# ======= Main =======

async def main():
    shutdown_event = register_shutdown_event()
    await init_cache()
    assert_connectable() # exit 1 on error

    while not shutdown_event.is_set():
        await run_idle_cycle()

    if shutdown_event.is_set():
        print("Shutdown")


if __name__ == "__main__":
    asyncio.run(main())
