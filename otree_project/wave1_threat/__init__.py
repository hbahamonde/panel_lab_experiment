from otree.api import *
import json


doc = """
Wave 1: baseline preferences, mechanism measures, and prototype news board
"""


class C(BaseConstants):
    NAME_IN_URL = 'wave1_threat'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    TOTAL_NEWS_BUDGET = 50
    NEWS_CLICK_COST = 5

    POLICY_CHOICES = [
        [1, 'Strongly favor option A'],
        [2, 'Moderately favor option A'],
        [3, 'Balanced / middle position'],
        [4, 'Moderately favor option B'],
        [5, 'Strongly favor option B'],
    ]

    WEIGHT_CHOICES = [
        [1, 'Not important at all'],
        [2, 'Slightly important'],
        [3, 'Moderately important'],
        [4, 'Very important'],
        [5, 'Extremely important'],
    ]

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

    NEWS_ITEMS = [
        dict(
            id='w1_n1',
            title_excerpt='Crime rates remain high across major urban areas',
            full_title='Crime rates remain high across major urban areas',
            full_text=(
                'Recent reports indicate that violent crime and property crime remain elevated. '
                'Public frustration has increased, and many voters now doubt whether ordinary '
                'institutional procedures are capable of restoring order quickly.'
            ),
            category='environment',
        ),
        dict(
            id='w1_n2',
            title_excerpt='Institutions criticized as slow and ineffective',
            full_title='Institutions criticized as slow and ineffective',
            full_text=(
                'Judicial backlogs, administrative delays, and weak enforcement have intensified the '
                'sense that institutions are not delivering. Commentators disagree on whether the '
                'problem is temporary or a deeper sign of institutional fragility.'
            ),
            category='institutions',
        ),
        dict(
            id='w1_n3',
            title_excerpt='Economic inequality becomes central campaign issue',
            full_title='Economic inequality becomes central campaign issue',
            full_text=(
                'A widening gap between high- and low-income households has become one of the central '
                'issues of the campaign. Citizens report growing concern that existing policy tools are '
                'not sufficient to address the problem.'
            ),
            category='economy',
        ),
        dict(
            id='w1_n4',
            title_excerpt='Candidate 1 promises reform within democratic constraints',
            full_title='Candidate 1 promises reform within democratic constraints',
            full_text=(
                'Candidate 1 argues that major reforms are still possible within democratic rules and '
                'institutional checks. The candidate emphasizes legality, oversight, and procedural restraint, '
                'even if policy change takes more time.'
            ),
            category='candidate',
        ),
        dict(
            id='w1_n5',
            title_excerpt='Candidate 2 promises fast targeted benefits through executive shortcuts',
            full_title='Candidate 2 promises fast targeted benefits through executive shortcuts',
            full_text=(
                'Candidate 2 argues that exceptional times require exceptional action. The candidate promises '
                'faster and more targeted benefits, but signals willingness to bypass some institutional constraints '
                'and weaken oversight in order to act decisively.'
            ),
            category='candidate',
        ),
    ]


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    pref_redistribution = models.IntegerField(
        label='What is your preferred position on redistribution policy?',
        choices=C.POLICY_CHOICES,
        widget=widgets.RadioSelect,
    )

    pref_crime = models.IntegerField(
        label='What is your preferred position on crime policy?',
        choices=C.POLICY_CHOICES,
        widget=widgets.RadioSelect,
    )

    pref_immigration = models.IntegerField(
        label='What is your preferred position on immigration policy?',
        choices=C.POLICY_CHOICES,
        widget=widgets.RadioSelect,
    )

    weight_redistribution = models.IntegerField(
        label='How important is redistribution policy to you when evaluating candidates?',
        choices=C.WEIGHT_CHOICES,
        widget=widgets.RadioSelect,
    )

    weight_crime = models.IntegerField(
        label='How important is crime policy to you when evaluating candidates?',
        choices=C.WEIGHT_CHOICES,
        widget=widgets.RadioSelect,
    )

    weight_immigration = models.IntegerField(
        label='How important is immigration policy to you when evaluating candidates?',
        choices=C.WEIGHT_CHOICES,
        widget=widgets.RadioSelect,
    )

    inst_capacity_pre = models.IntegerField(
        label='How capable are institutions of solving major problems without breaking democratic rules?',
        choices=C.CAPACITY_CHOICES,
        widget=widgets.RadioSelect,
    )

    collapse_risk_pre = models.IntegerField(
        label='How high is the risk of democratic collapse under current conditions?',
        choices=C.RISK_CHOICES,
        widget=widgets.RadioSelect,
    )

    wave1_news_opened_ids = models.LongStringField(blank=True)
    wave1_news_spent = models.IntegerField(initial=0)
    wave1_news_click_order = models.LongStringField(blank=True)
    wave1_news_time_seconds = models.FloatField(initial=0)

class Wave1Intro(Page):
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if 'news_budget_total' not in player.participant.vars:
            player.participant.vars['news_budget_total'] = C.TOTAL_NEWS_BUDGET
            player.participant.vars['news_budget_remaining'] = C.TOTAL_NEWS_BUDGET
            player.participant.vars['news_spent_total'] = 0
            player.participant.vars['all_opened_news_ids'] = []


class PrefRedistribution(Page):
    form_model = 'player'
    form_fields = ['pref_redistribution']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 1 of 8')


class PrefCrime(Page):
    form_model = 'player'
    form_fields = ['pref_crime']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 2 of 8')


class PrefImmigration(Page):
    form_model = 'player'
    form_fields = ['pref_immigration']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 3 of 8')


class WeightRedistribution(Page):
    form_model = 'player'
    form_fields = ['weight_redistribution']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 4 of 8')


class WeightCrime(Page):
    form_model = 'player'
    form_fields = ['weight_crime']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 5 of 8')


class WeightImmigration(Page):
    form_model = 'player'
    form_fields = ['weight_immigration']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 6 of 8')


class InstCapacityPre(Page):
    form_model = 'player'
    form_fields = ['inst_capacity_pre']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 7 of 8')


class CollapseRiskPre(Page):
    form_model = 'player'
    form_fields = ['collapse_risk_pre']
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def vars_for_template(player: Player):
        return dict(progress_label='Question 8 of 8')

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.participant.vars['pref_redistribution'] = player.pref_redistribution
        player.participant.vars['pref_crime'] = player.pref_crime
        player.participant.vars['pref_immigration'] = player.pref_immigration
        player.participant.vars['weight_redistribution'] = player.weight_redistribution
        player.participant.vars['weight_crime'] = player.weight_crime
        player.participant.vars['weight_immigration'] = player.weight_immigration
        player.participant.vars['inst_capacity_pre'] = player.inst_capacity_pre
        player.participant.vars['collapse_risk_pre'] = player.collapse_risk_pre


class Wave1NewsBoard(Page):
    form_model = 'player'
    form_fields = [
        'wave1_news_opened_ids',
        'wave1_news_spent',
        'wave1_news_click_order',
        'wave1_news_time_seconds',
    ]

    @staticmethod
    def vars_for_template(player: Player):
        return dict(
            news_items=C.NEWS_ITEMS,
            news_items_json=json.dumps(C.NEWS_ITEMS),
            click_cost=C.NEWS_CLICK_COST,
            budget_remaining=player.participant.vars.get('news_budget_remaining', C.TOTAL_NEWS_BUDGET),
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        opened_ids_raw = player.wave1_news_opened_ids or ''
        opened_ids = [x for x in opened_ids_raw.split(',') if x]

        previous_all = player.participant.vars.get('all_opened_news_ids', [])
        merged = previous_all.copy()
        for item_id in opened_ids:
            if item_id not in merged:
                merged.append(item_id)

        player.participant.vars['all_opened_news_ids'] = merged
        player.participant.vars['wave1_news_opened_ids'] = opened_ids
        player.participant.vars['wave1_news_click_order'] = player.wave1_news_click_order
        player.participant.vars['wave1_news_time_seconds'] = player.wave1_news_time_seconds
        player.participant.vars['news_spent_total'] = player.participant.vars.get('news_spent_total', 0) + player.wave1_news_spent
        player.participant.vars['news_budget_remaining'] = player.participant.vars.get('news_budget_remaining', C.TOTAL_NEWS_BUDGET) - player.wave1_news_spent
        

page_sequence = [
    Wave1Intro,
    PrefRedistribution,
    PrefCrime,
    PrefImmigration,
    WeightRedistribution,
    WeightCrime,
    WeightImmigration,
    InstCapacityPre,
    CollapseRiskPre,
    Wave1NewsBoard,
]