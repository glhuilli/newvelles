from datetime import datetime, timedelta
from dateutil.parser import parse
from collections import Counter, defaultdict
import os
import json
import pickle

import click


_PREFIX = 'newvelles_visualization_0.2.1_'


# Function to get the Monday of the week
def get_monday(date):
    return (date - timedelta(days=date.weekday())).date()


def save_data(data, filename):
    # Save data to a pickle file
    with open(filename, 'wb') as f:
        pickle.dump(data, f)


def load_data(filename):
    # Load data from a pickle file
    with open(filename, 'rb') as f:
        return pickle.load(f)


@click.command()
@click.option('--folder_name', default='./data/analysis/dump/newvelles-data-bucket', help='Folder with all files')
@click.option('--output_data', default='./data/analysis/newvelles-data-bucket.pkl', help='Output file')
def main(folder_name, output_data):
    # Initialize an empty dictionary to store data
    grouped_data = {}

    # Get a list of all .json files in the directory
    files = [f for f in os.listdir(folder_name) if os.path.isfile(os.path.join(folder_name, f)) and f.endswith('.json')]

    # Go through each file
    for file in files:
        # Parse the date from the filename
        date_str = file[len(_PREFIX):-5]  # Remove "_PREFIX" and ".json"
        date = parse(date_str)
        year = date.year
        month = date.month
        week_start = get_monday(date)

        # Load data from the file
        with open(os.path.join(folder_name, file), 'r') as f:
            data = json.load(f)

        # Extract titles
        titles = []
        for group1_data in data.values():
            for group2_data in group1_data.values():
                for title, title_data in group2_data.items():
                    titles.append(title)

        # Add titles to the dictionary
        if year not in grouped_data:
            grouped_data[year] = {}
        if month not in grouped_data[year]:
            grouped_data[year][month] = {}
        if week_start not in grouped_data[year][month]:
            grouped_data[year][month][week_start] = []

        grouped_data[year][month][week_start].extend(titles)

    # Save grouped data
    save_data(grouped_data, output_data)

    # Print grouped data
    for year, year_data in grouped_data.items():
        for month, month_data in year_data.items():
            tokens = Counter()
            for week_start, titles in month_data.items():
                print(f"Year: {year}, Month: {month}, Week Start: {week_start} -> Total titles: {len(titles)}")
                for title in titles:
                    tokens.update(title.split(' '))
                print(f'tokens (aprox): {len(tokens)}')


if __name__ == '__main__':
    main()
