import functools
from textwrap import dedent
from typing import Dict, List

from environs import Env
from more_itertools import chunked
from redis import Redis
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, ParseMode,
                      Update)
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, Filters, MessageHandler, Updater)

from elastic_api import ElasticConnection


def get_chunked_products(elastic_connection: ElasticConnection) -> List:
    products = [
        {'name': product['attributes']['name'], 'id': product['id']}
        for product in elastic_connection.get_products()['data']
    ]
    chunk_size = 8
    return list(chunked(products, chunk_size))


def get_menu_text():
    return '<b>Меню:</b>'


def get_menu_reply_markup(
    chunked_products: List,
    chunk_index: int
) -> InlineKeyboardMarkup:

    keyboard = []
    if chunked_products:
        for product in chunked_products[chunk_index]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        product['name'],
                        callback_data=product["id"]
                    )
                ]
            )
        chunkes_number = len(chunked_products)
        pagination_buttons = []
        if chunk_index > 0:
            callback_data = f'pagination: {chunk_index - 1}'
            pagination_buttons.append(
                InlineKeyboardButton(text='<<', callback_data=callback_data)
            )
        if chunkes_number-1 > chunk_index:
            callback_data = f'pagination: {chunk_index + 1}'
            pagination_buttons.append(
                InlineKeyboardButton(text='>>', callback_data=callback_data)
            )
        if pagination_buttons:
            keyboard.append(pagination_buttons)
    keyboard.append(
        [InlineKeyboardButton(text='Корзина', callback_data='Cart')]
    )
    return InlineKeyboardMarkup(keyboard)


def get_cart_text(cart: Dict, cart_items: Dict) -> str:
    cart_text = '<b>Ваша корзина:</b>\n\n'
    total = cart["data"]["meta"]["display_price"]["with_tax"]["formatted"]

    for cart_item in cart_items['data']:
        quantity = cart_item['quantity']
        display_price = cart_item['meta']['display_price']
        price_with_tax = display_price['with_tax']
        product_text = dedent(
            f'''\
            <em>{cart_item['name']}</em>
            {cart_item['description']}
            {price_with_tax['unit']['formatted']} за шт.
            <em>{quantity} шт. за {price_with_tax['value']['formatted']}</em>

            '''
        )
        cart_text += product_text

    return f'{cart_text} <b>ИТОГО: {total}</b>'


def get_cart_reply_markup(cart_items: Dict) -> InlineKeyboardMarkup:
    keyboard = []
    if cart_items['data']:
        keyboard.append(
            [InlineKeyboardButton(text='Оплатить', callback_data='Pay')]
        )

        for cart_item in cart_items['data']:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"Убрать {cart_item['name']} из корзины",
                        callback_data=cart_item['id']
                    )
                ]
            )

    keyboard.append(
        [InlineKeyboardButton(text='В меню', callback_data='To menu')]
    )
    return InlineKeyboardMarkup(keyboard)


def start(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    chunked_products = get_chunked_products(elastic_connection)
    reply_markup = get_menu_reply_markup(chunked_products, 0)
    update.message.reply_text(
        get_menu_text(),
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    return 'HANDLE_MENU'


def handle_menu(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    query = update.callback_query
    if not query:
        return 'HANDLE_MENU'
    # CallbackQueries need to be answered,
    # even if no notification to the user is needed
    # Some clients may have trouble otherwise.
    # See https://core.telegram.org/bots/api#callbackquery
    query.answer()
    chat_id = query.from_user.id

    if query.data == 'Cart':
        cart = elastic_connection.get_cart(cart_id=chat_id)
        cart_items = elastic_connection.get_cart_items(cart_id=chat_id)
        cart_text = get_cart_text(cart=cart, cart_items=cart_items)
        reply_markup = get_cart_reply_markup(cart_items=cart_items)
        query.message.edit_text(
            text=cart_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return 'HANDLE_CART'

    if query.data.startswith('pagination: '):
        chunked_products = get_chunked_products(elastic_connection)
        chunk_index = int(query.data.replace('pagination: ', ''))
        chunk_index = min(chunk_index, len(chunked_products) - 1)
        reply_markup = get_menu_reply_markup(
            chunked_products=chunked_products,
            chunk_index=chunk_index
        )
        query.message.edit_text(
            text=get_menu_text(),
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return 'HANDLE_MENU'

    product_id = query.data
    product = elastic_connection.get_product(product_id)["data"]
    main_image_id = product['relationships']['main_image']['data']['id']
    image_link = elastic_connection.get_file_link(main_image_id)
    price = product["attributes"]["price"]["RUB"]["amount"]
    formatted_price = '{:.2f}'.format(price)
    caption = (
        f'<b>{product["attributes"]["name"]}</b>\n\n'
        f'<em>{formatted_price} руб. за шт.</em>\n\n'
        f'{product["attributes"]["description"]}'
    )

    adding_button = InlineKeyboardButton(
        text='Добавить в корзину',
        callback_data=product_id
    )
    keyboard = [
        [adding_button],
        [InlineKeyboardButton(text='Корзина', callback_data='Cart')],
        [InlineKeyboardButton('Назад', callback_data='Back')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_photo(
        chat_id=chat_id,
        photo=image_link,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    context.bot.delete_message(
        chat_id=chat_id,
        message_id=query.message.message_id
    )

    return 'HANDLE_DESCRIPTION'


def handle_description(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    query = update.callback_query
    if not query:
        return 'HANDLE_DESCRIPTION'

    chat_id = query.from_user.id
    if query.data == 'Back':
        query.answer()
        chunked_products = get_chunked_products(elastic_connection)
        reply_markup = get_menu_reply_markup(chunked_products, 0)
        context.bot.send_message(
            chat_id=chat_id,
            text=get_menu_text(),
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        context.bot.delete_message(
            chat_id=chat_id,
            message_id=query.message.message_id
        )
        return 'HANDLE_MENU'

    if query.data == 'Cart':
        query.answer()
        cart = elastic_connection.get_cart(cart_id=chat_id)
        cart_items = elastic_connection.get_cart_items(cart_id=chat_id)
        cart_text = get_cart_text(cart=cart, cart_items=cart_items)
        reply_markup = get_cart_reply_markup(cart_items=cart_items)
        context.bot.send_message(
            chat_id=chat_id,
            text=cart_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        context.bot.delete_message(
            chat_id=chat_id,
            message_id=query.message.message_id
        )
        return 'HANDLE_CART'

    product_id = query.data
    elastic_connection.add_product_to_cart(
        cart_id=chat_id,
        product_id=product_id,
        quantity=1
    )
    query.answer(
        text='Товар был добавлен в корзину'
    )

    return 'HANDLE_DESCRIPTION'


def handle_cart(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    query = update.callback_query
    if not query:
        return 'HANDLE_CART'
    query.answer()
    chat_id = query.from_user.id
    if query.data == 'To menu':
        menu_text = get_menu_text()
        chunked_products = get_chunked_products(elastic_connection)
        reply_markup = get_menu_reply_markup(chunked_products, 0)
        query.message.edit_text(
            text=menu_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        return 'HANDLE_MENU'

    if query.data == 'Pay':
        text = 'Send your email:'
        reply_markup = InlineKeyboardMarkup([])
        query.message.edit_text(text=text, reply_markup=reply_markup)

        return 'WAITING_EMAIL'

    elastic_connection.remove_cart_item(cart_id=chat_id, item_id=query.data)
    cart = elastic_connection.get_cart(cart_id=chat_id)
    cart_items = elastic_connection.get_cart_items(cart_id=chat_id)

    query.message.edit_text(
        text=get_cart_text(cart=cart, cart_items=cart_items),
        parse_mode=ParseMode.HTML
    )
    query.message.edit_reply_markup(
        reply_markup=get_cart_reply_markup(cart_items=cart_items)
    )

    return 'HANDLE_CART'


def handle_email(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    name = str(update.message.chat_id)
    email = update.message.text
    elastic_connection.create_customer(name=name, email=email)
    text = 'Спасибо за заказ!\n Мы скоро свяжемся с Вами.'
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton('В меню', callback_data='To menu')]]
    )
    update.message.reply_text(text=text, reply_markup=reply_markup)

    return 'HANDLE_CART'


def handle_users_reply(
        update: Update,
        context: CallbackContext,
        redis_connection: Redis,
        elastic_connection: ElasticConnection) -> None:
    chat_id_prefix = 'pizza_shop_'
    chat_id = f'{chat_id_prefix}{update.message.chat_id}' if update.message\
        else f'{chat_id_prefix}{update.callback_query.from_user.id}'

    if update.message and update.message.text == '/start':
        user_state = 'START'
    else:
        user_state = redis_connection.get(chat_id)

    if not user_state:
        user_state = 'START'

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'WAITING_EMAIL': handle_email,
    }
    state_handler = states_functions[user_state]
    next_state = state_handler(update, context, elastic_connection)
    redis_connection.set(chat_id, next_state)


def main():
    env = Env()
    env.read_env()

    with env.prefixed('REDIS_'):
        redis_connection = Redis(
            host=env('HOST'),
            port=env('PORT'),
            password=env('PASSWORD'),
            decode_responses=True
        )

    with env.prefixed('ELASTIC_'):
        elastic_connection = ElasticConnection(
            client_id=env('PATH_CLIENT_ID'),
            client_secret=env('PATH_CLIENT_SECRET'),
        )

    users_reply_handler = functools.partial(
        handle_users_reply,
        redis_connection=redis_connection,
        elastic_connection=elastic_connection,
    )

    updater = Updater(env('PIZZA_BOT_TOKEN'))
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.text, users_reply_handler))
    dispatcher.add_handler(CommandHandler('start', users_reply_handler))
    dispatcher.add_handler(CallbackQueryHandler(users_reply_handler))
    updater.start_polling()


if __name__ == '__main__':
    main()
