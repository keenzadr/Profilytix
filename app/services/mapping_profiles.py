"""Reusable column mappings kept in the existing local QSettings store."""

from __future__ import annotations

import json
from dataclasses import asdict

from app.analytics.metrics import SelectedColumns

MAPPING_ROLES = ('date', 'revenue', 'expense', 'amount', 'category', 'description')
_KEY = 'column_mapping_profiles'


class MissingProfileColumns(ValueError):
    """Carry names separately so the UI translates only the owned template."""
    def __init__(self, columns):
        self.columns = tuple(columns)
        super().__init__('Missing columns: ' + ', '.join(columns))


class MappingProfiles:
    """Store names and mappings only, never spreadsheet contents or paths."""

    def __init__(self, settings: object) -> None:
        self.settings = settings

    def _read(self) -> dict:
        try:
            value = json.loads(self.settings.value(_KEY, '{}'))
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def names(self) -> list[str]:
        return sorted(self._read())

    def save(self, name: str, selected: SelectedColumns) -> None:
        name = name.strip()
        if not name or not selected.has_money_column:
            raise ValueError('A profile needs a name and at least one money column.')
        profiles = self._read()
        profiles[name] = asdict(selected)
        self.settings.setValue(_KEY, json.dumps(profiles, ensure_ascii=False))

    def load(self, name: str, available_columns: list[str]) -> SelectedColumns:
        profile = self._read().get(name)
        if not isinstance(profile, dict):
            raise ValueError('Profile not found or invalid.')
        for role in MAPPING_ROLES:
            values = profile.get(role, [])
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError('Invalid profile columns.')
        missing = sorted({column for role in MAPPING_ROLES for column in profile.get(role, [])} - set(available_columns))
        if missing:
            raise MissingProfileColumns(missing)
        selected = SelectedColumns(**{role: profile.get(role, []) for role in MAPPING_ROLES})
        if not selected.has_money_column:
            raise ValueError('The profile has no money columns.')
        return selected

    def delete(self, name: str) -> None:
        profiles = self._read()
        profiles.pop(name, None)
        self.settings.setValue(_KEY, json.dumps(profiles, ensure_ascii=False))
