import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from bot import constants
from bot.bot import ContestBot
from bot.models import Base


def load_db(url=constants.DATABASE_URI) -> Engine:
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine


if __name__ == "__main__":
    logger = logging.getLogger(__file__)
    logger.setLevel(constants.LOGGING_LEVEL)

    # noinspection PyArgumentList
    logging.basicConfig(format='[%(asctime)s] [%(levelname)s] [%(funcName)s] %(message)s',
                        handlers=[
                            logging.FileHandler(f"bot.log", encoding='utf-8'),
                            logging.StreamHandler()
                        ])

    initial_extensions = ['bot.cogs.contest']

    engine = load_db()
    bot = ContestBot(engine, description='A assistant for the Photography Lounge\'s monday contests')

    for extension in initial_extensions:
        bot.load_extension(extension)

    logger.info('Starting bot...')
    with open('token.dat', 'r') as file:
        bot.run(file.read(), bot=True, reconnect=True)
