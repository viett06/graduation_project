from app.crawler.BankCrawler import BankCrawler


class VCBBankCrawler(BankCrawler):
    BANK_CODE = "VCB"
    URL = "https://webgia.com/lai-suat/vietcombank/"
