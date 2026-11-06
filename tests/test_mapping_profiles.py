import pytest

from app.analytics.metrics import SelectedColumns


class Settings:
    def __init__(self): self.values = {}
    def value(self, key, default=None): return self.values.get(key, default)
    def setValue(self, key, value): self.values[key] = value


def test_profile_round_trip_and_schema_validation():
    from app.services.mapping_profiles import MappingProfiles
    store = MappingProfiles(Settings())
    selected = SelectedColumns(amount='Сумма', description='Описание')
    store.save('Банк', selected)
    assert store.names() == ['Банк']
    assert store.load('Банк', ['Сумма', 'Описание']) == selected
    with pytest.raises(ValueError, match='Описание'):
        store.load('Банк', ['Сумма'])
    assert store.names() == ['Банк']
    store.delete('Банк')
    assert store.names() == []


def test_profiles_reject_empty_names_and_survive_corrupt_settings():
    from app.services.mapping_profiles import MappingProfiles
    settings = Settings()
    settings.setValue('column_mapping_profiles', 'not-json')
    store = MappingProfiles(settings)
    assert store.names() == []
    with pytest.raises(ValueError): store.save(' ', SelectedColumns(amount='a'))
    with pytest.raises(ValueError): store.save('No money', SelectedColumns(category='c'))
