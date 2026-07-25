import click
import os
import sys

from gmail_parser.defaults import GmailParserDefaults as GPD
from gmail_parser.corpus import GMailCorpus


@click.group()
@click.pass_context
@click.option(
    "--gmail-secrets-json",
    "gmail_secrets_json",
    type=click.Path(),
    default=GPD.GMAIL_SECRETS_JSON,
    show_default=True,
    help="GMail client secrets file.",
)
@click.option(
    "--gmail-refresh-file",
    "gmail_refresh_file",
    type=click.Path(),
    default=GPD.GMAIL_REFRESH_FILE,
    show_default=True,
    help="GMail refresh file (if it exists).",
)
@click.option(
    "--gbot-refresh-file",
    "gbot_refresh_file",
    type=click.Path(),
    default=GPD.GBOT_REFRESH_FILE,
    show_default=True,
    help="GBot refresh file (if it exists).",
)
@click.option(
    "--journal-refresh-file",
    "journal_refresh_file",
    type=click.Path(),
    default=GPD.JOURNAL_REFRESH_FILE,
    show_default=True,
    help="Journal refresh file (if it exists).",
)
@click.option(
    "--enable-logging",
    "enable_logging",
    type=bool,
    default=GPD.ENABLE_LOGGING,
    show_default=True,
    help="Whether to enable logging.",
)
def cli(
    ctx: click.Context,
    gmail_secrets_json,
    gmail_refresh_file,
    gbot_refresh_file,
    journal_refresh_file,
    enable_logging,
):
    """Manage GMail."""
    try:
        ctx.obj = {
            "gmail": GMailCorpus(
                "andrew.torgesen@gmail.com",
                gmail_secrets_json=gmail_secrets_json,
                gmail_refresh_file=gmail_refresh_file,
                enable_logging=enable_logging,
                headless=True,
            ),
            "gbot": GMailCorpus(
                "goromal.bot@gmail.com",
                gmail_secrets_json=gmail_secrets_json,
                gmail_refresh_file=gbot_refresh_file,
                enable_logging=enable_logging,
                headless=True,
            ),
            "journal": GMailCorpus(
                "goromal.journal@gmail.com",
                gmail_secrets_json=gmail_secrets_json,
                gmail_refresh_file=journal_refresh_file,
                enable_logging=enable_logging,
                headless=True,
            ),
        }
    except Exception as e:
        sys.stderr.write(f"Program error: {e}")
        exit(1)


@cli.command()
@click.pass_context
@click.option(
    "--num-messages",
    "num_messages",
    type=int,
    default=1000,
    show_default=True,
    help="Number of messages to poll before cleaning.",
)
def clean(ctx: click.Context, num_messages):
    """Clean out promotions and social emails."""
    inbox = ctx.obj["gmail"].Inbox(num_messages)
    inbox.clean()


@cli.command()
@click.pass_context
@click.option(
    "--config",
    "config",
    type=click.Path(),
    default=GPD.MAIL_CLEAN_CONFIG,
    show_default=True,
    help="Label->action rules config (pipe-delimited LABEL|ACTION).",
)
@click.option(
    "--archive-root",
    "archive_root",
    type=click.Path(),
    default=GPD.GMAIL_ARCHIVE_ROOT,
    show_default=True,
    help="Directory under which archived emails are written.",
)
@click.option(
    "--num-messages",
    "num_messages",
    type=int,
    default=1000,
    show_default=True,
    help="Number of latest messages to load and process.",
)
def process(ctx: click.Context, config, archive_root, num_messages):
    """Apply label->action rules from CONFIG to the latest N messages.

    Emits one JSON progress event per line to stdout (consumed by the Mail UI),
    then a final {"summary": ...} line."""
    import json
    from gmail_parser.rules import parse_rules
    from gmail_parser.progress import ProgressReporter

    with open(os.path.expanduser(config)) as f:
        rules = parse_rules(f.read())
    reporter = ProgressReporter(sys.stdout)
    summary = ctx.obj["gmail"].process(
        rules, archive_root, num_messages=num_messages, reporter=reporter
    )
    sys.stdout.write(json.dumps({"summary": summary}) + "\n")
    sys.stdout.flush()


@cli.command(name="archive-index")
@click.option(
    "--archive-root",
    "archive_root",
    type=click.Path(),
    default=GPD.GMAIL_ARCHIVE_ROOT,
    show_default=True,
    help="Directory under which archived emails are written.",
)
def archive_index(archive_root):
    """Print the archived-email index as JSON."""
    import json
    from gmail_parser.archive_index import list_archives

    print(json.dumps(list_archives(os.path.expanduser(archive_root))))


@cli.command(name="archive-delete")
@click.option(
    "--archive-root",
    "archive_root",
    type=click.Path(),
    default=GPD.GMAIL_ARCHIVE_ROOT,
    show_default=True,
    help="Directory under which archived emails are written.",
)
@click.argument("label")
@click.argument("message_id")
def archive_delete(archive_root, label, message_id):
    """Permanently delete one archived email by LABEL and MESSAGE_ID."""
    from gmail_parser.archive_index import delete_archive

    delete_archive(os.path.expanduser(archive_root), label, message_id)


@cli.command()
@click.pass_context
@click.argument("recipient")
@click.argument("subject")
@click.argument("body")
def send(ctx: click.Context, recipient, subject, body):
    """Send an email."""
    ctx.obj["gmail"].send(to=recipient, subject=subject, message=body)


@cli.command()
@click.pass_context
@click.argument("recipient")
@click.argument("subject")
@click.argument("body")
def gbot_send(ctx: click.Context, recipient, subject, body):
    """Send an email from GBot."""
    ctx.obj["gbot"].send(to=recipient, subject=subject, message=body)


@cli.command()
@click.pass_context
@click.argument("recipient")
@click.argument("subject")
@click.argument("body")
def journal_send(ctx: click.Context, recipient, subject, body):
    """Send an email from Journal."""
    ctx.obj["journal"].send(to=recipient, subject=subject, message=body)


def main():
    cli()


if __name__ == "__main__":
    main()
