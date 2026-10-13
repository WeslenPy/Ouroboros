"""Tratamento de CPF (LGPD).

- CPF de político é ligado por HMAC com chave secreta; o número nunca é gravado.
- CPF de terceiros (fornecedor pessoa física) é exibido mascarado, no padrão dos portais do governo.
"""

import hashlib
import hmac
import re

from ouroboros.core.settings import get_settings

_NAO_DIGITO = re.compile(r"\D")


def digits(value: str | None) -> str:
    return _NAO_DIGITO.sub("", value or "")


def cpf_hmac(cpf: str | None) -> str | None:
    """HMAC-SHA256 do CPF (só dígitos). None se não for um CPF plausível."""
    d = digits(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return None
    key = get_settings().hash_key.get_secret_value().encode()
    return hmac.new(key, d.encode(), hashlib.sha256).hexdigest()


def mask_cpf(cpf: str) -> str:
    """12345678901 -> ***.456.789-**"""
    d = digits(cpf)
    return f"***.{d[3:6]}.{d[6:9]}-**"


def documento_publico(value: str | None) -> tuple[str | None, str | None]:
    """Documento de fornecedor pronto para exibir: (documento, tipo 'pj'|'pf').

    CNPJ sai completo (dado público). CPF sai mascarado.
    """
    d = digits(value)
    if len(d) == 14:
        return d, "pj"
    if len(d) == 11:
        return mask_cpf(d), "pf"
    return (d or None), None
