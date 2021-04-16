import click


@click.command()
@click.option('--limit', default=10, help='Top N news')
@click.option('--query', default='', help='Limit news to a particular query')
@click.option('--stats', is_flag=True, help='Add stats for each news article')
def main(limit, query, stats):
    print(f'fetch news...{limit} {query} {stats}')


if __name__ == '__main__':
    main()
