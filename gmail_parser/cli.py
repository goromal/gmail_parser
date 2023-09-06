import click

from gmail_parser.defaults import GmailParserDefaults as GPD
from gmail_parser.corpus import GMailCorpus

@click.group()
@click.pass_context
@click.option(
    "--gmail-secrets-json",
    "gmail_secrets_json",
    type=click.Path(exists=True),
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
    "--enable-logging",
    "enable_logging",
    type=bool,
    default=GPD.ENABLE_LOGGING,
    show_default=True,
    help="Whether to enable logging.",
)
def cli(ctx: click.Context, gmail_secrets_json, gmail_refresh_file, enable_logging):
    """Manage GMail."""
    ctx.obj = GMailCorpus("andrew.torgesen@gmail.com", gmail_secrets_json=gmail_secrets_json, gmail_refresh_file=gmail_refresh_file, enable_logging=enable_logging)

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
    inbox = ctx.obj.Inbox(num_messages)
    inbox.clean()

def main():
    cli()

if __name__ == "__main__":
    main()
