import argparse
import json


def create_parser():
    description = 'The script loads addresses to the Elastic store'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('-f',
                        '--file',
                        metavar='{file path}',
                        help=(
                            'path to JSON file to load, '
                            'default: downloads/addresses.json'
                        ),
                        default='downloads/addresses.json'
                        )

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    with open(args.file, 'r', encoding="UTF-8") as file:
        menu = json.load(file)
        print(menu)


if __name__ == '__main__':
    main()
