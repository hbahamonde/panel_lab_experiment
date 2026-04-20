from otree.api import *
from datetime import datetime, timedelta


doc = """
Welcome, consent, instructions, and practice round
"""


def study_schedule(session):
    wave1 = datetime.fromisoformat(session.config['wave1_date']).date()
    wave2 = datetime.fromisoformat(session.config['wave2_date']).date()
    wave3 = datetime.fromisoformat(session.config['wave3_date']).date()

    window_days = session.config['wave_window_days']

    wave1_deadline = wave1 + timedelta(days=window_days - 1)
    wave2_deadline = wave2 + timedelta(days=window_days - 1)
    wave3_deadline = wave3 + timedelta(days=window_days - 1)

    return dict(
        wave_window_days=window_days,
        wave1_date_display=wave1.strftime('%B %d, %Y'),
        wave2_date_display=wave2.strftime('%B %d, %Y'),
        wave3_date_display=wave3.strftime('%B %d, %Y'),
        wave1_deadline_display=wave1_deadline.strftime('%B %d, %Y'),
        wave2_deadline_display=wave2_deadline.strftime('%B %d, %Y'),
        wave3_deadline_display=wave3_deadline.strftime('%B %d, %Y'),
    )


class C(BaseConstants):
    NAME_IN_URL = 'intro_consent'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1
    PRACTICE_CLICK_COST = 5
    PRACTICE_BUDGET = 15

    CONSENT_CHOICES = [
        ['accept', 'I agree to participate'],
        ['decline', 'I do not agree to participate'],
    ]

    PRACTICE_VOTE_CHOICES = [
        ['candidate_1', 'Candidate 1'],
        ['candidate_2', 'Candidate 2'],
    ]

    PRACTICE_NEWS_ITEMS = [
        dict(
            id='p1',
            title_excerpt='Economic pressures remain high',
            full_title='Economic pressures remain high',
            full_text='Recent reports suggest that economic pressures remain high and continue to affect public opinion.',
        ),
        dict(
            id='p2',
            title_excerpt='Candidate 1 supports rule-based reform',
            full_title='Candidate 1 supports rule-based reform',
            full_text='Candidate 1 argues that reform should proceed within democratic rules and institutional checks.',
        ),
        dict(
            id='p3',
            title_excerpt='Candidate 2 supports faster executive action',
            full_title='Candidate 2 supports faster executive action',
            full_text='Candidate 2 argues that faster executive action is needed to deliver targeted benefits quickly.',
        ),
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


page_sequence = [
    Welcome,
    Consent,
    Decline,
    Instructions,
]