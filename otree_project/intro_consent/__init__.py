from otree.api import *
import json


doc = """
Welcome, consent, instructions, and practice round
"""


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

    practice_opened_ids = models.LongStringField(blank=True)
    practice_spent = models.IntegerField(initial=0)
    practice_click_order = models.LongStringField(blank=True)
    practice_time_seconds = models.FloatField(initial=0)

    practice_vote = models.StringField(
        choices=C.PRACTICE_VOTE_CHOICES,
        widget=widgets.RadioSelect,
        label='Practice vote: which candidate would you choose?',
        blank=True,
    )


class Welcome(Page):
    pass


class Consent(Page):
    form_model = 'player'
    form_fields = ['consent']

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


class PracticeIntro(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.consent == 'accept'


class PracticeNewsBoard(Page):
    form_model = 'player'
    form_fields = [
        'practice_opened_ids',
        'practice_spent',
        'practice_click_order',
        'practice_time_seconds',
    ]

    @staticmethod
    def is_displayed(player: Player):
        return player.consent == 'accept'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            news_items=C.PRACTICE_NEWS_ITEMS,
            click_cost=C.PRACTICE_CLICK_COST,
            budget_remaining=C.PRACTICE_BUDGET,
        )


class PracticeVote(Page):
    form_model = 'player'
    form_fields = ['practice_vote']

    @staticmethod
    def is_displayed(player: Player):
        return player.consent == 'accept'


class PracticeComplete(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.consent == 'accept'


page_sequence = [
    Welcome,
    Consent,
    Decline,
    Instructions,
    PracticeIntro,
    PracticeNewsBoard,
    PracticeVote,
    PracticeComplete,
]