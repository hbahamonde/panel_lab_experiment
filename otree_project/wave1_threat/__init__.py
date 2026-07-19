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
        [CONSTRAINED, 'Constrained collective procedure'],
        [EXECUTIVE, 'Executive-delegation procedure'],
    ]

    AGREEMENT_CHOICES = [[i, str(i)] for i in range(1, 8)]
    FIVE_POINT_CHOICES = [
        [1, 'Very low'], [2, 'Low'], [3, 'Moderate'], [4, 'High'], [5, 'Very high']
    ]

    NEWS_ITEMS = [
        dict(
            id='w1_capacity',
            title_excerpt='Independent public-service capacity report',
            full_title='Ordinary public-service capacity remains weak',
            full_text=(
                'The report concludes that collective public-service provision is functioning below its '
                'long-run capacity. Each point placed in the public account currently produces only 1.50 '
                'points of total group benefit.'
            ),
        ),
        dict(
            id='w1_budget',
            title_excerpt='National budget and healthcare briefing',
            full_title='Budget deadlock continues to disrupt public services',
            full_text=(
                'Parliament has failed to pass a budget for eight months. Healthcare waiting times have '
                'doubled, temporary funding rules remain in place, and service planning has stalled.'
            ),
        ),
        dict(
            id='w1_collective',
            title_excerpt='Briefing on the constrained procedure',
            full_title='Constrained procedure protects individual control and oversight',
            full_text=(
                'Under the constrained procedure, every member retains control over their own contribution. '
                'No single member can appropriate the public account, but underprovision remains possible.'
            ),
        ),
        dict(
            id='w1_executive',
            title_excerpt='Briefing on executive delegation',
            full_title='Executive delegation can accelerate provision',
            full_text=(
                'The executive can impose an equal contribution and uses a more productive implementation '
                'technology. The executive may also transfer as many as 20 collected points to themself.'
            ),
        ),
        dict(
            id='w1_audit',
            title_excerpt='Institutional oversight assessment',
            full_title='Oversight cannot prevent executive diversion',
            full_text=(
                'Auditors can report how much the executive retains after the round, but they cannot reverse '
                'the transfer. Delegation therefore trades implementation capacity for weaker ex ante control.'
            ),
        ),
        dict(
            id='w1_analysis',
            title_excerpt='Economic analysis of the institutional tradeoff',
            full_title='Efficiency advantage depends on institutional capacity',
            full_text=(
                'When ordinary capacity is weak, executive implementation can produce more public service. '
                'If ordinary capacity later recovers, that efficiency advantage may disappear while the risk '
                'of discretionary transfers remains.'
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
        label='Which procedure should govern this round?',
    )
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='How many of your 20 points do you place in the public-service account?',
        blank=True,
    )
    executive_tax = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='How many points must each group member contribute?',
        blank=True,
    )
    executive_rent = models.IntegerField(
        min=0, max=C.MAX_EXECUTIVE_RENT,
        label='How many collected points do you transfer to yourself?',
        blank=True,
    )
    is_executive = models.BooleanField(initial=False)
    timed_out = models.BooleanField(initial=False)
    round_payoff = models.FloatField(initial=0)

    inst_capacity_pre = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='Before the decision task, how capable are ordinary institutions of providing public services?',
    )
    collapse_risk_pre = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='Before the decision task, how high is the risk that democratic constraints will be seriously weakened?',
    )

    constraint_pre_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='A governance crisis can justify giving one leader temporary authority to act without prior group approval.')
    constraint_pre_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Rapid public-service provision can be worth reducing institutional oversight.')
    constraint_pre_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Major public decisions should remain collectively constrained even when this causes delay.')
    constraint_pre_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='An executive should be allowed to impose contributions when voluntary provision fails.')
    constraint_pre_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer slower collective action to efficient action by an executive who can benefit personally.')
    constraint_pre_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Weak oversight creates political risks that outweigh short-run efficiency gains.')
    constraint_pre_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='When ordinary institutions perform poorly, leaders should have greater freedom from normal constraints.')

    practice_contribution = models.IntegerField(min=0, max=10, label='Practice: choose a contribution from a 10-point endowment.')
    practice_tax = models.IntegerField(min=0, max=10, label='Practice: choose an equal contribution for every member.')
    practice_rent = models.IntegerField(min=0, max=10, label='Practice: choose how many collected points to transfer to yourself.')
    comprehension_1 = models.StringField(
        choices=[['individual', 'Each member chooses their own contribution'], ['executive', 'One executive chooses every contribution']],
        widget=widgets.RadioSelect,
        label='Under the constrained collective procedure, who chooses contributions?',
    )
    comprehension_2 = models.StringField(
        choices=[['yes', 'Yes'], ['no', 'No']], widget=widgets.RadioSelect,
        label='Can the executive transfer some collected points to themself?',
    )
    comprehension_3 = models.StringField(
        choices=[['all', 'Every round'], ['selected', 'Only the randomly selected round'], ['last', 'Only Round 10']],
        widget=widgets.RadioSelect,
        label='Which paid round determines your Wave-1 game earnings?',
    )

    wave1_news_display_order = models.LongStringField(blank=True)
    wave1_news_opened_ids = models.LongStringField(blank=True)
    wave1_news_spent = models.IntegerField(initial=0)
    wave1_news_click_order = models.LongStringField(blank=True)
    wave1_news_time_seconds = models.FloatField(initial=0)

    inst_capacity_w1 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After Wave 1, how capable is the constrained collective procedure of providing public services?',
    )
    collapse_risk_w1 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After Wave 1, how high is the risk of serious institutional weakening under executive delegation?',
    )
    constraint_w1_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The current governance crisis justifies temporary executive authority without prior group approval.')
    constraint_w1_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Rapid public-service provision is worth reducing institutional oversight in the current situation.')
    constraint_w1_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Major public decisions should remain collectively constrained despite the current delay.')
    constraint_w1_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The executive should be allowed to impose contributions under the current conditions.')
    constraint_w1_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer slower collective action to efficient action by an executive who can benefit personally.')
    constraint_w1_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The risks created by weak oversight outweigh current efficiency gains.')
    constraint_w1_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Because ordinary institutions are performing poorly, leaders need greater freedom from normal constraints.')


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
            page_title='Baseline judgments',
            explanation='For the following statements, 1 means strongly disagree and 7 means strongly agree.',
        )


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


class PracticeExecutive(Page):
    form_model = 'player'
    form_fields = ['practice_tax', 'practice_rent']
    template_name = 'wave1_threat/PracticeVote.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        if values['practice_rent'] > C.PLAYERS_PER_GROUP * values['practice_tax']:
            return 'The executive cannot transfer more points than the group contributes.'


class Comprehension(Page):
    form_model = 'player'
    form_fields = ['comprehension_1', 'comprehension_2', 'comprehension_3']
    template_name = 'wave1_threat/PracticeComplete.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        errors = []
        if values['comprehension_1'] != 'individual':
            errors.append('Under the constrained procedure, each member chooses their own contribution.')
        if values['comprehension_2'] != 'yes':
            errors.append('The executive can transfer collected points to themself.')
        if values['comprehension_3'] != 'selected':
            errors.append('One randomly selected round determines Wave-1 game earnings.')
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
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or not player.field_maybe_none('institution_vote'):
            player.institution_vote = C.CONSTRAINED
            player.timed_out = True


class VoteWaitPage(WaitPage):
    body_text = 'Waiting for the other members of this round\'s anonymous group.'
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
            page_title='Constrained collective decision',
            explanation=(
                f'Each point kept returns 1 point to you. Each point placed in the public account '
                f'produces {C.CONSTRAINED_MULTIPLIER_CRISIS:.2f} points for the group, divided equally.'
            ),
        )

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
            page_title='You are the executive for this round',
            explanation=(
                f'Choose an equal contribution for all five members. You may transfer at most '
                f'{C.MAX_EXECUTIVE_RENT} collected points to yourself. Remaining collected points '
                f'produce {C.EXECUTIVE_MULTIPLIER:.2f} points of group benefit each.'
            ),
        )

    @staticmethod
    def error_message(player, values):
        if values['executive_rent'] > C.PLAYERS_PER_GROUP * values['executive_tax']:
            return 'You cannot transfer more points than the group contributes.'

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
            page_title='Wave-1 judgments',
            explanation='Please answer after considering all ten rounds. For statements, 1 means strongly disagree and 7 means strongly agree.',
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        player.participant.vars['w1_final_vote'] = player.institution_vote
        late_votes = [p.institution_vote for p in player.in_rounds(8, 10)]
        player.participant.vars['w1_late_executive_share'] = sum(v == C.EXECUTIVE for v in late_votes) / 3
        player.participant.vars['inst_capacity_w1'] = player.inst_capacity_w1
        player.participant.vars['collapse_risk_w1'] = player.collapse_risk_w1

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
