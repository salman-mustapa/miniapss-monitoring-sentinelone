# src/logger.py
import logging
import os

# create folder logs
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# path file log
LOG_ALL = os.path.join(LOG_DIR, "all.log")
LOG_ERROR = os.path.join(LOG_DIR, "error.log")
LOG_SUCCESS = os.path.join(LOG_DIR, "success.log")

# custom level SUCCESS
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

def _success(self, message, *args, **kws):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)
logging.Logger.success = _success

# formatter
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# root logger
logger = logging.getLogger("SentinelOneLogger")

# configure handlers once
def init_logging():
    if logger.handlers:
        return logger  # already initialized

    logger.setLevel(logging.DEBUG)

    # all log
    all_handler = logging.FileHandler(LOG_ALL, encoding='utf-8')
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(formatter)
    logger.addHandler(all_handler)

    # error log
    error_handler = logging.FileHandler(LOG_ERROR, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # success log (custom level)
    success_handler = logging.FileHandler(LOG_SUCCESS, encoding='utf-8')
    success_handler.setLevel(SUCCESS_LEVEL_NUM)
    success_handler.setFormatter(formatter)
    logger.addHandler(success_handler)

    # console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

# convenience getter (some modules import get_logger)
def get_logger():
    return init_logging()

# helper wrappers (optional convenience)
def log_info(msg):
    init_logging().info(msg)

def log_error(msg):
    init_logging().error(msg)

def log_debug(msg):
    init_logging().debug(msg)

def log_warning(msg):
    init_logging().warning(msg)

def log_success(msg):
    init_logging().success(msg)
