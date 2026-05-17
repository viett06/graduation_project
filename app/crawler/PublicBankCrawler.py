from app.crawler.BankCrawler import BankCrawler


class PublicBankCrawler(BankCrawler):
    BANK_CODE = "PUBLIC"
    URL = "https://webgia.com/lai-suat/publicbank/"