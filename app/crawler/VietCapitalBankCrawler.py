from app.crawler.BankCrawler import BankCrawler


class VietComBankCrawler(BankCrawler):
    BANK_CODE = "VIETCAPITALBANK"
    URL = "https://webgia.com/lai-suat/vietcapitalbank/"
