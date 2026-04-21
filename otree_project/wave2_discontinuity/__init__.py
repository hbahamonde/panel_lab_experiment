from otree.api import *
import random
import json
from datetime import datetime, date, timedelta


doc = """
Wave 2: randomized discontinuity, post-treatment mechanisms, and news board
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
        gates_enabled=session.config.get('enable_wave_gates', False),
    )

def shuffled_items_once(player, field_name, items):
    stored_order = player.field_maybe_none(field_name)

    if stored_order:
        stored_ids = [x for x in stored_order.split(',') if x]
        item_map = {item['id']: item for item in items}
        return [item_map[item_id] for item_id in stored_ids if item_id in item_map]

    shuffled = random.sample(items, len(items))
    setattr(player, field_name, ','.join(item['id'] for item in shuffled))
    return shuffled

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
    NAME_IN_URL = 'wave2_discontinuity'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    TREATMENT_REVERSAL = 'reversal'
    TREATMENT_CONTROL = 'control'
    NEWS_CLICK_COST = 5

    CAPACITY_CHOICES = [
        [1, 'Very low'],
        [2, 'Low'],
        [3, 'Moderate'],
        [4, 'High'],
        [5, 'Very high'],
    ]

    RISK_CHOICES = [
        [1, 'Very low'],
        [2, 'Low'],
        [3, 'Moderate'],
        [4, 'High'],
        [5, 'Very high'],
    ]

    NEWS_ITEMS_COMMON = [
        dict(
            id='w2_n1',
            title_excerpt='Analysts debate whether recent improvements can last',
            full_title='Analysts debate whether recent improvements can last',
            full_text=(
                'Political analysts disagree on whether the latest developments reflect a durable shift '
                'or only a temporary fluctuation. Some argue that campaign promises now look more credible; '
                'others warn that the apparent change may be fragile.'
            ),
            category='environment',
        ),
        dict(
            id='w2_n2',
            title_excerpt='Candidate 1 repeats commitment to rule-based reform',
            full_title='Candidate 1 repeats commitment to rule-based reform',
            full_text=(
                'Candidate 1 continues to argue that reforms should proceed through ordinary democratic '
                'procedures, with oversight and institutional checks preserved even under pressure.'
            ),
            category='candidate',
        ),
        dict(
            id='w2_n3',
            title_excerpt='Candidate 2 insists strong executive action is still necessary',
            full_title='Candidate 2 insists strong executive action is still necessary',
            full_text=(
                'Candidate 2 argues that decisive action remains essential and that institutional constraints '
                'still prevent rapid and targeted policy delivery.'
            ),
            category='candidate',
        ),
    ]

    NEWS_ITEMS_REVERSAL = [
        dict(
            id='w2_r1',
            title_excerpt='New reports suggest inequality and crime are easing',
            full_title='New reports suggest inequality and crime are easing',
            full_text=(
                'Fresh indicators suggest that inequality and crime have both softened relative to the earlier '
                'campaign environment. The sense of immediate emergency appears weaker than before.'
            ),
            category='environment',
        ),
        dict(
            id='w2_r2',
            title_excerpt='Institutions appear more capable and enforcement more credible',
            full_title='Institutions appear more capable and enforcement more credible',
            full_text=(
                'Recent developments suggest that institutions are now functioning more effectively, with '
                'improved enforcement and greater administrative capacity than in the initial campaign stage.'
            ),
            category='institutions',
        ),
    ]

    NEWS_ITEMS_CONTROL = [
        dict(
            id='w2_c1',
            title_excerpt='High inequality and crime continue without visible relief',
            full_title='High inequality and crime continue without visible relief',
            full_text=(
                'Updated reports indicate that the earlier threat environment remains largely unchanged. '
                'Inequality and crime continue to weigh heavily on public perceptions of government performance.'
            ),
            category='environment',
        ),
        dict(
            id='w2_c2',
            title_excerpt='Institutions still criticized as weak and ineffective',
            full_title='Institutions still criticized as weak and ineffective',
            full_text=(
                'Observers continue to describe institutions as fragile, slow, and poorly equipped to manage '
                'current pressures through ordinary democratic channels.'
            ),
            category='institutions',
        ),
    ]


class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    for player in subsession.get_players():
        if 'treatment' not in player.participant.vars:
            player.participant.vars['treatment'] = random.choice(
                [C.TREATMENT_REVERSAL, C.TREATMENT_CONTROL]
            )


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    treatment = models.StringField()

    inst_capacity_post = models.IntegerField(
        label='Given the current situation, how capable are institutions of solving major problems without breaking democratic rules?',
        choices=C.CAPACITY_CHOICES,
        widget=widgets.RadioSelect,
    )

    collapse_risk_post = models.IntegerField(
        label='Given the current situation, how high is the risk of democratic collapse?',
        choices=C.RISK_CHOICES,
        widget=widgets.RadioSelect,
    )
    wave2_news_display_order = models.LongStringField(blank=True)
    wave2_news_opened_ids = models.LongStringField(blank=True)
    wave2_news_spent = models.IntegerField(initial=0)
    wave2_news_click_order = models.LongStringField(blank=True)
    wave2_news_time_seconds = models.FloatField(initial=0)


class Wave2LockedEarly(Page):
    @staticmethod
    def is_displayed(player: Player):
        return wave_status(player, 'wave2_date') == 'early'

    @staticmethod
    def vars_for_template(player: Player):
        return study_schedule(player.session)


class Wave2LockedLate(Page):
    @staticmethod
    def is_displayed(player: Player):
        return wave_status(player, 'wave2_date') == 'late'

    @staticmethod
    def vars_for_template(player: Player):
        return study_schedule(player.session)


class Wave2Intro(Page):
    @staticmethod
    def vars_for_template(player: Player):
        return study_schedule(player.session)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.treatment = player.participant.vars['treatment']

class TreatmentReveal(Page):
    @staticmethod
    def vars_for_template(player: Player):
        treatment = player.participant.vars['treatment']

        if treatment == C.TREATMENT_REVERSAL:
            scenario_title = 'Updated campaign environment'
            scenario_text = (
                'New information indicates that structural conditions have improved sharply. '
                'Inequality and crime have declined, institutions appear stronger, and enforcement '
                'capacity is now more credible than before.'
            )
        else:
            scenario_title = 'Updated campaign environment'
            scenario_text = (
                'New information indicates that the adverse structural threat persists. '
                'Inequality and crime remain high, institutions remain weak, and enforcement '
                'capacity is still not credible.'
            )

        return dict(
            scenario_title=scenario_title,
            scenario_text=scenario_text,
            treatment=treatment,
        )


class InstCapacityPost(Page):
    form_model = 'player'
    form_fields = ['inst_capacity_post']
    template_name = 'wave2_discontinuity/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 1 of 2')


class CollapseRiskPost(Page):
    form_model = 'player'
    form_fields = ['collapse_risk_post']
    template_name = 'wave2_discontinuity/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 2 of 2')

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.participant.vars['inst_capacity_post'] = player.inst_capacity_post
        player.participant.vars['collapse_risk_post'] = player.collapse_risk_post
        player.participant.vars['treatment'] = player.treatment


class Wave2NewsBoard(Page):
    form_model = 'player'
    form_fields = [
        'wave2_news_opened_ids',
        'wave2_news_spent',
        'wave2_news_click_order',
        'wave2_news_time_seconds',
    ]

    @staticmethod
    def vars_for_template(player: Player):
        treatment = player.participant.vars['treatment']

        if treatment == C.TREATMENT_REVERSAL:
            treatment_items = C.NEWS_ITEMS_REVERSAL
        else:
            treatment_items = C.NEWS_ITEMS_CONTROL


        all_items = C.NEWS_ITEMS_COMMON + treatment_items
        ordered_items = shuffled_items_once(player, 'wave2_news_display_order', all_items)

        return dict(
            news_items=ordered_items,
            news_items_json=json.dumps(ordered_items),
            click_cost=C.NEWS_CLICK_COST,
            budget_remaining=player.participant.vars.get('news_budget_remaining', 0),
            treatment=treatment,
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        opened_ids_raw = player.wave2_news_opened_ids or ''
        opened_ids = [x for x in opened_ids_raw.split(',') if x]

        previous_all = player.participant.vars.get('all_opened_news_ids', [])
        merged = previous_all.copy()
        for item_id in opened_ids:
            if item_id not in merged:
                merged.append(item_id)

        player.participant.vars['all_opened_news_ids'] = merged
        player.participant.vars['wave2_news_opened_ids'] = opened_ids
        player.participant.vars['wave2_news_click_order'] = player.wave2_news_click_order
        player.participant.vars['wave2_news_time_seconds'] = player.wave2_news_time_seconds
        player.participant.vars['news_spent_total'] = player.participant.vars.get('news_spent_total', 0) + player.wave2_news_spent
        player.participant.vars['news_budget_remaining'] = player.participant.vars.get('news_budget_remaining', 0) - player.wave2_news_spent


class Wave2Complete(Page):
    @staticmethod
    def vars_for_template(player: Player):
        return study_schedule(player.session)


page_sequence = [
    Wave2LockedEarly,
    Wave2LockedLate,
    Wave2Intro,
    TreatmentReveal,
    InstCapacityPost,
    CollapseRiskPost,
    Wave2NewsBoard,
    Wave2Complete,
]