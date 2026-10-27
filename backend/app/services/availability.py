"""Safe provider diagnostics, process-local quota cooldowns and explicit demo offers."""
import hashlib
import json
from threading import RLock
from time import monotonic
from uuid import uuid4


TEXT_FALLBACK_CODES = frozenset({'GENERATION_RATE_LIMIT', 'GENERATION_QUOTA_EXCEEDED',
    'GENERATION_UNAVAILABLE', 'GENERATION_TIMEOUT'})
IMAGE_FALLBACK_CODES = frozenset({'IMAGE_RATE_LIMIT', 'IMAGE_QUOTA_EXCEEDED',
    'IMAGE_UNAVAILABLE', 'IMAGE_TIMEOUT', 'IMAGE_PROVIDER_UNCONFIGURED'})


def daily_quota(payload):
    # Inspect only for classification. Never forward upstream messages to users/logs.
    text = json.dumps(payload, default=lambda _: '', ensure_ascii=True).lower()
    return any(word in text for word in ('insufficient_quota', 'perday', 'per_day',
        'daily', 'quota_exceeded', 'billing_hard_limit'))


class QuotaCooldown:
    def __init__(self, prefix, error_type):
        self.prefix, self.error_type = prefix, error_type
        self.until, self.code, self.message = 0, '', ''

    def check(self):
        remaining = self.until - monotonic()
        if remaining > 0:
            error = self.error_type(self.code, self.message)
            error.retry_after_seconds = max(1, int(remaining) + 1)
            raise error

    def limit(self, payload=None, retry_after=None):
        exhausted = daily_quota(payload)
        try:
            delay = min(86400, max(1, int(retry_after or 60)))
        except (ValueError, TypeError):
            delay = 60
        if exhausted:
            delay = 86400
        self.until = monotonic() + delay
        self.code = self.prefix + ('_QUOTA_EXCEEDED' if exhausted else '_RATE_LIMIT')
        self.message = ('Cota do provedor esgotada. A geração com IA está temporariamente indisponível.'
            if exhausted else 'Limite de requisições do provedor atingido. Tente novamente mais tarde.')
        error = self.error_type(self.code, self.message)
        error.retry_after_seconds = delay
        return error


class DemoOffers:
    """A short-lived offer binds explicit consent to the exact failed request.

    No credentials or briefing text are retained. Offers expire after 30 minutes
    or an app restart; the bounded registry is sufficient for the local MVP.
    """
    def __init__(self):
        self.entries = {}
        self.lock = RLock()

    @staticmethod
    def digest(briefing, product, rules):
        return hashlib.sha256(json.dumps([briefing.model_dump(mode='json'),
            product.model_dump(mode='json'), rules], sort_keys=True).encode()).hexdigest()

    def issue(self, briefing, product, rules, code):
        with self.lock:
            self.entries = {key: entry for key, entry in self.entries.items() if entry['until'] > monotonic()}
            if len(self.entries) >= 256:
                self.entries.pop(next(iter(self.entries)))
            token = str(uuid4())
            self.entries[token] = dict(digest=self.digest(briefing, product, rules),
                until=monotonic() + 1800, code=code, campaign_id=None)
            return token

    def get(self, token, briefing, product, rules):
        entry = self.entries.get(token)
        if not entry or entry['until'] < monotonic() or entry['digest'] != self.digest(briefing, product, rules):
            return None
        return entry
