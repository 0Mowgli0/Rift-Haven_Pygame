"""Message protocol shared by all SPADE agents.

Wire format: an XMPP message whose body is a JSON object:
    {"type": "<event type>", **payload}
with the FIPA-ish performative in the "performative" metadata and the
protocol name under metadata "ontology": "rpg-skeleton".

Routing uses spade Template objects (see TEMPLATES) so each behaviour only
receives its own event types. Games events (combat results et al.) also
mirror the exact same payloads through the local Bridge.
"""

from __future__ import annotations

import json

from spade.message import Message
from spade.template import Template

ONTOLOGY = "rpg-skeleton"


def build(to: str, performative: str, body: dict) -> Message:
    """Create a protocol message with JSON body."""
    m = Message(to=to)
    m.set_metadata("performative", performative)
    m.set_metadata("ontology", ONTOLOGY)
    m.body = json.dumps(body)
    return m


def parse(msg: Message) -> dict:
    """Parse an incoming protocol message into a dict (or {})."""
    try:
        return json.loads(msg.body)
    except (TypeError, ValueError):
        return {}


def t_for(performative: str, mtype: str | None = None) -> Template:
    """Template matching performative (and optional body 'type').

    NOTE: SPADE templates can't match on body contents, so agents match
    the body `type` in code after parsing; templates filter performatives.
    """
    t = Template()
    t.set_metadata("performative", performative)
    t.set_metadata("ontology", ONTOLOGY)
    # mtype is checked after parse() when several types share a performative.
    _ = mtype
    return t
