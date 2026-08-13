from otree.api import *


doc = """
Consent and instructions for the one-session interactive laboratory experiment.
"""


def study_details(session):
    return dict(
        participation_fee=session.config['participation_fee'],
        conversion=f"€{session.config['real_world_currency_per_point']:.2f}",
    )


class C(BaseConstants):
    NAME_IN_URL = 'study_start'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    CONSENT_CHOICES = [['accept', 'I agree to participate']]


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    consent = models.StringField(
        choices=C.CONSENT_CHOICES,
        widget=widgets.RadioSelect,
        label='Do you agree to participate in this study?',
    )


class Welcome(Page):
    @staticmethod
    def vars_for_template(player: Player):
        return study_details(player.session)


class Consent(Page):
    form_model = 'player'
    form_fields = ['consent']

    @staticmethod
    def vars_for_template(player: Player):
        return study_details(player.session)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.participant.vars['consent'] = player.consent


class Instructions(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.consent == 'accept'

    @staticmethod
    def vars_for_template(player: Player):
        return study_details(player.session)


page_sequence = [Welcome, Consent, Instructions]
