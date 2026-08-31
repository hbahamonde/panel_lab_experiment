import random
import time

from otree.api import *


doc = """
Block 2: a pool-randomized structural recovery or persistence condition, ten
repeated institutional-choice rounds, and individual ballots for immediate
and sustained democratic reversal.
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


def start_decision_timer(player, decision_name):
    key = f'block2_round_{player.round_number}_{decision_name}_started_at'
    player.participant.vars.setdefault(key, time.time())


def record_decision_time(player, decision_name, seconds_field, flag_field):
    key = f'block2_round_{player.round_number}_{decision_name}_started_at'
    started_at = player.participant.vars.pop(key, time.time())
    elapsed = max(0, time.time() - started_at)
    setattr(player, seconds_field, elapsed)
    setattr(player, flag_field, elapsed > C.DECISION_DELAY_THRESHOLD_SECONDS)


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
            p.participant.vars.get('block1_final_vote')
            for p in pool_players
            if p.participant.vars.get('block1_final_vote_observed', False)
        ]
        automatic_share = (
            sum(vote == C.AUTOMATIC for vote in observed_votes) / len(observed_votes)
            if observed_votes else 0.5
        )
        pool_summaries.append((automatic_share, random.random(), pool_id))

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
        player.matching_pool_size = player.participant.vars['matching_pool_size']
        if subsession.round_number == 1:
            subsession.session.vars['block2_paying_round'] = random.randint(1, C.NUM_ROUNDS)
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
        player.matching_pool_size = player.participant.vars['matching_pool_size']

    if subsession.round_number == 1:
        subsession.session.vars['block2_paying_round'] = random.randint(1, C.NUM_ROUNDS)


def approval_multiplier(player):
    treatment = player.field_maybe_none('treatment')
    if treatment is None:
        treatment = player.participant.vars['treatment']
        player.treatment = treatment
        player.randomization_stratum = player.participant.vars['randomization_stratum']
    if treatment == C.TREATMENT_RECOVERY:
        return C.APPROVAL_MULTIPLIER_RECOVERY
    return C.APPROVAL_MULTIPLIER_CRISIS


def choose_institution_and_leader(group):
    players = group.get_players()
    if solo_testing(group):
        player = players[0]
        other_automatic_votes = player.field_maybe_none('solo_other_automatic_votes')
        automatic_votes = int(player.field_maybe_none('institution_vote') == C.AUTOMATIC) + (
            other_automatic_votes if other_automatic_votes is not None else 2
        )
    else:
        automatic_votes = sum(
            p.field_maybe_none('institution_vote') == C.AUTOMATIC for p in players
        )
    group.automatic_votes = automatic_votes
    group.selected_institution = C.AUTOMATIC if automatic_votes >= 3 else C.APPROVAL
    group.realized_approval_multiplier = approval_multiplier(players[0])

    if solo_testing(group):
        player = players[0]
        if player.round_number % 2:
            player.is_leader = True
            player.participant.vars['times_leader'] = (
                player.participant.vars.get('times_leader', 0) + 1
            )
            group.leader_id = player.id_in_group
        else:
            group.leader_id = 0
        return

    minimum_count = min(p.participant.vars.get('times_leader', 0) for p in players)
    eligible = [
        p for p in players
        if p.participant.vars.get('times_leader', 0) == minimum_count
    ]
    leader = random.choice(eligible)
    leader.is_leader = True
    leader.participant.vars['times_leader'] = minimum_count + 1
    group.leader_id = leader.id_in_group


def record_proposal(group):
    if solo_testing(group) and group.leader_id == 0:
        group.proposed_allocation = 10
        group.proposed_transfer = 5
        return
    leader = group.get_player_by_id(group.leader_id)
    group.proposed_allocation = leader.field_maybe_none('proposed_allocation') or 0
    group.proposed_transfer = leader.field_maybe_none('proposed_transfer') or 0


def decide_approval(group):
    if group.selected_institution != C.APPROVAL:
        group.proposal_approved = False
        return

    if solo_testing(group):
        if group.leader_id == 0:
            participant_approval = (
                group.get_players()[0].field_maybe_none('approval_vote') == C.APPROVE
            )
            group.approval_votes = 2 + int(participant_approval)
        else:
            leader = group.get_player_by_id(group.leader_id)
            simulated_approvals = leader.field_maybe_none('solo_other_approval_votes')
            group.approval_votes = simulated_approvals if simulated_approvals is not None else 3
    else:
        group.approval_votes = sum(
            p.field_maybe_none('approval_vote') == C.APPROVE
            for p in group.get_players()
            if p.id_in_group != group.leader_id
        )
    group.proposal_approved = group.approval_votes >= C.APPROVAL_THRESHOLD


def calculate_round(group):
    players = group.get_players()
    proposal_implemented = (
        group.selected_institution == C.AUTOMATIC or group.proposal_approved
    )
    group.proposal_implemented = proposal_implemented
    group.fallback_used = not proposal_implemented

    if group.fallback_used:
        if solo_testing(group):
            total = (players[0].field_maybe_none('contribution') or 0) + C.SOLO_OTHER_CITIZENS * C.SOLO_OTHER_CONTRIBUTION
        else:
            total = sum(p.field_maybe_none('contribution') or 0 for p in players)
        group.total_contribution = total
        group.implemented_transfer = 0
        group.public_account = total
        group.per_capita_return = group.realized_approval_multiplier * total / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - (player.field_maybe_none('contribution') or 0) + group.per_capita_return
    else:
        allocation = group.proposed_allocation
        transfer = group.proposed_transfer
        public_account = C.GROUP_SIZE * allocation - transfer
        multiplier = (
            C.AUTOMATIC_MULTIPLIER
            if group.selected_institution == C.AUTOMATIC
            else group.realized_approval_multiplier
        )
        group.total_contribution = C.GROUP_SIZE * allocation
        group.implemented_transfer = transfer
        group.public_account = public_account
        group.per_capita_return = multiplier * public_account / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - allocation + group.per_capita_return
            if player.id_in_group == group.leader_id:
                player.round_payoff += transfer


class C(BaseConstants):
    NAME_IN_URL = 'group_decisions_2'
    PLAYERS_PER_GROUP = None
    GROUP_SIZE = 5
    NUM_ROUNDS = 10

    ENDOWMENT = 20
    APPROVAL_MULTIPLIER_CRISIS = 1.50
    APPROVAL_MULTIPLIER_RECOVERY = 2.50
    AUTOMATIC_MULTIPLIER = 2.50
    MAX_PERSONAL_TRANSFER = 20
    APPROVAL_THRESHOLD = 3
    SOLO_OTHER_CITIZENS = 4
    SOLO_OTHER_CONTRIBUTION = 10

    APPROVAL = 'approval'
    AUTOMATIC = 'automatic'
    APPROVE = 'approve'
    REJECT = 'reject'
    TREATMENT_RECOVERY = 'recovery'
    TREATMENT_PERSISTENCE = 'persistence'
    DECISION_DELAY_THRESHOLD_SECONDS = 90

    INSTITUTION_CHOICES = [
        [APPROVAL, 'Group approval required'],
        [AUTOMATIC, 'Decision takes effect directly'],
    ]
    APPROVAL_CHOICES = [
        [APPROVE, 'Approve the proposal'],
        [REJECT, 'Reject the proposal'],
    ]
    AGREEMENT_CHOICES = [[i, str(i)] for i in range(1, 8)]
    FIVE_POINT_CHOICES = [
        [1, 'Very low'], [2, 'Low'], [3, 'Moderate'], [4, 'High'], [5, 'Very high']
    ]
    CRISIS_SERIOUSNESS_CHOICES = [
        [1, 'Not serious'], [2, 'Slightly serious'], [3, 'Moderately serious'],
        [4, 'Serious'], [5, 'Very serious'],
    ]
    CONDITION_CHANGE_CHOICES = [
        [1, 'Much worse'], [2, 'Somewhat worse'], [3, 'No change'],
        [4, 'Somewhat better'], [5, 'Much better'],
    ]
class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    group_within_matching_pools(subsession)


class Group(BaseGroup):
    selected_institution = models.StringField()
    automatic_votes = models.IntegerField(initial=0)
    leader_id = models.IntegerField(initial=0)
    proposed_allocation = models.IntegerField(initial=0)
    proposed_transfer = models.IntegerField(initial=0)
    approval_votes = models.IntegerField(initial=0)
    proposal_approved = models.BooleanField(initial=False)
    proposal_implemented = models.BooleanField(initial=False)
    fallback_used = models.BooleanField(initial=False)
    total_contribution = models.IntegerField(initial=0)
    implemented_transfer = models.IntegerField(initial=0)
    public_account = models.IntegerField(initial=0)
    per_capita_return = models.FloatField(initial=0)
    realized_approval_multiplier = models.FloatField(initial=0)


class Player(BasePlayer):
    matching_pool_id = models.IntegerField()
    matching_pool_uid = models.StringField()
    matching_pool_size = models.IntegerField()
    treatment = models.StringField()
    randomization_stratum = models.IntegerField(initial=0)
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES, widget=widgets.RadioSelect,
        label='Should the selected person\'s proposal require group approval?',
        blank=True,
    )
    solo_other_automatic_votes = models.IntegerField(min=0, max=4, blank=True)
    solo_other_approval_votes = models.IntegerField(
        min=0, max=4, blank=True,
        label='Solo test: how many of the four simulated citizens approve the proposal?',
    )
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='How many of your 20 points do you put in the public-services fund?',
    )
    proposed_allocation = models.IntegerField(
        min=0, max=C.ENDOWMENT, blank=True,
        label='How many points should every citizen put in the public-services fund?',
    )
    proposed_transfer = models.IntegerField(
        min=0, max=C.MAX_PERSONAL_TRANSFER, blank=True,
        label='How many fund points should move to your own payoff?',
    )
    approval_vote = models.StringField(
        choices=C.APPROVAL_CHOICES, widget=widgets.RadioSelect,
        label='Do you approve or reject the selected person\'s proposal?', blank=True,
    )
    is_leader = models.BooleanField(initial=False)
    institution_vote_time_seconds = models.FloatField(initial=0)
    institution_vote_over_90 = models.BooleanField(initial=False)
    proposal_time_seconds = models.FloatField(initial=0)
    proposal_over_90 = models.BooleanField(initial=False)
    approval_time_seconds = models.FloatField(initial=0)
    approval_over_90 = models.BooleanField(initial=False)
    fallback_time_seconds = models.FloatField(initial=0)
    fallback_over_90 = models.BooleanField(initial=False)
    round_payoff = models.FloatField(initial=0)
    expected_payoff_citizens = models.IntegerField(
        min=0, max=60,
        label='If group approval is required, how many points do you expect to earn?',
        blank=True,
    )
    expected_payoff_leader = models.IntegerField(
        min=0, max=60,
        label='If the selected person\'s decision takes effect directly, how many points do you expect to earn?',
        blank=True,
    )
    expected_leader_transfer = models.IntegerField(
        min=0, max=C.MAX_PERSONAL_TRANSFER,
        label='How many fund points do you expect the selected person to propose moving to their own payoff?',
        blank=True,
    )

    block1_crisis_seriousness = models.IntegerField(
        choices=C.CRISIS_SERIOUSNESS_CHOICES, widget=widgets.RadioSelect,
        label='How serious did the public-service situation in Block 1 seem?',
        blank=True,
    )
    block2_condition_change = models.IntegerField(
        choices=C.CONDITION_CHANGE_CHOICES, widget=widgets.RadioSelect,
        label='Compared with Block 1, how did the public-service situation in Block 2 seem?',
        blank=True,
    )
    individual_method_effectiveness = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how well can the group support public services when the selected person\'s proposal requires group approval?',
        blank=True,
    )
    constraint_risk = models.IntegerField(
        choices=C.FIVE_POINT_CHOICES, widget=widgets.RadioSelect,
        label='After these rounds, how high is the risk that the usual limits on a leader\'s power will be seriously weakened?',
        blank=True,
    )
    constraint_1 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The current situation justifies allowing the selected person to act without group approval.', blank=True)
    constraint_2 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='More effective public services are worth giving up the approval vote in the current situation.', blank=True)
    constraint_3 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Citizens should retain an approval vote over binding group decisions, even if agreement can fail.', blank=True)
    constraint_4 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='The leader should be allowed to require every citizen to put the same number of points in the public-services fund.', blank=True)
    constraint_5 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='I prefer requiring approval to letting a selected person implement an unwanted transfer.', blank=True)
    constraint_6 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='Removing the approval vote creates risks that outweigh the current gains.', blank=True)
    constraint_7 = models.IntegerField(choices=C.AGREEMENT_CHOICES, label='When public services work poorly, selected decision-makers need more freedom to act without further approval.', blank=True)

    democratic_reversal = models.BooleanField(initial=False)
    immediate_democratic_reversal = models.BooleanField(initial=False)


class TreatmentAssignmentWaitPage(WaitPage):
    wait_for_all_groups = True
    body_text = 'Waiting for all participants to complete Block 1.'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    after_all_players_arrive = assign_treatments_after_block1


class Block2Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            rounds=C.NUM_ROUNDS,
            recovery=player.treatment == C.TREATMENT_RECOVERY,
            approval_multiplier=f'{approval_multiplier(player):.2f}',
            automatic_multiplier=f'{C.AUTOMATIC_MULTIPLIER:.2f}',
        )


class StrategicExpectations(Page):
    form_model = 'player'
    form_fields = [
        'expected_payoff_citizens',
        'expected_payoff_leader',
        'expected_leader_transfer',
    ]
    template_name = 'block2_reversal/QuestionPage.html'

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
    form_fields = ['institution_vote', 'solo_other_automatic_votes']
    template_name = 'block2_reversal/QuestionPage.html'
    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'institution_vote')
        return dict(
            page_title=f'Block 2 — Round {player.round_number} of {C.NUM_ROUNDS}',
            explanation=(
                'The public-services fund works at the rates shown at the start of Block 2. '
                'Under either method, the selected person may propose moving up to 20 fund '
                'points to their own payoff. This round may be selected for payment.'
            ),
            institution_vote_page=True,
            approval_multiplier=f'{approval_multiplier(player):.2f}',
            automatic_multiplier=f'{C.AUTOMATIC_MULTIPLIER:.2f}',
            optional_responses=development_mode(player),
            selected_vote=player.field_maybe_none('institution_vote'),
            slider_prefix='',
            solo_testing=solo_testing(player),
            solo_other_automatic_votes=(
                player.field_maybe_none('solo_other_automatic_votes')
                if player.field_maybe_none('solo_other_automatic_votes') is not None else 2
            ),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, ['institution_vote'])

    @staticmethod
    def before_next_page(player, timeout_happened):
        record_decision_time(
            player,
            'institution_vote',
            'institution_vote_time_seconds',
            'institution_vote_over_90',
        )
        if solo_testing(player) and player.field_maybe_none('solo_other_automatic_votes') is None:
            player.solo_other_automatic_votes = 2
        if player.round_number == 1:
            current_vote = player.field_maybe_none('institution_vote')
            first_votes_observed = (
                player.participant.vars.get('block1_final_vote_observed', False)
                and current_vote is not None
            )
            player.immediate_democratic_reversal = (
                first_votes_observed
                and player.participant.vars.get('block1_final_vote') == C.AUTOMATIC
                and current_vote == C.APPROVAL
            )
            player.participant.vars['block2_first_vote'] = current_vote
            player.participant.vars['block2_first_vote_observed'] = (
                current_vote is not None
            )
            player.participant.vars['immediate_democratic_reversal_observed'] = (
                first_votes_observed
            )
            player.participant.vars['immediate_democratic_reversal'] = (
                player.immediate_democratic_reversal
            )


class VoteWaitPage(WaitPage):
    body_text = 'Waiting for the other members of this round\'s anonymous group.'
    after_all_players_arrive = choose_institution_and_leader

class LeaderProposal(Page):
    form_model = 'player'
    template_name = 'block2_reversal/QuestionPage.html'

    @staticmethod
    def get_form_fields(player):
        fields = ['proposed_allocation', 'proposed_transfer']
        if solo_testing(player) and player.group.selected_institution == C.APPROVAL:
            fields.append('solo_other_approval_votes')
        return fields
    @staticmethod
    def is_displayed(player):
        return player.is_leader

    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'proposal')
        return dict(
            page_title='You are the selected person for this round',
            explanation=(
                'Propose how many points every citizen should put in the public-services fund '
                f'and whether up to {C.MAX_PERSONAL_TRANSFER} fund points should move to your payoff. '
                + (
                    f'If at least three of the other four citizens approve, the remaining fund uses '
                    f'the {approval_multiplier(player):.2f} rate. If they reject, everyone chooses '
                    'their own allocation.'
                    if player.group.selected_institution == C.APPROVAL
                    else f'Your proposal takes effect directly, and the remaining fund uses the '
                         f'{C.AUTOMATIC_MULTIPLIER:.2f} rate.'
                )
            ),
            institution_vote_page=False,
            slider_prefix='',
            optional_responses=development_mode(player),
            solo_testing=solo_testing(player),
        )

    @staticmethod
    def error_message(player, values):
        required = ['proposed_allocation', 'proposed_transfer']
        missing = require_all(player, values, required)
        if missing:
            return missing
        if values.get('proposed_transfer') is not None and values.get('proposed_allocation') is not None:
            if values['proposed_transfer'] > C.GROUP_SIZE * values['proposed_allocation']:
                return 'You cannot move more points than the group would put in the public-services fund.'

    @staticmethod
    def before_next_page(player, timeout_happened):
        record_decision_time(
            player,
            'proposal',
            'proposal_time_seconds',
            'proposal_over_90',
        )
        if (
            solo_testing(player)
            and player.group.selected_institution == C.APPROVAL
            and player.field_maybe_none('solo_other_approval_votes') is None
        ):
            player.solo_other_approval_votes = 3


class ProposalWaitPage(WaitPage):
    body_text = 'Waiting for the selected person\'s proposal.'
    after_all_players_arrive = record_proposal


class ApprovalVote(Page):
    form_model = 'player'
    form_fields = ['approval_vote']
    template_name = 'block2_reversal/QuestionPage.html'
    @staticmethod
    def is_displayed(player):
        return (
            player.group.selected_institution == C.APPROVAL
            and not player.is_leader
        )

    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'approval')
        return dict(
            page_title='Approve or reject the proposal',
            explanation=(
                f'The selected person proposes that every citizen put '
                f'{player.group.proposed_allocation} points in the fund and that '
                f'{player.group.proposed_transfer} fund points move to their own payoff. '
                f'At least three of the four other citizens must approve. If the proposal is '
                'rejected, every citizen will choose their own fund allocation.'
            ),
            institution_vote_page=False,
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, ApprovalVote.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        record_decision_time(
            player,
            'approval',
            'approval_time_seconds',
            'approval_over_90',
        )


class ApprovalWaitPage(WaitPage):
    body_text = 'Waiting for the group\'s approval decisions.'

    @staticmethod
    def is_displayed(player):
        return player.group.selected_institution == C.APPROVAL

    after_all_players_arrive = decide_approval


class FallbackAllocation(Page):
    form_model = 'player'
    form_fields = ['contribution']
    template_name = 'block2_reversal/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return (
            player.group.selected_institution == C.APPROVAL
            and not player.group.proposal_approved
        )

    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'fallback')
        return dict(
            page_title='The proposal was not approved',
            explanation=(
                'Each citizen now chooses how many of their own 20 points to put in the '
                f'public-services fund. Each fund point creates '
                f'{approval_multiplier(player):.2f} group points, shared equally. '
                'Points you do not put in the fund remain yours.'
            ),
            institution_vote_page=False,
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, FallbackAllocation.form_fields)

    @staticmethod
    def before_next_page(player, timeout_happened):
        record_decision_time(
            player,
            'fallback',
            'fallback_time_seconds',
            'fallback_over_90',
        )


class DecisionWaitPage(WaitPage):
    body_text = 'Waiting for all decisions in this round.'
    after_all_players_arrive = calculate_round

class RoundResults(Page):
    template_name = 'block2_reversal/RoundResults.html'

    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            round_number=player.round_number,
            institution_label=dict(C.INSTITUTION_CHOICES)[group.selected_institution],
            approval_rule_votes=C.GROUP_SIZE - group.automatic_votes,
            automatic_rule_votes=group.automatic_votes,
            solo_testing=solo_testing(player),
            approval_required=group.selected_institution == C.APPROVAL,
            is_leader=player.id_in_group == group.leader_id,
            proposed_allocation=group.proposed_allocation,
            proposed_transfer=group.proposed_transfer,
            approval_votes=group.approval_votes,
            proposal_approved=group.proposal_approved,
            proposal_implemented=group.proposal_implemented,
            fallback_used=group.fallback_used,
            total_contribution=group.total_contribution,
            implemented_transfer=group.implemented_transfer,
            public_account=group.public_account,
            per_capita_return=group.per_capita_return,
            round_payoff=player.round_payoff,
            approval_multiplier=group.realized_approval_multiplier,
            implemented_multiplier=(
                C.AUTOMATIC_MULTIPLIER
                if group.selected_institution == C.AUTOMATIC
                else group.realized_approval_multiplier
            ),
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        if player.round_number != C.NUM_ROUNDS:
            return
        block1_vote = player.participant.vars.get('block1_final_vote')
        block2_vote = player.field_maybe_none('institution_vote')
        final_votes_observed = (
            player.participant.vars.get('block1_final_vote_observed', False)
            and player.field_maybe_none('institution_vote') is not None
        )
        player.democratic_reversal = (
            final_votes_observed
            and block1_vote == C.AUTOMATIC
            and block2_vote == C.APPROVAL
        )
        player.participant.vars['block2_final_vote'] = block2_vote
        player.participant.vars['block2_final_vote_observed'] = (
            player.field_maybe_none('institution_vote') is not None
        )
        player.participant.vars['democratic_reversal_observed'] = final_votes_observed
        player.participant.vars['democratic_reversal'] = player.democratic_reversal
        late_votes = [p.field_maybe_none('institution_vote') for p in player.in_rounds(8, 10)]
        player.participant.vars['block2_late_automatic_share'] = sum(
            vote == C.AUTOMATIC for vote in late_votes
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

        paying_round = player.session.vars['block2_paying_round']
        selected_payoff = player.in_round(paying_round).round_payoff
        player.payoff = cu(selected_payoff)
        player.participant.vars['block2_paying_round'] = paying_round
        player.participant.vars['block2_selected_payoff'] = selected_payoff


class FinalQuestions(Page):
    form_model = 'player'
    form_fields = [
        'block1_crisis_seriousness', 'block2_condition_change',
        'individual_method_effectiveness', 'constraint_risk',
        'constraint_1', 'constraint_2', 'constraint_3', 'constraint_4',
        'constraint_5', 'constraint_6', 'constraint_7',
    ]
    template_name = 'block2_reversal/QuestionPage.html'

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
            slider_prefix='constraint_',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, FinalQuestions.form_fields)


class StudyComplete(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            paying_round=player.participant.vars['block2_paying_round'],
            selected_payoff=player.participant.vars['block2_selected_payoff'],
            block1_paying_round=player.participant.vars['block1_paying_round'],
            block1_selected_payoff=player.participant.vars.get('block1_selected_payoff', 0),
            total_payoff=player.participant.payoff,
            performance_payment=player.participant.payoff.to_real_world_currency(player.session),
            participation_fee=player.session.config['participation_fee'],
            total_payment=player.participant.payoff_plus_participation_fee(),
        )


page_sequence = [
    TreatmentAssignmentWaitPage,
    Block2Intro,
    StrategicExpectations,
    InstitutionVote,
    VoteWaitPage,
    LeaderProposal,
    ProposalWaitPage,
    ApprovalVote,
    ApprovalWaitPage,
    FallbackAllocation,
    DecisionWaitPage,
    RoundResults,
    FinalQuestions,
    StudyComplete,
]
