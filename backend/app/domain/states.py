"""Persisted workflow vocabulary and transition rules (no provider behavior)."""
from enum import StrEnum

class MessageState(StrEnum):
    DRAFT='draft'; APPROVED='approved'; REJECTED='rejected'; CANCELLED='cancelled'
    SENDING='sending'; SENT='sent'; UNKNOWN='unknown'; FAILED='failed'; DEMO='demo'

MESSAGE_TRANSITIONS = {
    'draft': {'approved','rejected','cancelled'},
    'approved': {'draft','sending','rejected','cancelled'},
    'rejected': {'draft','cancelled'},
    'sending': {'sent','unknown','failed'},
    'unknown': {'sent','failed'},
    'sent': set(), 'failed': set(), 'cancelled': set(), 'demo': set(),
}
JOB_TRANSITIONS = {
    'queued': {'running'}, 'running': {'done','failed','blocked','interrupted'},
    'failed': {'queued'}, 'blocked': {'queued'}, 'interrupted': {'queued'}, 'done': set(),
}
OPERATION_TRANSITIONS = {
    'pending': {'running','blocked','skipped'},
    'blocked': {'running','blocked','skipped'},
    'running': {'succeeded','failed','unknown','blocked'},
    'failed': {'running'}, 'unknown': {'succeeded','failed'},
    'succeeded': set(), 'skipped': set(),
}

def transition(db, entity, to_state, *, domain='message', reason=''):
    from ..core import Blocked
    from ..models import DomainTransition
    rules = {'message': MESSAGE_TRANSITIONS, 'job': JOB_TRANSITIONS, 'operation': OPERATION_TRANSITIONS}[domain]
    previous = entity.status
    if previous == to_state:
        return
    if to_state not in rules.get(previous, set()):
        raise Blocked(f'Invalid {domain} transition: {previous} -> {to_state}')
    entity.status = to_state
    db.add(DomainTransition(domain=domain, entity_id=entity.id, from_state=previous,
                            to_state=to_state, reason=reason[:120]))
