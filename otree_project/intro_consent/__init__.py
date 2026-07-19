from datetime import datetime, timedelta

from otree.api import *


doc = """
Consent and instructions for the two-wave interactive laboratory experiment.
"""


def study_schedule(session):
    wave1 = datetime.fromisoformat(session.config['wave1_date']).date()
    wave2 = datetime.fromisoformat(session.config['wave2_date']).date()
    window_days = session.config['wave_window_days']

    return dict(
        wave_window_days=window_days,
        wave1_date_display=wave1.strftime('%B %d, %Y'),
        wave2_date_display=wave2.strftime('%B %d, %Y'),
        wave1_deadline_display=(wave1 + timedelta(days=window_days - 1)).strftime('%B %d, %Y'),
        wave2_deadline_display=(wave2 + timedelta(days=window_days - 1)).strftime('%B %d, %Y'),
        participation_fee=session.config['participation_fee'],
        conversion=session.config['real_world_currency_per_point'],
    )


class C(BaseConstants):
    NAME_IN_URL = 'intro_consent'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    CONSENT_CHOICES = [
        ['accept', 'I agree to participate'],
        ['decline', 'I do not agree to participate'],
    ]


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
        return study_schedule(player.session)


class Consent(Page):
    form_model = 'player'
    form_fields = ['consent']

    @staticmethod
    def vars_for_template(player: Player):
        return study_schedule(player.session)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.participant.vars['consent'] = player.consent


class Decline(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.consent == 'decline'


class Instructions(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.consent == 'accept'

    @staticmethod
    def vars_for_template(player: Player):
        return study_schedule(player.session)


page_sequence = [Welcome, Consent, Decline, Instructions]
