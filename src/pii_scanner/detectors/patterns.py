"""Скомпилированные регулярные выражения для всех категорий."""

from __future__ import annotations

import re

# --- Контакты ---

EMAIL_RE = re.compile(
    r"\b(?!(?:info|support|help|admin|sales|contact|press|pr|marketing|"
    r"hello|career|hr|job|docflow|zamena|legal|zakaz|b2b|office|noreply|feedback)@)"
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)

PHONE_RE = re.compile(
    r"(?<!\d)(?:\+7|8)[\s\-\(\)]*(?!800\b)\d{3}[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{2}[\s\-\(\)]*\d{2}(?!\d)"
)

# --- Паспорт РФ ---

PASSPORT_RF_RE = re.compile(
    r"(?<!\d)(\d{2})\s?(\d{2})\s?(?:№\s*)?(\d{6})(?!\d)"
)
PASSPORT_CONTEXT_RE = re.compile(
    r"паспорт|серии?\s+\d|серия|документ,?\s+удостоверяющий", re.IGNORECASE
)

# --- СНИЛС ---

SNILS_RE = re.compile(
    r"(?<!\d)\d{3}[\-\s]?\d{3}[\-\s]?\d{3}[\-\s]?\d{2}(?!\d)"
)
SNILS_CONTEXT_RE = re.compile(r"снилс|пенсионн", re.IGNORECASE)

# --- ИНН ---

INN_RE = re.compile(r"(?<!\d)\d{10}(?!\d)|(?<!\d)\d{12}(?!\d)")
INN_CONTEXT_RE = re.compile(r"инн|идентификационный\s+номер", re.IGNORECASE)

# --- Водительское удостоверение ---

DRIVER_LICENSE_RE = re.compile(
    r"(?<!\d)(?:\d{2}\s?\d{2}\s?\d{6}|[А-ЯA-Z]{2}\s?\d{6})(?!\d)"
)
DRIVER_LICENSE_CONTEXT_RE = re.compile(
    r"водительск|вод\.?\s*удостоверен|ву\b|driver", re.IGNORECASE
)

# --- Банковская карта ---

BANK_CARD_RE = re.compile(
    r"(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)"
)
BANK_CARD_CONTEXT_RE = re.compile(
    r"карт[аыеу]|card|visa|mastercard|мир\b", re.IGNORECASE
)

# --- Банковский счёт (20 цифр) ---

BANK_ACCOUNT_RE = re.compile(r"(?<!\d)\d{20}(?!\d)")
BANK_ACCOUNT_CONTEXT_RE = re.compile(r"расч[её]тн|р/с|счет\b|счёт\b|account", re.IGNORECASE)

# --- БИК (9 цифр) ---

BIK_RE = re.compile(r"(?<!\d)\d{9}(?!\d)")
BIK_CONTEXT_RE = re.compile(r"бик|bik", re.IGNORECASE)

# --- ОГРН ---

OGRN_RE = re.compile(r"(?<!\d)(?:\d{13}|\d{15})(?!\d)")
OGRN_CONTEXT_RE = re.compile(r"огрн", re.IGNORECASE)

# --- CVV ---

CVV_CONTEXT_RE = re.compile(r"\bcvv2?\b|\bcvc2?\b|код\s+безопасности", re.IGNORECASE)
CVV_RE = re.compile(r"(?<!\d)\d{3,4}(?!\d)")

# --- Дата и место рождения ---

BIRTH_DATE_RE = re.compile(
    r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])[.\-/](?:0?[1-9]|1[0-2])[.\-/](?:19|20)\d{2}(?!\d)"
)
BIRTH_CONTEXT_RE = re.compile(
    r"д\.?\s*р\.?|год\s+рождения|г\.?\s*р\.?|рожд|date\s+of\s+birth|dob",
    re.IGNORECASE,
)
BIRTH_PLACE_RE = re.compile(
    # Убрана латиница для предотвращения срабатываний на английских документах
    r"(?:место\s+рождения|м\.р\.)[\s:;]+([А-ЯЁ][а-яёА-ЯЁ0-9\s\,\.\-]+)(?=\n|;|$)", 
    re.IGNORECASE
)

# --- Адрес ---

ADDRESS_RE = re.compile(
    # Убрана латиница (A-Za-z) для защиты от аббревиатур вроде "с. UK"
    r"(?:г\.|город|с\.|село|пгт\.?|пос\.?)\s+[А-ЯЁ][А-Яа-яЁё\-]+"
    r"|(?:ул\.|улица|пр\.|проспект|пер\.|переулок|пл\.|площадь|шоссе|ш\.|наб\.|набережная|бульвар|б-р)\s+[А-ЯЁ][А-Яа-яЁё0-9\.\-\s]{1,40}"
    r"(?:,?\s*д\.?\s*\d+[А-Яа-яЁё]?)?(?:,?\s*кв\.?\s*\d+)?",
)
POSTAL_INDEX_RE = re.compile(r"\b\d{6}\b") 

# --- ФИО ---

FIO_RE = re.compile(
    r"\b[А-ЯЁ][а-яё]{1,30}\s+[А-ЯЁ][а-яё]{1,30}\s+[А-ЯЁ][а-яё]{1,30}(?:ич|вна|вич|на|евна|ова|ев|ин|ын|ский|ской|ской)?\b"
)
FIO_INITIALS_RE = re.compile(
    r"\b[А-ЯЁ][а-яё]{1,30}\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.|[А-ЯЁ]\.\s*[А-ЯЁ]\.\s*[А-ЯЁ][а-яё]{1,30}"
)

# --- Биометрия ---

BIOMETRIC_TERMS_RE = re.compile(
    r"\b(?:отпечат\w+\s+пальц\w+|радужн\w+\s+оболочк\w+|"
    r"голосов\w+\s+(?:образ\w+|слепок)|"
    r"геометри\w+\s+лиц\w+|биометрическ\w+\s+(?:данн\w+|шаблон\w+))",
    re.IGNORECASE,
)

# --- Специальные категории ---

HEALTH_TERMS_RE = re.compile(
    r"\b(?:диагноз|анамнез|заболеван\w+|медицинск\w+\s+(?:карт\w+|справ\w+|заключен\w+|тайн\w+)|"
    r"группа\s+крови|резус|беремен\w+|инвалидност\w+|МКБ-?10|психиатр\w+|нарколог\w+|вич|спид|гепатит)",
    re.IGNORECASE,
)
RELIGION_TERMS_RE = re.compile(
    r"\b(?:православн\w+|католи[кч]\w*|мусульман\w+|иудаист\w+|буддист\w+)\b",
    re.IGNORECASE,
)
POLITICS_TERMS_RE = re.compile(
    r"\b(?:политическ\w+\s+(?:взгляд\w+|убежден\w+|принадлежн\w+|партия)|"
    r"член\s+парти\w+|партийн\w+\s+принадлеж\w+)",
    re.IGNORECASE,
)
RACE_TERMS_RE = re.compile(
    r"\b(?:этническ\w+\s+происхожден\w+)",
    re.IGNORECASE,
)

_SUSPICIOUS_NAMES_RE = re.compile(
    r"паспорт|снилс|инн|огрн|водит|справк|согласие|договор|анкет|резюме|"
    r"клиент|сотрудник|зарплат|physical|диагноз|банк|счет|карт|ca\d+_\d+",
    re.IGNORECASE
)