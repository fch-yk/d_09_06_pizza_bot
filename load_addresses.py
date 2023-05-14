import argparse
import json

from environs import Env

from elastic_api import ElasticConnection


def create_parser():
    description = (
        'The script loads entries to the Elastic store Pizzeria flow.'
    )
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        '--file',
        metavar='{file path}',
        help=(
            'path to JSON file to load, '
            'default: upload/addresses.json'
        ),
        default='upload/addresses.json'
    )
    parser.add_argument(
        '--courier_tg_id',
        type=int,
        metavar='{Courier telegram ID}',
        help=('Courier telegram ID '),
        default=0
    )

    return parser


def main():
    env = Env()
    env.read_env()
    with env.prefixed('ELASTIC_'):
        elastic_connection = ElasticConnection(
            client_id=env('PATH_CLIENT_ID'),
            client_secret=env('PATH_CLIENT_SECRET'),
        )
    parser = create_parser()
    args = parser.parse_args()
    with open(args.file, 'r', encoding="UTF-8") as file:
        addresses = json.load(file)

    for address in addresses:
        coordinates = address['coordinates']
        elastic_connection.create_pizzeria(
            address=address['address']['full'],
            alias=address['alias'],
            longitude=float(coordinates['lon']),
            latitude=float(coordinates['lat']),
            courier_tg_id=args.courier_tg_id,
        )


if __name__ == '__main__':
    main()
