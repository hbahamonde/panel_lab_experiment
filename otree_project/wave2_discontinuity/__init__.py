import random

from otree.api import *


doc = """
Block 2: a pool-randomized structural recovery or persistence condition, ten
repeated institutional-choice rounds, and the final within-session
democratic-reversal outcome.
"""


def development_mode(player):
    """Allow researchers to move through the demo without completing every field."""
    return player.session.config.get('allow_optional_responses', False)


def require_all(player, values, field_names):
    if development_mode(player):
        return
    if any(values.get(field_name) in (None, '') for field_name in field_names):
        return 'Please answer all questions before continuing.'


def solo_testing(obj):
    return obj.session.config.get('solo_testing', False)


def assign_treatments_after_block1(subsession):
    """Randomize pools after Block 1, pairing pools on pretreatment leader support."""
    players = subsession.get_players()

    if solo_testing(subsession):
        treatment = subsession.session.config.get(
            'solo_treatment', C.TREATMENT_RECOVERY
        )
        player = players[0]
        player.participant.vars['treatment'] = treatment
        player.participant.vars['randomization_stratum'] = 1
        for round_player in player.in_all_rounds():
            round_player.treatment = treatment
            round_player.randomization_stratum = 1
        subsession.session.vars['treatment_by_pool'] = {1: treatment}
        subsession.session.vars['treatment_randomization_pairs'] = []
        subsession.session.vars['treatment_unmatched_pools'] = [1]
        subsession.session.vars['randomization_stratum_by_pool'] = {1: 1}
        return

    pool_summaries = []
    pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in players})
    for pool_id in pool_ids:
        pool_players = [
            p for p in players
            if p.participant.vars['matching_pool_id'] == pool_id
        ]
        observed_votes = [
            p.participant.vars.get('w1_final_vote')
            for p in pool_players
            if p.participant.vars.get('w1_final_vote_observed', False)
        ]
        leader_share = (
            sum(vote == C.EXECUTIVE for vote in observed_votes) / len(observed_votes)
            if observed_votes else 0.5
        )
        pool_summaries.append((leader_share, random.random(), pool_id))

    pool_summaries.sort()
    ordered_pool_ids = [pool_id for _, _, pool_id in pool_summaries]
    treatment_by_pool = {}
    randomization_pairs = []
    stratum_by_pool = {}

    for pair_number, pair_start in enumerate(
        range(0, len(ordered_pool_ids) - 1, 2), start=1
    ):
        first_pool, second_pool = ordered_pool_ids[pair_start:pair_start + 2]
        if random.choice([True, False]):
            recovery_pool, persistence_pool = first_pool, second_pool
        else:
            recovery_pool, persistence_pool = second_pool, first_pool
        treatment_by_pool[recovery_pool] = C.TREATMENT_RECOVERY
        treatment_by_pool[persistence_pool] = C.TREATMENT_PERSISTENCE
        randomization_pairs.append([first_pool, second_pool])
        stratum_by_pool[first_pool] = pair_number
        stratum_by_pool[second_pool] = pair_number

    unmatched_pools = []
    if len(ordered_pool_ids) % 2:
        unmatched_pool = ordered_pool_ids[-1]
        treatment_by_pool[unmatched_pool] = random.choice(
            [C.TREATMENT_RECOVERY, C.TREATMENT_PERSISTENCE]
        )
        unmatched_pools.append(unmatched_pool)
        stratum_by_pool[unmatched_pool] = len(randomization_pairs) + 1

    for player in players:
        pool_id = player.participant.vars['matching_pool_id']
        treatment = treatment_by_pool[pool_id]
        stratum = stratum_by_pool[pool_id]
        player.participant.vars['treatment'] = treatment
        player.participant.vars['randomization_stratum'] = stratum
        for round_player in player.in_all_rounds():
            round_player.treatment = treatment
            round_player.randomization_stratum = stratum

    subsession.session.vars['treatment_by_pool'] = treatment_by_pool
    subsession.session.vars['treatment_randomization_pairs'] = randomization_pairs
    subsession.session.vars['treatment_unmatched_pools'] = unmatched_pools
    subsession.session.vars['randomization_stratum_by_pool'] = stratum_by_pool


def group_within_matching_pools(subsession):
    players = subsession.get_players()

    if solo_testing(subsession):
        if len(players) != 1:
            raise RuntimeError('Solo testing sessions require exactly one participant.')
        player = players[0]
        subsession.set_group_matrix([[player]])
        player.matching_pool_id = player.participant.vars['matching_pool_id']
        player.matching_pool_uid = player.participant.vars['matching_pool_uid']
        if subsession.round_number == 1:
            subsession.session.vars['wave2_paying_round'] = random.randint(1, C.NUM_ROUNDS)
        return

    groups = []
    pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in players})
    for pool_id in pool_ids:
        pool_players = [p for p in players if p.participant.vars['matching_pool_id'] == pool_id]
        random.shuffle(pool_players)
        if len(pool_players) % C.GROUP_SIZE != 0:
            raise RuntimeError(
                f'Matching pool {pool_id} contains {len(pool_players)} participants; '
                'Block 2 requires complete five-person groups.'
            )
        groups.extend(
            pool_players[index:index + C.GROUP_SIZE]
            for index in range(0, len(pool_players), C.GROUP_SIZE)
        )
    subsession.set_group_matrix(groups)
    for player in players:
        player.matching_pool_id = player.participant.vars['matching_pool_id']
        player.matching_pool_uid = player.participant.vars['matching_pool_uid']

    if subsession.round_number == 1:
        subsession.session.vars['wave2_paying_round'] = random.randint(1, C.NUM_ROUNDS)


def constrained_multiplier(player):
    treatment = player.field_maybe_none('treatment')
    if treatment is None:
        treatment = player.participant.vars['treatment']
        player.treatment = treatment
        player.randomization_stratum = player.participant.vars['randomization_stratum']
    if treatment == C.TREATMENT_RECOVERY:
        return C.CONSTRAINED_MULTIPLIER_RECOVERY
    return C.CONSTRAINED_MULTIPLIER_CRISIS


def choose_institution(group):
    players = group.get_players()
    if solo_testing(group):
        player = players[0]
        other_leader_votes = player.field_maybe_none('solo_other_leader_votes')
        executive_votes = int(player.institution_vote == C.EXECUTIVE) + (
            other_leader_votes if other_leader_votes is not None else 2
        )
    else:
        executive_votes = sum(p.institution_vote == C.EXECUTIVE for p in players)
    group.executive_votes = executive_votes
    group.selected_institution = C.EXECUTIVE if executive_votes >= 3 else C.CONSTRAINED
    group.realized_constrained_multiplier = constrained_multiplier(players[0])

    if group.selected_institution == C.EXECUTIVE:
        if solo_testing(group):
            executive = players[0]
            executive.is_executive = True
            executive.participant.vars['times_executive'] = (
                executive.participant.vars.get('times_executive', 0) + 1
            )
            group.executive_id = executive.id_in_group
            return
        minimum_count = min(p.participant.vars.get('times_executive', 0) for p in players)
        eligible = [p for p in players if p.participant.vars.get('times_executive', 0) == minimum_count]
        executive = random.choice(eligible)
        executive.is_executive = True
        executive.participant.vars['times_executive'] = minimum_count + 1
        group.executive_id = executive.id_in_group


def calculate_round(group):
    players = group.get_players()
    if group.selected_institution == C.CONSTRAINED:
        if solo_testing(group):
            total = (players[0].contribution or 0) + C.SOLO_OTHER_CITIZENS * C.SOLO_OTHER_CONTRIBUTION
        else:
            total = sum(p.contribution or 0 for p in players)
        group.total_contribution = total
        group.executive_tax = 0
        group.executive_rent = 0
        group.public_account = total
        group.per_capita_return = group.realized_constrained_multiplier * total / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - (player.contribution or 0) + group.per_capita_return
    else:
        executive = group.get_player_by_id(group.executive_id)
        tax = executive.executive_tax or 0
        rent = executive.executive_rent or 0
        public_account = C.GROUP_SIZE * tax - rent
        group.total_contribution = C.GROUP_SIZE * tax
        group.executive_tax = tax
        group.executive_rent = rent
        group.public_account = public_account
        group.per_capita_return = C.EXECUTIVE_MULTIPLIER * public_account / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - tax + group.per_capita_return
            if player.id_in_group == group.executive_id:
                player.round_payoff += rent


class C(BaseConstants):
    NAME_IN_URL = 'wave2_discontinuity'
    PLAYERS_PER_GROUP = None
    GROUP_SIZE = 5
    NUM_ROUNDS = 10

    ENDOWMENT = 20
    CONSTRAINED_MULTIPLIER_CRISIS = 1.50
    CONSTRAINED_MULTIPLIER_RECOVERY = 2.50
    EXECUTIVE_MULTIPLIER = 2.50
    MAX_EXECUTIVE_RENT = 20
    SOLO_OTHER_CITIZENS = 4
    SOLO_OTHER_CONTRIBUTION = 10

    CONSTRAINED = 'constrained'
    EXECUTIVE = 'executive'
    TREATMENT_RECOVERY = 'recovery'
    TREATMENT_PERSISTENCE = 'persistence'
    DEFAULT_CONTRIBUTION = 10
    DEFAULT_EXECUTIVE_TAX = 10
    DEFAULT_EXECUTIVE_RENT = 0

    INSTITUTION_CHOICES = [
        [CONSTRAINED, 'Each person chooses'],
        [EXECUTIVE, 'One person chooses for the group'],
    ]
    AGREEMENT_CHOICES = [[i, str(i)] for i in range(1, 8)]
    FIVE_POINT_CHOICES = [
        [1, 'Very low'], [2, 'Low'], [3, 'Moderate'], [4, 'High'], [5, 'Very high']
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
    matching_pool_uid = models.StringField()
    treatment = models.StringField()
    randomization_stratum = models.IntegerField(initial=0)
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES, widget=widgets.RadioSelect,
        label='How should the fund decision be made this round?',
        blank=True,
    )
    solo_other_leader_votes = models.IntegerField(min=0, max=4, blank=True)
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='How many of your 20 points do you put in the public-services fund?',
    )
    executive_tax = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='How many points must each group member put in the public-services fund?',
    )
    executive_rent = models.IntegerField(
        min=0, max=C.MAX_EXECUTIVE_RENT, blank=True,
        label='How many fund points do you move to your own payoff?',
    )
    is_executive = models.BooleanField(initial=False)
    timed_out = models.BooleanField(initial=False)
    institution_vote_timed_out = models.BooleanField(initial=False)
    round_payoff = models.FloatField(initial=0)
    expected_payoff_citizens = models.IntegerField(
        min=0, max=60,
        label='If Each person chooses is used in this round, how many points do you expect to earn?',
        blank=True,
    )
    expected_payoff_leader = models.IntegerField(
        min=0, max=60,
        label='If One person chooses for the group is used, how many points do you expect to earn?',
        blank=True,
    )
    expected_leader_transfer = models.IntegerField(
        min=0, max=C.MAX_EXECUTIVE_RENT,
        label='If one person chooses for the group, how many fund points do you expect the selected person to move to their own payoff?',
        blank=True,
    )

    citizen_effectiveness_b2 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how well can the group support public services when each citizen chooses how many points to put in the fund?',
        blank=True,
    )
    collapse_risk_w2 = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how high is the risk that the usual limits on a leader\'s power will be seriously weakened?',
        blank=True,
    )
    constraint_w2_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The current situation justifies giving one leader temporary power to act without asking the group first.', blank=True)
    constraint_w2_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Faster public services are worth reducing checks on a leader\'s power in the current situation.', blank=True)
    constraint_w2_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Citizens should keep control over major public decisions, even if decisions take longer.', blank=True)
    constraint_w2_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The leader should be allowed to require every citizen to put the same number of points in the public-services fund.', blank=True)
    constraint_w2_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer slower decisions by citizens to faster decisions by a leader who may move public-service points to a personal account.', blank=True)
    constraint_w2_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Weak limits on a leader\'s power create risks that outweigh the current gains.', blank=True)
    constraint_w2_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='When public services work poorly, a leader needs more freedom from the usual limits.', blank=True)

    democratic_reversal = models.BooleanField(initial=False)
    immediate_democratic_reversal = models.BooleanField(initial=False)


class TreatmentAssignmentWaitPage(WaitPage):
    wait_for_all_groups = True
    body_text = 'Waiting for all participants to complete Block 1.'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    after_all_players_arrive = assign_treatments_after_block1


class Wave2Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            rounds=C.NUM_ROUNDS,
            recovery=player.treatment == C.TREATMENT_RECOVERY,
            constrained_multiplier=f'{constrained_multiplier(player):.2f}',
            executive_multiplier=f'{C.EXECUTIVE_MULTIPLIER:.2f}',
        )


class StrategicExpectations(Page):
    form_model = 'player'
    form_fields = [
        'expected_payoff_citizens',
        'expected_payoff_leader',
        'expected_leader_transfer',
    ]
    template_name = 'wave2_discontinuity/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number in [1, C.NUM_ROUNDS]

    @staticmethod
    def vars_for_template(player):
        timing = 'first' if player.round_number == 1 else 'final'
        return dict(
            page_title='What do you expect in this round?',
            explanation=(
                f'Before the {timing} Block-2 choice, estimate what you would earn under '
                'each method and what the selected decision-maker would do. Enter your best '
                'estimates; these answers do not change your payoff.'
            ),
            institution_vote_page=False,
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, StrategicExpectations.form_fields)


class InstitutionVote(Page):
    form_model = 'player'
    form_fields = ['institution_vote', 'solo_other_leader_votes']
    template_name = 'wave2_discontinuity/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title=f'Block 2 — Round {player.round_number} of {C.NUM_ROUNDS}',
            explanation=(
                'The public-services fund works at the rates shown at the start of Block 2. '
                'With One person chooses for the group, the selected person may move up to '
                '20 fund points to their own payoff. This round may be selected for payment.'
            ),
            institution_vote_page=True,
            constrained_multiplier=f'{constrained_multiplier(player):.2f}',
            executive_multiplier=f'{C.EXECUTIVE_MULTIPLIER:.2f}',
            optional_responses=development_mode(player),
            selected_vote=player.field_maybe_none('institution_vote'),
            slider_prefix='',
            solo_testing=solo_testing(player),
            solo_other_leader_votes=(
                player.field_maybe_none('solo_other_leader_votes')
                if player.field_maybe_none('solo_other_leader_votes') is not None else 2
            ),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, ['institution_vote'])

    @staticmethod
    def before_next_page(player, timeout_happened):
        if solo_testing(player) and player.field_maybe_none('solo_other_leader_votes') is None:
            player.solo_other_leader_votes = 2
        if timeout_happened or not player.field_maybe_none('institution_vote'):
            player.institution_vote = random.choice([C.CONSTRAINED, C.EXECUTIVE])
            player.timed_out = True
            player.institution_vote_timed_out = True
        if player.round_number == 1:
            first_votes_observed = (
                player.participant.vars.get('w1_final_vote_observed', False)
                and not player.institution_vote_timed_out
            )
            player.immediate_democratic_reversal = (
                first_votes_observed
                and player.participant.vars.get('w1_final_vote') == C.EXECUTIVE
                and player.institution_vote == C.CONSTRAINED
            )
            player.participant.vars['w2_first_vote'] = player.institution_vote
            player.participant.vars['w2_first_vote_observed'] = (
                not player.institution_vote_timed_out
            )
            player.participant.vars['immediate_democratic_reversal_observed'] = (
                first_votes_observed
            )
            player.participant.vars['immediate_democratic_reversal'] = (
                player.immediate_democratic_reversal
            )


class VoteWaitPage(WaitPage):
    body_text = 'Waiting for the other members of this round\'s anonymous group.'
    after_all_players_arrive = choose_institution

class DemocraticContribution(Page):
    form_model = 'player'
    form_fields = ['contribution']
    template_name = 'wave2_discontinuity/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return player.group.selected_institution == C.CONSTRAINED

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Each person chooses',
            explanation=(
                f'Points you do not put in the public-services fund remain yours. Each point you put in the '
                f'fund creates {constrained_multiplier(player):.2f} group points. These points '
                f'are shared equally among all five members.'
            ),
            institution_vote_page=False,
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, DemocraticContribution.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or player.field_maybe_none('contribution') is None:
            player.contribution = C.DEFAULT_CONTRIBUTION
            player.timed_out = True


class ExecutiveDecision(Page):
    form_model = 'player'
    form_fields = ['executive_tax', 'executive_rent']
    template_name = 'wave2_discontinuity/QuestionPage.html'
    timeout_seconds = 90

    @staticmethod
    def is_displayed(player):
        return player.group.selected_institution == C.EXECUTIVE and player.is_executive

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='You are the decision-maker for this round',
            explanation=(
                f'Choose how many points every group member must put in the public-services fund. You may '
                f'move at most {C.MAX_EXECUTIVE_RENT} fund points to your own payoff. '
                f'Each point left in the fund creates {C.EXECUTIVE_MULTIPLIER:.2f} group points.'
            ),
            institution_vote_page=False,
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        missing = require_all(player, values, ExecutiveDecision.form_fields)
        if missing:
            return missing
        if values.get('executive_rent') is not None and values.get('executive_tax') is not None:
            if values['executive_rent'] > C.GROUP_SIZE * values['executive_tax']:
                return 'You cannot move more points than the group has put in the public-services fund.'

    @staticmethod
    def before_next_page(player, timeout_happened):
        if timeout_happened or player.field_maybe_none('executive_tax') is None:
            player.executive_tax = C.DEFAULT_EXECUTIVE_TAX
            player.executive_rent = C.DEFAULT_EXECUTIVE_RENT
            player.timed_out = True


class DecisionWaitPage(WaitPage):
    body_text = 'Waiting for all decisions in this round.'
    after_all_players_arrive = calculate_round

class RoundResults(Page):
    template_name = 'wave2_discontinuity/Results.html'

    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            round_number=player.round_number,
            institution_label=dict(C.INSTITUTION_CHOICES)[group.selected_institution],
            citizen_votes=C.GROUP_SIZE - group.executive_votes,
            leader_votes=group.executive_votes,
            solo_testing=solo_testing(player),
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

    @staticmethod
    def before_next_page(player, timeout_happened):
        if player.round_number != C.NUM_ROUNDS:
            return
        block1_vote = player.participant.vars.get('w1_final_vote')
        block2_vote = player.institution_vote
        final_votes_observed = (
            player.participant.vars.get('w1_final_vote_observed', False)
            and not player.institution_vote_timed_out
        )
        player.democratic_reversal = (
            final_votes_observed
            and block1_vote == C.EXECUTIVE
            and block2_vote == C.CONSTRAINED
        )
        player.participant.vars['w2_final_vote'] = block2_vote
        player.participant.vars['w2_final_vote_observed'] = not player.institution_vote_timed_out
        player.participant.vars['democratic_reversal_observed'] = final_votes_observed
        player.participant.vars['democratic_reversal'] = player.democratic_reversal
        late_votes = [p.institution_vote for p in player.in_rounds(8, 10)]
        player.participant.vars['w2_late_executive_share'] = sum(
            vote == C.EXECUTIVE for vote in late_votes
        ) / 3
        player.participant.vars['expected_payoff_citizens_b2_final'] = (
            player.field_maybe_none('expected_payoff_citizens')
        )
        player.participant.vars['expected_payoff_leader_b2_final'] = (
            player.field_maybe_none('expected_payoff_leader')
        )
        player.participant.vars['expected_leader_transfer_b2_final'] = (
            player.field_maybe_none('expected_leader_transfer')
        )
        first_round = player.in_round(1)
        player.participant.vars['expected_payoff_citizens_b2_initial'] = (
            first_round.field_maybe_none('expected_payoff_citizens')
        )
        player.participant.vars['expected_payoff_leader_b2_initial'] = (
            first_round.field_maybe_none('expected_payoff_leader')
        )
        player.participant.vars['expected_leader_transfer_b2_initial'] = (
            first_round.field_maybe_none('expected_leader_transfer')
        )

        paying_round = player.session.vars['wave2_paying_round']
        selected_payoff = player.in_round(paying_round).round_payoff
        player.payoff = cu(selected_payoff)
        player.participant.vars['wave2_paying_round'] = paying_round
        player.participant.vars['wave2_selected_payoff'] = selected_payoff


class Wave2Mechanism(Page):
    form_model = 'player'
    form_fields = [
        'citizen_effectiveness_b2', 'collapse_risk_w2',
        'constraint_w2_1', 'constraint_w2_2', 'constraint_w2_3', 'constraint_w2_4',
        'constraint_w2_5', 'constraint_w2_6', 'constraint_w2_7',
    ]
    template_name = 'wave2_discontinuity/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Final questions',
            explanation=(
                'All paid decisions are complete. Please answer the following questions '
                'about the situation you experienced.'
            ),
            institution_vote_page=False,
            slider_prefix='constraint_w2_',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, Wave2Mechanism.form_fields)


class Wave2Complete(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            paying_round=player.participant.vars['wave2_paying_round'],
            selected_payoff=player.participant.vars['wave2_selected_payoff'],
            wave1_selected_payoff=player.participant.vars.get('wave1_selected_payoff', 0),
            total_payoff=player.participant.payoff,
            performance_payment=player.participant.payoff.to_real_world_currency(player.session),
            participation_fee=player.session.config['participation_fee'],
            total_payment=player.participant.payoff_plus_participation_fee(),
        )


page_sequence = [
    TreatmentAssignmentWaitPage,
    Wave2Intro,
    StrategicExpectations,
    InstitutionVote,
    VoteWaitPage,
    DemocraticContribution,
    ExecutiveDecision,
    DecisionWaitPage,
    RoundResults,
    Wave2Mechanism,
    Wave2Complete,
]
