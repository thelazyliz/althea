import os
from modules.Exceptions import MissingEnvVar

# Loads secrets from env var
CONSUMER_KEY=os.getenv("CONSUMER_KEY",None)
CONSUMER_SECRET=os.getenv("CONSUMER_SECRET",None)
ACCESS_KEY=os.getenv("ACCESS_KEY",None)
ACCESS_SECRET=os.getenv("ACCESS_SECRET",None)
ALTHEA_TOKEN=os.getenv("ALTHEA_TOKEN",None)
CMC_API_KEY=os.getenv("CMC_API_KEY",None)

TG_CHATS = [i for i in os.environ.get("TG_CHATS").split(",")]

# Raises exception once any env var is missing
if not CONSUMER_KEY or CONSUMER_KEY.strip()=='':
    raise MissingEnvVar("Missing CONSUMER_KEY!")
if not CONSUMER_SECRET or CONSUMER_SECRET.strip()=='':
    raise MissingEnvVar("Missing CONSUMER_SECRET!")
if not ACCESS_KEY or ACCESS_KEY.strip()=='':
    raise MissingEnvVar("Missing ACCESS_KEY!")
if not ACCESS_SECRET or ACCESS_SECRET.strip()=='':
    raise MissingEnvVar("Missing ACCESS_SECRET!")
if not ALTHEA_TOKEN or ALTHEA_TOKEN.strip()=='':
    raise MissingEnvVar("Missing ALTHEA_TOKEN!")
if not CMC_API_KEY or CMC_API_KEY.strip()=='':
    raise MissingEnvVar("Missing CMC_API_KEY!")
if not TG_CHATS or len(TG_CHATS) == 0 :
    raise MissingEnvVar("Missing TG_CHATS!")
