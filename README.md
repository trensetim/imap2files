A small tool that streams incoming mails into local files.

# Configuration
The application is configured via environment variables. (Most important configurations are **marked**).

| Variable                     | Default Value          | Description                                                                              |
| ---------------------------- | ---------------------- | ---------------------------------------------------------------------------------------- |
| **mail_server**              | required               | Hostname of the IMAP server. Will be validated during TLS handshake.                     |
| mail_port                    | `993`                  | Port number of the IMAP server.                                                          |
| **mail_user**                | required               | Username to login as.                                                                    |
| **mail_password**            | required               | Password to login with.                                                                  |
| **mail_folder**              | `INBOX`                | The folder to search for incoming messages to process                                    |
| mail_filter                  | `UNSEEN`               | IMAP-SEARCH-compliant search query string (depending on the server capabilities)         |
| mail_idle_timeout_sec        | `1500` (25m)           | Longpolling-Interval for live-events. Must be below the server's idle timeout            |
| mail_disposition             | `mark_seen`            | What to do with a mail after processing (see below)                                      |
| mail_disposition_move_folder | `Trash`                | If and only if `mail_disposition==move`                                                  |
| cache_start_fresh            | `0` (off)              | Skip loading the cache database during boot                                              |
| cache_path                   | `./imap2files.cachedb` | (Default: Filename "db" in the current directory) Where to store the cache database file |
| cache_size                   | `100`                  | How many cache entries to keep                                                           |
| templates_base_dir           | `./templates`          | Base directory where to read the jinja templates from keep (see below)                   |
| template_xyz                 | optional               | Override the `{{templates_base_dir}/xyz.jinja` files (see below)                         |
| **output_base_dir**          | `./output`             | Where to write the mail files to                                                         |
| **output_write**             | `all`                  | Which types of output files to produce (see below)                                       |

## Docker Container
When running the application as a docker container, the following default configuration applies:

| Variable           | Value                         |
| ------------------ | ----------------------------- |
| templates_base_dir | /app/templates                |
| output_base_dir    | /app/output                   |
| cache_path         | /app/cache/imap2files.cachedb |

**Important** The container runs as `uid:gid=1000:1000`, so directories that get mounted as cache or output must have appropriate permissions for that user to write to them.
Similarly, the all files in the templates directory must be readable by that user.

## Filtering vs. Disposition
The set of unprocessed (ie. pending) mails is called the "ingest queue".
After one mail was processed, it needs to be removed from the ingest queue.

The ingest queue is formed by filtering all emails in the `mail_folder` by `mail_filter`.
After processing, the `mail_disposition` is applied.
Thus, this disposition **must remove** the mail from the ingest queue, to avoid processing it again.
So usually the user `mail_user` needs some limited write permissions to the source mailbox.

One may avoid needing write permissions by removing the mails from the ingest queue via some other means (eg. using an RFC5032 "YOUNGER 60"-filter)
and using `mail_disposition=noop`.

## Idempotancy Requirements
While the combination of a "cache" and `mail_disposition` try to reduce the amount of duplicate processing of mails, **it is not guaranteed that mails are processed only once**. In fact, the guarantee is more "**at least once**".

Some edge-cases are:
- the app gets killed before updating it's cache database
- the app gets killed before executing the `mail_disposition`
- the `mail_filter` does not exclude already-processed emails effectively (eg. by using a `YOUNGER`-filter)
- the `mail_filter`-vs-`mail_disposition` allow overlaps
- multiple replicas of this application are running and all simultaneously process one mail

This means that the target storage must either: allow overwriting already-existing outputs -- or -- ignore such write attempts.
Furthermore, if multiple replicas of this application run in parallel, the target storage must handle concurrent writes atomically.
Also, the `mail_disposition` must be idempotent (all implemented dispositions are already idempotent).

## Filtering
The `mail_filter` must be an [RFC3501 section 6.4.4](https://datatracker.ietf.org/doc/html/rfc3501#section-6.4.4)- or [RFC5032](https://datatracker.ietf.org/doc/html/rfc3501)-compliant IMAP SEARCH string.

Some useful examples are:
- `UNSEEN`
- `FLAGGED`
- `UNSEEN FLAGGED` (both conditions; ie. "AND")
- `KEYWORD some-tag-on-mail`
- `FROM src@example.com`
- `SUBJECT some-contained-phrase`
- `YOUNGER 60` (seconds)
- `FLAGGED YOUNGER 60` (both conditions)

## Configuring the output
There are multiple output files generated per email:
- `headers`: Contains a `key: value\n` mapping of all email headers
- `text`: Contains the plain-text body content
- `html`: Contains the HTML body content
- `attachments/{{ full_filename }}`: Contains the attachment payload of each of these attachments
- `custom`: For custom-formatted output of the mail

All those files are placed in the `output_base_dir`. The relative path within that directory can be modified via the templates (or `template_xyz`) variables.

Which outputs to produce at all can be configured via `output_write=all` or `output_write=headers,text`.
Possible values are
- headers
- text
- html
- custom
- attachments

There are multiple templates that configure the final shape of the output
| Environment Variable         | Filename                  | Description                                                             |
| ---------------------------- | ------------------------- | ----------------------------------------------------------------------- |
| template_custom              | custom.jinja              | File content of the `custom`-output file                                |
| template_custom_filename     | custom_filename.jinja     | Relative path of the `custom`-output file within `output_base_dir`      |
| template_body_text_filename  | body_text_filename.jinja  | Relative path of the `text`-output file within `output_base_dir`        |
| template_body_html_filename  | body_html_filename.jinja  | Relative path of the `html`-output file within `output_base_dir`        |
| template_headers_filename    | headers_filename.jinja    | Relative path of the `headers`-output file within `output_base_dir`     |
| template_attachment_filename | attachment_filename.jinja | Relative path of the `attachments`-output file within `output_base_dir` |
| template_log                 | log.jinja                 | How the app logs "processing email xyz ..." to stdout                   |

## Mail Disposition
The possible dispositions are
- `delete`
- `move` ... moves to `mail_disposition_move_folder` (default=`Trash`)
- `mark_seen`
- `mark_answered`
- `mark_flagged`
- `noop` ... No-Operation, ie: do nothing. Useful if the `mail_user` does not have write permissions on the mailbox and something like `mail_filter=YOUNGER 600` is used
