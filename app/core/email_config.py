from fastapi_mail import ConnectionConfig
import os
from dotenv import load_dotenv
load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME = "vanviet0611@gmail.com",
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
    MAIL_FROM = "vanviet0611@gmail.com",
    MAIL_PORT = 587,
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True,
    MAIL_FROM_NAME = "Analysis finance System"
)