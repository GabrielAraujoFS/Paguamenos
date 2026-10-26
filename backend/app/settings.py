"""Environment-only provider configuration; no dotenv or credentials in files."""
import os
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator


class GenerationConfig(BaseModel):
    provider: Literal['mock', 'gemini'] = 'mock'
    api_key: SecretStr = Field(default=SecretStr(''), repr=False)
    model: str = Field(default='gemini-3.5-flash-lite', pattern=r'^gemini-[a-zA-Z0-9.-]+$')
    timeout_seconds: float = Field(default=20, gt=0, le=120)
    visual_max_attempts: int = Field(default=2, ge=1, le=3)

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
                       timeout_seconds=os.getenv('GENERATION_TIMEOUT_SECONDS', '20'),
                       visual_max_attempts=os.getenv('VISUAL_MAX_ATTEMPTS', '2'))
        except ValueError:
            raise ValueError('Configuração Gemini inválida: verifique modelo e timeout.') from None


class ImageGenerationConfig(BaseModel):
    provider: Literal['disabled', 'google', 'openai', 'mock'] = 'disabled'
    api_key: SecretStr = Field(default=SecretStr(''), repr=False)
    model: Literal['gemini-3.1-flash-image', 'gemini-3.1-flash-lite-image', 'gpt-image-1-mini'] = 'gemini-3.1-flash-image'
    image_size: Literal['1K', '2K'] = '2K'
    timeout_seconds: float = Field(default=120, gt=0, le=300)
    max_attempts: int = Field(default=2, ge=1, le=2)
    mock_image_path: str | None = None

    @model_validator(mode='after')
    def supported_size(self):
        if self.provider == 'google' and self.model not in ('gemini-3.1-flash-image', 'gemini-3.1-flash-lite-image'):
            raise ValueError('O provedor Google exige um modelo Gemini de imagem.')
        if self.provider == 'google' and self.model == 'gemini-3.1-flash-lite-image' and self.image_size != '1K':
            raise ValueError('O modelo Flash Lite Image suporta somente 1K.')
        if self.provider == 'openai' and self.model != 'gpt-image-1-mini':
            raise ValueError('O provedor OpenAI deve usar gpt-image-1-mini.')
        return self

    @classmethod
    def from_environment(cls):
        provider = os.getenv('IMAGE_GENERATION_PROVIDER', 'disabled').strip().lower()
        if provider == 'disabled':
            return cls()
        if provider not in ('google', 'openai', 'mock'):
            raise ValueError('IMAGE_GENERATION_PROVIDER deve ser disabled, google, openai ou mock.')
        if provider == 'mock':
            path = os.getenv('IMAGE_MOCK_PATH', '').strip()
            if not path:
                raise ValueError('IMAGE_MOCK_PATH é obrigatória para geração local de fundos.')
            return cls(provider='mock', mock_image_path=path)
        key_name = 'OPENAI_API_KEY' if provider == 'openai' else 'GEMINI_API_KEY'
        key = os.getenv(key_name, '').strip()
        if not key:
            raise ValueError(f'{key_name} é obrigatória para geração de fundos {provider}.')
        try:
            config = cls(provider=provider, api_key=SecretStr(key),
                model='gpt-image-1-mini' if provider == 'openai' else os.getenv('IMAGE_MODEL', 'gemini-3.1-flash-image'),
                image_size=os.getenv('IMAGE_SIZE', '2K'),
                timeout_seconds=os.getenv('IMAGE_TIMEOUT_SECONDS', '120'),
                max_attempts=os.getenv('IMAGE_MAX_ATTEMPTS', '2'))
        except ValueError:
            raise ValueError('Configuração de imagem inválida.') from None
        return config
