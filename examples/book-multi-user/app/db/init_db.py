from sqlalchemy.exc import SQLAlchemyError

from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Professional, Service, User


def init_db() -> None:
    """Cria as tabelas e popula dados iniciais se necessário."""
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    seed_initial_data()


def seed_initial_data() -> None:
    """Insere admin, profissionais e serviços padrão quando o banco está vazio."""
    db = SessionLocal()
    try:
        if db.query(User).first() is not None:
            return

        admin = User(
            name="Admin",
            email="admin@example.com",
            password_hash=get_password_hash("admin123"),
            role="admin",
        )
        prof1_user = User(
            name="Ana",
            email="prof1@example.com",
            password_hash=get_password_hash("prof123"),
            role="professional",
        )
        prof2_user = User(
            name="Bruno",
            email="prof2@example.com",
            password_hash=get_password_hash("prof123"),
            role="professional",
        )

        db.add_all([admin, prof1_user, prof2_user])
        db.flush()

        db.add_all(
            [
                Professional(
                    user_id=prof1_user.id,
                    speciality="Cabeleireira",
                    working_days="1,2,3,4,5",
                    start_hour="08:00",
                    end_hour="18:00",
                ),
                Professional(
                    user_id=prof2_user.id,
                    speciality="Manicure",
                    working_days="1,2,3,4,5",
                    start_hour="08:00",
                    end_hour="18:00",
                ),
            ]
        )

        db.add_all(
            [
                Service(
                    professional_id=prof1_user.id,
                    name="Corte de cabelo",
                    duration_minutes=30,
                    price=50.0,
                ),
                Service(
                    professional_id=prof1_user.id,
                    name="Barba",
                    duration_minutes=20,
                    price=30.0,
                ),
                Service(
                    professional_id=prof1_user.id,
                    name="Combo Corte + Barba",
                    duration_minutes=50,
                    price=70.0,
                ),
                Service(
                    professional_id=prof2_user.id,
                    name="Manicure",
                    duration_minutes=45,
                    price=40.0,
                ),
            ]
        )

        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()