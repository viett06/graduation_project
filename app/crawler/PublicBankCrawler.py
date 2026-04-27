from app.crawler.BankCrawler import BankCrawler


class PublicBankCrawler(BankCrawler):
    BANK_CODE = "PUBLICBANK"
    URL = "https://webgia.com/lai-suat/publicbank/"