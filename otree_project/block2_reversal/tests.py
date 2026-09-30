from otree.api import Bot, SubmissionMustFail

from . import *


class PlayerBot(Bot):
    def play_round(self):
        if self.round_number == 1:
            yield Block2Intro
            if solo_testing(self.player):
                assert self.player.treatment == self.session.config['solo_treatment']
            else:
                assignments = {
                    p.matching_pool_id: p.treatment
                    for p in self.subsession.get_players()
                }
                assert self.player.treatment == assignments[self.player.matching_pool_id]
                if len(assignments) == 2:
                    assert set(assignments.values()) == {
                        C.TREATMENT_RECOVERY,
                        C.TREATMENT_PERSISTENCE,
                    }
            if not solo_testing(self.player) and self.player.participant.id_in_session == 1:
                original_assignments = dict(assignments)
                assign_treatments_after_block1(self.subsession)
                repeated_assignments = {
                    p.matching_pool_id: p.treatment
                    for p in self.subsession.get_players()
                }
                assert repeated_assignments == original_assignments

        if self.round_number in (1, C.NUM_ROUNDS):
            yield StrategicExpectations, dict(
                expected_payoff_citizens=25,
                expected_payoff_leader=30,
                expected_leader_transfer=5,
            )

        is_solo = solo_testing(self.player)
        # Rounds 3 and 5 test the exact 3-of-5 institutional threshold.
        if not is_solo and self.round_number == 3:
            vote = C.AUTOMATIC if self.player.id_in_group <= 3 else C.APPROVAL
            expected_method = C.AUTOMATIC
        elif not is_solo and self.round_number == 5:
            vote = C.AUTOMATIC if self.player.id_in_group <= 2 else C.APPROVAL
            expected_method = C.APPROVAL
        else:
            approval_required = self.round_number == 1 or self.round_number % 2 == 0
            vote = C.APPROVAL if approval_required else C.AUTOMATIC
            expected_method = vote
        yield InstitutionVote, dict(institution_vote=vote)

        expected_group_size = 1 if is_solo else C.GROUP_SIZE
        assert len(self.group.get_players()) == expected_group_size
        assert all(
            p.matching_pool_id == self.player.matching_pool_id
            for p in self.group.get_players()
        )
        assert len({p.treatment for p in self.group.get_players()}) == 1
        expected_real_leaders = 1 if (not is_solo or self.round_number % 2) else 0
        assert sum(p.is_leader for p in self.group.get_players()) == expected_real_leaders

        if self.player.is_leader:
            yield SubmissionMustFail(
                LeaderProposal,
                dict(proposed_allocation=1, proposed_transfer=6),
            )
            yield LeaderProposal, dict(
                proposed_allocation=10,
                proposed_transfer=5,
            )

        proposal_should_pass = self.round_number in (1, 4, 8)
        if expected_method == C.APPROVAL and not self.player.is_leader:
            if is_solo:
                approval_vote = C.APPROVE if proposal_should_pass else C.REJECT
            else:
                nonleader_ids = sorted(
                    p.id_in_group
                    for p in self.group.get_players()
                    if not p.is_leader
                )
                approval_count = 3 if proposal_should_pass else 2
                approval_vote = (
                    C.APPROVE
                    if self.player.id_in_group in nonleader_ids[:approval_count]
                    else C.REJECT
                )
            yield ApprovalVote, dict(approval_vote=approval_vote)

        if expected_method == C.APPROVAL and not proposal_should_pass:
            contribution = self.player.participant.id_in_session % (C.ENDOWMENT + 1)
            yield FallbackAllocation, dict(contribution=contribution)

        group = self.group
        assert group.selected_institution == expected_method
        if is_solo:
            assert group.leader_id in (0, 1)
        else:
            assert group.leader_id in range(1, C.GROUP_SIZE + 1)
        assert 0 <= self.player.round_payoff <= C.MAX_ROUND_PAYOFF
        expected_multiplier = (
            C.APPROVAL_MULTIPLIER_RECOVERY
            if self.player.treatment == C.TREATMENT_RECOVERY
            else C.APPROVAL_MULTIPLIER_CRISIS
        )
        assert group.realized_approval_multiplier == expected_multiplier
        if expected_method == C.APPROVAL:
            assert group.proposal_approved is proposal_should_pass
            assert group.fallback_used is (not proposal_should_pass)
        else:
            assert group.proposal_implemented is True
            assert group.fallback_used is False

        yield RoundResults

        if self.round_number == C.NUM_ROUNDS:
            yield FinalQuestions, dict(
                block1_crisis_seriousness=4,
                block2_condition_change=4,
                individual_method_effectiveness=4,
                constraint_risk=3,
                constraint_1=4,
                constraint_2=4,
                constraint_3=4,
                constraint_4=4,
                constraint_5=4,
                constraint_6=4,
                constraint_7=4,
            )
            yield BackgroundQuestions1, {}
            yield BackgroundQuestions2, {}

            participant = self.player.participant
            assert participant.vars['immediate_democratic_reversal'] is True
            assert participant.vars['democratic_reversal'] is True
            assert 1 <= participant.vars['block2_paying_round'] <= C.NUM_ROUNDS
            assert 0 <= participant.vars['block2_selected_payoff'] <= C.MAX_ROUND_PAYOFF
            assert 0 <= participant.payoff <= C.MAX_TOTAL_POINTS
            assert 10 <= float(participant.payoff_plus_participation_fee()) <= 15
            assert participant.finished is True
