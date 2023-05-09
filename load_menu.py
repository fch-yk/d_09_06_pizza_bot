import argparse
import json

from environs import Env

from elastic_api import ElasticConnection


def create_parser():
    description = (
        'The script loads products to the Elastic store. '
        'If the the hierarchy id and the node id are provided, '
        'the relationships will be created too.'
    )
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument(
        '--file',
        metavar='{file path}',
        help='path to JSON file to load, default: upload/menu.json',
        default='upload/menu.json'
    )
    parser.add_argument(
        '--hierarchy_id',
        metavar='{hierarchy id}',
        help='The hierarchy id in the Elastic store',
    )
    parser.add_argument(
        '--node_id',
        metavar='{node id}',
        help='The node id in the Elastic store',
    )
    parser.add_argument(
        '--price_book_id',
        metavar='{price book id}',
        help=(
            'The price book id in the Elastic store. If this option '
            'is omitted, the prices of the products will not be loaded'
        ),
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
        menu = json.load(file)

    products_ids = []
    for product in menu:
        product_creation_response = elastic_connection.create_product(
            name=product['name'],
            sku=str(product['id']),
            description=product['description']
        )
        product_id = product_creation_response['data']['id']
        products_ids.append(product_id)

        image_creation_response = elastic_connection.create_file(
            file_location=product['product_image']['url']
        )
        image_id = image_creation_response['data']['id']

        elastic_connection.create_product_file_relationships(
            product_id=product_id, files_ids=[image_id]
        )
        elastic_connection.create_main_image_relationships(
            product_id=product_id, file_id=image_id
        )
        if not args.price_book_id:
            continue

        elastic_connection.create_product_price(
            price_book_id=args.price_book_id,
            product_sku=product_creation_response['data']['attributes']['sku'],
            currency_code='RUB',
            amount=product['price'] * 100
        )

    if not (args.hierarchy_id and args.node_id):
        return

    elastic_connection.create_products_relationships(
        hierarchy_id=args.hierarchy_id,
        node_id=args.node_id,
        products_ids=products_ids
    )


if __name__ == '__main__':
    main()
