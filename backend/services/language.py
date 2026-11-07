import re
import unicodedata

LANGUAGE_NAMES = {
    "ar": "Arabic",
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "gu": "Gujarati",
    "hi": "Hindi",
    "ja": "Japanese",
    "km": "Khmer",
    "lo": "Lao",
    "my": "Burmese",
    "pt": "Portuguese",
    "th": "Thai",
    "zh": "Chinese",
}

SCRIPT_LANGUAGES = (
    (0x0900, 0x097F, "hi"),
    (0x0A80, 0x0AFF, "gu"),
    (0x0600, 0x06FF, "ar"),
    (0x0750, 0x077F, "ar"),
    (0x4E00, 0x9FFF, "zh"),
    (0x3400, 0x4DBF, "zh"),
    (0x3040, 0x30FF, "ja"),
    (0x0E00, 0x0E7F, "th"),
    (0x0E80, 0x0EFF, "lo"),
    (0x1780, 0x17FF, "km"),
    (0x1000, 0x109F, "my"),
)

NO_SPACE_LANGUAGES = {"ja", "zh", "th", "lo", "km", "my"}
LATIN_STOPWORDS = {
    "de": {"der", "die", "das", "und", "ist", "ein", "mit", "wie", "für"},
    "en": {"the", "and", "is", "in", "to", "of", "a", "how", "what"},
    "es": {"el", "la", "los", "las", "y", "es", "de", "en", "que", "cómo"},
    "fr": {"le", "la", "les", "et", "est", "de", "des", "en", "que", "comment"},
    "pt": {"o", "a", "os", "as", "e", "é", "de", "em", "que", "como"},
}
NORMALIZED_STOPWORDS = {
    language: {
        unicodedata.normalize("NFKD", word)
        .encode("ascii", "ignore")
        .decode("ascii")
        for word in stopwords
    }
    for language, stopwords in LATIN_STOPWORDS.items()
}
LATIN_LANGUAGES = ("en", "es", "fr", "de", "pt")
WORD_PATTERN = re.compile(r"[\w\u0900-\u0DFF\u0E00-\u0EFF\u1000-\u109F\u1780-\u17FF\u0600-\u06FF\u0750-\u077F]+", re.UNICODE)
INVISIBLE_PATTERN = re.compile(
    "[\ufeff\u200b\u200e\u200f\u202a-\u202e\u2060\u2066-\u2069]"
)
LANGUAGE_CODE_ALIASES = {
    "ara": "ar",
    "ar": "ar",
    "deu": "de",
    "ger": "de",
    "de": "de",
    "eng": "en",
    "en": "en",
    "spa": "es",
    "es": "es",
    "fra": "fr",
    "fre": "fr",
    "fr": "fr",
    "guj": "gu",
    "gu": "gu",
    "hin": "hi",
    "hi": "hi",
    "jpn": "ja",
    "ja": "ja",
    "khm": "km",
    "km": "km",
    "lao": "lo",
    "lo": "lo",
    "mya": "my",
    "bur": "my",
    "my": "my",
    "por": "pt",
    "pt": "pt",
    "tha": "th",
    "th": "th",
    "zho": "zh",
    "chi": "zh",
    "zh": "zh",
}


def normalize_text(value: str, *, strip_latin_accents: bool = False) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    if strip_latin_accents:
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFD", normalized)
            if not unicodedata.combining(character)
        )
    return normalized.casefold()


def normalize_quote(value: str) -> str:
    return " ".join(
        normalize_text(INVISIBLE_PATTERN.sub("", value)).split()
    ).strip()


def _script_language(value: str) -> str | None:
    if any(0x3040 <= ord(character) <= 0x30FF for character in value):
        return "ja"
    counts: dict[str, int] = {}
    for character in value:
        point = ord(character)
        for start, end, language in SCRIPT_LANGUAGES:
            if start <= point <= end:
                counts[language] = counts.get(language, 0) + 1
                break
    if not counts:
        return None
    return max(counts, key=counts.get)


def detect_language(value: str) -> str:
    if not value.strip():
        return "und"
    script_language = _script_language(value)
    if script_language:
        return script_language

    tokens = [
        normalize_text(token, strip_latin_accents=True)
        for token in WORD_PATTERN.findall(value)
    ]
    if len(tokens) < 2:
        return "en" if tokens else "und"
    scores = {
        language: sum(token in NORMALIZED_STOPWORDS[language] for token in tokens)
        for language in LATIN_STOPWORDS
    }
    best_language = max(scores, key=scores.get)
    if scores[best_language]:
        return best_language
    return "en"


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.split("-", 1)[0].lower(), code or "Unknown")


def language_code(value: str) -> str:
    return LANGUAGE_CODE_ALIASES.get(value.split("-", 1)[0].lower(), "und")


def word_count(value: str, language: str = "und") -> int:
    if language == "und":
        language = detect_language(value)
    if language in NO_SPACE_LANGUAGES:
        return (len(value.strip()) + 1) // 2
    return len(value.split())


def tokens(value: str, language: str = "und") -> list[str]:
    normalized = normalize_text(
        value,
        strip_latin_accents=language in {"en", "es", "fr", "de", "pt"},
    )
    if language in NO_SPACE_LANGUAGES:
        return [
            f"{left}{right}"
            for run in re.findall(r"[\u2e80-\u9fff\u3040-\u30ff\u0e00-\u0eff\u1000-\u109f\u1780-\u17ff]+", normalized)
            for left, right in zip(run, run[1:])
        ]
    stopwords = NORMALIZED_STOPWORDS.get(language, set())
    return [
        token
        for token in WORD_PATTERN.findall(normalized)
        if token not in stopwords
    ]


def estimate_tokens(value: str) -> int:
    counts: dict[str, int] = {}
    for character in value:
        point = ord(character)
        script = next(
            (
                language
                for start, end, language in SCRIPT_LANGUAGES
                if start <= point <= end
            ),
            "latin",
        )
        counts[script] = counts.get(script, 0) + 1
    rates = {
        "latin": 4,
        "hi": 2,
        "gu": 2,
        "ar": 2,
        "zh": 1.5,
        "ja": 1.5,
        "th": 2,
        "lo": 2,
        "km": 2,
        "my": 2,
    }
    return sum(
        int((characters + rates[script] - 1) // rates[script])
        for script, characters in counts.items()
    )
