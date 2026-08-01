"""Rotas HTTP da aplicação."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.sqlalchemy import (
    SQLAlchemyExpenseRepository,
    SQLAlchemyGroupRepository,
)
from app.schemas.expense import (
    CustomExpenseCreate,
    EqualExpenseCreate,
    ExpenseRead,
)
from app.schemas.group import GroupCreate, GroupRead, ParticipantCreate, ParticipantRead
from app.schemas.settlement import TransferRead
from app.services.expense import ExpenseService
from app.services.group import GroupService
from app.services.settlement import SettlementService

router = APIRouter()

@router.post("/groups", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupCreate, db: Session = Depends(get_db)) -> GroupService.create_group:
    """Cria um novo grupo."""
    repository = SQLAlchemyGroupRepository(db)
    service = GroupService(repository)
    return service.create_group(payload.name, [str(email) for email in payload.participant_emails])

@router.get("/groups/{group_id}", response_model=GroupRead)
def get_group(group_id: UUID, db: Session = Depends(get_db)) -> GroupService.view_group:
    """Retorna um grupo com participantes e saldos."""
    repository = SQLAlchemyGroupRepository(db)
    service = GroupService(repository)
    return service.view_group(group_id)

@router.post(
    "/groups/{group_id}/participants",
    response_model=ParticipantRead,
    status_code=status.HTTP_201_CREATED,
)
def add_participant(
    group_id: UUID, payload: ParticipantCreate, db: Session = Depends(get_db)
) -> ParticipantRead:
    """Adiciona um participante a um grupo."""
    repository = SQLAlchemyGroupRepository(db)
    service = GroupService(repository)
    return service.add_participant(group_id, str(payload.email))

@router.post(
    "/expenses/equal",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_equal_expense(
    payload: EqualExpenseCreate, db: Session = Depends(get_db)
) -> ExpenseRead:
    """Registra despesa igualitária."""
    group_repository = SQLAlchemyGroupRepository(db)
    expense_repository = SQLAlchemyExpenseRepository(db)
    service = ExpenseService(group_repository, expense_repository)
    return service.register_equal_expense(
        group_id=payload.group_id,
        description=payload.description,
        paid_by=payload.paid_by,
        amount=payload.amount,
        participant_ids=payload.participant_ids,
    )

@router.post(
    "/expenses/custom",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_expense(
    payload: CustomExpenseCreate, db: Session = Depends(get_db)
) -> ExpenseRead:
    """Registra despesa customizada."""
    group_repository = SQLAlchemyGroupRepository(db)
    expense_repository = SQLAlchemyExpenseRepository(db)
    service = ExpenseService(group_repository, expense_repository)
    return service.register_custom_expense(
        group_id=payload.group_id,
        description=payload.description,
        paid_by=payload.paid_by,
        amount=payload.amount,
        splits=[
            {
                "participant_id": split.participant_id,
                "amount": split.amount,
                "percentage": split.percentage,
            }
            for split in payload.splits
        ],
    )

@router.get("/groups/{group_id}/balances")
def get_group_balances(group_id: UUID, db: Session = Depends(get_db)) -> dict:
    """Retorna os saldos calculados do grupo."""
    group_repository = SQLAlchemyGroupRepository(db)
    expense_repository = SQLAlchemyExpenseRepository(db)
    service = ExpenseService(group_repository, expense_repository)
    return service.get_group_balances(group_id)

@router.post("/groups/{group_id}/settlement", response_model=list[TransferRead])
def settle_group(group_id: UUID, db: Session = Depends(get_db)) -> list:
    """Gera o plano de liquidação do grupo."""
    expense_repository = SQLAlchemyExpenseRepository(db)
    service = SettlementService(expense_repo=expense_repository)
    return service.settle_group(group_id)