from app.crawler.BankCrawler import BankCrawler


class VCBNeoCrawler(BankCrawler):
    BANK_CODE = "VCBNEO"
    URL = "https://webgia.com/lai-suat/vcbneo/"