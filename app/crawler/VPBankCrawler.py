from app.crawler.BankCrawler import BankCrawler


class VPBankCrawler(BankCrawler):
    BANK_CODE = "VPB"
    URL = "https://webgia.com/lai-suat/vpbank/"
