import logging
import os

# Path Constants
BASE_DIR = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
TOKEN = os.path.join(BASE_DIR, 'token.dat')
DATABASE = os.path.join(BASE_DIR, 'database.db')

# Other constants
LOGGING_LEVEL = logging.DEBUG
