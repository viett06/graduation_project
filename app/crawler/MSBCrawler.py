from app.crawler.BankCrawler import BankCrawler


class MSBCrawler(BankCrawler):
    BANK_CODE = "MSB"
    URL = "https://webgia.com/lai-suat/maritimebank/"