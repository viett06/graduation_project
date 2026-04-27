from app.crawler.BankCrawler import BankCrawler


class SHBCrawler(BankCrawler):
    BANK_CODE = "SHB"
    URL = "https://webgia.com/lai-suat/shb/"