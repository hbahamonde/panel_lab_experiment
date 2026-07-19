import random
from datetime import date, datetime, timedelta

from otree.api import *


doc = """
Wave 2: pre-refresh memory measurement, a pool-randomized structural recovery
or persistence condition, costly information, ten repeated institutional-choice
rounds, and the final two-wave democratic-reversal outcome.
"""


def wave_status(player):
    if not player.session.config.get('enable_wave_gates', False):
        return 'open'
    wave_date = datetime.fromisoformat(player.session.config['wave2_date']).date()
    deadline = wave_date + timedelta(days=player.session.config['wave_window_days'] - 1)
    if date.today() < wave_date:
        return 'early'
    if date.today() > deadline:
        return 'late'
    return 'open'


def study_schedule(session):
    wave2 = datetime.fromisoformat(session.config['wave2_date']).date()
    deadline = wave2 + timedelta(days=session.config['wave_window_days'] - 1)
    return dict(
        wave2_date_display=wave2.strftime('%B %d, %Y'),
        wave2_deadline_display=deadline.strftime('%B %d, %Y'),
    )


def shuffled_items_once(player, field_name, items):
    stored_order = player.field_maybe_none(field_name)
    item_map = {item['id']: item for item in items}
    if stored_order:
        return [item_map[item_id] for item_id in stored_order.split(',') if item_id in item_map]
    shuffled = random.sample(items, len(items))
    setattr(player, field_name, ','.join(item['id'] for item in shuffled))
    return shuffled


def group_within_matching_pools(subsession):
    players = subsession.get_players()
    groups = []
    pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in players})
    for pool_id in pool_ids:
        pool_players = [p for p in players if p.participant.vars['matching_pool_id'] == pool_id]
        random.shuffle(pool_players)
        if len(pool_players) % C.PLAYERS_PER_GROUP != 0:
            raise RuntimeError(
                f'Matching pool {pool_id} contains {len(pool_players)} participants; '
                'Wave 2 requires complete five-person groups.'
            )
        groups.extend(
            pool_players[index:index + C.PLAYERS_PER_GROUP]
            for index in range(0, len(pool_players), C.PLAYERS_PER_GROUP)
        )
    subsession.set_group_matrix(groups)
    for player in players:
        player.matching_pool_id = player.participant.vars['matching_pool_id']
        player.treatment = player.participant.vars['treatment']

    if subsession.round_number == 1:
        subsession.session.vars['wave2_paying_round'] = random.randint(1, C.NUM_ROUNDS)


def constrained_multiplier(player):
    if player.treatment == C.TREATMENT_REVERSAL:
        return C.CONSTRAINED_MULTIPLIER_RECOVERY
    return C.CONSTRAINED_MULTIPLIER_CRISIS


def choose_institution(group):
    players = group.get_players()
    executive_votes = sum(p.institution_vote == C.EXECUTIVE for p in players)
    group.executive_votes = executive_votes
    group.selected_institution = C.EXECUTIVE if executive_votes >= 3 else C.CONSTRAINED
    group.realized_constrained_multiplier = constrained_multiplier(players[0])

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
        group.per_capita_return = group.realized_constrained_multiplier * total / C.PLAYERS_PER_GROUP
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
    NAME_IN_URL = 'wave2_discontinuity'
    PLAYERS_PER_GROUP = 5
    NUM_ROUNDS = 10

    ENDOWMENT = 20
    CONSTRAINED_MULTIPLIER_CRISIS = 1.50
    CONSTRAINED_MULTIPLIER_RECOVERY = 2.50
    EXECUTIVE_MULTIPLIER = 2.50
    MAX_EXECUTIVE_RENT = 20
    INFO_CLICK_COST = 4
    COMPLETION_BONUS = 25
    BELIEF_BONUS_MAX = 5

    CONSTRAINED = 'constrained'
    EXECUTIVE = 'executive'
    TREATMENT_REVERSAL = 'reversal'
    TREATMENT_CONTROL = 'control'

    INSTITUTION_CHOICES = [
        [CONSTRAINED, 'Constrained collective procedure'],
        [EXECUTIVE, 'Executive-delegation procedure'],
    ]
    AGREEMENT_CHOICES = [[i, str(i)] for i in range(1, 8)]
    FIVE_POINT_CHOICES = [
        [1, 'Very low'], [2, 'Low'], [3, 'Moderate'], [4, 'High'], [5, 'Very high']
    ]
    MEMORY_CAPACITY_CHOICES = [
        ['low', 'Low capacity'], ['moderate', 'Moderate capacity'],
        ['high', 'High capacity'], ['unsure', 'I do not remember'],
    ]
    MEMORY_VOTE_CHOICES = [
        [CONSTRAINED, 'Constrained collective procedure'],
        [EXECUTIVE, 'Executive-delegation procedure'],
        ['unsure', 'I do not remember'],
    ]

    NEWS_ITEMS_COMMON = [
        dict(
            id='w2_collective',
            title_excerpt='Updated briefing on the constrained procedure',
            full_title='Collective constraints and oversight remain unchanged',
            full_text=(
                'Every member continues to control their own contribution, public returns remain equal, '
                'and no participant can appropriate the public account. Only the productivity of ordinary '
                'public-service provision may have changed.'
            ),
        ),
        dict(
            id='w2_executive',
            title_excerpt='Updated briefing on executive delegation',
            full_title='Executive authority and discretion remain unchanged',
            full_text=(
                'The executive still imposes an equal contribution, uses the 2.50 implementation technology, '
                'and may transfer as many as 20 collected points to themself.'
            ),
        ),
        dict(
            id='w2_tradeoff',
            title_excerpt='Independent assessment of the institutional tradeoff',
            full_title='Relative performance depends on ordinary institutional capacity',
            full_text=(
                'The executive procedure has not changed. If ordinary public-service capacity recovered, '
                'executive discretion no longer carries a technological advantage. If the crisis persists, '
                'the original advantage remains.'
            ),
        ),
    ]
    NEWS_ITEMS_REVERSAL = [
        dict(
            id='w2_state_capacity',
            title_excerpt='New public-service capacity report',
            full_title='Ordinary implementation capacity has recovered',
            full_text=(
                'The independent report finds that administrative capacity and interagency coordination have '
                'improved. Each point contributed under the constrained procedure now produces 2.50 points '
                'of total group benefit rather than 1.50.'
            ),
        ),
        dict(
            id='w2_state_budget',
            title_excerpt='New national budget report',
            full_title='Budget agreement stabilizes public-service financing',
            full_text=(
                'Parliament has adopted a budget agreement, temporary funding rules have ended, and municipal '
                'service providers can plan using ordinary procedures.'
            ),
        ),
        dict(
            id='w2_state_health',
            title_excerpt='New healthcare-system report',
            full_title='Healthcare backlog has stabilized',
            full_text=(
                'Waiting times remain elevated but have stopped increasing. New appropriations and improved '
                'administrative coordination have reduced the need for extraordinary implementation powers.'
            ),
        ),
    ]
    NEWS_ITEMS_CONTROL = [
        dict(
            id='w2_state_capacity',
            title_excerpt='New public-service capacity report',
            full_title='Ordinary implementation capacity remains weak',
            full_text=(
                'The independent report finds no durable improvement in administrative capacity or coordination. '
                'Each point contributed under the constrained procedure continues to produce 1.50 points of '
                'total group benefit.'
            ),
        ),
        dict(
            id='w2_state_budget',
            title_excerpt='New national budget report',
            full_title='Budget deadlock continues',
            full_text=(
                'No budget agreement has been adopted. Temporary funding rules and uncertainty about public-service '
                'planning remain in place.'
            ),
        ),
        dict(
            id='w2_state_health',
            title_excerpt='New healthcare-system report',
            full_title='Healthcare backlog continues to grow',
            full_text=(
                'Waiting times have continued to increase, and administrative coordination remains weak. '
                'Ordinary implementation procedures have not recovered.'
            ),
        ),
    ]


class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    group_within_matching_pools(subsession)


class Group(BaseGroup):
    selected_institution = models.StringField()
    executive_votes = models.IntegerField(initial=0)
    executive_id = models.IntegerField(initial=0)
    total_contribution = models.IntegerField(initial=0)
    executive_tax = models.IntegerField(initial=0)
    executive_rent = models.IntegerField(initial=0)
    public_account = models.IntegerField(initial=0)
    per_capita_return = models.FloatField(initial=0)
    realized_constrained_multiplier = models.FloatField(initial=0)


class Player(BasePlayer):
    matching_pool_id = models.IntegerField()
    treatment = models.StringField()
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES, widget=widgets.RadioSelect,
        label='Which procedure should govern this round?',
    )
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='How many of your 20 points do you place in the public-service account?',
    )
    executive_tax = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='How many points must each group member contribute?',
    )
    executive_rent = models.IntegerField(
        min=0, max=C.MAX_EXECUTIVE_RENT, blank=True,
        label='How many collected points do you transfer to yourself?',
    )
    is_executive = models.BooleanField(initial=False)
    timed_out = models.BooleanField(initial=False)
    round_payoff = models.FloatField(initial=0)

    memory_free_recall = models.LongStringField(
        label='Without reopening earlier material, what do you remember about the institutional environment and group task in Wave 1?',
    )
    memory_w1_capacity = models.StringField(
        choices=C.MEMORY_CAPACITY_CHOICES, widget=widgets.RadioSelect,
        label='What level of ordinary public-service capacity was described in Wave 1?',
    )
    memory_w1_vote = models.StringField(
        choices=C.MEMORY_VOTE_CHOICES, widget=widgets.RadioSelect,
        label='Which procedure did you choose in the final round of Wave 1?',
    )
    belief_recovery_pre = models.IntegerField(
        min=0, max=100,
        label='Before opening any new report, what is the probability (0--100) that ordinary institutional capacity has recovered since Wave 1?',
    )

    wave2_news_display_order = models.LongStringField(blank=True)
    wave2_news_opened_ids = models.LongStringField(blank=True)
    wave2_news_spent = models.IntegerField(initial=0)
    wave2_news_click_order = models.LongStringField(blank=True)
    wave2_news_time_seconds = models.FloatField(initial=0)
    belief_recovery_post_search = models.IntegerField(
        min=0, max=100,
        label='After your information choices, what is the probability (0--100) that ordinary institutional capacity has recovered?',
    )
    inst_capacity_immediate = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='Based on the information currently available to you, how capable is the constrained procedure of providing public services?',
    )

    inst_capacity_w2 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After Wave 2, how capable is the constrained collective procedure of providing public services?',
    )
    collapse_risk_w2 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After Wave 2, how high is the risk of serious institutional weakening under executive delegation?',
    )
    belief_recovery_final = models.IntegerField(
        min=0, max=100,
        label='After all ten rounds, what is the probability (0--100) that ordinary institutional capacity recovered before Wave 2?',
    )
    constraint_w2_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The current situation justifies temporary executive authority without prior group approval.')
    constraint_w2_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Rapid public-service provision is worth reducing institutional oversight in the current situation.')
    constraint_w2_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Major public decisions should remain collectively constrained despite possible delay.')
    constraint_w2_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The executive should be allowed to impose contributions under the current conditions.')
    constraint_w2_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer slower collective action to efficient action by an executive who can benefit personally.')
    constraint_w2_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The risks created by weak oversight outweigh current efficiency gains.')
    constraint_w2_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Because ordinary institutions are performing poorly, leaders need greater freedom from normal constraints.')

    democratic_reversal = models.BooleanField(initial=False)
    belief_bonus = models.FloatField(initial=0)


class Wave2LockedEarly(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'early'

    @staticmethod
    def vars_for_template(player):
        return study_schedule(player.session)


class Wave2LockedLate(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'late'

    @staticmethod
    def vars_for_template(player):
        return study_schedule(player.session)


class Wave2Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        return dict(
            information_remaining=player.participant.vars.get('info_budget_remaining', 0),
            rounds=C.NUM_ROUNDS,
        )


class MemoryAndPrior(Page):
    form_model = 'player'
    form_fields = ['memory_free_recall', 'memory_w1_capacity', 'memory_w1_vote', 'belief_recovery_pre']
    template_name = 'wave2_discontinuity/TreatmentReveal.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'open'


class Wave2NewsBoard(Page):
    form_model = 'player'
    form_fields = ['wave2_news_opened_ids', 'wave2_news_spent', 'wave2_news_click_order', 'wave2_news_time_seconds']

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        condition_items = C.NEWS_ITEMS_REVERSAL if player.treatment == C.TREATMENT_REVERSAL else C.NEWS_ITEMS_CONTROL
        items = shuffled_items_once(player, 'wave2_news_display_order', C.NEWS_ITEMS_COMMON + condition_items)
        return dict(
            news_items=items,
            click_cost=C.INFO_CLICK_COST,
            budget_remaining=player.participant.vars.get('info_budget_remaining', 0),
            storage_key=f'w2-news-{player.participant.code}',
        )

    @staticmethod
    def error_message(player, values):
        opened = [item for item in (values.get('wave2_news_opened_ids') or '').split(',') if item]
        valid_ids = {item['id'] for item in C.NEWS_ITEMS_COMMON + C.NEWS_ITEMS_REVERSAL + C.NEWS_ITEMS_CONTROL}
        expected_spend = len(opened) * C.INFO_CLICK_COST
        budget = player.participant.vars.get('info_budget_remaining', 0)
        if len(opened) != len(set(opened)) or not set(opened).issubset(valid_ids):
            return 'The submitted report record is invalid. Please reload the page and make your choices again.'
        if values.get('wave2_news_spent') != expected_spend or expected_spend > budget:
            return 'The submitted information cost does not match the reports opened. Please reload the page.'

    @staticmethod
    def before_next_page(player, timeout_happened):
        opened = [item for item in (player.wave2_news_opened_ids or '').split(',') if item]
        spent = len(opened) * C.INFO_CLICK_COST
        player.wave2_news_spent = spent
        player.participant.vars['wave2_news_opened_ids'] = opened
        player.participant.vars['wave2_news_click_order'] = player.wave2_news_click_order or ''
        player.participant.vars['wave2_news_time_seconds'] = player.wave2_news_time_seconds or 0
        player.participant.vars['info_spent_total'] = player.participant.vars.get('info_spent_total', 0) + spent
        player.participant.vars['info_budget_remaining'] = player.participant.vars.get('info_budget_remaining', 0) - spent


class PostSearchBelief(Page):
    form_model = 'player'
    form_fields = ['belief_recovery_post_search', 'inst_capacity_immediate']
    template_name = 'wave2_discontinuity/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1 and wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Assessment after information search',
            explanation='These judgments are recorded before any Wave-2 group outcome is observed.',
        )


class InstitutionVote(Page):
    form_model = 'player'
    form_fields = ['institution_vote']
    template_name = 'wave2_discontinuity/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title=f'Wave 2 — Round {player.round_number} of {C.NUM_ROUNDS}',
            explanation=(
                'Vote privately for the procedure governing this round. Ordinary public-service capacity may '
                'have recovered or may remain weak. The executive procedure is unchanged. This round may be '
                'selected for payment.'
            ),
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or not player.field_maybe_none('institution_vote'):
            player.institution_vote = C.CONSTRAINED
            player.timed_out = True


class VoteWaitPage(WaitPage):
    body_text = 'Waiting for the other members of this round\'s anonymous group.'
    after_all_players_arrive = choose_institution

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open'


class DemocraticContribution(Page):
    form_model = 'player'
    form_fields = ['contribution']
    template_name = 'wave2_discontinuity/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open' and player.group.selected_institution == C.CONSTRAINED

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Constrained collective decision',
            explanation=(
                'Each point kept returns 1 point to you. Depending on current institutional capacity, each '
                'public-account point produces either 1.50 or 2.50 total points for the group, divided equally.'
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
    template_name = 'wave2_discontinuity/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open' and player.group.selected_institution == C.EXECUTIVE and player.is_executive

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='You are the executive for this round',
            explanation=(
                f'Choose an equal contribution for all members. You may transfer at most '
                f'{C.MAX_EXECUTIVE_RENT} collected points to yourself. Remaining points produce '
                f'{C.EXECUTIVE_MULTIPLIER:.2f} points of total group benefit each.'
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

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open'


class RoundResults(Page):
    template_name = 'wave2_discontinuity/Results.html'

    @staticmethod
    def is_displayed(player):
        return wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            round_number=player.round_number,
            institution_label=dict(C.INSTITUTION_CHOICES)[group.selected_institution],
            executive_selected=group.selected_institution == C.EXECUTIVE,
            is_executive=player.id_in_group == group.executive_id,
            total_contribution=group.total_contribution,
            executive_tax=group.executive_tax,
            executive_rent=group.executive_rent,
            public_account=group.public_account,
            per_capita_return=group.per_capita_return,
            round_payoff=player.round_payoff,
            constrained_multiplier=group.realized_constrained_multiplier,
        )


class Wave2Mechanism(Page):
    form_model = 'player'
    form_fields = [
        'inst_capacity_w2', 'collapse_risk_w2', 'belief_recovery_final',
        'constraint_w2_1', 'constraint_w2_2', 'constraint_w2_3', 'constraint_w2_4',
        'constraint_w2_5', 'constraint_w2_6', 'constraint_w2_7',
    ]
    template_name = 'wave2_discontinuity/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS and wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Final judgments',
            explanation='Please answer after considering all ten Wave-2 rounds. For statements, 1 means strongly disagree and 7 means strongly agree.',
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        w1_vote = player.participant.vars.get('w1_final_vote')
        w2_vote = player.institution_vote
        player.democratic_reversal = w1_vote == C.EXECUTIVE and w2_vote == C.CONSTRAINED
        player.participant.vars['w2_final_vote'] = w2_vote
        player.participant.vars['democratic_reversal'] = player.democratic_reversal
        late_votes = [p.institution_vote for p in player.in_rounds(8, 10)]
        player.participant.vars['w2_late_executive_share'] = sum(v == C.EXECUTIVE for v in late_votes) / 3

        truth = 1 if player.treatment == C.TREATMENT_REVERSAL else 0
        probability = player.in_round(1).belief_recovery_post_search / 100
        player.belief_bonus = round(C.BELIEF_BONUS_MAX * (1 - (probability - truth) ** 2), 2)

        paying_round = player.session.vars['wave2_paying_round']
        selected_payoff = player.in_round(paying_round).round_payoff
        information_remaining = player.participant.vars.get('info_budget_remaining', 0)
        player.payoff = cu(selected_payoff + information_remaining + C.COMPLETION_BONUS + player.belief_bonus)

        player.participant.vars['wave2_paying_round'] = paying_round
        player.participant.vars['wave2_selected_payoff'] = selected_payoff
        player.participant.vars['belief_bonus'] = player.belief_bonus


class Wave2Complete(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS and wave_status(player) == 'open'

    @staticmethod
    def vars_for_template(player):
        return dict(
            paying_round=player.participant.vars['wave2_paying_round'],
            selected_payoff=player.participant.vars['wave2_selected_payoff'],
            wave1_selected_payoff=player.participant.vars.get('wave1_selected_payoff', 0),
            information_remaining=player.participant.vars.get('info_budget_remaining', 0),
            completion_bonus=C.COMPLETION_BONUS,
            belief_bonus=player.belief_bonus,
            total_payoff=player.participant.payoff,
            performance_payment=player.participant.payoff.to_real_world_currency(player.session),
            participation_fee=player.session.config['participation_fee'],
            total_payment=player.participant.payoff_plus_participation_fee(),
        )


page_sequence = [
    Wave2LockedEarly,
    Wave2LockedLate,
    Wave2Intro,
    MemoryAndPrior,
    Wave2NewsBoard,
    PostSearchBelief,
    InstitutionVote,
    VoteWaitPage,
    DemocraticContribution,
    ExecutiveDecision,
    DecisionWaitPage,
    RoundResults,
    Wave2Mechanism,
    Wave2Complete,
]
