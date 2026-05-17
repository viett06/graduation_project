from app.crawler.BankCrawler import BankCrawler


class VietCapitalBankCrawler(BankCrawler):
    BANK_CODE = "VCCB"
    URL = "https://webgia.com/lai-suat/vietcapitalbank/"
