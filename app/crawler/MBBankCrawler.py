from app.crawler.BankCrawler import BankCrawler


class MBBankCrawler(BankCrawler):
    BANK_CODE = "MB"
    URL = "https://webgia.com/lai-suat/mbbank/"