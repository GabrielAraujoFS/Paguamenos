"""Environment-only provider configuration; no dotenv or credentials in files."""
import os
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class GenerationConfig(BaseModel):
    provider: Literal['mock', 'gemini'] = 'mock'
    api_key: SecretStr = Field(default=SecretStr(''), repr=False)
    model: str = Field(default='gemini-3.5-flash-lite', pattern=r'^gemini-[a-zA-Z0-9.-]+$')
    timeout_seconds: float = Field(default=20, gt=0, le=120)

    @classmethod
    def from_environment(cls):
        provider = os.getenv('GENERATION_PROVIDER', 'mock').strip().lower()
        # Mock must work independently of unused Gemini settings.
        if provider == 'mock':
            return cls()
        if provider != 'gemini':
            raise ValueError('GENERATION_PROVIDER deve ser mock ou gemini.')
        key = os.getenv('GEMINI_API_KEY', '').strip()
        if not key:
            raise ValueError('GEMINI_API_KEY é obrigatória para GENERATION_PROVIDER=gemini.')
        try:
            return cls(provider=provider, api_key=SecretStr(key),
                       model=os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite'),
                       timeout_seconds=os.getenv('GENERATION_TIMEOUT_SECONDS', '20'))
        except ValueError:
            raise ValueError('Configuração Gemini inválida: verifique modelo e timeout.') from None
