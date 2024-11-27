import logging


logger = logging.getLogger("CallbackManager")
logger.setLevel(logging.CRITICAL)

stream = logging.StreamHandler()
logger.addHandler(stream)
