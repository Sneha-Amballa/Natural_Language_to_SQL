import logging

logger = logging.getLogger("agent.state")

class AgentState:
    IDLE = "IDLE"
    UNDERSTAND = "UNDERSTAND"
    PLAN = "PLAN"
    CALL_TOOL = "CALL_TOOL"
    WAIT_TOOL = "WAIT_TOOL"
    PROCESS_RESULT = "PROCESS_RESULT"
    GENERATE_FINAL_RESPONSE = "GENERATE_FINAL_RESPONSE"
    FINISHED = "FINISHED"

class StateMachine:
    """Manages explicit agent state and logs transitions."""
    
    def __init__(self, initial_state: str = AgentState.IDLE):
        self._current_state = initial_state
        logger.info(f"State initialized: {self._current_state}")
        
    @property
    def current_state(self) -> str:
        return self._current_state
        
    def transition_to(self, new_state: str) -> None:
        """Transitions state, logging the event."""
        old_state = self._current_state
        self._current_state = new_state
        logger.info({
            "event": "state_transition",
            "from": old_state,
            "to": new_state
        })
