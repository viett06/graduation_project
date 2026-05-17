from app.crawler.BankCrawler import BankCrawler


class VietTinBankCrawler(BankCrawler):
    BANK_CODE = "CTG"
    URL = "https://webgia.com/lai-suat/vietinbank/"
