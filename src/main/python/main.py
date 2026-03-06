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
        msg.delete()
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
    return MailBox(CONFIGURATION.mail_server, timeout=5).login(CONFIGURATION.mail_user, CONFIGURATION.mail_password)

async def run_idle_cycle(shutdown_event: threading.Event):
    with open_mailbox() as mailbox:
        mailbox.folder.set(CONFIGURATION.mail_folder)
        await fetch(mailbox) # initial catch-up
        while not shutdown_event.is_set():
            mailbox.idle.wait(timeout=CONFIGURATION.mail_idle_timeout_sec)
            # no matter whether we return by timeout or by receiving events:
            # we scan here completely again, because there is a time delay between the last fetch and this cycle's StartIdle()
            # so we need to continuously play catch-up. The "IDLE" is just there to play catch-up faster than the regular scan interval
            await fetch(mailbox)

def test_connect():
    with open_mailbox() as mailbox:
        mailbox.folder.set(CONFIGURATION.mail_folder)

        # test whether we can fetch mails at all
        iterator = mailbox.fetch(limit=1, mark_seen=False, bulk=False)
        for _ in iterator:
            pass # just consume the iterator for test


def register_shutdown_event():
    shutdown_event = threading.Event()
    signal(SIGINT, lambda *_: shutdown_event.set())
    signal(SIGTERM, lambda *_: shutdown_event.set())
    return shutdown_event

async def main():
    shutdown_evt = register_shutdown_event()

    if not CONFIGURATION.cache_start_fresh:
        await CACHE.try_load()

    try:
        test_connect()
        print("Connection to mail server established")
    except Exception as e: # pylint: disable=W0718
        print(f"Failed to connect to mail server: {e}")
        sys.exit(1)

    while not shutdown_evt.is_set():
        await run_idle_cycle(shutdown_evt)

    if shutdown_evt.is_set():
        print("Shutdown")


if __name__ == "__main__":
    asyncio.run(main())
