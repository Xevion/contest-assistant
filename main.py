import logging

from contest import client, constants

if __name__ == "__main__":
    bot = client.ContestClient()

    logger = logging.getLogger(__file__)
    logger.setLevel(constants.LOGGING_LEVEL)

    logging.basicConfig(format='[%(asctime)s] [%(levelname)s] [%(funcName)s] %(message)s',
                        handlers=[
                            logging.FileHandler(f"bot.log", encoding='utf-8'),
                            logging.StreamHandler()
                        ])

    logger.info('Starting bot.')
    with open('token.dat', 'r') as file:
        bot.run(file.read())
