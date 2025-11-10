"""Shared address schemas."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field


STATE_PATTERN = re.compile(r"^[A-Z]{2}$")
POSTAL_CODE_PATTERN = re.compile(r"^[0-9]{5}(?:[-\s]?[0-9]{4})?$")


class PostalAddress(BaseModel):
    """Represents a normalized postal address."""

    street: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    postal_code: str = Field(min_length=1)

    model_config = ConfigDict(from_attributes=True)


class PostalAddressInput(BaseModel):
    """User-submitted postal address payload."""

    street: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=1)
    postal_code: str = Field(min_length=1)

    model_config = ConfigDict(populate_by_name=True)

    def normalized(self) -> PostalAddress:
        """Return a :class:`PostalAddress` with trimmed field values."""

        street = self.street.strip()
        city = self.city.strip()
        state = self.state.strip().upper()
        postal_code = self.postal_code.strip()

        if STATE_PATTERN.match(state) is None:
            raise ValueError("State must be a two-letter abbreviation.")

        if POSTAL_CODE_PATTERN.match(postal_code) is None:
            raise ValueError("Enter a valid ZIP code (##### or #####-####).")

        return PostalAddress(
            street=street,
            city=city,
            state=state,
            postal_code=postal_code,
        )


def build_postal_address(
    street: str | None,
    city: str | None,
    state: str | None,
    postal_code: str | None,
) -> PostalAddress | None:
    """Create a :class:`PostalAddress` if all components are present."""

    parts = [street, city, state, postal_code]
    if any(part is None or not str(part).strip() for part in parts):
        return None

    return PostalAddress(
        street=str(street).strip(),
        city=str(city).strip(),
        state=str(state).strip(),
        postal_code=str(postal_code).strip(),
    )


__all__ = [
    "PostalAddress",
    "PostalAddressInput",
    "build_postal_address",
]
