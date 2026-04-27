from typing import Dict

from fastapi import APIRouter, Depends, BackgroundTasks, Query, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.security.guards import require_roles
from app.core.security.rbac import RoleEnum
from app.crawler.crawler_service import CrawlerService, logger
from app.core.security.dependencies import get_current_active_user
from app.db.session import SessionLocal
from app.models.bank import Bank
from app.models.crawlerLog import CrawlerLog

router = APIRouter()

async def run_crawl_task(bank_code: str, admin_id: int):
    db_gen = get_db()
    db = next(db_gen)
    try:
        service = CrawlerService(db)
        await service.crawl_and_update(bank_code, admin_id)
    except Exception as e:
        logger.error(f"Task failed: {e}")
    finally:
        db.close()

@router.post("/trigger")
async def trigger_crawl(
    background_tasks: BackgroundTasks,
    bank_code: str = Query(None, description="Bank code, None = crawl all"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.MANAGER)),
):
    admin_id = current_user.get("id")

    if bank_code:
        bank = db.query(Bank).filter(Bank.code == bank_code, Bank.status == True).first()
        if not bank:
            raise HTTPException(status_code=404, detail=f"Bank '{bank_code}' not found or inactive")
        background_tasks.add_task(run_crawl_task, bank_code, admin_id)
        return {"message": f"Crawling {bank_code} in background"}
    else:
        banks = db.query(Bank).filter(Bank.status == True).all()
        for bank in banks:
            background_tasks.add_task(run_crawl_task, bank.code, admin_id)
        return {"message": f"Crawling {len(banks)} banks in background"}

@router.get("/status")
async def get_last_crawl_logs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),  # thêm auth nếu cần
):
    logs = db.query(CrawlerLog).order_by(CrawlerLog.created_at.desc()).limit(20).all()
    return logs