import time

from otree.api import *


doc = """
Consent and instructions for the one-session interactive laboratory experiment.
"""


def study_details(session):
    return dict(
        participation_fee=f"€{session.config['participation_fee']:.2f}",
        bonus_cap=f"€{session.config['performance_bonus_cap']:.2f}",
    )


class C(BaseConstants):
    NAME_IN_URL = 'study_start'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    CONSENT_FORM_VERSION = '2026-08-31-v2'
    CONSENT_CHOICES = [[
        'accept',
        'I have read the information above and agree to take part in this study.',
    ]]


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    consent = models.StringField(
        choices=C.CONSENT_CHOICES,
        widget=widgets.RadioSelect,
        label='Please confirm your participation:',
    )
    consent_form_version = models.StringField(blank=True)
    consent_recorded_at = models.FloatField()


class Consent(Page):
    form_model = 'player'
    form_fields = ['consent']

    @staticmethod
    def vars_for_template(player: Player):
        return study_details(player.session)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.consent_form_version = C.CONSENT_FORM_VERSION
        player.consent_recorded_at = time.time()
        player.participant.vars['consent'] = player.consent
        player.participant.vars['consent_form_version'] = player.consent_form_version
        player.participant.vars['consent_recorded_at'] = player.consent_recorded_at


class Instructions(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.consent == 'accept'

    @staticmethod
    def vars_for_template(player: Player):
        return study_details(player.session)


page_sequence = [Consent, Instructions]
