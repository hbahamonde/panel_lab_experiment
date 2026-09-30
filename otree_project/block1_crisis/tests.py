from otree.api import Bot, SubmissionMustFail

from . import *


class PlayerBot(Bot):
    def play_round(self):
        if self.round_number == 1:
            yield Block1Intro
            yield PracticeIntro
            yield SubmissionMustFail(
                PracticeGroupChoice,
                dict(practice_allocation=1, practice_transfer=6),
            )
            yield PracticeGroupChoice, dict(
                practice_allocation=10,
                practice_transfer=5,
            )
            yield PracticeApproval, dict(practice_approval=C.APPROVE)
            yield PracticeIndividualChoice, dict(practice_contribution=10)
            yield Comprehension, dict(
                comprehension_1='same',
                comprehension_2='three',
                comprehension_3='fallback',
                comprehension_4='no',
                comprehension_5='selected',
            )

        if self.round_number == C.NUM_ROUNDS:
            yield StrategicExpectations, dict(
                expected_payoff_citizens=25,
                expected_payoff_leader=30,
                expected_leader_transfer=5,
            )

        is_solo = solo_testing(self.player)
        # Rounds 3 and 5 test the exact 3-of-5 institutional threshold. The
        # last ballot is direct implementation so the reversal checks apply.
        if not is_solo and self.round_number == 3:
            vote = C.AUTOMATIC if self.player.id_in_group <= 3 else C.APPROVAL
            expected_method = C.AUTOMATIC
        elif not is_solo and self.round_number == 5:
            vote = C.AUTOMATIC if self.player.id_in_group <= 2 else C.APPROVAL
            expected_method = C.APPROVAL
        else:
            direct = self.round_number % 2 == 1 or self.round_number == C.NUM_ROUNDS
            vote = C.AUTOMATIC if direct else C.APPROVAL
            expected_method = vote
        yield InstitutionVote, dict(institution_vote=vote)

        expected_group_size = 1 if is_solo else C.GROUP_SIZE
        assert len(self.group.get_players()) == expected_group_size
        assert all(
            p.matching_pool_id == self.player.matching_pool_id
            for p in self.group.get_players()
        )
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

        proposal_should_pass = self.round_number in (4, 8)
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
        if expected_method == C.APPROVAL:
            assert group.proposal_approved is proposal_should_pass
            assert group.fallback_used is (not proposal_should_pass)
        else:
            assert group.proposal_implemented is True
            assert group.fallback_used is False

        yield RoundResults

        if self.round_number == C.NUM_ROUNDS:
            assert self.player.participant.vars['block1_final_vote'] == C.AUTOMATIC
            assert 1 <= self.player.participant.vars['block1_paying_round'] <= C.NUM_ROUNDS
            assert 0 <= self.player.participant.vars['block1_selected_payoff'] <= C.MAX_ROUND_PAYOFF
            yield Block1Complete
