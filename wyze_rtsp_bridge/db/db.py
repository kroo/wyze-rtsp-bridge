from typing import Optional

import pathlib
import sqlite3

import sqlalchemy
import sqlalchemy.engine
import sqlalchemy.orm
import wyzecam.api_models
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from wyze_rtsp_bridge.config import Config
from wyze_rtsp_bridge.db import models


class WyzeRtspDatabase:
    def __init__(self, config: Config, echo: bool = False):
        self.config = config
        self.engine: Optional[sqlalchemy.engine.Engine] = None
        self.echo = echo

        self.open()

    def open(self):
        path = pathlib.Path(self.config.db_path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = sqlalchemy.create_engine(
            f"sqlite:///{path}", echo=self.echo, future=True
        )
        models.Base.metadata.create_all(self.engine)

    def close(self):
        if self.engine:
            self.engine.dispose()
        self.engine = None

    def session(self) -> sqlalchemy.orm.Session:
        assert self.engine
        return sqlalchemy.orm.Session(self.engine)


def get_credentials(db: WyzeRtspDatabase) -> Optional[models.CredentialModel]:
    with db.session() as session:
        result = session.execute(
            select(models.Credential).where(
                models.Credential.id == models.CREDENTIAL_ID
            )
        ).first()

    if result is None:
        return None

    from_orm: models.CredentialModel = models.CredentialModel.from_orm(
        result[0]
    )
    return from_orm


def set_credentials(
    db: WyzeRtspDatabase, auth_info: wyzecam.api_models.WyzeCredential
) -> None:
    with db.session() as session:
        model = models.Credential(
            **dict(auth_info.dict(), id=models.CREDENTIAL_ID)
        )
        session.merge(model)
        session.commit()
