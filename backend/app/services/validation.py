import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from app.schemas import Severity, ValidationResult
from app.schemas.configuration import parse_rules


TEXT_FIELDS = ('title', 'subtitle', 'cta', 'disclaimer')
CORE_FIELDS = (*TEXT_FIELDS, 'product_id', 'product_name', 'price', 'authorized_offer')


def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKD', text.casefold())
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


def expression_pattern(expression: str):
    # Whole expressions: "cura" does not match "procura". Accents, case and
    # repeated whitespace do not affect comparisons; punctuation is preserved.
    return re.compile(r'(?<!\w)' + re.escape(normalize(expression)) + r'(?!\w)')


def contains(text, expression):
    return bool(expression_pattern(expression).search(normalize(str(text or ''))))


def fingerprint(content, product, rules, visual_evidence=None):
    payload = dict(
        content=content,
        product=product.model_dump(mode='json') if product else None,
        rules=parse_rules(rules).model_dump(mode='json'),
        visual_evidence=visual_evidence or {},
    )
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def text_commercial_checks(text, product, rules):
    """Bounded syntax checks, not semantic verification of arbitrary offers."""
    normalized = normalize(str(text or ''))
    original = normalized
    if product is not None:
        # Only the complete catalog offer authorizes its amounts and conditions.
        normalized = expression_pattern(product.authorized_offer).sub('', normalized)
    # BRL with exactly two decimals, optionally grouped thousands.
    amount = r'(?:[1-9]\d{0,2}(?:\.\d{3})+|\d+),\d{2}(?!\w|[.,]\d|\s*\d)'
    matches = list(re.finditer(r'r\$\s*(' + amount + r')', normalized))
    currency_count = normalized.count('r$')
    prices_ok = len(matches) == currency_count
    if rules.commercial.text_price_policy == 'forbid':
        prices_ok = not re.search(r'r\$|\breais\b|\bbrl\b|\$|€|£', original)
    elif matches:
        prices_ok = prices_ok and product is not None and all(
            Decimal(match.group(1).replace('.', '').replace(',', '.')) == product.price
            for match in matches
        )
    # Flag unsupported currency notation rather than treating it as verified.
    unsupported_currency = re.search(r'\breais\b|\bbrl\b|\bus\$|\$|€|£', normalized.replace('r$', ''))
    prices_ok = prices_ok and not unsupported_currency
    offer_claim = (
        any(contains(normalized, marker) for marker in rules.commercial.offer_markers)
        or re.search(r'\d+(?:[.,]\d+)?\s*%|\bleve\s+\d|\bpague\s+\d|\b\d+\s+por\b', normalized)
    )
    return bool(prices_ok), not bool(offer_claim)


def validate_content(content, product, rules):
    rules = parse_rules(rules)
    results = []

    def check(code, field, passed, message, severity=Severity.CRITICAL):
        prefix = 'OK: ' if passed else 'Falha: '
        results.append(ValidationResult(
            rule_code=code, severity=severity, field=field,
            passed=bool(passed), message=prefix + message,
        ))

    check('PRODUCT_EXISTS', 'product_id', product is not None, 'Produto deve existir no catálogo.')
    try:
        price = Decimal(str(content.get('price')))
        matches = price.is_finite() and product is not None and price == product.price
    except (InvalidOperation, ValueError, TypeError):
        matches = False
    check('PRICE_MATCH', 'price', matches, 'Preço deve corresponder ao catálogo.')
    for field, attribute, code in [
        ('product_name', 'name', 'PRODUCT_NAME_MATCH'),
        ('authorized_offer', 'authorized_offer', 'OFFER_MATCH'),
    ]:
        check(code, field, product is not None and content.get(field) == getattr(product, attribute),
              'O campo deve reproduzir o valor autorizado no catálogo.')
    for field in dict.fromkeys([*CORE_FIELDS, *rules.required_fields]):
        value = content.get(field)
        check('REQUIRED_FIELD', field, value is not None and bool(str(value).strip()), 'Campo obrigatório.')
    channel = content.get('channel')
    check('CHANNEL_ALLOWED', 'channel', channel in rules.allowed_channels, 'Canal deve ser permitido.')
    for field, limit in rules.character_limits.get(channel, {}).items():
        check('CHARACTER_LIMIT', field, len(str(content.get(field) or '')) <= limit,
              f'Limite de {limit} caracteres.', rules.severities.get('CHARACTER_LIMIT', Severity.CRITICAL))
    for field, expressions in rules.required_information.items():
        for expression in expressions:
            check('REQUIRED_INFORMATION', field, contains(content.get(field), expression),
                  f'Inclua a informação obrigatória: {expression}',
                  rules.severities.get('REQUIRED_INFORMATION', Severity.CRITICAL))
    for code, expressions, required in [
        ('REQUIRED_EXPRESSION', rules.required_expressions, True),
        ('FORBIDDEN_EXPRESSION', rules.forbidden_expressions, False),
    ]:
        for rule in expressions:
            if channel not in rule.channels:
                continue
            # A required expression may occur in any one configured field.
            # Report a forbidden expression separately for each configured field.
            if required:
                check(code, ','.join(rule.fields), any(contains(content.get(f), rule.expression) for f in rule.fields),
                      f'Inclua em um dos campos indicados: {rule.expression}', rule.severity)
            else:
                for field in rule.fields:
                    check(code, field, not contains(content.get(field), rule.expression),
                          f'O campo não deve conter: {rule.expression}', rule.severity)
    for field in TEXT_FIELDS:
        prices_ok, offers_ok = text_commercial_checks(content.get(field), product, rules)
        check('TEXT_PRICE_MATCH', field, prices_ok,
              'Use preço em R$ 0,00 igual ao catálogo, ou copie a oferta autorizada completa; respeite a política de preços em texto.')
        check('TEXT_OFFER_MATCH', field, offers_ok,
              'Condições comerciais reconhecidas exigem a oferta autorizada completa do catálogo.')
    if product is not None and any(term in normalize(product.category) for term in ('farmac', 'medicamento')):
        authorized = f'{product.description} {product.authorized_offer}'
        for field in ('title', 'subtitle', 'cta'):
            for claim in ('cura', 'trata', 'previne', 'eficacia', 'resultado garantido'):
                if contains(content.get(field), claim) and not contains(authorized, claim):
                    check('HEALTH_CLAIM_REVIEW', field, False,
                          f'Alegação de saúde ou eficácia sem autorização explícita: {claim}. Revisão regulatória humana necessária.',
                          Severity.WARNING)
    return results


def successful(results):
    return all(r.passed for r in results if r.severity == Severity.CRITICAL)
