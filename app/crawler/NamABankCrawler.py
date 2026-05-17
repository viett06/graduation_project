from app.crawler.BankCrawler import BankCrawler


class NamABankCrawler(BankCrawler):
    BANK_CODE = "NAB"
    URL = "https://webgia.com/lai-suat/namabank/"