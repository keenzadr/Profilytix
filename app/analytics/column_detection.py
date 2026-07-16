"""Keyword-based financial column detection."""

from __future__ import annotations

import re
from dataclasses import dataclass


COLUMN_ROLES = ("date", "revenue", "expense", "amount", "category")
AUTO_SELECT_THRESHOLDS = {
    "date": 0.6,
    "revenue": 0.7,
    "expense": 0.7,
    "amount": 0.7,
    "category": 0.7,
}
WEAK_HEADER_AUTO_SELECT_THRESHOLDS = {
    "date": 0.6,
    "revenue": 0.8,
    "expense": 0.8,
    "amount": 0.75,
    "category": 0.8,
}

DATE_KEYWORDS = (
    "date",
    "datetime",
    "timestamp",
    "time",
    "day",
    "month",
    "year",
    "period",
    "week",
    "quarter",
    "created",
    "created at",
    "updated",
    "updated at",
    "posted",
    "posted at",
    "operation date",
    "transaction date",
    "payment date",
    "invoice date",
    "order date",
    "sale date",
    "booking date",
    "document date",
    "report date",
    "дата",
    "дата операции",
    "дата транзакции",
    "дата платежа",
    "дата оплаты",
    "дата счета",
    "дата заказа",
    "дата продажи",
    "дата документа",
    "дата создания",
    "дата обновления",
    "дата проводки",
    "дата отчета",
    "время",
    "день",
    "месяц",
    "год",
    "период",
    "неделя",
    "квартал",
    "создано",
    "обновлено",
    "проведено",
    "күн",
    "күні",
)

REVENUE_KEYWORDS = (
    "revenue",
    "income",
    "sales",
    "sale",
    "turnover",
    "proceeds",
    "receipt",
    "receipts",
    "cash in",
    "cash inflow",
    "inflow",
    "incoming",
    "credit",
    "payment received",
    "amount received",
    "client payment",
    "customer payment",
    "gross revenue",
    "net revenue",
    "gross sales",
    "net sales",
    "sales amount",
    "revenue amount",
    "income amount",
    "выручка",
    "доход",
    "доходы",
    "продажи",
    "продажа",
    "оборот",
    "поступление",
    "поступления",
    "приход",
    "приходы",
    "приход денег",
    "зачисление",
    "зачисления",
    "получено",
    "полученная сумма",
    "оплата от клиента",
    "оплата клиента",
    "платеж клиента",
    "входящий платеж",
    "сумма дохода",
    "сумма выручки",
    "сумма прихода",
    "сумма поступления",
    "реализация",
    "валовая выручка",
    "чистая выручка",
    "касса приход",
    "кіріс",
    "түсім",
)

EXPENSE_KEYWORDS = (
    "expense",
    "expenses",
    "cost",
    "costs",
    "spend",
    "spending",
    "outflow",
    "cash out",
    "cash outflow",
    "debit",
    "withdrawal",
    "write off",
    "payment",
    "paid out",
    "supplier payment",
    "vendor payment",
    "purchase",
    "purchases",
    "rent",
    "salary",
    "payroll",
    "tax",
    "taxes",
    "fee",
    "fees",
    "commission",
    "commissions",
    "loss",
    "losses",
    "cogs",
    "operating expense",
    "expense amount",
    "cost amount",
    "расход",
    "расходы",
    "затраты",
    "издержки",
    "траты",
    "списание",
    "списания",
    "уход",
    "оплата",
    "оплаты",
    "выплата",
    "выплаты",
    "закуп",
    "закупка",
    "закупки",
    "аренда",
    "зарплата",
    "зп",
    "налог",
    "налоги",
    "комиссия",
    "комиссии",
    "себестоимость",
    "исходящий платеж",
    "платеж поставщику",
    "оплата поставщику",
    "сумма расхода",
    "сумма списания",
    "сумма затрат",
    "расходная часть",
    "минус",
    "шығын",
)

CATEGORY_KEYWORDS = (
    "category",
    "subcategory",
    "type",
    "kind",
    "group",
    "class",
    "tag",
    "label",
    "segment",
    "department",
    "project",
    "article",
    "account",
    "purpose",
    "reason",
    "operation type",
    "transaction type",
    "payment type",
    "cost category",
    "expense category",
    "income category",
    "revenue category",
    "категория",
    "подкатегория",
    "тип",
    "вид",
    "группа",
    "класс",
    "тег",
    "метка",
    "сегмент",
    "отдел",
    "проект",
    "статья",
    "статья расходов",
    "статья доходов",
    "счет",
    "назначение",
    "назначение платежа",
    "основание",
    "причина",
    "операция",
    "тип операции",
    "вид операции",
    "тип платежа",
    "категория расхода",
    "категория дохода",
    "санат",
    "түрі",
)

GENERIC_AMOUNT_KEYWORDS = (
    "amount",
    "sum",
    "total",
    "value",
    "money",
    "balance",
    "сумма",
    "итого",
    "значение",
    "деньги",
    "баланс",
)

AMOUNT_KEYWORDS = GENERIC_AMOUNT_KEYWORDS + (
    "transaction amount",
    "operation amount",
    "payment amount",
    "balance change",
    "net amount",
    "gross amount",
    "signed amount",
    "movement amount",
)

DIRECTION_KEYWORDS = (
    "direction",
    "flow",
    "side",
    "operation",
    "operation type",
    "transaction type",
    "income expense",
    "debit credit",
    "credit debit",
    "in out",
    "money flow",
    "cash flow",
    "type",
    "kind",
    "status",
    "РЅР°РїСЂР°РІР»РµРЅРёРµ",
    "РґРІРёР¶РµРЅРёРµ",
    "РґРµРЅРµР¶РЅС‹Р№ РїРѕС‚РѕРє",
    "РґРµРЅРµР¶РЅС‹Р№ РїРѕС‚РѕРє",
    "С‚РёРї",
    "РІРёРґ",
    "РѕРїРµСЂР°С†РёСЏ",
    "С‚РёРї РѕРїРµСЂР°С†РёРё",
    "РїСЂРёС…РѕРґ СЂР°СЃС…РѕРґ",
    "РґРµР±РµС‚ РєСЂРµРґРёС‚",
    "РґРѕС…РѕРґ СЂР°СЃС…РѕРґ",
)

DIRECTION_VALUE_KEYWORDS = (
    "income",
    "expense",
    "revenue",
    "cost",
    "in",
    "out",
    "inflow",
    "outflow",
    "incoming",
    "outgoing",
    "debit",
    "credit",
    "plus",
    "minus",
    "positive",
    "negative",
    "receipt",
    "payment",
    "withdrawal",
    "РґРѕС…РѕРґ",
    "СЂР°СЃС…РѕРґ",
    "РїСЂРёС…РѕРґ",
    "СѓС…РѕРґ",
    "РїРѕСЃС‚СѓРїР»РµРЅРёРµ",
    "СЃРїРёСЃР°РЅРёРµ",
    "Р·Р°С‡РёСЃР»РµРЅРёРµ",
    "РІС‹РїР»Р°С‚Р°",
    "РґРµР±РµС‚",
    "РєСЂРµРґРёС‚",
    "РїР»СЋСЃ",
    "РјРёРЅСѓСЃ",
)

CURRENCY_TOKENS = (
    "$",
    "€",
    "£",
    "¥",
    "₽",
    "₸",
    "₴",
    "₺",
    "₹",
    "₩",
    "฿",
    "₫",
    "₱",
    "₪",
    "₦",
    "usd",
    "eur",
    "gbp",
    "jpy",
    "cny",
    "rub",
    "rur",
    "kzt",
    "kgs",
    "uzs",
    "uah",
    "try",
    "inr",
    "krw",
    "aud",
    "cad",
    "chf",
    "sek",
    "nok",
    "dkk",
    "pln",
    "czk",
    "huf",
    "ron",
    "bgn",
    "gel",
    "amd",
    "azn",
    "aed",
    "sar",
    "qar",
    "kwd",
    "bhd",
    "omr",
    "ils",
    "egp",
    "zar",
    "brl",
    "mxn",
    "ars",
    "clp",
    "cop",
    "pen",
    "idr",
    "myr",
    "sgd",
    "thb",
    "vnd",
    "php",
    "hkd",
    "twd",
    "nzd",
    "dollar",
    "dollars",
    "euro",
    "руб",
    "рубль",
    "рублей",
    "тенге",
    "тг",
    "сом",
    "сум",
    "грн",
    "гривна",
)

ROLE_KEYWORDS = {
    "date": DATE_KEYWORDS,
    "revenue": REVENUE_KEYWORDS,
    "expense": EXPENSE_KEYWORDS,
    "amount": AMOUNT_KEYWORDS,
    "category": CATEGORY_KEYWORDS,
}

ROLE_LABELS = {
    "date": "Date",
    "revenue": "Revenue",
    "expense": "Expenses",
    "amount": "Amount",
    "category": "Category",
}

DATE_PATTERNS = (
    re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"),
    re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"),
    re.compile(r"^\d{4}-\d{1,2}-\d{1,2}[ t]\d{1,2}:\d{2}"),
)


@dataclass(frozen=True)
class ColumnMatch:
    """Detected source column and match confidence."""

    column_name: str | None
    confidence: float
    reason: str = ""


@dataclass(frozen=True)
class ColumnCandidate:
    """Potential source column for a role or derived mode."""

    column_name: str
    confidence: float
    reason: str = ""


@dataclass(frozen=True)
class MoneyValueProfile:
    """Simple value profile for distinguishing money values from IDs."""

    checked_count: int
    numeric_ratio: float
    decimal_ratio: float
    currency_or_sign_ratio: float
    long_integer_ratio: float
    small_integer_ratio: float
    zero_ratio: float
    unique_ratio: float


@dataclass(frozen=True)
class ColumnDetectionResult:
    """Detected financial columns."""

    date: ColumnMatch
    revenue: ColumnMatch
    expense: ColumnMatch
    amount: ColumnMatch
    category: ColumnMatch
    candidates: dict[str, list[ColumnCandidate]]
    money_candidates: list[ColumnCandidate]
    direction_candidates: list[ColumnCandidate]
    weak_headers: bool
    needs_user_confirmation: bool

    def get(self, role: str) -> ColumnMatch:
        """Return a role match by role name."""
        return getattr(self, role)


def detect_columns(
    column_names: list[str],
    preview_rows: list[list[str]] | None = None,
) -> ColumnDetectionResult:
    """Detect important financial columns from headers and preview values."""
    preview_rows = preview_rows or []
    role_scores: dict[str, list[tuple[float, str, str]]] = {
        role: [] for role in COLUMN_ROLES
    }
    money_scores: list[tuple[float, str, str]] = []
    direction_scores: list[tuple[float, str, str]] = []
    weak_headers = headers_are_weak(column_names)

    for column_index, column_name in enumerate(column_names):
        normalized_name = normalize_text(column_name)
        values = [
            row[column_index]
            for row in preview_rows
            if column_index < len(row) and row[column_index] != ""
        ]

        for role in COLUMN_ROLES:
            score, reason = _score_column(role, normalized_name, values)
            role_scores[role].append((score, column_name, reason))

        money_score, money_reason = _score_money_candidate(normalized_name, values)
        money_scores.append((money_score, column_name, money_reason))

        direction_score, direction_reason = _score_direction_candidate(normalized_name, values)
        direction_scores.append((direction_score, column_name, direction_reason))

    assigned_columns: set[str] = set()
    matches: dict[str, ColumnMatch] = {}
    candidates = {
        role: _candidates_from_scores(scores)
        for role, scores in role_scores.items()
    }

    for role in COLUMN_ROLES:
        threshold = _auto_select_threshold(role, weak_headers)
        role_candidates = sorted(role_scores[role], key=lambda item: item[0], reverse=True)
        match = ColumnMatch(column_name=None, confidence=0.0)
        for score, column_name, reason in role_candidates:
            if score < threshold or column_name in assigned_columns:
                continue
            match = ColumnMatch(column_name=column_name, confidence=round(score, 2), reason=reason)
            assigned_columns.add(column_name)
            break
        matches[role] = match

    money_candidates = _candidates_from_scores(money_scores)
    direction_candidates = _candidates_from_scores(direction_scores)
    has_money_match = any(
        matches[role].column_name is not None for role in ("revenue", "expense", "amount")
    )
    needs_user_confirmation = (
        weak_headers
        or not has_money_match
        or any(
            matches[role].column_name is not None and matches[role].confidence < 0.8
            for role in COLUMN_ROLES
        )
    )

    return ColumnDetectionResult(
        date=matches["date"],
        revenue=matches["revenue"],
        expense=matches["expense"],
        amount=matches["amount"],
        category=matches["category"],
        candidates=candidates,
        money_candidates=money_candidates,
        direction_candidates=direction_candidates,
        weak_headers=weak_headers,
        needs_user_confirmation=needs_user_confirmation,
    )


def normalize_text(value: str) -> str:
    """Normalize header text for keyword matching."""
    text = value.casefold().replace("ё", "е")
    text = re.sub(r"[_\-/\\|:;.,()\[\]{}]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def headers_are_weak(column_names: list[str]) -> bool:
    """Return whether column names are generic or not descriptive."""
    if not column_names:
        return True

    weak_count = sum(_is_weak_header(column_name) for column_name in column_names)
    return weak_count / len(column_names) >= 0.6


def _is_weak_header(column_name: str) -> bool:
    """Return whether a single header looks generic."""
    normalized_name = normalize_text(column_name)
    if not normalized_name:
        return True

    if re.fullmatch(r"\d+", normalized_name):
        return True

    if normalized_name.startswith("unnamed"):
        return True

    return bool(
        re.fullmatch(
            r"(col|column|field|var|value|f|x)\s*\d+",
            normalized_name,
        )
    )


def _auto_select_threshold(role: str, weak_headers: bool) -> float:
    """Return the minimum score needed to auto-select a detected column."""
    if weak_headers:
        return WEAK_HEADER_AUTO_SELECT_THRESHOLDS[role]
    return AUTO_SELECT_THRESHOLDS[role]


def _candidates_from_scores(scores: list[tuple[float, str, str]]) -> list[ColumnCandidate]:
    """Convert raw scores to sorted candidates."""
    candidates = [
        ColumnCandidate(column_name=column_name, confidence=round(score, 2), reason=reason)
        for score, column_name, reason in scores
        if score > 0
    ]
    return sorted(candidates, key=lambda candidate: candidate.confidence, reverse=True)[:5]


def _score_column(role: str, normalized_name: str, values: list[str]) -> tuple[float, str]:
    """Score a column for a specific role."""
    keyword_score, keyword_reason = _score_keywords(normalized_name, ROLE_KEYWORDS[role])
    if keyword_score >= 0.7:
        return keyword_score, keyword_reason

    if role == "date":
        date_score = _score_date_values(values)
        if date_score > keyword_score:
            return date_score, "date-like values"

    if role in {"revenue", "expense"} and keyword_score > 0:
        money_score = _score_money_values(values)
        if money_score > 0:
            return min(keyword_score + 0.1, 0.9), f"{keyword_reason}, money-like values"

    if role == "amount":
        amount_score, amount_reason = _score_money_candidate(normalized_name, values)
        if amount_score > keyword_score:
            return amount_score, amount_reason

    if role == "category":
        category_score = _score_category_values(values)
        if category_score > keyword_score:
            return category_score, "repeated text values"

    return keyword_score, keyword_reason


def _score_keywords(normalized_name: str, keywords: tuple[str, ...]) -> tuple[float, str]:
    """Score a normalized header against role keywords."""
    if not normalized_name:
        return 0.0, ""

    for keyword in keywords:
        normalized_keyword = normalize_text(keyword)
        if normalized_name == normalized_keyword:
            return 1.0, f"exact keyword: {keyword}"

    for keyword in keywords:
        normalized_keyword = normalize_text(keyword)
        if _contains_phrase(normalized_name, normalized_keyword):
            return 0.75, f"partial keyword: {keyword}"

    for keyword in GENERIC_AMOUNT_KEYWORDS:
        normalized_keyword = normalize_text(keyword)
        if normalized_name == normalized_keyword or _contains_phrase(normalized_name, normalized_keyword):
            return 0.25, f"generic amount keyword: {keyword}"

    return 0.0, ""


def _contains_phrase(text: str, phrase: str) -> bool:
    """Return whether text contains phrase as words."""
    return f" {phrase} " in f" {text} "


def _score_date_values(values: list[str]) -> float:
    """Score a column by how many preview values look like dates."""
    if not values:
        return 0.0

    checked_values = values[:30]
    matches = sum(_looks_like_date(value) for value in checked_values)
    ratio = matches / len(checked_values)
    return 0.65 if ratio >= 0.7 else 0.0


def _looks_like_date(value: str) -> bool:
    """Return whether a preview value resembles a common date format."""
    text = value.strip()
    return any(pattern.match(text) for pattern in DATE_PATTERNS)


def _score_money_values(values: list[str]) -> float:
    """Score a column by how many preview values look like money values."""
    profile = _money_value_profile(values)
    if profile.checked_count == 0 or profile.numeric_ratio < 0.7:
        return 0.0

    if _is_id_like_numeric_profile(profile):
        return 0.0

    return 0.2


def _looks_like_money(value: str) -> bool:
    """Return whether a preview value resembles a numeric or currency value."""
    profile = _money_value_profile([value])
    return profile.checked_count > 0 and profile.numeric_ratio > 0


def _score_money_candidate(normalized_name: str, values: list[str]) -> tuple[float, str]:
    """Score a column as a generic money/amount candidate."""
    keyword_score, keyword_reason = _score_keywords(normalized_name, GENERIC_AMOUNT_KEYWORDS)
    profile = _money_value_profile(values)
    if profile.checked_count == 0:
        return keyword_score, keyword_reason

    if profile.numeric_ratio < 0.7:
        return keyword_score, keyword_reason

    if _is_id_like_numeric_profile(profile):
        return keyword_score, keyword_reason

    if profile.zero_ratio >= 0.95:
        return keyword_score, keyword_reason

    if profile.currency_or_sign_ratio >= 0.2:
        score = 0.85
        reason = "currency or signed numeric values"
    elif profile.decimal_ratio >= 0.5:
        score = 0.85
        reason = "decimal numeric values"
    elif profile.decimal_ratio >= 0.2:
        score = 0.75
        reason = "some decimal numeric values"
    else:
        score = 0.6
        reason = "numeric values"

    if keyword_score > 0:
        score = min(score + 0.15, 0.95)
        reason = f"{keyword_reason}, {reason}"

    return score, reason


def _money_value_profile(values: list[str]) -> MoneyValueProfile:
    """Return a compact profile for money-like numeric values."""
    checked_values = [
        value.strip()
        for value in values[:50]
        if value is not None and value.strip() and not _looks_like_date(value)
    ]
    if not checked_values:
        return MoneyValueProfile(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    numeric_values: list[str] = []
    decimal_count = 0
    currency_or_sign_count = 0
    long_integer_count = 0
    small_integer_count = 0
    zero_count = 0

    for value in checked_values:
        parsed = _parse_numeric_profile_value(value)
        if parsed is None:
            continue

        numeric_text, numeric_value, has_decimal = parsed
        numeric_values.append(numeric_text)
        if has_decimal:
            decimal_count += 1
        if _value_has_currency_or_sign(value):
            currency_or_sign_count += 1

        digit_count = len(re.sub(r"\D", "", numeric_text))
        if not has_decimal and digit_count >= 5:
            long_integer_count += 1
        if not has_decimal and abs(numeric_value) <= 20:
            small_integer_count += 1
        if numeric_value == 0:
            zero_count += 1

    numeric_count = len(numeric_values)
    checked_count = len(checked_values)
    if numeric_count == 0:
        return MoneyValueProfile(checked_count, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    return MoneyValueProfile(
        checked_count=checked_count,
        numeric_ratio=numeric_count / checked_count,
        decimal_ratio=decimal_count / numeric_count,
        currency_or_sign_ratio=currency_or_sign_count / numeric_count,
        long_integer_ratio=long_integer_count / numeric_count,
        small_integer_ratio=small_integer_count / numeric_count,
        zero_ratio=zero_count / numeric_count,
        unique_ratio=len(set(numeric_values)) / numeric_count,
    )


def _parse_numeric_profile_value(value: str) -> tuple[str, float, bool] | None:
    """Parse a preview value into normalized numeric text and decimal flag."""
    text = str(value).strip()
    if not text:
        return None

    if any(character in text for character in "{}[]:"):
        return None

    normalized_text = normalize_text(text)
    has_currency = any(
        token in text.casefold() or token in normalized_text
        for token in CURRENCY_TOKENS
    )
    if re.search(r"[a-zа-я]", text.casefold()) and not has_currency:
        return None

    numeric_text = re.sub(r"[^\d,.\-+()]", "", text)
    if not re.search(r"\d", numeric_text):
        return None

    negative = numeric_text.startswith("(") and numeric_text.endswith(")")
    numeric_text = numeric_text.replace("(", "").replace(")", "")

    decimal_separator = ""
    if "," in numeric_text and "." in numeric_text:
        decimal_separator = "," if numeric_text.rfind(",") > numeric_text.rfind(".") else "."
    elif "," in numeric_text:
        parts = numeric_text.rsplit(",", 1)
        decimal_separator = "," if len(parts) == 2 and len(parts[1]) <= 2 else ""
    elif "." in numeric_text:
        parts = numeric_text.rsplit(".", 1)
        decimal_separator = "." if len(parts) == 2 and len(parts[1]) <= 2 else ""

    if decimal_separator == ",":
        normalized = numeric_text.replace(".", "").replace(",", ".")
    elif decimal_separator == ".":
        normalized = numeric_text.replace(",", "")
    else:
        normalized = numeric_text.replace(",", "").replace(".", "")

    normalized = normalized.replace("+", "")
    if negative and not normalized.startswith("-"):
        normalized = f"-{normalized}"

    try:
        numeric_value = float(normalized)
    except ValueError:
        return None

    return normalized, numeric_value, bool(decimal_separator)


def _value_has_currency_or_sign(value: str) -> bool:
    """Return whether a value includes currency tokens or explicit signs."""
    text = str(value).casefold()
    normalized_text = normalize_text(value)
    if any(token in text or token in normalized_text for token in CURRENCY_TOKENS):
        return True
    return bool(re.search(r"(^|[\s(])[+-]\s*\d", text))


def _is_id_like_numeric_profile(profile: MoneyValueProfile) -> bool:
    """Return whether numeric values look more like IDs/codes than money."""
    if profile.currency_or_sign_ratio > 0 or profile.decimal_ratio > 0:
        return False

    return profile.long_integer_ratio >= 0.7 or profile.small_integer_ratio >= 0.9


def _score_direction_candidate(normalized_name: str, values: list[str]) -> tuple[float, str]:
    """Score a column as an income/expense direction candidate."""
    keyword_score, keyword_reason = _score_keywords(normalized_name, DIRECTION_KEYWORDS)
    checked_values = [normalize_text(value) for value in values[:50] if value.strip()]
    if not checked_values:
        return keyword_score, keyword_reason

    matches = sum(
        any(_contains_phrase(value, normalize_text(keyword)) for keyword in DIRECTION_VALUE_KEYWORDS)
        for value in checked_values
    )
    ratio = matches / len(checked_values)

    if ratio >= 0.5:
        score = max(keyword_score, 0.75)
        reason = keyword_reason or "income/expense-like values"
        return score, reason

    return keyword_score, keyword_reason


def _score_category_values(values: list[str]) -> float:
    """Score category-like text values from preview rows."""
    if len(values) < 5:
        return 0.0

    checked_values = [normalize_text(value) for value in values[:50] if normalize_text(value)]
    if not checked_values:
        return 0.0

    unique_count = len(set(checked_values))
    unique_ratio = unique_count / len(checked_values)
    text_like_count = sum(not _looks_like_money(value) and not _looks_like_date(value) for value in checked_values)
    text_ratio = text_like_count / len(checked_values)

    if text_ratio >= 0.8 and unique_ratio <= 0.7:
        return 0.55
    return 0.0
