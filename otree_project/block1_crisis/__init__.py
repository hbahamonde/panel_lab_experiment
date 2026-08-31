import random
import time

from otree.api import *


doc = """
Block 1 of the one-session experiment: a common public-service crisis, ten
repeated institutional-choice/public-good rounds and process measurement.
Participants are anonymously rematched within 10- or 15-person pools.
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


def flexible_pool_sizes(player_count):
    """Prefer 10-person pools and use one 15-person pool for a remainder of five."""
    if player_count < 10:
        raise RuntimeError(
            'Production sessions require at least 10 completed participants.'
        )
    if player_count % C.GROUP_SIZE != 0:
        raise RuntimeError(
            'The completed session roster must be divisible into five-person groups.'
        )
    if player_count % 10 == 0:
        return [10] * (player_count // 10)
    return [10] * ((player_count - 15) // 10) + [15]


def start_decision_timer(player, decision_name):
    key = f'block1_round_{player.round_number}_{decision_name}_started_at'
    player.participant.vars.setdefault(key, time.time())


def record_decision_time(player, decision_name, seconds_field, flag_field):
    key = f'block1_round_{player.round_number}_{decision_name}_started_at'
    started_at = player.participant.vars.pop(key, time.time())
    elapsed = max(0, time.time() - started_at)
    setattr(player, seconds_field, elapsed)
    setattr(player, flag_field, elapsed > C.DECISION_DELAY_THRESHOLD_SECONDS)


def assign_matching_pools(subsession):
    players = subsession.get_players()

    if solo_testing(subsession):
        if len(players) != 1:
            raise RuntimeError('Solo testing sessions require exactly one participant.')
        player = players[0]
        if subsession.round_number == 1:
            player.participant.vars['matching_pool_id'] = 1
            player.participant.vars['matching_pool_uid'] = f'{subsession.session.code}-pool-1'
            player.participant.vars['matching_pool_size'] = 1
            player.participant.vars['times_leader'] = 0
            subsession.session.vars['block1_paying_round'] = random.randint(1, C.NUM_ROUNDS)
        subsession.set_group_matrix([[player]])
        player.matching_pool_id = 1
        player.matching_pool_uid = player.participant.vars['matching_pool_uid']
        player.matching_pool_size = 1
        return

    if subsession.round_number == 1:
        pool_sizes = flexible_pool_sizes(len(players))
        subsession.session.vars['matching_pool_sizes'] = pool_sizes
        shuffled = random.sample(players, len(players))
        position = 0
        for pool_id, pool_size in enumerate(pool_sizes, start=1):
            pool_members = shuffled[position:position + pool_size]
            position += pool_size
            for player in pool_members:
                player.participant.vars['matching_pool_id'] = pool_id
                player.participant.vars['matching_pool_uid'] = (
                    f'{subsession.session.code}-pool-{pool_id}'
                )
                player.participant.vars['matching_pool_size'] = pool_size
                player.participant.vars['times_leader'] = 0

        subsession.session.vars['block1_paying_round'] = random.randint(1, C.NUM_ROUNDS)

    groups = []
    pool_ids = sorted({p.participant.vars['matching_pool_id'] for p in players})
    for pool_id in pool_ids:
        pool_players = [p for p in players if p.participant.vars['matching_pool_id'] == pool_id]
        random.shuffle(pool_players)
        if len(pool_players) % C.GROUP_SIZE != 0:
            raise RuntimeError(
                f'Matching pool {pool_id} contains {len(pool_players)} participants; '
                'each pool must be divisible into five-person groups.'
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

    if solo_testing(group):
        player = players[0]
        if player.round_number % 2:
            player.is_leader = True
            player.participant.vars['times_leader'] = (
                player.participant.vars.get('times_leader', 0) + 1
            )
            group.leader_id = player.id_in_group
        else:
            group.leader_id = 0  # simulated leader; lets one-browser tests show approval
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
        group.per_capita_return = C.APPROVAL_MULTIPLIER_CRISIS * total / C.GROUP_SIZE
        for player in players:
            player.round_payoff = C.ENDOWMENT - (player.field_maybe_none('contribution') or 0) + group.per_capita_return
    else:
        allocation = group.proposed_allocation
        transfer = group.proposed_transfer
        public_account = C.GROUP_SIZE * allocation - transfer
        multiplier = (
            C.AUTOMATIC_MULTIPLIER
            if group.selected_institution == C.AUTOMATIC
            else C.APPROVAL_MULTIPLIER_CRISIS
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
    NAME_IN_URL = 'group_decisions_1'
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

class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    assign_matching_pools(subsession)


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


class Player(BasePlayer):
    matching_pool_id = models.IntegerField()
    matching_pool_uid = models.StringField()
    matching_pool_size = models.IntegerField()
    institution_vote = models.StringField(
        choices=C.INSTITUTION_CHOICES,
        widget=widgets.RadioSelect,
        label='Should the selected person\'s proposal require group approval?',
        blank=True,
    )
    solo_other_automatic_votes = models.IntegerField(min=0, max=4, blank=True)
    solo_other_approval_votes = models.IntegerField(
        min=0, max=4, blank=True,
        label='Solo test: how many of the four simulated citizens approve the proposal?',
    )
    contribution = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='How many of your 20 points do you put in the public-services fund?',
        blank=True,
    )
    proposed_allocation = models.IntegerField(
        min=0, max=C.ENDOWMENT,
        label='How many points should every citizen put in the public-services fund?',
        blank=True,
    )
    proposed_transfer = models.IntegerField(
        min=0, max=C.MAX_PERSONAL_TRANSFER,
        label='How many fund points should move to your own payoff?',
        blank=True,
    )
    approval_vote = models.StringField(
        choices=C.APPROVAL_CHOICES,
        widget=widgets.RadioSelect,
        label='Do you approve or reject the selected person\'s proposal?',
        blank=True,
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

    practice_contribution = models.IntegerField(min=0, max=20, label='How many of your 20 points do you put in the public-services fund?', blank=True)
    practice_allocation = models.IntegerField(min=0, max=20, label='How many points should every citizen put in the public-services fund?', blank=True)
    practice_transfer = models.IntegerField(min=0, max=20, label='How many fund points should move to your own payoff?', blank=True)
    practice_approval = models.StringField(
        choices=C.APPROVAL_CHOICES, widget=widgets.RadioSelect,
        label='Would you approve or reject this proposal?', blank=True,
    )
    comprehension_1 = models.StringField(
        choices=[['same', 'A randomly selected person proposes the allocation under both methods'], ['different', 'A selected person is used only when the decision takes effect directly']],
        widget=widgets.RadioSelect,
        label='Who proposes the equal allocation under the two methods?',
        blank=True,
    )
    comprehension_2 = models.StringField(
        choices=[['three', 'At least three of the four other citizens'], ['two', 'At least two of the four other citizens'], ['all', 'All four other citizens']], widget=widgets.RadioSelect,
        label='When group approval is required, how many of the four other citizens must approve?',
        blank=True,
    )
    comprehension_3 = models.StringField(
        choices=[['fallback', 'Everyone chooses their own fund allocation'], ['automatic', 'The proposal takes effect anyway']],
        widget=widgets.RadioSelect,
        label='What happens when a proposal requiring group approval is rejected?',
        blank=True,
    )
    comprehension_4 = models.StringField(
        choices=[['yes', 'Yes'], ['no', 'No']], widget=widgets.RadioSelect,
        label='When a decision takes effect directly, can the other citizens reject the proposal before it is implemented?',
        blank=True,
    )
    comprehension_5 = models.StringField(
        choices=[['all', 'Every round'], ['selected', 'Only the randomly selected round'], ['last', 'Only Round 10']],
        widget=widgets.RadioSelect,
        label='Which paid round determines your game earnings from Block 1?',
        blank=True,
    )

class Block1Intro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            rounds=C.NUM_ROUNDS,
            group_size=C.GROUP_SIZE,
        )


class PracticeIntro(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1


class PracticeIndividualChoice(Page):
    form_model = 'player'
    form_fields = ['practice_contribution']
    template_name = 'block1_crisis/PracticeIndividualChoice.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, PracticeIndividualChoice.form_fields)


class PracticeGroupChoice(Page):
    form_model = 'player'
    form_fields = ['practice_allocation', 'practice_transfer']
    template_name = 'block1_crisis/PracticeGroupChoice.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        missing = require_all(player, values, PracticeGroupChoice.form_fields)
        if missing:
            return missing
        if values.get('practice_transfer') is not None and values.get('practice_allocation') is not None:
            if values['practice_transfer'] > C.GROUP_SIZE * values['practice_allocation']:
                return 'The selected person cannot move more points than the group would put in the public-services fund.'


class PracticeApproval(Page):
    form_model = 'player'
    form_fields = ['practice_approval']
    template_name = 'block1_crisis/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='Try it: group approval',
            explanation=(
                'Suppose the selected person proposes that every citizen put 10 points '
                'in the fund and that 5 fund points move to that person\'s own payoff. '
                'When group approval is required, the other four citizens see the full '
                'proposal and decide whether to approve or reject it.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, PracticeApproval.form_fields)


class Comprehension(Page):
    form_model = 'player'
    form_fields = [
        'comprehension_1', 'comprehension_2', 'comprehension_3',
        'comprehension_4', 'comprehension_5',
    ]
    template_name = 'block1_crisis/Comprehension.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def error_message(player, values):
        if development_mode(player):
            return
        errors = []
        if values['comprehension_1'] != 'same':
            errors.append('The software selects a person to propose the allocation under both methods.')
        if values['comprehension_2'] != 'three':
            errors.append('At least three of the four other citizens must approve the proposal.')
        if values['comprehension_3'] != 'fallback':
            errors.append('After rejection, every citizen chooses their own fund allocation.')
        if values['comprehension_4'] != 'no':
            errors.append('A proposal that takes effect directly cannot be rejected before implementation.')
        if values['comprehension_5'] != 'selected':
            errors.append('One randomly selected round determines your Block-1 game earnings.')
        if errors:
            return 'Please review: ' + ' '.join(errors)


class StrategicExpectations(Page):
    form_model = 'player'
    form_fields = [
        'expected_payoff_citizens',
        'expected_payoff_leader',
        'expected_leader_transfer',
    ]
    template_name = 'block1_crisis/QuestionPage.html'

    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            page_title='What do you expect in this round?',
            explanation=(
                'Before choosing, estimate what you would earn under each method and '
                'what the selected decision-maker would do. Enter your best estimates; these answers do not '
                'change your payoff.'
            ),
            slider_prefix='',
            optional_responses=development_mode(player),
        )

    @staticmethod
    def error_message(player, values):
        return require_all(player, values, StrategicExpectations.form_fields)


class InstitutionVote(Page):
    form_model = 'player'
    form_fields = ['institution_vote', 'solo_other_automatic_votes']
    template_name = 'block1_crisis/InstitutionChoice.html'
    @staticmethod
    def vars_for_template(player):
        start_decision_timer(player, 'institution_vote')
        return dict(
            round_number=player.round_number,
            total_rounds=C.NUM_ROUNDS,
            approval_multiplier=f'{C.APPROVAL_MULTIPLIER_CRISIS:.2f}',
            automatic_multiplier=f'{C.AUTOMATIC_MULTIPLIER:.2f}',
            optional_responses=development_mode(player),
            selected_vote=player.field_maybe_none('institution_vote'),
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


class VoteWaitPage(WaitPage):
    body_text = 'Waiting for the other members of this round\'s anonymous group.'
    after_all_players_arrive = choose_institution_and_leader


class LeaderProposal(Page):
    form_model = 'player'
    template_name = 'block1_crisis/QuestionPage.html'

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
                    f'the {C.APPROVAL_MULTIPLIER_CRISIS:.2f} rate. If they reject, everyone chooses '
                    'their own allocation.'
                    if player.group.selected_institution == C.APPROVAL
                    else f'Your proposal takes effect directly, and the remaining fund uses the '
                         f'{C.AUTOMATIC_MULTIPLIER:.2f} rate.'
                )
            ),
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
    template_name = 'block1_crisis/QuestionPage.html'
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
    template_name = 'block1_crisis/QuestionPage.html'

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
                f'{C.APPROVAL_MULTIPLIER_CRISIS:.2f} group points, shared equally. '
                'Points you do not put in the fund remain yours.'
            ),
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
    template_name = 'block1_crisis/RoundResults.html'

    @staticmethod
    def vars_for_template(player):
        group = player.group
        return dict(
            round_number=player.round_number,
            total_rounds=C.NUM_ROUNDS,
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
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        if player.round_number != C.NUM_ROUNDS:
            return
        player.participant.vars['block1_final_vote'] = player.field_maybe_none('institution_vote')
        player.participant.vars['block1_final_vote_observed'] = (
            player.field_maybe_none('institution_vote') is not None
        )
        late_votes = [p.field_maybe_none('institution_vote') for p in player.in_rounds(8, 10)]
        player.participant.vars['block1_late_automatic_share'] = sum(v == C.AUTOMATIC for v in late_votes) / 3
        player.participant.vars['expected_payoff_citizens_b1'] = (
            player.field_maybe_none('expected_payoff_citizens')
        )
        player.participant.vars['expected_payoff_leader_b1'] = (
            player.field_maybe_none('expected_payoff_leader')
        )
        player.participant.vars['expected_leader_transfer_b1'] = (
            player.field_maybe_none('expected_leader_transfer')
        )

        paying_round = player.session.vars['block1_paying_round']
        selected_payoff = player.in_round(paying_round).round_payoff
        player.payoff = cu(selected_payoff)
        player.participant.vars['block1_paying_round'] = paying_round
        player.participant.vars['block1_selected_payoff'] = selected_payoff


class Block1Complete(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == C.NUM_ROUNDS

    @staticmethod
    def vars_for_template(player):
        return dict(
            paying_round=player.participant.vars['block1_paying_round'],
            selected_payoff=player.participant.vars['block1_selected_payoff'],
        )


page_sequence = [
    Block1Intro,
    PracticeIntro,
    PracticeGroupChoice,
    PracticeApproval,
    PracticeIndividualChoice,
    Comprehension,
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
    Block1Complete,
]
