from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Session, select

from .db import get_session, init_db
from .models import Client, ContentItem, PostStatus, PublishAttempt, SocialAccount


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Open Social Scheduler 2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "open-social-scheduler-v2"}


@app.get("/api/control-center")
def control_center(session: Session = Depends(get_session)):
    clients = session.exec(select(Client).where(Client.active == True)).all()  # noqa: E712
    items = session.exec(select(ContentItem)).all()
    attempts = session.exec(select(PublishAttempt)).all()

    by_status = {status.value: 0 for status in PostStatus}
    for item in items:
        by_status[item.status.value] = by_status.get(item.status.value, 0) + 1

    failures = [a for a in attempts if a.status.upper() == "FAILED"]
    scheduled = [i for i in items if i.status == PostStatus.scheduled and i.scheduled_at]
    scheduled.sort(key=lambda x: x.scheduled_at or datetime.max)

    next_post = scheduled[0] if scheduled else None
    return {
        "clients_active": len(clients),
        "content_total": len(items),
        "status": by_status,
        "publish_failures": len(failures),
        "next_publication": next_post,
    }


@app.get("/api/clients")
def list_clients(session: Session = Depends(get_session)):
    return session.exec(select(Client).order_by(Client.name)).all()


@app.post("/api/clients", response_model=Client)
def create_client(client: Client, session: Session = Depends(get_session)):
    existing = session.exec(select(Client).where(Client.slug == client.slug)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Client slug already exists")
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@app.get("/api/social-accounts")
def list_social_accounts(session: Session = Depends(get_session)):
    return session.exec(select(SocialAccount)).all()


@app.post("/api/social-accounts", response_model=SocialAccount)
def create_social_account(account: SocialAccount, session: Session = Depends(get_session)):
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@app.get("/api/content")
def list_content(session: Session = Depends(get_session)):
    return session.exec(select(ContentItem).order_by(ContentItem.created_at.desc())).all()


@app.post("/api/content", response_model=ContentItem)
def create_content(item: ContentItem, session: Session = Depends(get_session)):
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.patch("/api/content/{item_id}/status", response_model=ContentItem)
def update_content_status(item_id: int, status: PostStatus, session: Session = Depends(get_session)):
    item = session.get(ContentItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    item.status = status
    item.updated_at = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
