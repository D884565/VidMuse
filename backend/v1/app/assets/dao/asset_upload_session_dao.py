from typing import Optional

from sqlalchemy.orm import Session

from backend.v1.app.models.asset_upload_session import AssetUploadSession


class AssetUploadSessionDAO:
    @staticmethod
    def create_session(db: Session, session_data: dict) -> AssetUploadSession:
        session = AssetUploadSession(**session_data)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_by_session_id(db: Session, session_id: str) -> Optional[AssetUploadSession]:
        return db.query(AssetUploadSession).filter(AssetUploadSession.session_id == session_id).first()

    @staticmethod
    def find_active_session(
        db: Session,
        *,
        asset_id: Optional[int],
        mode: str,
        file_hash: str,
        chunk_size: int,
    ) -> Optional[AssetUploadSession]:
        query = db.query(AssetUploadSession).filter(
            AssetUploadSession.mode == mode,
            AssetUploadSession.file_hash == file_hash,
            AssetUploadSession.chunk_size == chunk_size,
            AssetUploadSession.status.in_(["pending", "uploading"]),
        )
        if asset_id is None:
            query = query.filter(AssetUploadSession.asset_id.is_(None))
        else:
            query = query.filter(AssetUploadSession.asset_id == asset_id)
        return query.order_by(AssetUploadSession.created_at.desc()).first()

    @staticmethod
    def update_session(db: Session, session_id: str, update_data: dict) -> Optional[AssetUploadSession]:
        db.query(AssetUploadSession).filter(AssetUploadSession.session_id == session_id).update(update_data)
        db.commit()
        return AssetUploadSessionDAO.get_by_session_id(db, session_id)

    @staticmethod
    def delete_session(db: Session, session_id: str) -> bool:
        deleted = db.query(AssetUploadSession).filter(AssetUploadSession.session_id == session_id).delete()
        db.commit()
        return deleted > 0

