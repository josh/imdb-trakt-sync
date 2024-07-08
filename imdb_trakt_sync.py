import click


@click.command()
@click.option(
    "--imdb-watchlist-url",
    required=True,
    envvar="IMDB_WATCHLIST_URL",
)
def main(imdb_watchlist_url: str) -> None:
    click.echo(imdb_watchlist_url)


if __name__ == "__main__":
    main()
