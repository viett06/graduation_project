from app.crawler.BankCrawler import BankCrawler


class VCBNeoBankCrawler(BankCrawler):
    BANK_CODE = "VCBNEOBANK"
    URL = "https://webgia.com/lai-suat/vcbneo/"
