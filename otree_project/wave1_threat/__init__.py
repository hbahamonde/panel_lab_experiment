import random
from datetime import datetime

from otree.api import *


doc = """
Wave 1 of the two-wave panel: common low-capacity environment, ten repeated
institutional-choice/public-good rounds, costly information, and mechanism
measurement. Participants are anonymously rematched within ten-person pools.
"""


def shuffled_items_once(player, field_name, items):
    stored_order = player.field_maybe_none(field_name)
    item_map = {item['id']: item for item in items}
    if stored_order:
        return [item_map[item_id] for item_id in stored_order.split(',') if item_id in item_map]
    shuffled = random.sample(items, len(items))
    setattr(player, field_name, ','.join(item['id'] for item in shuffled))
    return shuffled


def development_mode(player):
    """Allow researchers to move through the demo without completing every field."""
    return player.session.config.get('allow_optional_responses', False)


def require_all(player, values, field_names):
    if development_mode(player):
        return
    if any(values.get(field_name) in (None, '') for field_name in field_names):
        return 'Please answer all questions before continuing.'


def assign_matching_pools(subsession):
    players = subsession.get_players()
    pool_size = subsession.session.config.get('matching_pool_size', C.MATCHING_POOL_SIZE)

    if subsession.round_number == 1:
        if len(players) % C.PLAYERS_PER_GROUP != 0:
            raise RuntimeError('The session size must be divisible by five.')

        shuffled = random.sample(players, len(players))
        for index, player in enumerate(shuffled):
            pool_id = index // pool_size + 1
            player.participant.vars['matching_pool_id'] = pool_id
            player.participant.vars['times_executive'] = 0

        pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in shuffled})
        randomized_pool_ids = random.sample(pool_ids, len(pool_ids))
        midpoint = (len(randomized_pool_ids) + 1) // 2
        reversal_ids = set(randomized_pool_ids[:midpoint])
        for player in shuffled:
            treatment = 'reversal' if player.participant.vars['matching_pool_id'] in reversal_ids else 'control'
            player.participant.vars['treatment'] = treatment

        subsession.session.vars['wave1_paying_round'] = random.randint(1, C.NUM_ROUNDS)

    groups = []
    pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in players})
    for pool_id in pool_ids:
        pool_players = [p for p in players if p.participant.vars['matching_pool_id'] == pool_id]
        random.shuffle(pool_players)
        if len(pool_players) % C.PLAYERS_PER_GROUP != 0:
            raise RuntimeError(
                f'Matching pool {pool_id} contains {len(pool_players)} participants; '
                'each pool must be divisible into five-person groups.'
            )
        groups.extend(
            pool_players[index:index + C.PLAYERS_PER_GROUP]
            for index in range(0, len(pool_players), C.PLAYERS_PER_GROUP)
        )

    subsession.set_group_matrix(groups)
    for player in players:
        player.matching_pool_id = player.participant.vars['matching_pool_id']


def choose_institution(group):
    players = group.get_players()
    undemocratic_votes = sum(p.institution_vote == C.EXECUTIVE for p in players)
    group.executive_votes = undemocratic_votes
    group.selected_institution = C.EXECUTIVE if undemocratic_votes >= 3 else C.CONSTRAINED

    if group.selected_institution == C.EXECUTIVE:
        minimum_count = min(p.participant.vars.get('times_executive', 0) for p in players)
        eligible = [p for p in players if p.participant.vars.get('times_executive', 0) == minimum_count]
        executive = random.choice(eligible)
        executive.is_executive = True
        executive.participant.vars['times_executive'] = minimum_count + 1
        group.executive_id = executive.id_in_group


def calculate_round(group):
    players = group.get_players()
    if group.selected_institution == C.CONSTRAINED:
        total = sum(p.contribution or 0 for p in players)
        group.total_contribution = total
        group.executive_tax = 0
        group.executive_rent = 0
        group.public_account = total
        group.per_capita_return = C.CONSTRAINED_MULTIPLIER_CRISIS * total / C.PLAYERS_PER_GROUP
        for player in players:
            player.round_payoff = C.ENDOWMENT - (player.contribution or 0) + group.per_capita_return
    else:
        executive = group.get_player_by_id(group.executive_id)
        tax = executive.executive_tax or 0
        rent = executive.executive_rent or 0
        public_account = C.PLAYERS_PER_GROUP * tax - rent
        group.total_contribution = C.PLAYERS_PER_GROUP * tax
        group.executive_tax = tax
        group.executive_rent = rent
        group.public_account = public_account
        group.per_capita_return = C.EXECUTIVE_MULTIPLIER * public_account / C.PLAYERS_PER_GROUP
        for player in players:
            player.round_payoff = C.ENDOWMENT - tax + group.per_capita_return
            if player.id_in_group == group.executive_id:
                player.round_payoff += rent


class C(BaseConstants):
    NAME_IN_URL = 'wave1_threat'
    PLAYERS_PER_GROUP = 5
    MATCHING_POOL_SIZE = 10
    NUM_ROUNDS = 10

    ENDOWMENT = 20
    CONSTRAINED_MULTIPLIER_CRISIS = 1.50
    CONSTRAINED_MULTIPLIER_RECOVERY = 2.50
    EXECUTIVE_MULTIPLIER = 2.50
    MAX_EXECUTIVE_RENT = 20

    INFO_BUDGET = 24
    INFO_CLICK_COST = 4

    CONSTRAINED = 'constrained'
    EXECUTIVE = 'executive'
    INSTITUTION_CHOICES = [
        [CONSTRAINED, 'Citizens decide'],
        [EXECUTIVE, 'A leader decides'],
    ]

    AGREEMENT_CHOICES = [[i, str(i)] for i in range(1, 8)]
    FIVE_POINT_CHOICES = [
        [1, 'Very low'], [2, 'Low'], [3, 'Moderate'], [4, 'High'], [5, 'Very high']
    ]

    NEWS_ITEMS = [
        dict(
            id='w1_capacity',
            title_excerpt='Report on how well public services are working',
            full_title='Public services remain under strain',
            full_text=(
                'An independent review finds that public services are working less effectively than usual. '
                'When citizens decide, each point placed in the public-service account currently produces '
                '1.50 points for the group in total.'
            ),
        ),
        dict(
            id='w1_budget',
            title_excerpt='Update on the national budget and healthcare',
            full_title='The budget delay continues to disrupt public services',
            full_text=(
                'Parliament has failed to pass a budget for eight months. Healthcare waiting times have '
                'doubled, temporary funding rules remain in place, and service planning has stalled.'
            ),
        ),
        dict(
            id='w1_collective',
            title_excerpt='Report on what happens when citizens decide',
            full_title='Each citizen keeps control of their own contribution',
            full_text=(
                'When citizens decide, each citizen chooses their own contribution. No citizen can take '
                'points from the public-service account, but the group may contribute too little.'
            ),
        ),
        dict(
            id='w1_executive',
            title_excerpt='Report on what happens when a leader decides',
            full_title='A leader can provide services faster but has personal discretion',
            full_text=(
                'The leader sets the same required contribution for all five citizens. The leader can turn '
                'the remaining points into public services more effectively, but may keep up to 20 collected '
                'points for themself.'
            ),
        ),
        dict(
            id='w1_audit',
            title_excerpt='Report on checks on the leader',
            full_title='The leader must disclose any points kept after the round',
            full_text=(
                'The group is told how many points the leader kept, but it cannot reverse that choice. Giving '
                'the leader control may improve public services, but citizens give up control before the choice.'
            ),
        ),
        dict(
            id='w1_analysis',
            title_excerpt='Comparison of the two ways of deciding',
            full_title='The best-performing option depends on how well public services work',
            full_text=(
                'When public services are under strain, a leader can produce more public benefit from the '
                'same number of points. If services later recover, that advantage may disappear, while the '
                'leader would still be allowed to keep some collected points.'
            ),
        ),
    ]


class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    assign_matching_pools(subsession)


class Group(BaseGroup):
    selected_institution = models.StringField()
    executive_votes = models.IntegerField(initial=0)
    executive_id = models.IntegerField(initial=0)
    total_contribution = models.IntegerField(initial=0)
    executive_tax = models.IntegerField(initial=0)
    executive_rent = models.IntegerField(initial=0)
    public_account = models.IntegerField(initial=0)
    per_capita_return = models.FloatField(initial=0)


class Player(BasePlayer):
    matching_pool_id = models.IntegerField()
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES,
        widget=widgets.RadioSelect,
        label='Who should make the public-service decision this round?',
        blank=True,
    )
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='How many of your 20 points do you place in the public-service account?',
        blank=True,
    )
    executive_tax = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='How many points must each citizen contribute?',
        blank=True,
    )
    executive_rent = models.IntegerField(
        min=0, max=C.MAX_EXECUTIVE_RENT,
        label='How many collected points do you keep for yourself?',
        blank=True,
    )
    is_executive = models.BooleanField(initial=False)
    timed_out = models.BooleanField(initial=False)
    round_payoff = models.FloatField(initial=0)

    inst_capacity_pre = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='At this point, how well can citizens provide public services when each citizen chooses their own contribution?',
        blank=True,
    )
    collapse_risk_pre = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='At this point, how high is the risk that the usual limits on a leader\'s power will be seriously weakened?',
        blank=True,
    )

    constraint_pre_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='A crisis can justify giving one leader temporary power to act without asking the group first.', blank=True)
    constraint_pre_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Faster public services can be worth reducing checks on a leader\'s power.', blank=True)
    constraint_pre_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Citizens should keep control over major public decisions, even if decisions take longer.', blank=True)
    constraint_pre_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='A leader should be allowed to require equal contributions when voluntary contributions are too low.', blank=True)
    constraint_pre_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer slower decisions by citizens to faster decisions by a leader who may keep some collected points.', blank=True)
    constraint_pre_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Weak limits on a leader\'s power create risks that outweigh short-term gains.', blank=True)
    constraint_pre_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='When public services work poorly, a leader should have more freedom from the usual limits.', blank=True)

    practice_contribution = models.IntegerField(min=0, max=10, label='How many of your 10 points do you contribute?', blank=True)
    practice_tax = models.IntegerField(min=0, max=10, label='Choose the contribution required from each citizen.', blank=True)
    practice_rent = models.IntegerField(min=0, max=10, label='How many collected points do you keep for yourself?', blank=True)
    comprehension_1 = models.StringField(
        choices=[['individual', 'Each citizen chooses their own contribution'], ['executive', 'One leader chooses every citizen\'s contribution']],
        widget=widgets.RadioSelect,
        label='When citizens decide, who chooses the contributions?',
        blank=True,
    )
    comprehension_2 = models.StringField(
        choices=[['yes', 'Yes'], ['no', 'No']], widget=widgets.RadioSelect,
        label='Can the leader keep some of the collected points?',
        blank=True,
    )
    comprehension_3 = models.StringField(
        choices=[['all', 'Every round'], ['selected', 'Only the randomly selected round'], ['last', 'Only Round 10']],
        widget=widgets.RadioSelect,
        label='Which paid round determines your game earnings from Session 1?',
        blank=True,
    )

    wave1_news_display_order = models.LongStringField(blank=True)
    wave1_news_opened_ids = models.LongStringField(blank=True)
    wave1_news_spent = models.IntegerField(initial=0)
    wave1_news_click_order = models.LongStringField(blank=True)
    wave1_news_time_seconds = models.FloatField(initial=0)

    inst_capacity_w1 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how well can citizens provide public services when each citizen chooses their own contribution?',
        blank=True,
    )
    collapse_risk_w1 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how high is the risk that the usual limits on a leader\'s power will be seriously weakened?',
        blank=True,
    )
    constraint_w1_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The current crisis justifies giving one leader temporary power to act without asking the group first.', blank=True)
    constraint_w1_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Faster public services are worth reducing checks on a leader\'s power in the current situation.', blank=True)
    constraint_w1_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Citizens should keep control over major public decisions, even if decisions take longer.', blank=True)
    constraint_w1_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The leader should be allowed to require equal contributions in the current situation.', blank=True)
    constraint_w1_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer slower decisions by citizens to faster decisions by a leader who may keep some collected points.', blank=True)
    constraint_w1_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Weak limits on a leader\'s power create risks that outweigh the current gains.', blank=True)
    constraint_w1_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Because public services are working poorly, a leader needs more freedom from the usual limits.', blank=True)


class Wave1Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        if 'info_budget_remaining' not in player.participant.vars:
            player.participant.vars['info_budget_remaining'] = C.INFO_BUDGET
            player.participant.vars['info_spent_total'] = 0
        return dict(
            rounds=C.NUM_ROUNDS,
            group_size=C.PLAYERS_PER_GROUP,
            info_budget=C.INFO_BUDGET,
        )


class BaselineSurvey(Page):
    form_model = 'player'
    form_fields = [
        'inst_capacity_pre', 'collapse_risk_pre',
        'constraint_pre_1', 'constraint_pre_2', 'constraint_pre_3', 'constraint_pre_4',
        'constraint_pre_5', 'constraint_pre_6', 'constraint_pre_7',
    ]
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Your first impressions',
            explanation='Please answer the two questions about public services first.',
            slider_prefix='constraint_pre_',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, BaselineSurvey.form_fields)


class PracticeIntro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1


class PracticeDemocratic(Page):
    form_model = 'player'
    form_fields = ['practice_contribution']
    template_name = 'wave1_threat/PracticeNewsBoard.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, PracticeDemocratic.form_fields)


class PracticeExecutive(Page):
    form_model = 'player'
    form_fields = ['practice_tax', 'practice_rent']
    template_name = 'wave1_threat/PracticeVote.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        missing = require_all(player, values, PracticeExecutive.form_fields)
        if missing:
            return missing
        if values.get('practice_rent') is not None and values.get('practice_tax') is not None:
            if values['practice_rent'] > C.PLAYERS_PER_GROUP * values['practice_tax']:
                return 'The leader cannot keep more points than the group contributes.'


class Comprehension(Page):
    form_model = 'player'
    form_fields = ['comprehension_1', 'comprehension_2', 'comprehension_3']
    template_name = 'wave1_threat/PracticeComplete.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        if development_mode(player):
            return
        errors = []
        if values['comprehension_1'] != 'individual':
            errors.append('When citizens decide, each citizen chooses their own contribution.')
        if values['comprehension_2'] != 'yes':
            errors.append('The leader can keep some of the collected points.')
        if values['comprehension_3'] != 'selected':
            errors.append('One randomly selected round determines your Session-1 game earnings.')
        if errors:
            return 'Please review: ' + ' '.join(errors)


class Wave1NewsBoard(Page):
    form_model = 'player'
    form_fields = ['wave1_news_opened_ids', 'wave1_news_spent', 'wave1_news_click_order', 'wave1_news_time_seconds']

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        items = shuffled_items_once(player, 'wave1_news_display_order', C.NEWS_ITEMS)
        return dict(
            news_items=items,
            click_cost=C.INFO_CLICK_COST,
            budget_remaining=player.participant.vars.get('info_budget_remaining', C.INFO_BUDGET),
            storage_key=f'w1-news-{player.participant.code}',
        )

    @staticmethod
    def error_message(player, values):
        opened = [item for item in (values.get('wave1_news_opened_ids') or '').split(',') if item]
        valid_ids = {item['id'] for item in C.NEWS_ITEMS}
        expected_spend = len(opened) * C.INFO_CLICK_COST
        budget = player.participant.vars.get('info_budget_remaining', C.INFO_BUDGET)
        if len(opened) != len(set(opened)) or not set(opened).issubset(valid_ids):
            return 'The submitted report record is invalid. Please reload the page and make your choices again.'
        if values.get('wave1_news_spent') != expected_spend or expected_spend > budget:
            return 'The submitted information cost does not match the reports opened. Please reload the page.'

    @staticmethod
    def before_next_page(player, timeout_happened):
        opened = [item for item in (player.wave1_news_opened_ids or '').split(',') if item]
        spent = len(opened) * C.INFO_CLICK_COST
        player.wave1_news_spent = spent
        player.participant.vars['wave1_news_opened_ids'] = opened
        player.participant.vars['wave1_news_click_order'] = player.wave1_news_click_order or ''
        player.participant.vars['wave1_news_time_seconds'] = player.wave1_news_time_seconds or 0
        player.participant.vars['info_spent_total'] = player.participant.vars.get('info_spent_total', 0) + spent
        player.participant.vars['info_budget_remaining'] = player.participant.vars.get('info_budget_remaining', C.INFO_BUDGET) - spent


class InstitutionVote(Page):
    form_model = 'player'
    form_fields = ['institution_vote']
    template_name = 'wave1_threat/BeginMainStudy.html'
    timeout_seconds = 90

    @staticmethod
    def vars_for_template(player):
        return dict(
            round_number=player.round_number,
            total_rounds=C.NUM_ROUNDS,
            constrained_multiplier=C.CONSTRAINED_MULTIPLIER_CRISIS,
            executive_multiplier=C.EXECUTIVE_MULTIPLIER,
            optional_responses=development_mode(player),
            selected_vote=player.field_maybe_none('institution_vote'),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, InstitutionVote.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or not player.field_maybe_none('institution_vote'):
            player.institution_vote = C.CONSTRAINED
            player.timed_out = True


class VoteWaitPage(WaitPage):
    body_text = 'Waiting for the other citizens in this round\'s anonymous group.'
    after_all_players_arrive = choose_institution


class DemocraticContribution(Page):
    form_model = 'player'
    form_fields = ['contribution']
    template_name = 'wave1_threat/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return player.group.selected_institution == C.CONSTRAINED

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Citizens decide',
            explanation=(
                f'Each point kept returns 1 point to you. Each point placed in the public account '
                f'produces {C.CONSTRAINED_MULTIPLIER_CRISIS:.2f} points for the group, divided equally.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, DemocraticContribution.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or player.field_maybe_none('contribution') is None:
            player.contribution = 0
            player.timed_out = True


class ExecutiveDecision(Page):
    form_model = 'player'
    form_fields = ['executive_tax', 'executive_rent']
    template_name = 'wave1_threat/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return player.group.selected_institution == C.EXECUTIVE and player.is_executive

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='You are the leader for this round',
            explanation=(
                f'Choose the contribution required from all five citizens. You may keep at most '
                f'{C.MAX_EXECUTIVE_RENT} collected points for yourself. Each remaining point produces '
                f'{C.EXECUTIVE_MULTIPLIER:.2f} points for the group in total.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        missing = require_all(player, values, ExecutiveDecision.form_fields)
        if missing:
            return missing
        if values.get('executive_rent') is not None and values.get('executive_tax') is not None:
            if values['executive_rent'] > C.PLAYERS_PER_GROUP * values['executive_tax']:
                return 'You cannot keep more points than the group contributes.'

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or player.field_maybe_none('executive_tax') is None:
            player.executive_tax = 0
            player.executive_rent = 0
            player.timed_out = True


class DecisionWaitPage(WaitPage):
    body_text = 'Waiting for all decisions in this round.'
    after_all_players_arrive = calculate_round


class RoundResults(Page):
    template_name = 'wave1_threat/Results.html'

    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            round_number=player.round_number,
            total_rounds=C.NUM_ROUNDS,
            institution_label=dict(C.INSTITUTION_CHOICES)[group.selected_institution],
            executive_selected=group.selected_institution == C.EXECUTIVE,
            is_executive=player.id_in_group == group.executive_id,
            total_contribution=group.total_contribution,
            executive_tax=group.executive_tax,
            executive_rent=group.executive_rent,
            public_account=group.public_account,
            per_capita_return=group.per_capita_return,
            round_payoff=player.round_payoff,
        )


class Wave1Mechanism(Page):
    form_model = 'player'
    form_fields = [
        'inst_capacity_w1', 'collapse_risk_w1',
        'constraint_w1_1', 'constraint_w1_2', 'constraint_w1_3', 'constraint_w1_4',
        'constraint_w1_5', 'constraint_w1_6', 'constraint_w1_7',
    ]
    template_name = 'wave1_threat/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Your views after the rounds',
            explanation='Please answer after considering all ten rounds.',
            slider_prefix='constraint_w1_',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, Wave1Mechanism.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        player.participant.vars['w1_final_vote'] = player.institution_vote
        late_votes = [p.institution_vote for p in player.in_rounds(8, 10)]
        player.participant.vars['w1_late_executive_share'] = sum(v == C.EXECUTIVE for v in late_votes) / 3
        player.participant.vars['inst_capacity_w1'] = player.field_maybe_none('inst_capacity_w1')
        player.participant.vars['collapse_risk_w1'] = player.field_maybe_none('collapse_risk_w1')

        paying_round = player.session.vars['wave1_paying_round']
        selected_payoff = player.in_round(paying_round).round_payoff
        player.payoff = cu(selected_payoff)
        player.participant.vars['wave1_paying_round'] = paying_round
        player.participant.vars['wave1_selected_payoff'] = selected_payoff


class Wave1Complete(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            paying_round=player.participant.vars['wave1_paying_round'],
            selected_payoff=player.participant.vars['wave1_selected_payoff'],
            information_remaining=player.participant.vars.get('info_budget_remaining', 0),
            wave2_date=datetime.fromisoformat(player.session.config['wave2_date']).strftime('%B %d, %Y'),
            gates_enabled=player.session.config.get('enable_wave_gates', False),
        )


page_sequence = [
    Wave1Intro,
    BaselineSurvey,
    PracticeIntro,
    PracticeDemocratic,
    PracticeExecutive,
    Comprehension,
    Wave1NewsBoard,
    InstitutionVote,
    VoteWaitPage,
    DemocraticContribution,
    ExecutiveDecision,
    DecisionWaitPage,
    RoundResults,
    Wave1Mechanism,
    Wave1Complete,
]
