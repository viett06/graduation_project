from app.crawler.BankCrawler import BankCrawler


class TPBankCrawler(BankCrawler):
    BANK_CODE = "TPB"
    URL = "https://webgia.com/lai-suat/tpbank/"
