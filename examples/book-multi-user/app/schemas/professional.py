from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


def _normalize_working_days(value: str) -> str:
    try:
        days = [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError as exc:
        raise ValueError("working_days deve conter inteiros separados por vírgula") from exc

    if not days or any(d < 0 or d > 6 for d in days) or len(days) != len(set(days)):
        raise ValueError("working_days deve conter inteiros únicos entre 0 e 6")

    return ",".join(str(d) for d in sorted(days))


def _validate_hour(value: str) -> str:
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ValueError("hour deve usar o formato HH:MM") from exc
    return value


class ProfessionalBase(BaseModel):
    speciality: str = Field(..., min_length=1, max_length=100)
    working_days: str = Field(default="1,2,3,4,5")
    start_hour: str = Field(default="08:00")
    end_hour: str = Field(default="18:00")

    @field_validator("working_days")
    @classmethod
    def validate_working_days(cls, value: str) -> str:
        return _normalize_working_days(value)

    @field_validator("start_hour", "end_hour")
    @classmethod
    def validate_hour(cls, value: str) -> str:
        return _validate_hour(value)

    @model_validator(mode="after")
    def end_after_start(self):
        start = datetime.strptime(self.start_hour, "%H:%M").time()
        end = datetime.strptime(self.end_hour, "%H:%M").time()
        if end <= start:
            raise ValueError("end_hour deve ser maior que start_hour")
        return self


class ProfessionalCreate(ProfessionalBase):
    user_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=120)
    password: str | None = Field(default=None, min_length=6, max_length=128)

    @model_validator(mode="after")
    def check_creation_mode(self):
        has_identity = self.user_id is not None
        has_credentials = self.name is not None and self.email is not None and self.password is not None

        if has_identity and has_credentials:
            raise ValueError("Informe user_id ou name/email/password, não ambos")

        if not has_identity and not has_credentials:
            raise ValueError("Informe user_id ou name/email/password")

        return self


class ProfessionalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=120)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    speciality: str | None = Field(default=None, min_length=1, max_length=100)
    working_days: str | None = None
    start_hour: str | None = None
    end_hour: str | None = None

    @field_validator("working_days")
    @classmethod
    def validate_working_days_optional(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _normalize_working_days(value)

    @field_validator("start_hour", "end_hour")
    @classmethod
    def validate_hour_optional(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_hour(value)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_hour and self.end_hour:
            start = datetime.strptime(self.start_hour, "%H:%M").time()
            end = datetime.strptime(self.end_hour, "%H:%M").time()
            if end <= start:
                raise ValueError("end_hour deve ser maior que start_hour")
        return self


class ProfessionalRead(BaseModel):
    id: int
    name: str
    email: str
    role: str = "professional"
    speciality: str | None = None
    working_days: str | None = None
    start_hour: str | None = None
    end_hour: str | None = None