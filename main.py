#!/usr/bin/env python
# pylint: disable=C0116,W0613
import logging

from peewee import BigIntegerField, CharField, IntegerField, Model, SqliteDatabase
from random import random, randint

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ForceReply
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from telegram.error import BadRequest

from secret import BOT_TOKEN

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

# Database
main_db = SqliteDatabase("./main.db")

resale_percentage = 0.77


class Players(Model):
    # Self
    id = BigIntegerField(unique=True)
    first_name = CharField(null=True)
    pinned_message = BigIntegerField(null=True)

    # Stats
    messages = BigIntegerField(default=0)
    messages_total = BigIntegerField(default=0)

    contacts = BigIntegerField(default=0)
    contacts_state = IntegerField(default=0)
    contacts_total = BigIntegerField(default=0)

    groups = BigIntegerField(default=0)
    groups_state = IntegerField(default=0)
    groups_total = BigIntegerField(default=0)

    channels = BigIntegerField(default=0)
    channels_state = IntegerField(default=0)
    channels_total = BigIntegerField(default=0)

    supergroups = BigIntegerField(default=0)
    supergroups_state = IntegerField(default=0)
    supergroups_total = BigIntegerField(default=0)

    class Meta:
        database = main_db


main_db.connect()
main_db.create_tables([Players])


def get_or_create_user(id: int):
    return Players.get_or_create(id=id)


def get_stats(id: int):
    user, _ = get_or_create_user(id)

    return {
        "messages": {
            "unlocked": True,
            "price": None,
            "quantity": user.messages,
            "total": user.messages_total,
        },
        "contacts": {
            "unlock_at": {"messages": 10},
            "unlocked": user.contacts_state,
            "price": {"messages": 10},
            "quantity": user.contacts,
            "total": user.contacts_total,
        },
        "groups": {
            "unlock_at": {"messages": 100, "contacts": 4},
            "unlocked": user.groups_state,
            "price": {"messages": 100, "contacts": 4},
            "quantity": user.groups,
            "total": user.groups_total,
        },
        "channels": {
            "unlock_at": {"messages": 1000, "contacts": 16},
            "unlocked": user.channels_state,
            "price": {"messages": 1000, "contacts": 16},
            "quantity": user.channels,
            "total": user.channels_total,
        },
        "supergroups": {
            "unlock_at": {"messages": 10000, "contacts": 256, "groups": 1},
            "unlocked": user.supergroups_state,
            "price": {"messages": 10000, "contacts": 256, "groups": 1},
            "quantity": user.supergroups,
            "total": user.supergroups_total,
        },
    }


def update_pinned_message(id: int, context: CallbackContext):
    user, _ = get_or_create_user(id)

    message = "– Messages: {}".format(user.messages)
    if user.contacts_state:
        message += "\n– Contacts: {}".format(user.contacts)
    if user.groups_state:
        message += "\n– Groups: {}".format(user.groups)
    if user.channels_state:
        message += "\n– Channels: {}".format(user.channels)
    if user.supergroups_state:
        message += "\n– Supergroups: {}".format(user.supergroups)

    try:
        context.bot.edit_message_text(message, user.id, user.pinned_message)
    except BadRequest:  # Not edit to be done
        return


def check_achievements(id: int, context: CallbackContext):
    user, _ = get_or_create_user(id)
    stats = get_stats(id)

    for item, attrs in stats.items():  # e.g., "contacts": {"unlock_at", ...}
        if "unlock_at" in attrs and not stats[item]["unlocked"]:
            unlock = True
            for unlock_item, unlock_quantity in attrs["unlock_at"].items():  # e.g., "messages": 10
                if stats[unlock_item]["quantity"] < unlock_quantity:
                    unlock = False
                    break
            if unlock:
                exec("user.{}_state = 1".format(item))  # Worst thing I ever wrote probably, sorry not sorry.
                user.save()
                context.bot.send_message(user.id, "Unlocked {}!".format(item))


def pinned_and_achievements(id: int, context: CallbackContext):
    """
    Because I'm lazy.
    """
    update_pinned_message(id, context)
    check_achievements(id, context)


def start(update: Update, context: CallbackContext) -> None:
    _user = update.effective_user
    user, created = get_or_create_user(_user.id)

    if created:
        user.first_name = _user.first_name
        user.save()
        update.message.reply_text("Welcome, {}!".format(user.first_name))
    else:
        update.message.reply_text("Welcome back, {}!".format(user.first_name))

    update.message.reply_text("== Placeholder for the tutorial ==")

    update.message.reply_text("You're ready to play!")

    update.message.reply_text(
        "Now, I am going to pin your counter to this conversation, so that you can see your progress!")
    counter = update.message.reply_text("Start talking to play!")
    user.pinned_message = counter.message_id
    user.save()

    try:
        context.bot.unpin_chat_message(update.message.chat.id)
    except:
        pass

    context.bot.pin_chat_message(update.message.chat.id, counter.message_id)


def help(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Help!')


def interface(update: Update, context: CallbackContext) -> None:
    _user = update.effective_user
    user, _ = get_or_create_user(_user.id)

    if update.callback_query and update.callback_query.data != "stop":  # Choices
        stats = get_stats(_user.id)
        query = update.callback_query
        query.answer()
        data = query.data

        if data[0] == "c":
            buy_price = stats["contacts"]["price"]["messages"]
            sell_price = int(buy_price * resale_percentage)

            if data[1] == "b":  # Buy
                if data[2:] == "1":
                    user.messages -= buy_price
                    user.contacts += 1
                    user.contacts_total += 1
                elif data[2:] == "10":
                    user.messages -= 10 * buy_price
                    user.contacts += 10
                    user.contacts_total += 10
                else:
                    qt = user.messages // buy_price
                    user.messages -= buy_price * qt
                    user.contacts += qt
                    user.contacts_total += qt
                user.save()
                stats = get_stats(_user.id)
            elif data[1] == "s":  # Sell
                if data[2:] == "1":
                    user.messages += sell_price
                    user.messages_total += sell_price
                    user.contacts -= 1
                elif data[2:] == "10":
                    user.messages -= 10 * sell_price
                    user.messages_total += 10 * sell_price
                    user.contacts -= 10
                else:
                    qt = user.contacts * sell_price
                    user.messages += qt
                    user.messages_total += qt
                    user.contacts -= user.contacts
                user.save()
                stats = get_stats(_user.id)

            message = "**Contacts**\nYou have {} Contacts.\nFind: -{} messages.\nForfeit: +{} messages.".format(
                stats["contacts"]["quantity"], buy_price, sell_price)

            # Select
            buy = []
            if stats["messages"]["quantity"] >= buy_price:
                buy.append(InlineKeyboardButton("Find 1 Contact", callback_data="cb1"))
                if stats["messages"]["quantity"] >= 10 * buy_price:
                    buy.append(InlineKeyboardButton("Find 10 Contacts", callback_data="cb10"))
                buy.append(InlineKeyboardButton("Find Max Contacts", callback_data="cbmax"))

            sell = []
            if stats["contacts"]["quantity"] >= 1:
                sell.append(InlineKeyboardButton("Forfeit 1 Contact", callback_data="cs1"))
                if stats["contacts"]["quantity"] >= 10:
                    sell.append(InlineKeyboardButton("Forfeit 10 Contacts", callback_data="cs10"))
                sell.append(InlineKeyboardButton("Forfeit All Contacts", callback_data="csmax"))

        elif data[0] == "g":
            buy_price = stats["groups"]["price"]
            sell_price = {k: int(v * resale_percentage) for k, v in buy_price.items()}

            if data[1] == "b":  # Buy
                if data[2:] == "1":
                    user.messages -= buy_price["messages"]
                    user.contacts -= buy_price["contacts"]

                    user.groups += 1
                    user.groups_total += 1
                elif data[2:] == "10":
                    user.messages -= 10 * buy_price["messages"]
                    user.contacts -= 10 * buy_price["contacts"]

                    user.groups += 10
                    user.groups_total += 10
                else:
                    qt = min(user.messages // buy_price["messages"], user.messages // buy_price["contacts"])
                    user.messages -= buy_price["messages"] * qt
                    user.contacts -= buy_price["contacts"] * qt

                    user.groups += qt
                    user.groups_total += qt
                user.save()
                stats = get_stats(_user.id)
            elif data[1] == "s":  # Sell
                if data[2:] == "1":
                    user.messages += sell_price["messages"]
                    user.messages_total += sell_price["messages"]
                    user.contacts += sell_price["contacts"]
                    user.contacts_total += sell_price["contacts"]

                    user.groups -= 1
                elif data[2:] == "10":
                    user.messages -= 10 * sell_price["messages"]
                    user.messages_total += 10 * sell_price["messages"]
                    user.contacts -= 10 * sell_price["contacts"]
                    user.contacts_total += 10 * sell_price["contacts"]

                    user.groups -= 10
                else:
                    qt_messages = user.groups * sell_price["messages"]
                    user.messages += qt_messages
                    user.messages_total += qt_messages
                    qt_contacts = user.groups * sell_price["contacts"]
                    user.contacts += qt_contacts
                    user.contacts_total += qt_contacts

                    user.groups -= user.groups
                user.save()
                stats = get_stats(_user.id)

            message = "**Groups**\nYou have {} Groups.\nJoin: -{} messages, -{} contacts.\nLeave: +{} messages, " \
                      "+{} contacts.".format(stats["groups"]["quantity"], buy_price["messages"], buy_price["contacts"],
                                             sell_price["messages"], sell_price["contacts"])

            # Select
            buy = []
            if stats["messages"]["quantity"] >= buy_price["messages"] and stats["contacts"]["quantity"] >= buy_price["contacts"]:
                buy.append(InlineKeyboardButton("Join 1 Group", callback_data="gb1"))
                if stats["messages"]["quantity"] >= 10 * buy_price["messages"] and stats["contacts"]["quantity"] >= 10 * buy_price["contacts"]:
                    buy.append(InlineKeyboardButton("Join 10 Groups", callback_data="gb10"))
                buy.append(InlineKeyboardButton("Join Max Groups", callback_data="gbmax"))

            sell = []
            if stats["groups"]["quantity"] >= 1:
                sell.append(InlineKeyboardButton("Leave 1 Group", callback_data="gs1"))
                if stats["groups"]["quantity"] >= 10:
                    sell.append(InlineKeyboardButton("Leave 10 Groups", callback_data="gs10"))
                sell.append(InlineKeyboardButton("Leave All Groups", callback_data="gsmax"))

        elif data[0] == "h":
            pass
        elif data[0] == "s":
            pass
        else:
            raise ValueError("Invalid argument: {}.".format(data))

        reply_markup = InlineKeyboardMarkup([buy, sell, [InlineKeyboardButton("Back", callback_data="stop")]])

        try:
            query.edit_message_text(message, reply_markup=reply_markup)
        except BadRequest:  # Not edit to be done
            pass

    else:  # Main
        stats = get_stats(_user.id)
        choices = []
        if stats["contacts"]["unlocked"]:
            choices.append(InlineKeyboardButton("Contacts", callback_data="cx"))
        if stats["groups"]["unlocked"]:
            choices.append(InlineKeyboardButton("Groups", callback_data="gx"))
        if stats["channels"]["unlocked"]:
            choices.append(InlineKeyboardButton("Channels", callback_data="hx"))
        if stats["supergroups"]["unlocked"]:
            choices.append(InlineKeyboardButton("Supergroups", callback_data="sx"))

        if choices:
            message = "**Interface**\nSelect what you would like to bargain:"
            reply_markup = InlineKeyboardMarkup([choices])
        else:
            message = "You don't have enough messages for now..."
            reply_markup = None

        if update.callback_query:  # "stop"
            update.callback_query.edit_message_text(message, reply_markup=reply_markup)
        else:
            update.message.reply_text(message, reply_markup=reply_markup)

    pinned_and_achievements(user.id, context)


def stop(update: Update, context: CallbackContext) -> None:
    Players.delete().where(Players.id == update.effective_user.id).execute()
    update.message.reply_text('Stop!')


def answer(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(update.message.text)

    _user = update.effective_user
    user, _ = get_or_create_user(_user.id)
    user.messages += 2
    user.messages_total += 2
    user.save()

    pinned_and_achievements(user.id, context)


def main() -> None:
    # Create the Updater and pass it your bot's token.
    updater = Updater(BOT_TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler(["interface", "buy", "sell", "join", "leave"], interface))
    updater.dispatcher.add_handler(CallbackQueryHandler(interface))
    dispatcher.add_handler(CommandHandler("stop", stop))

    # on non command i.e message - echo the message on Telegram
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, answer))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
