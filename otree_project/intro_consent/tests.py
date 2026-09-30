from otree.api import Bot, expect

from . import *


class PlayerBot(Bot):
    def play_round(self):
        yield Consent, dict(consent='accept')
        expect(self.player.consent, 'accept')
        yield Instructions
