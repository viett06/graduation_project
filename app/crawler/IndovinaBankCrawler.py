from app.crawler.BankCrawler import BankCrawler


class IndovinaBankCrawler(BankCrawler):
    BANK_CODE = "IVB"
    URL = "https://webgia.com/lai-suat/indovinabank/"