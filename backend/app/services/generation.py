from typing import Protocol
from app.schemas import Briefing, Channel, GeneratedText, Product
class GenerationService(Protocol):
    def generate(self, briefing: Briefing, product: Product) -> list[GeneratedText]: ...
class MockGenerationService:
    def generate(self, briefing: Briefing, product: Product) -> list[GeneratedText]:
        titles = {Channel.FEED: 'Conheça {name}', Channel.STORY: 'Seu próximo cuidado: {name}', Channel.BANNER: 'Descubra {name}'}
        return [GeneratedText(channel=channel, title=titles[channel].format(name=product.name), subtitle=product.description, cta='Conheça o produto') for channel in briefing.channels]
