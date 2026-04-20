from otree.api import *
import json
from datetime import datetime, date, timedelta


doc = """
Wave 3: final campaign news board and vote
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


def wave_status(player, wave_key):
    if not player.session.config.get('enable_wave_gates', False):
        return 'open'

    wave_date = datetime.fromisoformat(player.session.config[wave_key]).date()
    window_days = player.session.config['wave_window_days']
    wave_deadline = wave_date + timedelta(days=window_days - 1)
    today = date.today()

    if today < wave_date:
        return 'early'
    if today > wave_deadline:
        return 'late'
    return 'open'


class C(BaseConstants):
    NAME_IN_URL = 'wave3_election'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1
    NEWS_CLICK_COST = 5

    CANDIDATE_CHOICES = [
        ['candidate_1', 'Candidate 1'],
        ['candidate_2', 'Candidate 2'],
    ]

    NEWS_ITEMS = [
        dict(
            id='w3_n1',
            title_excerpt='Late campaign analysts warn election may reshape institutional future',
            full_title='Late campaign analysts warn election may reshape institutional future',
            full_text=(
                'Observers now describe the election as a high-stakes choice about how political authority '
                'should be exercised. Several analysts argue that the winning candidate could reshape the role '
                'of oversight, legality, and institutional restraint for years to come.'
            ),
            category='institutions',
        ),
        dict(
            id='w3_n2',
            title_excerpt='Candidate 1 closing message stresses rules, oversight, and durable reform',
            full_title='Candidate 1 closing message stresses rules, oversight, and durable reform',
            full_text=(
                'In the final stage of the campaign, Candidate 1 argues that major reforms should remain '
                'anchored in democratic procedures. The campaign emphasizes rule-based reform, institutional '
                'credibility, and the long-term value of preserving oversight.'
            ),
            category='candidate',
        ),
        dict(
            id='w3_n3',
            title_excerpt='Candidate 2 closing message stresses speed, decisiveness, and targeted benefits',
            full_title='Candidate 2 closing message stresses speed, decisiveness, and targeted benefits',
            full_text=(
                'Candidate 2 closes the campaign by arguing that voters cannot afford delay. The campaign '
                'promises rapid, targeted benefits and forceful action, while again signaling willingness to '
                'bypass some institutional constraints if necessary.'
            ),
            category='candidate',
        ),
        dict(
            id='w3_n4',
            title_excerpt='Editorial questions whether procedural limits are a luxury in times of threat',
            full_title='Editorial questions whether procedural limits are a luxury in times of threat',
            full_text=(
                'A widely discussed editorial asks whether procedural limits and checks remain appropriate '
                'when citizens perceive urgent threats. Supporters see this as realism; critics argue it '
                'normalizes dangerous shortcuts.'
            ),
            category='commentary',
        ),
        dict(
            id='w3_n5',
            title_excerpt='Final voter brief compares immediate gains against long-run institutional risks',
            full_title='Final voter brief compares immediate gains against long-run institutional risks',
            full_text=(
                'A final campaign brief presents the election as a tradeoff between immediate policy delivery '
                'and long-run institutional protections. It emphasizes that the choice is not only about issues, '
                'but also about the acceptable boundaries of executive power.'
            ),
            category='summary',
        ),
    ]


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    wave3_news_opened_ids = models.LongStringField(blank=True)
    wave3_news_spent = models.IntegerField(initial=0)
    wave3_news_click_order = models.LongStringField(blank=True)
    wave3_news_time_seconds = models.FloatField(initial=0)

    final_vote = models.StringField(
        choices=C.CANDIDATE_CHOICES,
        widget=widgets.RadioSelect,
        label='Which candidate do you vote for?',
    )


class Wave3LockedEarly(Page):
    @staticmethod
    def is_displayed(player: Player):
        return wave_status(player, 'wave3_date') == 'early'

    @staticmethod
    def vars_for_template(player: Player):
        return study_schedule(player.session)


class Wave3LockedLate(Page):
    @staticmethod
    def is_displayed(player: Player):
        return wave_status(player, 'wave3_date') == 'late'

    @staticmethod
    def vars_for_template(player: Player):
        return study_schedule(player.session)


class Wave3Intro(Page):
    pass


class Wave3NewsBoard(Page):
    form_model = 'player'
    form_fields = [
        'wave3_news_opened_ids',
        'wave3_news_spent',
        'wave3_news_click_order',
        'wave3_news_time_seconds',
    ]

    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            news_items=C.NEWS_ITEMS,
            news_items_json=json.dumps(C.NEWS_ITEMS),
            click_cost=C.NEWS_CLICK_COST,
            budget_remaining=player.participant.vars.get('news_budget_remaining', 0),
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        opened_ids_raw = player.wave3_news_opened_ids or ''
        opened_ids = [x for x in opened_ids_raw.split(',') if x]

        previous_all = player.participant.vars.get('all_opened_news_ids', [])
        merged = previous_all.copy()
        for item_id in opened_ids:
            if item_id not in merged:
                merged.append(item_id)

        player.participant.vars['all_opened_news_ids'] = merged
        player.participant.vars['wave3_news_opened_ids'] = opened_ids
        player.participant.vars['wave3_news_click_order'] = player.wave3_news_click_order
        player.participant.vars['wave3_news_time_seconds'] = player.wave3_news_time_seconds
        player.participant.vars['news_spent_total'] = player.participant.vars.get('news_spent_total', 0) + player.wave3_news_spent
        player.participant.vars['news_budget_remaining'] = player.participant.vars.get('news_budget_remaining', 0) - player.wave3_news_spent


class FinalVote(Page):
    form_model = 'player'
    form_fields = ['final_vote']

    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            budget_remaining=player.participant.vars.get('news_budget_remaining', 0),
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.participant.vars['final_vote'] = player.final_vote


class VoteComplete(Page):
    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            final_vote_label=dict(C.CANDIDATE_CHOICES).get(player.final_vote, player.final_vote),
            budget_remaining=player.participant.vars.get('news_budget_remaining', 0),
            total_spent=player.participant.vars.get('news_spent_total', 0),
        )


page_sequence = [
    Wave3LockedEarly,
    Wave3LockedLate,
    Wave3Intro,
    Wave3NewsBoard,
    FinalVote,
    VoteComplete,
]