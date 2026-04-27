from app.crawler.BankCrawler import BankCrawler


class OCBCrawler(BankCrawler):
    BANK_CODE = "OCB"
    URL = "https://webgia.com/lai-suat/ocb/"