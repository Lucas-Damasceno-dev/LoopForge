"""Repositórios SQLAlchemy."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError
from app.models.entities import Expense, Group, Participant, Split
from app.models.orm import ExpenseORM, ExpenseSplitORM, GroupORM, ParticipantORM

from app.repositories.base import ExpenseRepository, GroupRepository

class SQLAlchemyGroupRepository(GroupRepository):
    """Repositório de grupos usando SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Recebe a sessão do banco."""
        self.session = session

    def create(self, group: Group) -> Group:
        """Persiste um grupo e seus participantes."""
        group_orm = GroupORM(
            id=group.id,
            name=group.name,
            status=group.status,
            created_at=group.created_at,
        )
        for participant in group.participants:
            group_orm.participants.append(
                ParticipantORM(
                    id=participant.id,
                    email=participant.email,
                    name=participant.name,
                    status=participant.status,
                    created_at=participant.created_at,
                    invite_expires_at=participant.invite_expires_at,
                )
            )
        self.session.add(group_orm)
        self.session.commit()
        self.session.refresh(group_orm)
        return group

    def get(self, group_id) -> Group | None:
        """Busca um grupo pelo id."""
        group_orm = self.session.get(GroupORM, group_id)
        if group_orm is None:
            return None
        return Group(
            id=group_orm.id,
            name=group_orm.name,
            status=group_orm.status,
            created_at=group_orm.created_at,
            participants=[
                Participant(
                    id=participant.id,
                    email=participant.email,
                    name=participant.name,
                    status=participant.status,
                    balance=Decimal("0.00"),
                    created_at=participant.created_at,
                    invite_expires_at=participant.invite_expires_at,
                )
                for participant in group_orm.participants
            ],
        )

    def add_participant(self, group_id, participant: Participant) -> Participant:
        """Adiciona um participante a um grupo existente."""
        group_orm = self.session.get(GroupORM, group_id)
        if group_orm is None:
            raise NotFoundError("Grupo não encontrado.")
        participant_orm = ParticipantORM(
            id=participant.id,
            group_id=group_id,
            email=participant.email,
            name=participant.name,
            status=participant.status,
            created_at=participant.created_at,
            invite_expires_at=participant.invite_expires_at,
        )
        group_orm.participants.append(participant_orm)
        self.session.add(participant_orm)
        self.session.commit()
        return participant

class SQLAlchemyExpenseRepository(ExpenseRepository):
    """Repositório de despesas usando SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Recebe a sessão do banco."""
        self.session = session

    def create(self, expense: Expense) -> Expense:
        """Persiste uma despesa e suas divisões."""
        expense_orm = ExpenseORM(
            id=expense.id,
            group_id=expense.group_id,
            paid_by=expense.paid_by,
            description=expense.description,
            amount=expense.amount,
            split_type=expense.split_type,
            created_at=expense.created_at,
        )
        for split in expense.splits:
            expense_orm.splits.append(
                ExpenseSplitORM(
                    participant_id=split.participant_id,
                    amount=split.amount,
                    percentage=split.percentage,
                )
            )
        self.session.add(expense_orm)
        self.session.commit()
        return expense

    def list_by_group(self, group_id) -> list[Expense]:
        """Lista as despesas de um grupo."""
        statement = (
            select(ExpenseORM)
            .where(ExpenseORM.group_id == group_id)
            .options(selectinload(ExpenseORM.splits))
        )
        expenses_orm = self.session.scalars(statement).all()
        return [
            Expense(
                id=expense.id,
                group_id=expense.group_id,
                paid_by=expense.paid_by,
                description=expense.description,
                amount=expense.amount,
                split_type=expense.split_type,
                created_at=expense.created_at,
                splits=[
                    Split(
                        participant_id=split.participant_id,
                        amount=split.amount,
                        percentage=split.percentage,
                    )
                    for split in expense.splits
                ],
            )
            for expense in expenses_orm
        ]