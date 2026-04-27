import asyncio

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
import logging

from app.crawler.OCBCrawler import OCBCrawler
from app.crawler.AgribankCrawler import AgribankCrawler
from app.crawler.BIDVCrawler import BIDVCrawler
from app.crawler.HLBankCrawler import HongLeongCrawler
from app.crawler.MSBCrawler import MSBCrawler
from app.crawler.PublicBankCrawler import PublicBankCrawler
from app.crawler.SCBCrawler import SCBCrawler
from app.crawler.SHBCrawler import SHBCrawler
from app.crawler.TPBankCrawler import TPBankCrawler
from app.crawler.VCBNeoBankCrawler import VCBNeoBankCrawler
from app.crawler.VietCapitalBankCrawler import VietComBankCrawler
from app.models.interestRate import InterestRate
from app.models.bank import Bank
logger = logging.getLogger(__name__)


class CrawlerService:
    def __init__(self, db: Session):
        self.db = db
        self._rate_svc = None
        self._audit_svc = None

    @property
    def audit_svc(self):
        if not self._audit_svc:
            from app.service.auditLogService import AuditLogService
            self._audit_svc = AuditLogService(self.db)
        return self._audit_svc

    @property
    def rate_svc(self):
        if not self._rate_svc:
            from app.service.interestRateService import InterestRateService
            self._rate_svc = InterestRateService(self.db)
        return self._rate_svc

    def process_crawled_rates(self, bank_id: int, new_rates: List[dict], admin_id: int = 1):
        changes = {"updated": 0, "created": 0}

        current_rates_map = {
            r.term_month: r for r in self.db.query(InterestRate).filter(
                InterestRate.bank_id == bank_id,
                InterestRate.is_current == True
            ).all()
        }

        try:
            for item in new_rates:
                term = item['term_month']
                new_rate_val = Decimal(str(item['rate']))
                existing = current_rates_map.get(term)

                if existing and existing.rate == new_rate_val:
                    continue

                if existing:
                    if existing.rate != new_rate_val:
                        existing.is_current = False
                        existing.updated_at = datetime.now()

                        self._log_rate_change(existing, admin_id)

                        self._create_new_rate_record(bank_id, item, new_rate_val, admin_id)
                        changes["updated"] += 1

                else:
                    self._create_new_rate_record(bank_id, item, new_rate_val, admin_id)
                    changes["created"] += 1

            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing rates for bank_id {bank_id}: {e}")
            raise e
        return changes

    def _create_new_rate_record(self, bank_id, item, rate_val, admin_id):
        new_record = InterestRate(
            bank_id=bank_id,
            term_month=item['term_month'],
            rate=rate_val,
            min_amount=item.get('min_amount', 0),
            max_amount=item.get('max_amount', None),
            effective_date=item.get('effective_date', datetime.now()),
            is_current=True,
            create_by=admin_id
        )
        self.db.add(new_record)

    def _log_rate_change(self, existing, admin_id):

        rate_id = existing.id

        self.rate_svc.delete_interest_rate_and_save_audit_log(admin_id, rate_id)

    async def crawl_and_update(
            self,
            bank_code: Optional[str] = None,
            admin_id: int = 1
    ):


        # if bank_code is None or bank_code.upper() == "WEBGIA":
        #     crawler = WebGiaCrawler(self.db)


        crawler_map = {
            "AGRIBANK": AgribankCrawler,
            "BIDV": BIDVCrawler,
            "HONGLEONG": HongLeongCrawler,
            "MSB": MSBCrawler,
            "OCB": OCBCrawler,
            "PUBLICBANK": PublicBankCrawler,
            "SCB": SCBCrawler,
            "SHB": SHBCrawler,
            "TPBANK": TPBankCrawler,
            "VCBNEOBANK": VCBNeoBankCrawler,
            "VIETCAPITALBANK": VietComBankCrawler
        }

        crawler_class = crawler_map.get(bank_code.upper())

        if not crawler_class:
            return {
                "status": "failed",
                "reason": f"No crawler config for {bank_code}"
            }

        crawler = crawler_class(self.db)

        # Crawl data
        try:
            result = await crawler.crawl()

        except Exception as e:
            logger.exception("Crawler crashed")
            return {
                "status": "failed",
                "reason": str(e)
            }

        if result.get("status") != "parsed":
            return result

        # Normalize output

        rates_data = result.get("rates_data")

        if not rates_data:
            # fallback cho crawler chỉ crawl 1 bank
            if "rates" in result and bank_code:
                rates_data = {
                    bank_code.upper(): result["rates"]
                }
            else:
                return {
                    "status": "failed",
                    "reason": "No rates data returned"
                }

        # Update DB
        total_changes = {}

        for b_code, rates in rates_data.items():

            bank = (
                self.db.query(Bank)
                .filter(Bank.code == b_code.upper())
                .first()
            )

            if not bank:
                logger.warning(f"Bank code {b_code} not found in DB")
                continue

            try:
                changes = self.process_crawled_rates(
                    bank_id = int(bank.id),
                    new_rates=rates,
                    admin_id=admin_id
                )

                total_changes[b_code] = changes

                # notify realtime
                if changes["updated"] > 0 or changes["created"] > 0:
                    await self._notify_update(b_code, changes)
                else:
                    logger.info(f"No rate changes for {b_code}")

            except Exception as e:
                logger.exception(f"Update failed for {b_code}")

                total_changes[b_code] = {
                    "status": "failed",
                    "reason": str(e)
                }

        # Return
        return {
            "status": "success",
            "data": total_changes
        }

    async def _notify_update(self, bank_code, changes):
        try:
            from app.core.socket.websocket import manager
            await manager.broadcast_rate_update(bank_code, changes)
        except Exception as e:
            logger.exception("Notify websocket failed")

    async def crawl_all_banks(self, admin_id: int = 1):
        """
        Automatically iterates through the list of supported banks
        to trigger the crawling and data update process.
        """
        results = {}

        bank_codes = [
            "AGRIBANK", "BIDV", "HONGLEONG", "MSB", "OCB",
            "PUBLICBANK", "SCB", "SHB", "TPBANK",
            "VCBNEOBANK", "VIETCAPITALBANK"
        ]

        logger.info(f"Starting automated crawl process for {len(bank_codes)} banks.")

        for bank_code in bank_codes:
            try:
                logger.info(f"🔍 Processing: {bank_code}")

                status = await self.crawl_and_update(
                    bank_code=bank_code,
                    admin_id=admin_id
                )

                results[bank_code] = status
                logger.info(f"Successfully updated: {bank_code}")

                # Politeness delay to prevent rate-limiting/IP blocking
                await asyncio.sleep(2)

            except Exception as e:
                # Catch errors for individual banks so the entire loop doesn't fail
                logger.error(f"Error crawling {bank_code}: {str(e)}")
                results[bank_code] = {"status": "failed", "error": str(e)}

                continue

        logger.info("Automated crawl cycle completed.")
        return results