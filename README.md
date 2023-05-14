# Pizza shop telegram bot

The project works with the following components:

- The **Telegram shop bot** communicates with customers on the [Telegram](https://telegram.org/) platform;
- The **Redis database** is used to save the current customer state ("in the menu", "in the cart" and so on). Go to [redislabs.com](https://redislabs.com/) to learn more about the Redis platform.
- The **Elastic store** is used as a [CMS](https://en.wikipedia.org/wiki/Content_management_system/); it stores information about products, prices, customers and so on. Go to [elasticpath.dev](https://elasticpath.dev/) to find out more about Elastic Path Commerce Cloud.

## Demo bots

- **Telegram shop bot** demo is [here](https://t.me/yk_fish_bot).

![telegram bot image](screenshots/tg_bot.gif)

## Prerequisites

Python 3.11 is required.

## Installation

- Download the project files.
- It is recommended to use [venv](https://docs.python.org/3/library/venv.html?highlight=venv#module-venv) for project isolation.
- Set up packages:

```bash
pip install -r requirements.txt
```

- Go to [@BotFather](https://t.me/BotFather) and register your **Telegram shop bot**;
  - _Note_: Bots can't initiate conversations with users. You must send a message to your bot first;
- Go to [redislabs.com](https://redislabs.com/) and create your **Redis database**;
- Go to [elasticpath.com](https://euwest.cm.elasticpath.com/):
  - create your **Elastic store**;
  - add a price book;
  - add a catalog;
  - add a hierarchy;
  - add currencies;
  - add products; you can use the `load_menu.py` script to load products from the JSON file (see [Script `load_menu.py`](#script-load_menupy) for more);
  - add a flow `Pizzerias`; you can use the `create_pizzerias_model.py` script,  (see [Script `create_pizzerias_model.py`](#script-create_pizzerias_modelpy) for more);
  - add pizzerias entries; you can use the `load_addresses.py` script to load pizzerias from the JSON file (see [Script `load_addresses.py`](#script-load_addressespy) for more);
  - add latitude and longitude to the `customers` flow; you can use the `add_customer_location.py` script (see [Script `add_customer_location.py`](#script-add_customer_locationpy) for more)
- Set up environmental variables in your operating system or in .env file. The variables are:
  - `FISH_BOT_TOKEN` is your **Telegram shop bot** token from [@BotFather](https://t.me/BotFather) (obligatory);
  - `REDIS_HOST` is a public endpoint for your **Redis database** (obligatory);
  - `REDIS_PASSWORD`is a password for your **Redis database** (obligatory);
  - `REDIS_PORT` is a port for your **Redis database** (obligatory);
  - `ELASTIC_PATH_CLIENT_ID` is the **Elastic store** client ID  (obligatory);
  - `ELASTIC_PATH_CLIENT_SECRET` is the **Elastic store** client secret  (obligatory).

To set up variables in .env file, create it in the root directory of the project and fill it up like this:

```bash
FISH_BOT_TOKEN=replace_me
REDIS_HOST=replace_me
REDIS_PASSWORD=replace_me
REDIS_PORT=13604
ELASTIC_PATH_CLIENT_ID=replace_me
ELASTIC_PATH_CLIENT_SECRET=replace_me
```

## Script `load_menu.py`

The script loads products to the Elastic store. If the the hierarchy id and the node id are provided, the relationships will be created too.

Usage of the `load_menu.py` script:

```bash
python load_menu.py [-h] [--file {file path}] [--hierarchy_id {hierarchy id}] [--node_id {node id}] [--price_book_id {price book id}]
```

Options:

- `-h`, `--help` - show the help message and exit;
- `--file {file path}` - path to JSON file to load, default: upload/menu.json, the example of the file is [here](upload/menu.json);
- `--hierarchy_id {hierarchy id}` - the hierarchy id in the Elastic store;
- `--node_id {node id}` - the node id in the Elastic store;
- `--price_book_id {price book id}` - the price book id in the Elastic store. If this option is omitted, the prices of the products will not be loaded

## Script `create_pizzerias_model.py`

The script creates a flow `Pizzerias` with the following fields:

- `Address` (string);
- `Alias` (string);
- `Longitude` (float);
- `Latitude` (float);
- `Courier telegram ID` (integer);

Run:

```bash
python create_pizzeria_model.py
```

## Script `load_addresses.py`

The script loads entries to the Elastic store `Pizzerias` flow.
Usage of the script:

```bash
python load_addresses.py [-h] [--file {file path}] [--courier_tg_id {Courier telegram ID}]
```

options:

- `-h`, `--help` - show the help message and exit;
- `--file {file path}` - path to the JSON file to load, default: upload/addresses.json, the example of the file is [here](upload/addresses.json);
- `--courier_tg_id` - Courier telegram ID

## Script `add_customer_location.py`

The script extends the customer flow in the Elastic store. It adds the following fields:

- `Longitude` (float);
- `Latitude` (float);

Run:

```bash
python add_customer_location.py
```

## Usage of the Telegram shop bot

- Start your **Telegram shop bot**:

```bash
python tg_bot.py
```

- Go to the bot and start shopping.

## Project goals

The project was created for educational purposes.
It's a lesson for python and web developers at [Devman](https://dvmn.org/).
